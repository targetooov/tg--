from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.database import (
    async_session_factory,
    add_scheduled_broadcast,
    get_user_tasks,
)
from keyboards.main_menu import back_to_menu_kb, cancel_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class ScheduledState(StatesGroup):
    waiting_text = State()
    waiting_targets = State()
    waiting_time = State()


@router.callback_query(F.data == "menu_scheduled")
async def callback_scheduled(callback: CallbackQuery):
    async with async_session_factory() as db:
        tasks = await get_user_tasks(db, callback.from_user.id, limit=10)

    pending = [t for t in tasks if t.status == "pending"]

    text = (
        f"⏰ <b>Отложенные рассылки</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    if pending:
        for t in pending[:5]:
            targets = t.get_targets()
            text += f"  ⏳ #{t.id} — {len(targets)} целей\n"
    else:
        text += "  Нет отложенных рассылок\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━━\nДля создания новой нажмите «Создать»."
    await safe_edit(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать", callback_data="sched_create")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]),
    )
    await callback.answer()


@router.callback_query(F.data == "sched_create")
async def callback_sched_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ScheduledState.waiting_text)
    await safe_edit(
        callback.message,
        "⏰ <b>Создание отложенной рассылки</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 Введите текст:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(F.text, ScheduledState.waiting_text)
async def handle_sched_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Текст не может быть пустым.")
        return
    await state.update_data(sched_text=text)
    await state.set_state(ScheduledState.waiting_targets)
    await message.answer(
        "📋 Введите список чатов (каждый с новой строки):",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )


@router.message(F.text, ScheduledState.waiting_targets)
async def handle_sched_targets(message: Message, state: FSMContext):
    raw = message.text.strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
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
    await state.update_data(sched_targets=targets)
    await state.set_state(ScheduledState.waiting_time)
    current_year = datetime.now(timezone.utc).year
    await message.answer(
        f"⏰ Введите время запуска:\n"
        f"<code>{current_year}-01-15 14:30</code> — конкретное время\n"
        f"<code>через 30 минут</code> — через N минут\n"
        f"<code>завтра 10:00</code> — завтра в указанное время",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )


@router.message(F.text, ScheduledState.waiting_time)
async def handle_sched_time(message: Message, state: FSMContext):
    raw = message.text.strip().lower()
    now = datetime.now(timezone.utc)

    try:
        if raw.startswith("через "):
            parts = raw.replace("через ", "").split()
            minutes = int(parts[0])
            run_at = now + timedelta(minutes=minutes)
        elif raw.startswith("завтра "):
            time_str = raw.replace("завтра ", "")
            h, m = map(int, time_str.split(":"))
            run_at = (now + timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)
        else:
            run_at = datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except Exception:
        await message.answer("⚠️ Неверный формат времени. Попробуйте ещё раз.")
        return

    if run_at <= now:
        await message.answer("⚠️ Время должно быть в будущем.")
        return

    data = await state.get_data()
    text = data.get("sched_text", "")
    targets = data.get("sched_targets", [])

    async with async_session_factory() as db:
        sb = await add_scheduled_broadcast(db, message.from_user.id, text, targets, run_at)

    await state.clear()
    await message.answer(
        f"✅ <b>Отложенная рассылка создана!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 #{sb.id}\n"
        f"🎯 Целей: {len(targets)}\n"
        f"⏰ Запуск: {run_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Рассылка выполнится автоматически.",
        reply_markup=back_to_menu_kb(), parse_mode="HTML",
    )
    log.info("User %d: отложенная рассылка #%d на %s", message.from_user.id, sb.id, run_at)
