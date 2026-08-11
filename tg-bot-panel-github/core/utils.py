from __future__ import annotations

from datetime import datetime, timezone

from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from core.config import config


def is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


def parse_link(raw: str) -> str | None:
    raw = raw.strip()
    raw = raw.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "")
    if not raw:
        return None
    if raw.startswith("@"):
        return raw
    if raw.startswith("+"):
        return None
    if raw.startswith("-"):
        return raw
    if raw.isdigit():
        return f"-100{raw}"
    if raw.isalnum() or (raw.replace("_", "").isalnum()):
        return f"@{raw}"
    return raw


def parse_target_list(raw: str) -> list[str]:
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    targets = []
    for line in lines:
        parsed = parse_link(line)
        if parsed:
            targets.append(parsed)
    return targets


async def safe_edit(message, text: str, reply_markup=None, parse_mode: str = "HTML") -> bool:
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except TelegramBadRequest:
        return False
    except Exception:
        return False


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def pagination_kb(
    items: list,
    page: int,
    per_page: int,
    callback_prefix: str,
    back_callback: str = "menu_back",
) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page
    page_items = items[start:end]

    buttons: list[list[InlineKeyboardButton]] = []

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️", callback_data=f"{callback_prefix}_page_{page - 1}"
        ))
    nav_row.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}", callback_data="noop"
    ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="▶️", callback_data=f"{callback_prefix}_page_{page + 1}"
        ))
    if total_pages > 1:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=buttons), page_items, page, total_pages
