from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.utils import pagination_kb


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="noop"),
        ],
        [
            InlineKeyboardButton(text="📁 Сессии", callback_data="menu_upload_sessions"),
            InlineKeyboardButton(text="🗂 Аккаунты", callback_data="menu_accounts"),
        ],
        [
            InlineKeyboardButton(text="✉️ Рассылка", callback_data="menu_broadcast"),
            InlineKeyboardButton(text="📤 ЛС-рассылка", callback_data="menu_dm_broadcast"),
        ],
        [
            InlineKeyboardButton(text="📋 Шаблоны", callback_data="menu_templates"),
            InlineKeyboardButton(text="⏰ Отложенные", callback_data="menu_scheduled"),
        ],
        [
            InlineKeyboardButton(text="🗂 Очередь", callback_data="menu_queue"),
            InlineKeyboardButton(text="📈 Статистика", callback_data="menu_stats"),
        ],
        [
            InlineKeyboardButton(text="🔍 Парсинг", callback_data="menu_parser"),
            InlineKeyboardButton(text="🤖 Авто-ответы", callback_data="menu_auto_reply"),
        ],
        [
            InlineKeyboardButton(text="💎 Подписка", callback_data="menu_subscription"),
            InlineKeyboardButton(text="👥 Рефералы", callback_data="menu_referral"),
        ],
        [
            InlineKeyboardButton(text="📂 Папки целей", callback_data="menu_folders"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="noop"),
        ],
    ]
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb(confirm_data: str, cancel_data: str = "menu_back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=confirm_data),
                InlineKeyboardButton(text="❌ Нет", callback_data=cancel_data),
            ]
        ]
    )


def accounts_list_kb(accounts: list, page: int = 0, per_page: int = 20) -> InlineKeyboardMarkup:
    kb, page_items, page, total_pages = pagination_kb(
        items=accounts,
        page=page,
        per_page=per_page,
        callback_prefix="accounts",
        back_callback="menu_back",
    )
    buttons: list[list[InlineKeyboardButton]] = []
    for acc in page_items:
        icon = "🟢" if acc.is_valid and not acc.is_banned else "🔴"
        label = acc.username or acc.first_name or acc.phone or f"#{acc.id}"
        buttons.append([
            InlineKeyboardButton(text=f"{icon} {label}", callback_data=f"account_view_{acc.id}")
        ])
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"accounts_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"accounts_page_{page + 1}"))
    if total_pages > 1:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def account_detail_kb(account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"account_delete_{account_id}")],
            [InlineKeyboardButton(text="🔙 К списку", callback_data="menu_accounts")],
        ]
    )


def confirm_delete_kb(account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"account_confirm_delete_{account_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"account_view_{account_id}"),
            ]
        ]
    )


def templates_list_kb(templates: list, page: int = 0, per_page: int = 15) -> InlineKeyboardMarkup:
    kb, page_items, page, total_pages = pagination_kb(
        items=templates,
        page=page,
        per_page=per_page,
        callback_prefix="templates",
        back_callback="menu_back",
    )
    buttons: list[list[InlineKeyboardButton]] = []
    for t in page_items:
        buttons.append([
            InlineKeyboardButton(text=f"📝 {t.name}", callback_data=f"template_view_{t.id}")
        ])
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"templates_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"templates_page_{page + 1}"))
    if total_pages > 1:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="➕ Создать шаблон", callback_data="template_create")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def template_detail_kb(template_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"template_delete_{template_id}")],
            [InlineKeyboardButton(text="🔙 К списку", callback_data="menu_templates")],
        ]
    )


def queue_list_kb(tasks: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    kb, page_items, page, total_pages = pagination_kb(
        items=tasks,
        page=page,
        per_page=per_page,
        callback_prefix="queue",
        back_callback="menu_back",
    )
    buttons: list[list[InlineKeyboardButton]] = []
    for t in page_items:
        status_icon = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}.get(t.status, "❓")
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} #{t.id} — {t.status}",
                callback_data=f"task_view_{t.id}",
            )
        ])
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"queue_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"queue_page_{page + 1}"))
    if total_pages > 1:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def task_detail_kb(task_id: int, is_running: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_running:
        buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data=f"task_cancel_{task_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 К очереди", callback_data="menu_queue")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить подпись", callback_data="settings_edit_signature")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Детальная статистика", callback_data="stats_detail")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def subscription_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎫 Ввести инвайт-код", callback_data="sub_invite_code")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def referral_kb(bot_username: str, ref_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Пригласить друга", url=f"https://t.me/{bot_username}?start={ref_code}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_back")]
        ]
    )


def sessions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📁 Загрузить сессию", callback_data="menu_upload_sessions")],
            [InlineKeyboardButton(text="📦 Пакетная загрузка", callback_data="menu_batch_sessions")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def admin_users_list_paginated_kb(users: list, page: int = 0, per_page: int = 20) -> InlineKeyboardMarkup:
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
