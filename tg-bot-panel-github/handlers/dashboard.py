from __future__ import annotations

from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.config import config, SUBSCRIPTION_PLANS
from core.database import (
    async_session_factory,
    get_user_by_telegram_id,
    get_or_create_subscription,
    count_user_accounts,
    count_total_tasks,
    count_total_sent,
    get_user_tasks,
)
from keyboards.main_menu import main_menu_kb, back_to_menu_kb, stats_kb
from handlers.start import _is_admin
from core.utils import safe_edit

router = Router()


@router.callback_query(F.data == "menu_dashboard")
async def callback_dashboard(callback: CallbackQuery):
    async with async_session_factory() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        sub = await get_or_create_subscription(db, callback.from_user.id)
        acc_count = await count_user_accounts(db, callback.from_user.id)

    from handlers.start import _dashboard_text
    is_adm = _is_admin(user) if user else False
    await safe_edit(
        callback.message,
        _dashboard_text(user, sub, acc_count),
        reply_markup=main_menu_kb(is_admin=is_adm),
    )
    await callback.answer()


@router.callback_query(F.data == "menu_stats")
async def callback_stats(callback: CallbackQuery):
    async with async_session_factory() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        sub = await get_or_create_subscription(db, callback.from_user.id)
        acc_count = await count_user_accounts(db, callback.from_user.id)
        tasks = await get_user_tasks(db, callback.from_user.id, limit=10)

    plan_name = sub.plan.upper() if sub else "TRIAL"
    msgs = f"{sub.messages_used}/{sub.messages_limit}" if sub else "0/50"
    chats = f"{sub.chats_used}/{sub.chats_limit}" if sub else "0/5"

    recent = ""
    for t in tasks[:5]:
        icon = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}.get(t.status, "❓")
        recent += f"  {icon} #{t.id} — {t.status} ({len(t.get_targets())} целей)\n"
    if not recent:
        recent = "  Пока нет рассылок\n"

    text = (
        f"📈 <b>Статистика</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 Подписка: <b>{plan_name}</b>\n"
        f"🟢 Аккаунтов: <b>{acc_count}</b>\n"
        f"📨 Сообщений сегодня: <b>{msgs}</b>\n"
        f"🎯 Чатов сегодня: <b>{chats}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Последние задачи:</b>\n{recent}"
    )
    await safe_edit(callback.message, text, reply_markup=stats_kb())
    await callback.answer()


@router.callback_query(F.data == "stats_detail")
async def callback_stats_detail(callback: CallbackQuery):
    async with async_session_factory() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        sub = await get_or_create_subscription(db, callback.from_user.id)
        acc_count = await count_user_accounts(db, callback.from_user.id)
        all_tasks = await get_user_tasks(db, callback.from_user.id, limit=100)

    done = sum(1 for t in all_tasks if t.status == "done")
    running = sum(1 for t in all_tasks if t.status == "running")
    pending = sum(1 for t in all_tasks if t.status == "pending")
    errors = sum(1 for t in all_tasks if t.status == "error")

    member_since = user.created_at.strftime("%d.%m.%Y") if user else "—"
    plan_name = sub.plan.upper() if sub else "TRIAL"
    expires = sub.expires_at.strftime("%d.%m.%Y") if sub and sub.expires_at else "∞"

    text = (
        f"📈 <b>Детальная статистика</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Пользователь: <b>{user.first_name if user else '—'}</b>\n"
        f"📅 Зарегистрирован: <b>{member_since}</b>\n"
        f"💎 Подписка: <b>{plan_name}</b> (до {expires})\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Общая статистика:</b>\n"
        f"  🟢 Аккаунтов: {acc_count}\n"
        f"  📋 Всего задач: {len(all_tasks)}\n"
        f"  ✅ Выполнено: {done}\n"
        f"  🔄 В процессе: {running}\n"
        f"  ⏳ В очереди: {pending}\n"
        f"  ❌ Ошибки: {errors}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_edit(callback.message, text, reply_markup=stats_kb())
    await callback.answer()
