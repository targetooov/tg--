from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.database import (
    async_session_factory,
    add_auto_reply_rule,
    get_user_auto_reply_rules,
    toggle_auto_reply_rule,
    delete_auto_reply_rule,
)
from keyboards.main_menu import back_to_menu_kb, cancel_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class AutoReplyState(StatesGroup):
    waiting_keyword = State()
    waiting_response = State()


def _rules_list_text(rules: list) -> str:
    if not rules:
        return (
            "🤖 <b>Авто-ответы</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 У вас нет правил.\n"
            "Создайте правило для автоматических ответов на ключевые слова."
        )
    text = (
        f"🤖 <b>Авто-ответы</b> ({len(rules)})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    for r in rules:
        status = "🟢" if r.is_active else "🔴"
        kw = r.keyword[:30]
        resp_preview = r.response_text[:40] + "..." if len(r.response_text) > 40 else r.response_text
        text += f"{status} <b>{kw}</b>\n    → <i>{resp_preview}</i>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━"
    return text


def _rules_list_kb(rules: list) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for r in rules[:15]:
        status = "🟢" if r.is_active else "🔴"
        kw = r.keyword[:25]
        buttons.append([
            InlineKeyboardButton(text=f"{status} {kw}", callback_data=f"autoreply_view_{r.id}")
        ])
    buttons.append([InlineKeyboardButton(text="➕ Создать правило", callback_data="autoreply_create")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "menu_auto_reply")
async def callback_auto_reply(callback: CallbackQuery):
    async with async_session_factory() as db:
        rules = await get_user_auto_reply_rules(db, callback.from_user.id)
    await safe_edit(callback.message, _rules_list_text(rules), reply_markup=_rules_list_kb(rules))
    await callback.answer()


@router.callback_query(F.data == "autoreply_create")
async def callback_autoreply_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AutoReplyState.waiting_keyword)
    await safe_edit(
        callback.message,
        "➕ <b>Новое правило</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введите ключевое слово (или фразу),\n"
        "на которое бот будет отвечать:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(F.text, AutoReplyState.waiting_keyword)
async def handle_keyword(message: Message, state: FSMContext):
    keyword = message.text.strip()
    if not keyword or len(keyword) > 256:
        await message.answer("⚠️ Ключевое слово: 1-256 символов.")
        return
    await state.update_data(ar_keyword=keyword)
    await state.set_state(AutoReplyState.waiting_response)
    await message.answer(
        f"🔑 Ключевое слово: <code>{keyword}</code>\n\n"
        "📝 Введите текст ответа:",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )


@router.message(F.text, AutoReplyState.waiting_response)
async def handle_response(message: Message, state: FSMContext):
    response = message.text.strip()
    if not response:
        await message.answer("⚠️ Текст ответа не может быть пустым.")
        return
    data = await state.get_data()
    keyword = data.get("ar_keyword", "")

    async with async_session_factory() as db:
        await add_auto_reply_rule(db, message.from_user.id, keyword, response)

    await state.clear()
    await message.answer(
        f"✅ <b>Правило создано!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 Ключевое слово: <code>{keyword}</code>\n"
        f"📝 Ответ: <code>{response[:100]}</code>",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    log.info("User %d: создал autoreply правило '%s'", message.from_user.id, keyword)


@router.callback_query(F.data.startswith("autoreply_view_"))
async def callback_autoreply_view(callback: CallbackQuery):
    rule_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        rules = await get_user_auto_reply_rules(db, callback.from_user.id)
    rule = next((r for r in rules if r.id == rule_id), None)
    if not rule:
        await callback.answer("Правило не найдено", show_alert=True)
        return

    status = "🟢 Включено" if rule.is_active else "🔴 Выключено"
    text = (
        f"🤖 <b>Правило #{rule.id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 Ключевое слово: <code>{rule.keyword}</code>\n"
        f"📝 Ответ:\n<code>{rule.response_text}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Статус: {status}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔴 Выключить" if rule.is_active else "🟢 Включить",
                callback_data=f"autoreply_toggle_{rule.id}",
            )
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"autoreply_delete_{rule.id}")
        ],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="menu_auto_reply")],
    ])
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("autoreply_toggle_"))
async def callback_autoreply_toggle(callback: CallbackQuery):
    rule_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        await toggle_auto_reply_rule(db, rule_id)
    await callback.answer("✅ Статус изменён", show_alert=True)
    async with async_session_factory() as db:
        rules = await get_user_auto_reply_rules(db, callback.from_user.id)
    rule = next((r for r in rules if r.id == rule_id), None)
    if rule:
        status = "🟢 Включено" if rule.is_active else "🔴 Выключено"
        text = (
            f"🤖 <b>Правило #{rule.id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 Ключевое слово: <code>{rule.keyword}</code>\n"
            f"📝 Ответ:\n<code>{rule.response_text}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Статус: {status}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔴 Выключить" if rule.is_active else "🟢 Включить",
                    callback_data=f"autoreply_toggle_{rule.id}",
                )
            ],
            [
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"autoreply_delete_{rule.id}")
            ],
            [InlineKeyboardButton(text="🔙 К списку", callback_data="menu_auto_reply")],
        ])
        await safe_edit(callback.message, text, reply_markup=kb)


@router.callback_query(F.data.startswith("autoreply_delete_"))
async def callback_autoreply_delete(callback: CallbackQuery):
    rule_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        await delete_auto_reply_rule(db, rule_id)
    await callback.answer("🗑 Правило удалено", show_alert=True)
    async with async_session_factory() as db:
        rules = await get_user_auto_reply_rules(db, callback.from_user.id)
    await safe_edit(callback.message, _rules_list_text(rules), reply_markup=_rules_list_kb(rules))
