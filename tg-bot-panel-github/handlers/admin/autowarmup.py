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
    get_admin_task_by_id,
)
from keyboards.admin_tools import admin_tools_kb, tool_confirm_kb, tool_back_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class WarmupState(StatesGroup):
    waiting_groups = State()
    waiting_messages = State()
    confirming = State()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "tool_autowarmup")
async def callback_autowarmup(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.set_state(WarmupState.waiting_groups)
    await safe_edit(
        callback.message,
        "🔥 <b>Автопрогрев</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте список групп (каждая с новой строки):\n"
        "• <code>@group_name</code>\n"
        "• <code>https://t.me/group_name</code>",
        reply_markup=tool_back_kb(),
    )
    await callback.answer()


@router.message(F.text, WarmupState.waiting_groups)
async def handle_warmup_groups(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    groups = []
    for line in lines:
        line = line.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "")
        if not line.startswith("@") and not line.startswith("-"):
            line = f"@{line}"
        groups.append(line)

    await state.update_data(warmup_groups=groups)
    await state.set_state(WarmupState.waiting_messages)
    await message.answer(
        f"🔥 Групп: <b>{len(groups)}</b>\n\n"
        "📝 Введите количество сообщений на аккаунт (рекомендуется 3-10):",
        reply_markup=tool_back_kb(), parse_mode="HTML",
    )


@router.message(F.text, WarmupState.waiting_messages)
async def handle_warmup_count(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        count = int(message.text.strip())
        if count < 1 or count > 50:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Число от 1 до 50.")
        return

    data = await state.get_data()
    groups = data.get("warmup_groups", [])

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)

    if not accounts:
        await message.answer("❌ Нет аккаунтов.", reply_markup=tool_back_kb())
        await state.clear()
        return

    total = len(accounts) * len(groups) * count
    await state.update_data(warmup_count=count)
    await state.set_state(WarmupState.confirming)

    text = (
        f"🔥 <b>Подтверждение прогрева</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🟢 Аккаунтов: <b>{len(accounts)}</b>\n"
        f"📂 Групп: <b>{len(groups)}</b>\n"
        f"📝 Сообщений/аккаунт/группу: <b>{count}</b>\n"
        f"📊 Всего сообщений: ~<b>{total}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Запустить?"
    )
    await message.answer(text, reply_markup=tool_confirm_kb("autowarmup"), parse_mode="HTML")


@router.callback_query(F.data == "tool_confirm_autowarmup", WarmupState.confirming)
async def callback_confirm_autowarmup(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    groups = data.get("warmup_groups", [])
    count = data.get("warmup_count", 3)

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)
        task = await create_admin_task(db, "autowarmup", {
            "groups": groups, "messages_per_group": count,
        }, total=len(accounts) * len(groups) * count)

    await state.clear()
    await safe_edit(
        callback.message,
        f"🔥 <b>Прогрев запущен!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Задача: #{task.id}\n"
        f"📊 Аккаунтов: {len(accounts)}\n"
        f"📂 Групп: {len(groups)}",
        reply_markup=tool_back_kb(),
    )

    asyncio.create_task(_run_warmup(task.id, groups, count))
    log.info("Admin: запущен автопрогрев #%d", task.id)
    await callback.answer()


async def _run_warmup(task_id: int, groups: list[str], msgs_per_group: int):
    from telethon import TelegramClient

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

            for group in groups:
                try:
                    entity = await client.get_entity(group)
                except Exception:
                    total_errors += 1
                    error_log.append(f"{group}: не найден")
                    continue

                warmup_phrases = [
                    "👍", "Отлично", "Согласен", "Интересно", "👍🏻",
                    "Круто", "Норм", "Ок", "+", "Лайк",
                    "Хорошая мысль", "Знакомо", "Точно", "Верно", "🔥",
                ]

                for _ in range(msgs_per_group):
                    try:
                        msg = random.choice(warmup_phrases)
                        await client.send_message(entity, msg)
                        total_done += 1
                        await asyncio.sleep(random.uniform(5, 20))
                    except Exception as e:
                        total_errors += 1
                        error_log.append(f"{group}: {type(e).__name__}")
                        break

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

    log.info("Автопрогрев #%d завершён: done=%d errors=%d", task_id, total_done, total_errors)
