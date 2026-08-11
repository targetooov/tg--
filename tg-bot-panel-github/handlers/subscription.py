from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import SUBSCRIPTION_PLANS
from core.database import (
    async_session_factory,
    get_or_create_subscription,
    use_invite_code,
    set_subscription_plan,
    get_user_by_telegram_id,
)
from keyboards.main_menu import back_to_menu_kb, cancel_kb
from keyboards.subscription import subscription_info_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class SubState(StatesGroup):
    waiting_invite_code = State()


@router.callback_query(F.data == "menu_subscription")
async def callback_subscription(callback: CallbackQuery):
    async with async_session_factory() as db:
        sub = await get_or_create_subscription(db, callback.from_user.id)

    plan_info = SUBSCRIPTION_PLANS.get(sub.plan)
    plan_name = plan_info.name if plan_info else sub.plan.upper()

    expires = "∞"
    if sub.expires_at:
        delta = sub.expires_at - datetime.now(timezone.utc)
        if delta.days > 0:
            expires = f"{delta.days} дн."
        else:
            expires = "Истекла!"

    msgs = f"{sub.messages_used}/{sub.messages_limit}"
    chats = f"{sub.chats_used}/{sub.chats_limit}"

    text = (
        f"💎 <b>Ваша подписка</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 План: <b>{plan_name}</b>\n"
        f"📨 Сообщений/день: <b>{msgs}</b>\n"
        f"🎯 Чатов/день: <b>{chats}</b>\n"
        f"⏰ Действует: <b>{expires}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Используйте инвайт-код для получения подписки.\n"
        f"Зарабатывайте дни через рефералов!"
    )
    await safe_edit(callback.message, text, reply_markup=subscription_info_kb())
    await callback.answer()


@router.callback_query(F.data == "sub_invite_code")
async def callback_invite_code(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubState.waiting_invite_code)
    await safe_edit(
        callback.message,
        "🎫 <b>Введите инвайт-код</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте код, полученный от администратора.",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(F.text, SubState.waiting_invite_code)
async def handle_invite_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    async with async_session_factory() as db:
        inv = await use_invite_code(db, code)
        if not inv:
            await message.answer(
                "❌ Инвайт-код недействителен или уже использован.",
                reply_markup=cancel_kb(),
            )
            await state.clear()
            return

        await set_subscription_plan(db, message.from_user.id, inv.plan)
        await state.clear()

    plan_info = SUBSCRIPTION_PLANS.get(inv.plan)
    plan_name = plan_info.name if plan_info else inv.plan

    await message.answer(
        f"✅ <b>Инвайт-код принят!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 Подписка: <b>{plan_name}</b>\n"
        f"📨 Лимит сообщений: <b>{plan_info.messages_per_day if plan_info else '—'}</b>\n"
        f"🎯 Лимит чатов: <b>{plan_info.chats_limit if plan_info else '—'}</b>",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    log.info("User %d активировал инвайт-код %s (план: %s)", message.from_user.id, code, inv.plan)
