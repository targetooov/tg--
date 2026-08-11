from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def subscription_info_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="noop")],
            [InlineKeyboardButton(text="🎫 Ввести инвайт-код", callback_data="sub_invite_code")],
            [InlineKeyboardButton(text="💎 Активировать подписку", callback_data="menu_subscription")],
            [InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="noop")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def subscription_manage_kb(is_active: bool, expires_at: str = "") -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    if is_active:
        buttons.append([InlineKeyboardButton(text=f"✅ Подписка активна до {expires_at}", callback_data="noop")])
    else:
        buttons.append([InlineKeyboardButton(text="❌ Подписка неактивна", callback_data="noop")])
    buttons.append([
        InlineKeyboardButton(text="🎫 Ввести инвайт-код", callback_data="sub_invite_code"),
    ])
    buttons.append([
        InlineKeyboardButton(text="💳 Продлить подписку", callback_data="sub_renew"),
    ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
