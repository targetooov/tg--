from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.database import (
    async_session_factory,
    get_user_accounts,
    delete_account,
)
from core.logger import log
from keyboards.main_menu import accounts_list_kb, account_detail_kb, confirm_delete_kb, back_to_menu_kb
from workers.session_manager import delete_session_file
from core.utils import safe_edit

router = Router()


@router.callback_query(F.data == "menu_accounts")
async def callback_accounts(callback: CallbackQuery):
    async with async_session_factory() as db:
        accounts = await get_user_accounts(db, callback.from_user.id)

    if not accounts:
        await safe_edit(
            callback.message,
            "🗂 <b>Мои аккаунты</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 У вас пока нет сессий.\n"
            "Загрузите через «📁 Сессии».",
            reply_markup=back_to_menu_kb(),
        )
    else:
        text = (
            f"🗂 <b>Мои аккаунты</b> ({len(accounts)})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for acc in accounts:
            icon = "🟢" if acc.is_valid and not acc.is_banned else "🔴"
            name = acc.username or acc.first_name or acc.phone or f"#{acc.id}"
            text += f"{icon} <b>{name}</b>\n"
        text += "\n━━━━━━━━━━━━━━━━━━━━━━"
        await safe_edit(callback.message, text, reply_markup=accounts_list_kb(accounts))
    await callback.answer()


@router.callback_query(F.data.startswith("account_view_"))
async def callback_account_view(callback: CallbackQuery):
    account_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        accounts = await get_user_accounts(db, callback.from_user.id)
    account = next((a for a in accounts if a.id == account_id), None)
    if not account:
        await callback.answer("❌ Аккаунт не найден", show_alert=True)
        return

    status = "🟢 Активен" if account.is_valid and not account.is_banned else "🔴 Заблокирован"
    name = account.username or account.first_name or account.phone or "—"
    text = (
        f"👤 <b>{name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 ID: <code>{account.id}</code>\n"
        f"📱 Телефон: <code>{account.phone or '—'}</code>\n"
        f"📝 @{account.username or '—'}\n"
        f"📛 {account.first_name or '—'}\n"
        f"📊 {status}\n"
        f"📅 {account.added_at.strftime('%d.%m.%Y %H:%M') if account.added_at else '—'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_edit(callback.message, text, reply_markup=account_detail_kb(account_id))
    await callback.answer()


@router.callback_query(F.data.startswith("account_delete_"))
async def callback_account_delete(callback: CallbackQuery):
    account_id = int(callback.data.split("_")[-1])
    await safe_edit(
        callback.message,
        "⚠️ <b>Удалить аккаунт?</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Это действие необратимо.",
        reply_markup=confirm_delete_kb(account_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("account_confirm_delete_"))
async def callback_confirm_delete(callback: CallbackQuery):
    account_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        accounts = await get_user_accounts(db, callback.from_user.id)
        account = next((a for a in accounts if a.id == account_id), None)
        if account:
            await delete_session_file(account.session_path)
            await delete_account(db, account_id)

    await safe_edit(callback.message, "🗑 Аккаунт удалён.", reply_markup=back_to_menu_kb())
    log.info("User %d удалил аккаунт %d", callback.from_user.id, account_id)
    await callback.answer()
