from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_tools_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="noop"),
            ],
            [
                InlineKeyboardButton(text="🔥 Автопрогрев", callback_data="tool_autowarmup"),
                InlineKeyboardButton(text="👻 Теневой инвайт", callback_data="tool_shadow_invite"),
            ],
            [
                InlineKeyboardButton(text="👁 Масслукинг", callback_data="tool_mass_looking"),
                InlineKeyboardButton(text="❤️ Масслайкинг", callback_data="tool_mass_liking"),
            ],
            [
                InlineKeyboardButton(text="🎯 Масстаргет", callback_data="tool_mass_target"),
                InlineKeyboardButton(text="🧠 Нейрокментинг", callback_data="tool_neuro_comment"),
            ],
            [
                InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="noop"),
            ],
            [
                InlineKeyboardButton(text="📋 История задач", callback_data="tool_history"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")],
        ]
    )


def tool_confirm_kb(tool: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Запустить", callback_data=f"tool_confirm_{tool}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_tools"),
            ]
        ]
    )


def tool_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_tools")]
        ]
    )


def tool_task_kb(task_id: int, is_running: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_running:
        buttons.append([InlineKeyboardButton(text="❌ Остановить", callback_data=f"tool_stop_{task_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 К списку", callback_data="tool_history")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
