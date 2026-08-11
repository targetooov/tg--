from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.database import (
    async_session_factory,
    add_account,
    get_account_by_session_path,
)
from core.logger import log
from keyboards.main_menu import back_to_menu_kb, cancel_kb, sessions_kb
from workers.session_manager import validate_session_file, save_session_file
from core.utils import safe_edit

router = Router()


class UploadSessionState(StatesGroup):
    waiting_for_file = State()


@router.callback_query(F.data == "menu_sessions")
async def callback_sessions_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(
        callback.message,
        "📁 <b>Сессии</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите действие:",
        reply_markup=sessions_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu_upload_sessions")
async def callback_upload_sessions(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UploadSessionState.waiting_for_file)
    await safe_edit(
        callback.message,
        "📁 <b>Загрузка сессий</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте файлы <code>.session</code>\n"
        "Можно загрузить несколько файлов за раз.\n\n"
        "Каждая сессия будет проверена на валидность.\n"
        "Для отмены нажмите «Назад».",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(StateFilter(UploadSessionState.waiting_for_file), F.document)
async def handle_session_file(message: Message, state: FSMContext):
    document = message.document
    if not document or not document.file_name:
        await message.answer("❌ Отправьте файл с расширением .session")
        return

    if not document.file_name.endswith(".session"):
        await message.answer(
            f"❌ Файл <code>{document.file_name}</code> не является сессией.\n"
            "Нужен файл <code>.session</code>",
            parse_mode="HTML",
        )
        return

    status_msg = await message.answer(
        f"⏳ Загружаю и проверяю <code>{document.file_name}</code>...",
        parse_mode="HTML",
    )

    try:
        file = await message.bot.download(document)
        file_content = file.read()
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка загрузки: {e}")
        return

    saved_path = await save_session_file(file_content, document.file_name)
    session_info = await validate_session_file(saved_path)

    if session_info.is_valid:
        async with async_session_factory() as db:
            existing = await get_account_by_session_path(db, session_info.session_path)
            if existing:
                await status_msg.edit_text(
                    f"⚠️ Сессия <code>{document.file_name}</code> уже загружена.",
                    parse_mode="HTML",
                )
                return
            await add_account(
                db,
                user_id=message.from_user.id,
                session_path=session_info.session_path,
                phone=session_info.phone,
                username=session_info.username,
                first_name=session_info.first_name,
                is_valid=True,
            )
        name = session_info.username or session_info.first_name or session_info.phone
        await status_msg.edit_text(
            f"✅ <b>Сессия принята!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📁 <code>{document.file_name}</code>\n"
            f"👤 <b>{name}</b>\n"
            f"🆔 <code>{session_info.user_id}</code>",
            parse_mode="HTML",
        )
        log.info("User %d загрузил сессию: %s (%s)", message.from_user.id, document.file_name, name)
    else:
        from workers.session_manager import delete_session_file
        await delete_session_file(session_info.session_path)
        await status_msg.edit_text(
            f"❌ <b>Сессия невалидна!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📁 <code>{document.file_name}</code>\n"
            f"📝 {session_info.error}",
            parse_mode="HTML",
        )


@router.message(StateFilter(UploadSessionState.waiting_for_file))
async def handle_not_document(message: Message):
    await message.answer(
        "⚠️ Отправьте файл <code>.session</code> или нажмите «Отмена»",
        parse_mode="HTML",
    )
