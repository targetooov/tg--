from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.config import config
from core.database import (
    async_session_factory,
    get_user_by_telegram_id,
    count_user_accounts,
    count_user_referrals,
)
from core.utils import safe_edit
from core.logger import log

router = Router()


@router.callback_query(F.data == "menu_referral")
async def callback_referral(callback: CallbackQuery):
    async with async_session_factory() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        acc_count = await count_user_accounts(db, callback.from_user.id)
        ref_count = await count_user_referrals(db, callback.from_user.id)

    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start={user.ref_code}"

    text = (
        f"👥 <b>Реферальная система</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Приглашайте друзей и получайте <b>+{config.REF_REWARD_DAYS} день</b> "
        f"Trial-подписки за каждого реферала!\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Рефералов: <b>{ref_count}</b>\n"
        f"💎 Награда: <b>+{config.REF_REWARD_DAYS} день</b> за реферала\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    from keyboards.main_menu import referral_kb
    await safe_edit(callback.message, text, reply_markup=referral_kb(bot_username, user.ref_code))
    await callback.answer()
