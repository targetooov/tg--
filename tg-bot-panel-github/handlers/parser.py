from __future__ import annotations

import asyncio

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import config
from core.database import (
    async_session_factory,
    get_valid_accounts,
    add_parsed_member,
    get_user_parsed_members,
    count_user_parsed_members,
    delete_parsed_members,
)
from keyboards.main_menu import back_to_menu_kb, cancel_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class ParserState(StatesGroup):
    waiting_link = State()
    waiting_account = State()


def _parse_link(raw: str) -> str | None:
    raw = raw.strip()
    raw = raw.replace("https://t.me/", "").replace("http://t.me/", "")
    raw = raw.replace("t.me/", "")
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


@router.callback_query(F.data == "menu_parser")
async def callback_parser(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ParserState.waiting_link)
    async with async_session_factory() as db:
        count = await count_user_parsed_members(db, callback.from_user.id)

    text = (
        f"🔍 <b>Парсинг участников</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 В базе: <b>{count}</b> участников\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        "Отправьте ссылку на канал или группу для парсинга.\n"
        "Форматы:\n"
        "• <code>@channel_name</code>\n"
        "• <code>https://t.me/channel_name</code>\n"
        "• <code>-1001234567890</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои участники", callback_data="parser_list")],
        [InlineKeyboardButton(text="🗑 Очистить базу", callback_data="parser_clear")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
    ])
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "parser_list")
async def callback_parser_list(callback: CallbackQuery):
    async with async_session_factory() as db:
        members = await get_user_parsed_members(db, callback.from_user.id, limit=50)
        total = await count_user_parsed_members(db, callback.from_user.id)

    if not members:
        await safe_edit(
            callback.message,
            "📋 <b>Парсинг</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 База пуста. Отправьте ссылку для парсинга.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_parser")],
            ]),
        )
        await callback.answer()
        return

    sources: dict[str, int] = {}
    for m in members:
        src = m.source_chat or "—"
        sources[src] = sources.get(src, 0) + 1

    text = (
        f"📋 <b>Участники</b> ({total} всего):\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    for src, cnt in sources.items():
        text += f"📂 <code>{src}</code> — {cnt} чел.\n"
    text += "\n━━━━━━━━━━━━━━━━━━━━━━\n<b>Последние 50:</b>\n"
    for m in members[:50]:
        name = m.first_name or ""
        if m.last_name:
            name += f" {m.last_name}"
        name = name.strip() or "—"
        uname = f"@{m.username}" if m.username else "—"
        text += f"• <b>{name}</b> | {uname} | <code>{m.telegram_id or '—'}</code>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Экспорт ID", callback_data="parser_export_ids")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="parser_list")],
    ])
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "parser_export_ids")
async def callback_parser_export_ids(callback: CallbackQuery):
    async with async_session_factory() as db:
        members = await get_user_parsed_members(db, callback.from_user.id, limit=5000)

    if not members:
        await callback.answer("Нет участников", show_alert=True)
        return

    ids = [str(m.telegram_id) for m in members if m.telegram_id]
    text = "\n".join(ids)

    if len(text) > 4000:
        text = text[:4000] + f"\n... и ещё {len(ids) - len(text.splitlines())} ID"

    await safe_edit(
        callback.message,
        f"📋 <b>ID участников</b> ({len(ids)}):\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<code>{text}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="parser_list")],
        ]),
    )
    await callback.answer()


@router.callback_query(F.data == "parser_clear")
async def callback_parser_clear(callback: CallbackQuery):
    async with async_session_factory() as db:
        await delete_parsed_members(db, callback.from_user.id)
    await callback.answer("🗑 База очищена", show_alert=True)
    async with async_session_factory() as db:
        count = await count_user_parsed_members(db, callback.from_user.id)
    await safe_edit(
        callback.message,
        f"🔍 <b>Парсинг участников</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 В базе: <b>{count}</b> участников\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        "Отправьте ссылку на канал или группу:",
        reply_markup=back_to_menu_kb(),
    )


