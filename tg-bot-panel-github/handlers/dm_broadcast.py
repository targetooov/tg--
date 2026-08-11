from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.database import (
    async_session_factory,
    create_broadcast_task,
    get_valid_accounts,
    get_or_create_subscription,
    increment_messages_used,
)
from keyboards.main_menu import back_to_menu_kb, cancel_kb
from workers.task_queue import task_queue, BroadcastJob
from core.utils import safe_edit
from core.logger import log

router = Router()


class DmBroadcastState(StatesGroup):
    waiting_target = State()
    waiting_text = State()
    confirming = State()


@router.callback_query(F.data == "menu_dm_broadcast")
async def callback_dm_broadcast(callback: CallbackQuery, state: FSMContext):
    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db, callback.from_user.id)
        sub = await get_or_create_subscription(db, callback.from_user.id)

    if not accounts:
        await safe_edit(callback.message, "❌ Нет аккаунтов.", reply_markup=back_to_menu_kb())
        await callback.answer()
        return

    remaining = sub.messages_limit - sub.messages_used
    await state.set_state(DmBroadcastState.waiting_target)
    await safe_edit(
        callback.message,
        f"✉️ <b>Рассылка по ЛС</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📨 Осталось: <b>{remaining}/{sub.messages_limit}</b>\n\n"
        f"🎯 Введите username или ID получателя:\n"
        f"<code>@username</code> или <code>123456789</code>",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(F.text, DmBroadcastState.waiting_target)
async def handle_dm_target(message: Message, state: FSMContext):
    target = message.text.strip()
    if not target.startswith("@") and not target.isdigit() and not (target.startswith("-") and target[1:].isdigit()):
        await message.answer("⚠️ Введите @username или числовой ID (допускаются отрицательные ID).")
        return
    await state.update_data(dm_target=target)
    await state.set_state(DmBroadcastState.waiting_text)
    await message.answer(
        "📝 Введите текст сообщения:",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )


@router.message(F.text, DmBroadcastState.waiting_text)
async def handle_dm_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Текст не может быть пустым.")
        return
    await state.update_data(dm_text=text)
    data = await state.get_data()
    target = data.get("dm_target", "")
    display = text[:300] + "..." if len(text) > 300 else text
    await state.set_state(DmBroadcastState.confirming)
    await message.answer(
        f"✉️ <b>Подтверждение</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 Получатель: <code>{target}</code>\n"
        f"📝 Текст:\n<code>{display}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Отправить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="dm_confirm"),
             InlineKeyboardButton(text="❌ Отмена", callback_data="menu_back")]
        ]),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "dm_confirm", DmBroadcastState.confirming)
async def callback_dm_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    target = data.get("dm_target", "")
    text = data.get("dm_text", "")

    async with async_session_factory() as db:
        task = await create_broadcast_task(db, callback.from_user.id, text, [target], broadcast_type="dm")
        await increment_messages_used(db, callback.from_user.id, 1)

    job = BroadcastJob(
        task_id=task.id, user_id=callback.from_user.id, text=text,
        targets=[target], chat_id=callback.message.chat.id,
    )
    await task_queue.enqueue(job)

    await state.clear()
    await safe_edit(
        callback.message,
        f"✅ <b>ЛС отправляется!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Задача: #{task.id}\n"
        f"🎯 Получатель: <code>{target}</code>",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()
