from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.utils import pagination_kb


def folders_list_kb(folders: list, page: int = 0, per_page: int = 20) -> InlineKeyboardMarkup:
    kb, page_items, page, total_pages = pagination_kb(
        items=folders,
        page=page,
        per_page=per_page,
        callback_prefix="folders",
        back_callback="menu_back",
    )
    buttons: list[list[InlineKeyboardButton]] = []
    for f in page_items:
        targets = f.get_targets()
        buttons.append([
            InlineKeyboardButton(
                text=f"📂 {f.name} ({len(targets)} целей)",
                callback_data=f"folder_view_{f.id}",
            )
        ])
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"folders_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"folders_page_{page + 1}"))
    if total_pages > 1:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="➕ Создать папку", callback_data="folder_create")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def folder_detail_kb(folder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"folder_rename_{folder_id}")],
            [InlineKeyboardButton(text="📝 Изменить цели", callback_data=f"folder_edit_targets_{folder_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"folder_delete_{folder_id}")],
            [InlineKeyboardButton(text="🔙 К списку", callback_data="menu_folders")],
        ]
    )


def folder_confirm_delete_kb(folder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"folder_confirm_delete_{folder_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"folder_view_{folder_id}"),
            ]
        ]
    )


def folders_select_kb(folders: list, page: int = 0, per_page: int = 20) -> InlineKeyboardMarkup:
    kb, page_items, page, total_pages = pagination_kb(
        items=folders,
        page=page,
        per_page=per_page,
        callback_prefix="folders_select",
        back_callback="menu_back",
    )
    buttons: list[list[InlineKeyboardButton]] = []
    for f in page_items:
        targets = f.get_targets()
        buttons.append([
            InlineKeyboardButton(
                text=f"📂 {f.name} ({len(targets)} целей)",
                callback_data=f"folder_pick_{f.id}",
            )
        ])
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"folders_select_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"folders_select_page_{page + 1}"))
    if total_pages > 1:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="❌ Без папки", callback_data="broadcast_targets_skip")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
