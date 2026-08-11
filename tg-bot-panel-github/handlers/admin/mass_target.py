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


class MassTargetState(StatesGroup):
    waiting_targets = State()
    waiting_text = State()
    confirming = State()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "tool_mass_target")
async def callback_mass_target(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.set_state(MassTargetState.waiting_targets)
    await safe_edit(
        callback.message,
        "🎯 <b>Масстаргет</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Массовая отправка сообщений по списку целей.\n\n"
        "Отправьте список юзернеймов/ID (каждый с новой строки):\n"
        "<code>@user1</code>\n<code>@user2</code>\n<code>-1001234567890</code>",
        reply_markup=tool_back_kb(),
    )
    await callback.answer()


@router.message(F.text, MassTargetState.waiting_targets)
async def handle_target_targets(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    targets = []
    for line in lines:
        line = line.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "")
        if not line.startswith("@") and not line.startswith("-"):
            if line.isdigit():
                line = f"-100{line}"
            else:
                line = f"@{line}"
        targets.append(line)

    await state.update_data(mt_targets=targets)
    await state.set_state(MassTargetState.waiting_text)
    await message.answer(
        f"🎯 Целей: <b>{len(targets)}</b>\n\n"
        "📝 Введите текст сообщения для рассылки:",
        reply_markup=tool_back_kb(), parse_mode="HTML",
    )


@router.message(F.text, MassTargetState.waiting_text)
async def handle_target_text(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Текст не может быть пустым.")
        return

    await state.update_data(mt_text=text)

    data = await state.get_data()
    targets = data.get("mt_targets", [])

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)

    if not accounts:
        await message.answer("❌ Нет аккаунтов.", reply_markup=tool_back_kb())
        await state.clear()
        return

    await state.set_state(MassTargetState.confirming)
    display = text[:300] + "..." if len(text) > 300 else text
    text_msg = (
        f"🎯 <b>Подтверждение масстаргета</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Целей: <b>{len(targets)}</b>\n"
        f"🟢 Аккаунтов: <b>{len(accounts)}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Текст:</b>\n<code>{display}</code>\n\n"
        f"Запустить?"
    )
    await message.answer(text_msg, reply_markup=tool_confirm_kb("mass_target"), parse_mode="HTML")


@router.callback_query(F.data == "tool_confirm_mass_target", MassTargetState.confirming)
async def callback_confirm_mass_target(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    targets = data.get("mt_targets", [])
    text = data.get("mt_text", "")

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)
        task = await create_admin_task(db, "mass_target", {
            "targets": targets, "text": text,
        }, total=len(targets))

    await state.clear()
    await safe_edit(
        callback.message,
        f"🎯 <b>Масстаргет запущен!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Задача: #{task.id}\n"
        f"👥 Целей: {len(targets)}\n"
        f"🟢 Аккаунтов: {len(accounts)}",
        reply_markup=tool_back_kb(),
    )

    asyncio.create_task(_run_mass_target(task.id, targets, text))
    log.info("Admin: запущен масстаргет #%d", task.id)
    await callback.answer()


async def _run_mass_target(task_id: int, targets: list[str], text: str):
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

            for target in targets:
                try:
                    entity = await client.get_entity(target)
                    await client.send_message(entity, text)
                    total_done += 1
                except Exception as e:
                    total_errors += 1
                    error_log.append(f"{target}: {type(e).__name__}")

                await asyncio.sleep(random.uniform(config.BROADCAST_DELAY_MIN, config.BROADCAST_DELAY_MAX))

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

    log.info("Масстаргет #%d завершён: done=%d errors=%d", task_id, total_done, total_errors)
