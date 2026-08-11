from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import SUBSCRIPTION_PLANS
from core.database import (
    async_session_factory,
    create_broadcast_task,
    get_valid_accounts,
    get_or_create_subscription,
    increment_messages_used,
    increment_chats_used,
    get_user_folders,
)
from core.logger import log
from keyboards.main_menu import back_to_menu_kb, cancel_kb
from keyboards.folders import folders_select_kb
from workers.task_queue import task_queue, BroadcastJob
from core.utils import safe_edit

router = Router()


class BroadcastState(StatesGroup):
    waiting_text = State()
    waiting_targets = State()
    confirming = State()


def _check_limits(sub) -> tuple[bool, str]:
    if sub.messages_used >= sub.messages_limit:
        return False, f"❌ Лимит сообщений: {sub.messages_used}/{sub.messages_limit}\nОбновится завтра."
    return True, ""


@router.callback_query(F.data == "menu_broadcast")
async def callback_broadcast(callback: CallbackQuery, state: FSMContext):
    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db, callback.from_user.id)
        sub = await get_or_create_subscription(db, callback.from_user.id)

    if not accounts:
        await safe_edit(
            callback.message,
            "✉️ <b>Рассылка</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ Нет аккаунтов.\n"
            "Загрузите через «📁 Сессии».",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    ok, err = _check_limits(sub)
    if not ok:
        await safe_edit(callback.message, err, reply_markup=back_to_menu_kb())
        await callback.answer()
        return

    await state.set_state(BroadcastState.waiting_text)
    plan = SUBSCRIPTION_PLANS.get(sub.plan)
    remaining = sub.messages_limit - sub.messages_used
    await safe_edit(
        callback.message,
        f"✉️ <b>Рассылка</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🟢 Аккаунтов: <b>{len(accounts)}</b>\n"
        f"📨 Осталось сообщений: <b>{remaining}/{sub.messages_limit}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Отправьте текст для рассылки:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(F.text, BroadcastState.waiting_text)
async def handle_broadcast_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Текст не может быть пустым.")
        return
    await state.update_data(broadcast_text=text)
    await state.set_state(BroadcastState.waiting_targets)

    async with async_session_factory() as db:
        folders = await get_user_folders(db, message.from_user.id)

    kb_buttons: list[list[InlineKeyboardButton]] = []
    if folders:
        for f in folders[:5]:
            targets = f.get_targets()
            kb_buttons.append([
                InlineKeyboardButton(
                    text=f"📂 {f.name} ({len(targets)})",
                    callback_data=f"broadcast_folder_{f.id}",
                )
            ])
    kb_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="menu_back")])

    await message.answer(
        "📋 <b>Целевые чаты</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте список (каждый с новой строки):\n"
        "• <code>@username</code>\n"
        "• <code>-1001234567890</code>\n"
        "• <code>https://t.me/username</code>\n\n"
        + ("💡 Или выберите папку:" if folders else ""),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("broadcast_folder_"))
async def callback_broadcast_folder(callback: CallbackQuery, state: FSMContext):
    folder_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        from core.database import get_folder_by_id
        folder = await get_folder_by_id(db, folder_id)

    if not folder or folder.user_id != callback.from_user.id:
        await callback.answer("Папка не найдена", show_alert=True)
        return

    folder_targets = folder.get_targets()
    data = await state.get_data()
    existing_targets = data.get("broadcast_targets", [])

    all_targets = existing_targets + folder_targets
    await state.update_data(broadcast_targets=all_targets)

    targets_display = "\n".join(f"  • {t}" for t in all_targets[:20])
    if len(all_targets) > 20:
        targets_display += f"\n  ... и ещё {len(all_targets) - 20}"

    async with async_session_factory() as db:
        sub = await get_or_create_subscription(db, callback.from_user.id)
    remaining = sub.messages_limit - sub.messages_used

    text = data.get("broadcast_text", "")
    display = text[:400] + "..." if len(text) > 400 else text

    await state.set_state(BroadcastState.confirming)
    await safe_edit(
        callback.message,
        f"📋 <b>Подтверждение</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Текст:</b>\n<code>{display}</code>\n\n"
        f"<b>Цели ({len(all_targets)}):</b>\n{targets_display}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📨 Сообщений: {len(all_targets)} (осталось {remaining})\n\n"
        f"Запустить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Запустить", callback_data="broadcast_confirm"),
             InlineKeyboardButton(text="❌ Отмена", callback_data="menu_back")]
        ]),
    )
    await callback.answer()


@router.message(F.text, BroadcastState.waiting_targets)
async def handle_broadcast_targets(message: Message, state: FSMContext):
    raw = message.text.strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        await message.answer("⚠️ Список пуст.")
        return

    targets = []
    for line in lines:
        line = line.replace("https://t.me/", "").replace("http://t.me/", "")
        line = line.replace("t.me/", "")
        if not line:
            continue
        if not line.startswith("@") and not line.startswith("-"):
            if line.isdigit():
                line = f"-100{line}"
            elif line.lstrip("-").isdigit():
                pass
            else:
                line = f"@{line}"
        targets.append(line)

    await state.update_data(broadcast_targets=targets)
    await state.set_state(BroadcastState.confirming)

    async with async_session_factory() as db:
        sub = await get_or_create_subscription(db, message.from_user.id)

    remaining = sub.messages_limit - sub.messages_used
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    display = text[:400] + "..." if len(text) > 400 else text
    targets_display = "\n".join(f"  • {t}" for t in targets[:15])

    await message.answer(
        f"📋 <b>Подтверждение</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Текст:</b>\n<code>{display}</code>\n\n"
        f"<b>Цели ({len(targets)}):</b>\n{targets_display}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📨 Сообщений: {len(targets)} (осталось {remaining})\n\n"
        f"Запустить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Запустить", callback_data="broadcast_confirm"),
             InlineKeyboardButton(text="❌ Отмена", callback_data="menu_back")]
        ]),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "broadcast_confirm", BroadcastState.confirming)
async def callback_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    targets = data.get("broadcast_targets", [])

    if not text or not targets:
        await callback.answer("❌ Данные неполные", show_alert=True)
        await state.clear()
        return

    async with async_session_factory() as db:
        sub = await get_or_create_subscription(db, callback.from_user.id)
        task = await create_broadcast_task(db, callback.from_user.id, text, targets)
        await increment_messages_used(db, callback.from_user.id, len(targets))
        await increment_chats_used(db, callback.from_user.id, len(targets))

    job = BroadcastJob(
        task_id=task.id, user_id=callback.from_user.id, text=text,
        targets=targets, chat_id=callback.message.chat.id,
    )
    await task_queue.enqueue(job)

    await state.clear()
    await safe_edit(
        callback.message,
        f"✅ <b>Рассылка запущена!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Задача: #{task.id}\n"
        f"🎯 Целей: {len(targets)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Результаты будут отправлены по завершении.",
        reply_markup=back_to_menu_kb(),
    )
    log.info("User %d: рассылка task=%d, targets=%d", callback.from_user.id, task.id, len(targets))
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def callback_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(callback.message, "❌ Отменено.", reply_markup=back_to_menu_kb())
    await callback.answer()
