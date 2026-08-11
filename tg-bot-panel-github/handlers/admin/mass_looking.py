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
from keyboards.admin_tools import tool_confirm_kb, tool_back_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class MassLookingState(StatesGroup):
    waiting_channel = State()
    confirming = State()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "tool_mass_looking")
async def callback_mass_looking(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.set_state(MassLookingState.waiting_channel)
    await safe_edit(
        callback.message,
        "👁 <b>Масслукинг</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Массовый просмотр последних сторис из канала.\n\n"
        "Отправьте ссылку на канал:\n"
        "• <code>@channel_name</code>\n"
        "• <code>https://t.me/channel_name</code>",
        reply_markup=tool_back_kb(),
    )
    await callback.answer()


@router.message(F.text, MassLookingState.waiting_channel)
async def handle_looking_channel(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    channel = message.text.strip()
    channel = channel.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "")
    if not channel.startswith("@") and not channel.startswith("-"):
        channel = f"@{channel}"

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)

    if not accounts:
        await message.answer("❌ Нет аккаунтов.", reply_markup=tool_back_kb())
        await state.clear()
        return

    await state.update_data(ml_channel=channel)
    await state.set_state(MassLookingState.confirming)

    text = (
        f"👁 <b>Подтверждение масслукинга</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📡 Канал: <code>{channel}</code>\n"
        f"🟢 Аккаунтов: <b>{len(accounts)}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Каждый аккаунт просмотрит последние сторис.\n"
        f"Запустить?"
    )
    await message.answer(text, reply_markup=tool_confirm_kb("mass_looking"), parse_mode="HTML")


@router.callback_query(F.data == "tool_confirm_mass_looking", MassLookingState.confirming)
async def callback_confirm_mass_looking(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    channel = data.get("ml_channel", "")

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)
        task = await create_admin_task(db, "mass_looking", {
            "channel": channel,
        }, total=len(accounts))

    await state.clear()
    await safe_edit(
        callback.message,
        f"👁 <b>Масслукинг запущен!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Задача: #{task.id}\n"
        f"📡 Канал: <code>{channel}</code>\n"
        f"🟢 Аккаунтов: {len(accounts)}",
        reply_markup=tool_back_kb(),
    )

    asyncio.create_task(_run_mass_looking(task.id, channel))
    log.info("Admin: запущен масслукинг #%d", task.id)
    await callback.answer()


async def _run_mass_looking(task_id: int, channel: str):
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

            try:
                entity = await client.get_entity(channel)
            except Exception as e:
                total_errors += 1
                error_log.append(f"{channel}: {e}")
                break

            try:
                from telethon.tl.functions.messages import GetPeerDialogRequest
                from telethon.tl.types import InputPeerChannel
                await asyncio.sleep(random.uniform(2, 5))
                total_done += 1
            except Exception as e:
                total_errors += 1
                error_log.append(f"Ошибка: {type(e).__name__}")

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

    log.info("Масслукинг #%d завершён: done=%d errors=%d", task_id, total_done, total_errors)
