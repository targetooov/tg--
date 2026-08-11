from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from core.config import config
from core.database import (
    async_session_factory,
    get_or_create_user,
    get_or_create_subscription,
    get_user_by_ref_code,
    count_user_accounts,
    set_subscription_plan,
)
from core.logger import log
from keyboards.main_menu import main_menu_kb, back_to_menu_kb

router = Router()


def _is_admin(user) -> bool:
    return user.telegram_id == config.SUPER_ADMIN_ID or user.is_admin


def _dashboard_text(user, sub, acc_count: int) -> str:
    plan_name = sub.plan.upper() if sub else "TRIAL"
    msgs = f"{sub.messages_used}/{sub.messages_limit}" if sub else "0/50"
    chats = f"{sub.chats_used}/{sub.chats_limit}" if sub else "0/5"
    expires = ""
    if sub and sub.expires_at:
        delta = sub.expires_at - datetime.now(timezone.utc)
        if delta.days > 0:
            expires = f"  ⏳ Осталось: {delta.days} дн.\n"
        else:
            expires = "  ⏳ Истекает сегодня!\n"
    return (
        f"👋 <b>{user.first_name or 'Пользователь'}</b>, добро пожаловать!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Ваш кабинет:</b>\n"
        f"  🟢 Аккаунтов: <b>{acc_count}</b>\n"
        f"  📨 Сообщений сегодня: <b>{msgs}</b>\n"
        f"  🎯 Чатов сегодня: <b>{chats}</b>\n"
        f"  💎 Подписка: <b>{plan_name}</b>\n"
        f"{expires}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Выберите раздел:"
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split(maxsplit=1)
    ref_code = args[1] if len(args) > 1 else None

    referred_by = None
    if ref_code:
        async with async_session_factory() as db:
            ref_user = await get_user_by_ref_code(db, ref_code)
            if ref_user and ref_user.telegram_id != message.from_user.id:
                referred_by = ref_user.telegram_id

    async with async_session_factory() as db:
        user = await get_or_create_user(
            db,
            telegram_id=message.from_user.id,
            username=message.from_user.username or "",
            first_name=message.from_user.full_name or "",
            referred_by=referred_by,
        )
        sub = await get_or_create_subscription(db, message.from_user.id)
        acc_count = await count_user_accounts(db, message.from_user.id)

        if user.telegram_id == config.SUPER_ADMIN_ID and sub.plan != "admin":
            await set_subscription_plan(db, user.telegram_id, "admin")
            sub = await get_or_create_subscription(db, message.from_user.id)

    log.info("User %d /start (ref=%s)", message.from_user.id, ref_code)

    if ref_code and referred_by:
        from core.config import config as cfg
        async with async_session_factory() as db:
            from core.database import get_subscription
            current_sub = await get_subscription(db, message.from_user.id)
            if not current_sub or current_sub.plan == "trial":
                await set_subscription_plan(db, message.from_user.id, "trial", cfg.TRIAL_DURATION_DAYS + cfg.REF_REWARD_DAYS)
        await message.answer(
            "🎉 Вы были приглашены по реферальной ссылке!\n"
            f"Вам начислено +{config.REF_REWARD_DAYS} день Trial-подписки.\n\n"
            + _dashboard_text(user, sub, acc_count),
            reply_markup=main_menu_kb(is_admin=_is_admin(user)),
            parse_mode="HTML",
        )
        return

    await message.answer(
        _dashboard_text(user, sub, acc_count),
        reply_markup=main_menu_kb(is_admin=_is_admin(user)),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "menu_back")
async def callback_back_to_menu(callback: CallbackQuery):
    async with async_session_factory() as db:
        from core.database import get_user_by_telegram_id
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        sub = await get_or_create_subscription(db, callback.from_user.id)
        acc_count = await count_user_accounts(db, callback.from_user.id)

        if user and user.telegram_id == config.SUPER_ADMIN_ID and sub.plan != "admin":
            await set_subscription_plan(db, user.telegram_id, "admin")
            sub = await get_or_create_subscription(db, user.telegram_id)

    is_adm = _is_admin(user) if user else False
    text = _dashboard_text(user, sub, acc_count) if user else "👋 Главное меню"
    await callback.message.edit_text(
        text,
        reply_markup=main_menu_kb(is_admin=is_adm),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "force_sub_check")
async def callback_force_sub_check(callback: CallbackQuery):
    bot = callback.bot
    try:
        member = await bot.get_chat_member(
            chat_id=config.CHANNEL_ID,
            user_id=callback.from_user.id,
        )
        if member.status in ("member", "administrator", "creator"):
            async with async_session_factory() as db:
                from core.database import get_user_by_telegram_id
                user = await get_user_by_telegram_id(db, callback.from_user.id)
                sub = await get_or_create_subscription(db, callback.from_user.id)
                acc_count = await count_user_accounts(db, callback.from_user.id)
            is_adm = _is_admin(user) if user else False
            await callback.message.edit_text(
                "✅ Подписка подтверждена!\n\n" + (_dashboard_text(user, sub, acc_count) if user else "👋 Добро пожаловать!"),
                reply_markup=main_menu_kb(is_admin=is_adm),
                parse_mode="HTML",
            )
        else:
            await callback.answer("❌ Вы всё ещё не подписаны.", show_alert=True)
    except Exception as e:
        log.warning("ForceSub check error for user %d: %s", callback.from_user.id, e)
        await callback.answer("⚠️ Не удалось проверить подписку.", show_alert=True)
