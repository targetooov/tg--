from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.config import config
from core.database import (
    async_session_factory,
    count_users,
    count_total_tasks,
    count_total_sent,
    get_all_users,
    get_all_accounts_admin,
)
from keyboards.admin import admin_panel_kb
from keyboards.main_menu import back_to_menu_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "admin_panel")
async def callback_admin_panel(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    async with async_session_factory() as db:
        user_count = await count_users(db)
        task_count = await count_total_tasks(db)
        sent_count = await count_total_sent(db)
        acc_count = len(await get_all_accounts_admin(db))

    text = (
        f"👑 <b>Админ-панель</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Общая статистика:</b>\n"
        f"  👥 Пользователей: <b>{user_count}</b>\n"
        f"  🟢 Аккаунтов: <b>{acc_count}</b>\n"
        f"  📋 Всего задач: <b>{task_count}</b>\n"
        f"  📨 Всего отправлено: <b>{sent_count}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_edit(callback.message, text, reply_markup=admin_panel_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    async with async_session_factory() as db:
        user_count = await count_users(db)
        task_count = await count_total_tasks(db)
        sent_count = await count_total_sent(db)
        users = await get_all_users(db, limit=50)

    active = sum(1 for u in users if not u.is_banned)
    banned = sum(1 for u in users if u.is_banned)
    admins = sum(1 for u in users if u.is_admin)

    text = (
        f"📊 <b>Детальная статистика</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Всего пользователей: <b>{user_count}</b>\n"
        f"  ✅ Активных: {active}\n"
        f"  🚫 Забанено: {banned}\n"
        f"  👑 Админов: {admins}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Всего задач: <b>{task_count}</b>\n"
        f"📨 Всего отправлено: <b>{sent_count}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_edit(callback.message, text, reply_markup=admin_panel_kb())
    await callback.answer()