@router.message(F.text, ~F.text.startswith("/"), ParserState.waiting_link)
async def handle_parser_link(message: Message, state: FSMContext):
    raw = message.text.strip()
    chat_id = _parse_link(raw)
    if not chat_id:
        await message.answer(
            "⚠️ Неверный формат. Используйте:\n"
            "• <code>@channel_name</code>\n"
            "• <code>https://t.me/channel_name</code>",
            parse_mode="HTML",
        )
        return

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db, message.from_user.id)

    if not accounts:
        await message.answer(
            "❌ Нет аккаунтов. Загрузите .session файлы через «📁 Сессии».",
            reply_markup=back_to_menu_kb(),
        )
        await state.clear()
        return

    await state.update_data(parser_chat=chat_id)

    if len(accounts) == 1:
        await state.update_data(parser_account_id=accounts[0].id)
        await _start_parsing(message, state, chat_id, accounts[0])
        return

    await state.set_state(ParserState.waiting_account)
    text = "🔑 <b>Выберите аккаунт для парсинга:</b>\n\n"
    buttons: list[list[InlineKeyboardButton]] = []
    for acc in accounts[:10]:
        label = acc.username or acc.first_name or acc.phone or f"#{acc.id}"
        buttons.append([
            InlineKeyboardButton(text=f"🟢 {label}", callback_data=f"parser_acc_{acc.id}")
        ])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="menu_back")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("parser_acc_"))
async def callback_parser_account(callback: CallbackQuery, state: FSMContext):
    account_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    chat_id = data.get("parser_chat", "")
    if not chat_id:
        await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
        return

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db, callback.from_user.id)
    account = next((a for a in accounts if a.id == account_id), None)
    if not account:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return

    await state.update_data(parser_account_id=account_id)
    await callback.message.edit_text("⏳ Парсинг... Подождите.")
    await _start_parsing_callback(callback, state, chat_id, account)


async def _start_parsing(message: Message, state: FSMContext, chat_id: str, account):
    status = await message.answer("⏳ Парсинг... Подождите.")
    await _do_parse(message.from_user.id, chat_id, account, message.bot, status)


async def _start_parsing_callback(callback: CallbackQuery, state: FSMContext, chat_id: str, account):
    await _do_parse(callback.from_user.id, chat_id, account, callback.bot, callback.message)


async def _do_parse(user_id: int, chat_id: str, account, bot, status_msg):
    from telethon import TelegramClient
    from pathlib import Path

    session_stem = Path(account.session_path).with_suffix("")
    client = TelegramClient(str(session_stem), config.API_ID, config.API_HASH)
    parsed = 0
    errors = 0

    try:
        await client.connect()
        if not await client.is_user_authorized():
            await status_msg.edit_text("❌ Аккаунт не авторизован.")
            return

        try:
            entity = await client.get_entity(chat_id)
        except Exception as e:
            await status_msg.edit_text(f"❌ Не удалось найти чат: <code>{e}</code>", parse_mode="HTML")
            return

        try:
            participants = await client.get_participants(entity, limit=50000)
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка парсинга: <code>{e}</code>", parse_mode="HTML")
            return

        async with async_session_factory() as db:
            for user in participants:
                try:
                    await add_parsed_member(
                        db,
                        user_id=user_id,
                        telegram_id=user.id,
                        username=user.username or "",
                        first_name=user.first_name or "",
                        last_name=user.last_name or "",
                        phone=user.phone or "",
                        source_chat=chat_id,
                    )
                    parsed += 1
                except Exception:
                    errors += 1

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML")
        return
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    async with async_session_factory() as db:
        total = await count_user_parsed_members(db, user_id)
    await status_msg.edit_text(
        f"✅ <b>Парсинг завершён!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔍 Распарсено: <b>{parsed}</b>\n"
        f"❌ Ошибок: <b>{errors}</b>\n"
        f"📊 Всего в базе: <b>{total}</b>",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    log.info("User %d: парсинг %s — %d участников", user_id, chat_id, parsed)
