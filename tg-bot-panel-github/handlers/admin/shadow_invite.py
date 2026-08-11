from __future__ import annotations

import asyncio
import random
from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import config
from core.database import (
    async_session_factory,
    get_valid_accounts,
    create_admin_task,
    update_admin_task,
)
from keyboards.admin_tools import admin_tools_kb, tool_confirm_kb, tool_back_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class ShadowInviteState(StatesGroup):
    waiting_group = State()
    waiting_usernames = State()
    confirming = State()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "tool_shadow_invite")
async def callback_shadow_invite(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.set_state(ShadowInviteState.waiting_group)
    await safe_edit(
        callback.message,
        "👻 <b>Теневой инвайт</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте ссылку на группу/чат:\n"
        "• <code>@group_name</code>\n"
        "• <code>https://t.me/+invite_hash</code>",
        reply_markup=tool_back_kb(),
    )
    await callback.answer()


@router.message(F.text, ShadowInviteState.waiting_group)
async def handle_invite_group(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    group = message.text.strip()
    group = group.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "")
    await state.update_data(si_group=group)
    await state.set_state(ShadowInviteState.waiting_usernames)
    await message.answer(
        f"👻 Группа: <code>{group}</code>\n\n"
        "📝 Отправьте список юзернеймов (каждый с новой строки):\n"
        "<code>@user1</code>\n<code>@user2</code>",
        reply_markup=tool_back_kb(), parse_mode="HTML",
    )


@router.message(F.text, ShadowInviteState.waiting_usernames)
async def handle_invite_usernames(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    usernames = []
    for line in lines:
        line = line.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "")
        if not line.startswith("@"):
            line = f"@{line}"
        usernames.append(line)

    data = await state.get_data()
    group = data.get("si_group", "")

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)

    if not accounts:
        await message.answer("❌ Нет аккаунтов.", reply_markup=tool_back_kb())
        await state.clear()
        return

    await state.update_data(si_usernames=usernames)
    await state.set_state(ShadowInviteState.confirming)

    text = (
        f"👻 <b>Подтверждение инвайта</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📂 Группа: <code>{group}</code>\n"
        f"👥 Юзеров: <b>{len(usernames)}</b>\n"
        f"🟢 Аккаунтов: <b>{len(accounts)}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Запустить?"
    )
    await message.answer(text, reply_markup=tool_confirm_kb("shadow_invite"), parse_mode="HTML")


@router.callback_query(F.data == "tool_confirm_shadow_invite", ShadowInviteState.confirming)
async def callback_confirm_shadow_invite(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    group = data.get("si_group", "")
    usernames = data.get("si_usernames", [])

    async with async_session_factory() as db:
        task = await create_admin_task(db, "shadow_invite", {
            "group": group, "usernames": usernames,
        }, total=len(usernames))

    await state.clear()
    await safe_edit(
        callback.message,
        f"👻 <b>Инвайт запущен!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Задача: #{task.id}\n"
        f"📂 Группа: <code>{group}</code>\n"
        f"👥 Юзеров: {len(usernames)}",
        reply_markup=tool_back_kb(),
    )

    asyncio.create_task(_run_shadow_invite(task.id, group, usernames))
    log.info("Admin: запущен теневой инвайт #%d", task.id)
    await callback.answer()


async def _run_shadow_invite(task_id: int, group: str, usernames: list[str]):
    from telethon import TelegramClient
    from telethon.tl.functions.channels import InviteToChannelRequest

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)
        await update_admin_task(db, task_id, status="running")

    total_done = 0
    total_errors = 0
    error_log = []

    for account in accounts:
        session_stem = Path(account.session_path).with_suffix("")
        client = TelegramClient(str(session_stem), config.API_ID, config.API_HASH)

        try:
            await client.connect()
            if not await client.is_user_authorized():
                continue

            try:
                target_entity = await client.get_entity(group)
            except Exception as e:
                total_errors += 1
                error_log.append(f"Группа {group}: {e}")
                break

            for i in range(0, len(usernames), 5):
                batch = usernames[i:i+5]
                users_to_invite = []
                for uname in batch:
                    try:
                        user_entity = await client.get_entity(uname)
                        users_to_invite.append(user_entity)
                    except Exception as e:
                        total_errors += 1
                        error_log.append(f"{uname}: {type(e).__name__}")

                if users_to_invite:
                    try:
                        await client(InviteToChannelRequest(target_entity, users_to_invite))
                        total_done += len(users_to_invite)
                    except Exception as e:
                        total_errors += len(users_to_invite)
                        error_log.append(f"Батч: {type(e).__name__}")

                await asyncio.sleep(random.uniform(3, 8))

        except Exception as e:
            total_errors += 1
            error_log.append(f"Ошибка: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async with async_session_factory() as db:
        await update_admin_task(db, task_id, status="done", done=total_done, errors=total_errors, error_log=error_log[:50])

    log.info("Теневой инвайт #%d завершён: done=%d errors=%d", task_id, total_done, total_errors)
