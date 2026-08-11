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


class MassLikingState(StatesGroup):
    waiting_channel = State()
    confirming = State()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "tool_mass_liking")
async def callback_mass_liking(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.set_state(MassLikingState.waiting_channel)
    await safe_edit(
        callback.message,
        "❤️ <b>Масслайкинг</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Массовые лайки последних постов в канале.\n\n"
        "Отправьте ссылку на канал:\n"
        "• <code>@channel_name</code>\n"
        "• <code>https://t.me/channel_name</code>",
        reply_markup=tool_back_kb(),
    )
    await callback.answer()


@router.message(F.text, MassLikingState.waiting_channel)
async def handle_liking_channel(message: Message, state: FSMContext):
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

    await state.update_data(mlk_channel=channel)
    await state.set_state(MassLikingState.confirming)

    text = (
        f"❤️ <b>Подтверждение масслайкинга</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📡 Канал: <code>{channel}</code>\n"
        f"🟢 Аккаунтов: <b>{len(accounts)}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Каждый аккаунт лайкнет последние посты.\n"
        f"Запустить?"
    )
    await message.answer(text, reply_markup=tool_confirm_kb("mass_liking"), parse_mode="HTML")


@router.callback_query(F.data == "tool_confirm_mass_liking", MassLikingState.confirming)
async def callback_confirm_mass_liking(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    channel = data.get("mlk_channel", "")

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)
        task = await create_admin_task(db, "mass_liking", {
            "channel": channel,
        }, total=len(accounts))

    await state.clear()
    await safe_edit(
        callback.message,
        f"❤️ <b>Масслайкинг запущен!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Задача: #{task.id}\n"
        f"📡 Канал: <code>{channel}</code>\n"
        f"🟢 Аккаунтов: {len(accounts)}",
        reply_markup=tool_back_kb(),
    )

    asyncio.create_task(_run_mass_liking(task.id, channel))
    log.info("Admin: запущен масслайкинг #%d", task.id)
    await callback.answer()


async def _run_mass_liking(task_id: int, channel: str):
    from telethon import TelegramClient
    from telethon.tl.functions.messages import GetMessagesRequest
    from telethon.tl.types import InputPeerChannel, InputChannel

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
                messages = await client.get_messages(entity, limit=10)
            except Exception as e:
                total_errors += 1
                error_log.append(f"Получение постов: {type(e).__name__}")
                continue

            for msg in messages:
                try:
                    await asyncio.sleep(random.uniform(2, 8))
                    from telethon.tl.functions.messages import SendReactionRequest
                    from telethon.tl.types import ReactionEmoji
                    await client(SendReactionRequest(
                        peer=entity,
                        msg_id=msg.id,
                        reaction=[ReactionEmoji(emoticon="❤️")],
                    ))
                    total_done += 1
                except Exception as e:
                    total_errors += 1
                    error_log.append(f"Лайк #{msg.id}: {type(e).__name__}")

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

    log.info("Масслайкинг #%d завершён: done=%d errors=%d", task_id, total_done, total_errors)
