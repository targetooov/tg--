from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.config import config
from core.database import (
    async_session_factory,
    get_all_tasks_admin,
    count_total_tasks,
    count_total_sent,
)
from keyboards.admin import admin_panel_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "admin_monitor")
async def callback_admin_monitor(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    async with async_session_factory() as db:
        tasks = await get_all_tasks_admin(db, limit=20)
        total_tasks = await count_total_tasks(db)
        total_sent = await count_total_sent(db)

    text = (
        f"📈 <b>Мониторинг рассылок</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 Всего задач: <b>{total_tasks}</b>\n"
        f"📨 Всего отправлено: <b>{total_sent}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Последние задачи:</b>\n"
    )

    for t in tasks[:15]:
        icon = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}.get(t.status, "❓")
        targets = t.get_targets()
        text += f"  {icon} #{t.id} — user:{t.user_id} — {t.status} ({len(targets)} целей)\n"

    if not tasks:
        text += "  Пока нет задач\n"

    text += "━━━━━━━━━━━━━━━━━━━━━━"
    await safe_edit(callback.message, text, reply_markup=admin_panel_kb())
    await callback.answer()
