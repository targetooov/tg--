from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.config import config
from core.database import (
    async_session_factory,
    get_all_users,
    ban_user,
    unban_user,
    make_admin,
    count_user_accounts,
    get_or_create_subscription,
)
from keyboards.admin import admin_panel_kb, admin_users_list_kb, admin_user_detail_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "admin_users")
async def callback_admin_users(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    async with async_session_factory() as db:
        users = await get_all_users(db, limit=30)

    text = (
        f"👥 <b>Пользователи</b> ({len(users)})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    for u in users[:20]:
        icon = "👑" if u.is_admin else ("🚫" if u.is_banned else "👤")
        label = u.username or u.first_name or f"ID:{u.telegram_id}"
        text += f"{icon} <b>{label}</b> — {u.telegram_id}\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━"

    await safe_edit(callback.message, text, reply_markup=admin_users_list_kb(users))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_view_"))
async def callback_admin_user_view(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    telegram_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        from core.database import get_user_by_telegram_id
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        acc_count = await count_user_accounts(db, telegram_id)
        sub = await get_or_create_subscription(db, telegram_id)

    status = "🚫 Забанен" if user.is_banned else ("👑 Админ" if user.is_admin else "✅ Активен")
    label = user.username or user.first_name or "—"

    text = (
        f"👤 <b>{label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"📝 Юзернейм: @{user.username or '—'}\n"
        f"📛 Имя: {user.first_name or '—'}\n"
        f"📊 Статус: {status}\n"
        f"💎 Подписка: <b>{sub.plan.upper() if sub else 'TRIAL'}</b>\n"
        f"🟢 Аккаунтов: <b>{acc_count}</b>\n"
        f"🔗 Реферал-код: <code>{user.ref_code}</code>\n"
        f"📅 Зарегистрирован: {user.created_at.strftime('%d.%m.%Y') if user.created_at else '—'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_edit(callback.message, text, reply_markup=admin_user_detail_kb(telegram_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_ban_"))
async def callback_admin_ban(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    telegram_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        await ban_user(db, telegram_id)
    log.info("Admin %d забанил пользователя %d", callback.from_user.id, telegram_id)
    await callback.answer("🚫 Пользователь забанен", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=admin_user_detail_kb(telegram_id))


@router.callback_query(F.data.startswith("admin_user_unban_"))
async def callback_admin_unban(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    telegram_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        await unban_user(db, telegram_id)
    log.info("Admin %d разбанил пользователя %d", callback.from_user.id, telegram_id)
    await callback.answer("✅ Пользователь разбанен", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=admin_user_detail_kb(telegram_id))


@router.callback_query(F.data.startswith("admin_user_makeadmin_"))
async def callback_admin_make_admin(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    telegram_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        await make_admin(db, telegram_id)
    log.info("Admin %d назначил админом %d", callback.from_user.id, telegram_id)
    await callback.answer("👑 Пользователь теперь админ", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=admin_user_detail_kb(telegram_id))
