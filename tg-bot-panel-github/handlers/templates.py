from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.database import (
    async_session_factory,
    add_template,
    get_user_templates,
    delete_template,
)
from keyboards.main_menu import templates_list_kb, template_detail_kb, back_to_menu_kb, cancel_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class TemplateState(StatesGroup):
    waiting_name = State()
    waiting_text = State()


@router.callback_query(F.data == "menu_templates")
async def callback_templates(callback: CallbackQuery):
    async with async_session_factory() as db:
        templates = await get_user_templates(db, callback.from_user.id)

    if not templates:
        await safe_edit(
            callback.message,
            "📋 <b>Шаблоны</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 У вас нет шаблонов.\n"
            "Создайте шаблон для быстрой рассылки.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать", callback_data="template_create")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
            ]),
        )
    else:
        text = (
            f"📋 <b>Шаблоны</b> ({len(templates)})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for t in templates:
            preview = t.text[:50] + "..." if len(t.text) > 50 else t.text
            text += f"📝 <b>{t.name}</b>\n  <i>{preview}</i>\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━"
        await safe_edit(callback.message, text, reply_markup=templates_list_kb(templates))
    await callback.answer()


@router.callback_query(F.data.startswith("templates_page_"))
async def callback_templates_page(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        templates = await get_user_templates(db, callback.from_user.id)

    if not templates:
        await safe_edit(
            callback.message,
            "📋 <b>Шаблоны</b>\n\n📭 У вас нет шаблонов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать", callback_data="template_create")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
            ]),
        )
    else:
        text = f"📋 <b>Шаблоны</b> ({len(templates)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for t in templates:
            preview = t.text[:50] + "..." if len(t.text) > 50 else t.text
            text += f"📝 <b>{t.name}</b>\n  <i>{preview}</i>\n\n"
        await safe_edit(callback.message, text, reply_markup=templates_list_kb(templates, page=page))
    await callback.answer()


@router.callback_query(F.data == "template_create")
async def callback_template_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TemplateState.waiting_name)
    await safe_edit(
        callback.message,
        "➕ <b>Создание шаблона</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 Введите название шаблона:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(F.text, TemplateState.waiting_name)
async def handle_template_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 100:
        await message.answer("⚠️ Название должно быть от 1 до 100 символов.")
        return
    await state.update_data(template_name=name)
    await state.set_state(TemplateState.waiting_text)
    await message.answer(
        "📝 Введите текст шаблона:\n\n"
        "Можно использовать HTML-разметку.",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )


@router.message(F.text, TemplateState.waiting_text)
async def handle_template_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Текст не может быть пустым.")
        return
    data = await state.get_data()
    name = data.get("template_name", "Без названия")

    async with async_session_factory() as db:
        await add_template(db, message.from_user.id, name, text)

    await state.clear()
    await message.answer(
        f"✅ Шаблон <b>{name}</b> создан!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=back_to_menu_kb(), parse_mode="HTML",
    )
    log.info("User %d создал шаблон: %s", message.from_user.id, name)


@router.callback_query(F.data.startswith("template_view_"))
async def callback_template_view(callback: CallbackQuery):
    template_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        templates = await get_user_templates(db, callback.from_user.id)
    t = next((x for x in templates if x.id == template_id), None)
    if not t:
        await callback.answer("Шаблон не найден", show_alert=True)
        return
    text = (
        f"📝 <b>{t.name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<code>{t.text}</code>"
    )
    await safe_edit(callback.message, text, reply_markup=template_detail_kb(template_id))
    await callback.answer()


@router.callback_query(F.data.startswith("template_confirm_delete_"))
async def callback_template_confirm_delete(callback: CallbackQuery):
    template_id = int(callback.data.split("_")[-1])
    text = (
        f"⚠️ <b>Удалить шаблон?</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Это действие необратимо."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"template_delete_{template_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_templates")],
    ])
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("template_delete_"))
async def callback_template_delete(callback: CallbackQuery):
    template_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        await delete_template(db, template_id)
    await safe_edit(
        callback.message,
        "🗑 <b>Шаблон удалён!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()
