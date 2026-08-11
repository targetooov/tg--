from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import config
from core.database import (
    async_session_factory,
    create_broadcast_task,
    get_all_users,
    get_valid_accounts,
)
from keyboards.admin import admin_panel_kb, admin_confirm_global_broadcast_kb, cancel_admin_kb
from workers.task_queue import task_queue, BroadcastJob
from core.utils import safe_edit
from core.logger import log

router = Router()


class GlobalBroadcastState(StatesGroup):
    waiting_text = State()
    confirming = State()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "admin_global_broadcast")
async def callback_global_broadcast(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)

    if not accounts:
        await callback.answer("❌ Нет аккаунтов для рассылки", show_alert=True)
        return

    await state.set_state(GlobalBroadcastState.waiting_text)
    await safe_edit(
        callback.message,
        f"📨 <b>Глобальная рассылка</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Доступно аккаунтов: <b>{len(accounts)}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Отправьте текст сообщения для глобальной рассылки.\n"
        f"Сообщение будет отправлено ВСЕМ пользователям бота.",
        reply_markup=cancel_admin_kb(),
    )
    await callback.answer()


@router.message(F.text, GlobalBroadcastState.waiting_text)
async def handle_global_text(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Текст не может быть пустым.")
        return

    await state.update_data(global_text=text)
    await state.set_state(GlobalBroadcastState.confirming)

    async with async_session_factory() as db:
        users = await get_all_users(db, limit=1000)

    display = text[:300] + "..." if len(text) > 300 else text
    await message.answer(
        f"📨 <b>Подтверждение глобальной рассылки</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Текст:</b>\n<code>{display}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Получателей: {len(users)}</b>\n\n"
        f"Запустить?",
        reply_markup=admin_confirm_global_broadcast_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_global_confirm", GlobalBroadcastState.confirming)
async def callback_global_confirm(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    text = data.get("global_text", "")

    async with async_session_factory() as db:
        users = await get_all_users(db, limit=10000)
        accounts = await get_valid_accounts(db)

    if not accounts:
        await callback.answer("❌ Нет аккаунтов", show_alert=True)
        await state.clear()
        return

    async with async_session_factory() as db:
        for user in users:
            task = await create_broadcast_task(
                db,
                user_id=user.telegram_id,
                text=text,
                targets=[f"user:{user.telegram_id}"],
                broadcast_type="dm",
            )
        job = BroadcastJob(
            task_id=task.id,
            user_id=user.telegram_id,
            text=text,
            targets=[f"user:{user.telegram_id}"],
            chat_id=callback.message.chat.id,
        )
        await task_queue.enqueue(job)

    await state.clear()
    await safe_edit(
        callback.message,
        f"✅ <b>Глобальная рассылка запущена!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📨 Получателей: {len(users)}\n"
        f"📋 Задач создано: {len(users)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Результаты будут отправлены по завершении.",
        reply_markup=admin_panel_kb(),
    )
    log.info("Admin global broadcast: %d users, text=%s", len(users), text[:50])
    await callback.answer()
