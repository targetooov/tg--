from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.config import config
from core.database import async_session_factory, get_admin_tasks
from keyboards.admin_tools import admin_tools_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "admin_tools")
async def callback_admin_tools(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    text = (
        "🛠 <b>Инструменты админа</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔥 Автопрогрев — прогрев аккаунтов в группах\n"
        "👻 Теневой инвайт — тихий инвайт юзеров\n"
        "👁 Масслукинг — массовый просмотр сторис\n"
        "❤️ Масслайкинг — массовые лайки\n"
        "🎯 Масстаргет — массовая рассылка по целям\n"
        "🧠 Нейрокментинг — AI-комментарии\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Все операции используют ваши аккаунты."
    )
    await safe_edit(callback.message, text, reply_markup=admin_tools_kb())
    await callback.answer()


@router.callback_query(F.data == "tool_history")
async def callback_tool_history(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    async with async_session_factory() as db:
        tasks = await get_admin_tasks(db, limit=15)

    if not tasks:
        text = "📋 <b>История задач</b>\n\nПока нет задач."
    else:
        text = (
            f"📋 <b>История задач</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        icons = {
            "autowarmup": "🔥", "shadow_invite": "👻",
            "mass_looking": "👁", "mass_liking": "❤️",
            "mass_target": "🎯", "neuro_comment": "🧠",
        }
        status_icons = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌", "cancelled": "🚫"}
        for t in tasks:
            icon = icons.get(t.tool, "🔧")
            s_icon = status_icons.get(t.status, "❓")
            text += f"{s_icon} {icon} #{t.id} — {t.tool} ({t.done}/{t.total})\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━"

    from keyboards.admin_tools import tool_back_kb
    await safe_edit(callback.message, text, reply_markup=tool_back_kb())
    await callback.answer()
