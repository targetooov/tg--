from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.utils import pagination_kb


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="noop"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton(text="👥 Юзеры", callback_data="admin_users"),
            ],
            [
                InlineKeyboardButton(text="📨 Глобальная", callback_data="admin_global_broadcast"),
                InlineKeyboardButton(text="📈 Мониторинг", callback_data="admin_monitor"),
            ],
            [
                InlineKeyboardButton(text="🎫 Инвайт-коды", callback_data="admin_invite"),
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings"),
            ],
            [
                InlineKeyboardButton(text="🛠 Инструменты", callback_data="admin_tools"),
            ],
            [
                InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="noop"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def admin_users_list_kb(users: list, page: int = 0, per_page: int = 20) -> InlineKeyboardMarkup:
    kb, page_items, page, total_pages = pagination_kb(
        items=users,
        page=page,
        per_page=per_page,
        callback_prefix="admin_users",
        back_callback="admin_panel",
    )
    buttons: list[list[InlineKeyboardButton]] = []
    for u in page_items:
        icon = "👑" if u.is_admin else ("🚫" if u.is_banned else "👤")
        label = u.username or u.first_name or f"ID:{u.telegram_id}"
        buttons.append([
            InlineKeyboardButton(text=f"{icon} {label}", callback_data=f"admin_user_view_{u.telegram_id}")
        ])
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_users_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_users_page_{page + 1}"))
    if total_pages > 1:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_user_detail_kb(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚫 Забанить", callback_data=f"admin_user_ban_{telegram_id}"),
                InlineKeyboardButton(text="✅ Разбан", callback_data=f"admin_user_unban_{telegram_id}"),
            ],
            [
                InlineKeyboardButton(text="👑 Сделать админом", callback_data=f"admin_user_makeadmin_{telegram_id}"),
            ],
            [InlineKeyboardButton(text="🔙 К списку", callback_data="admin_users")],
        ]
    )


def admin_invite_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Генерировать код", callback_data="admin_invite_gen")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")],
        ]
    )


def admin_settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Канал (Force-Sub)", callback_data="admin_set_channel")],
            [InlineKeyboardButton(text="✍️ Подпись по умолчанию", callback_data="admin_set_signature")],
            [InlineKeyboardButton(text="⏱ Задержки рассылки", callback_data="admin_set_delays")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")],
        ]
    )


def admin_confirm_global_broadcast_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Запустить", callback_data="admin_global_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel"),
            ]
        ]
    )


def cancel_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")]
        ]
    )
