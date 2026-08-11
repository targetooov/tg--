from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from core.database import (
    async_session_factory,
    get_or_create_user,
    get_or_create_subscription,
)
from core.logger import log


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        user = event.from_user
        if user is None:
            return await handler(event, data)

        if user.is_bot:
            return None

        async with async_session_factory() as db_session:
            db_user = await get_or_create_user(
                db_session,
                telegram_id=user.id,
                username=user.username or "",
                first_name=user.full_name or "",
            )
            sub = await get_or_create_subscription(db_session, user.id)

            if db_user.is_banned:
                if isinstance(event, Message):
                    await event.answer("🚫 Ваш аккаунт заблокирован.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Ваш аккаунт заблокирован.", show_alert=True)
                return None

            data["db_user"] = db_user
            data["db_subscription"] = sub

        return await handler(event, data)
