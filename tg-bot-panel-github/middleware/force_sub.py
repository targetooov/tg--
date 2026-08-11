from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import config
from core.logger import log


class ForceSubMiddleware(BaseMiddleware):
    def __init__(self, channel_id: int, channel_url: str):
        self.channel_id = channel_id
        self.channel_url = channel_url
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        if not config.force_sub_enabled:
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        if user_id == config.SUPER_ADMIN_ID:
            return await handler(event, data)

        bot = data.get("bot")
        if bot is None:
            return await handler(event, data)

        try:
            member = await bot.get_chat_member(
                chat_id=self.channel_id,
                user_id=user_id,
            )
            if member.status in ("member", "administrator", "creator"):
                return await handler(event, data)
        except Exception as e:
            log.warning(
                "ForceSub: ошибка проверки подписки user %d: %s",
                user_id,
                e,
            )
            return await handler(event, data)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📢 Подписаться на канал",
                        url=self.channel_url,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Проверить подписку",
                        callback_data="force_sub_check",
                    )
                ],
            ]
        )

        if isinstance(event, Message):
            await event.answer(
                "⚠️ Для использования бота необходимо подписаться на наш канал!",
                reply_markup=kb,
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                "⚠️ Сначала подпишитесь на канал, затем нажмите «Проверить подписку»",
                show_alert=True,
            )
        return None
