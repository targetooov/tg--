from __future__ import annotations

import zipfile
import io

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.database import async_session_factory, add_account, get_account_by_session_path
from keyboards.main_menu import cancel_kb
from workers.session_manager import validate_session_file, save_session_file
from core.utils import safe_edit
from core.logger import log

router = Router()


class BatchState(StatesGroup):
    waiting_zip = State()


@router.callback_query(F.data == "menu_batch_sessions")
async def callback_batch(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BatchState.waiting_zip)
    await safe_edit(
        callback.message,
        "📦 <b>Пакетная загрузка</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте ZIP-архив с файлами <code>.session</code>\n"
        "Все сессии будут проверены и добавлены.",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(StateFilter(BatchState.waiting_zip), F.document)
async def handle_zip(message: Message, state: FSMContext):
    doc = message.document
    if not doc or not doc.file_name or not doc.file_name.endswith(".zip"):
        await message.answer("❌ Отправьте ZIP-архив.")
        return

    status = await message.answer("⏳ Загружаю архив...")

    try:
        file = await message.bot.download(doc)
        content = file.read()
    except Exception as e:
        await status.edit_text(f"❌ Ошибка загрузки: {e}")
        return

    added = 0
    errors = 0
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            session_files = [n for n in zf.namelist() if n.endswith(".session")]
            for name in session_files:
                data = zf.read(name)
                saved = await save_session_file(data, name)
                info = await validate_session_file(saved)
                if info.is_valid:
                    async with async_session_factory() as db:
                        existing = await get_account_by_session_path(db, info.session_path)
                        if not existing:
                            await add_account(
                                db, user_id=message.from_user.id,
                                session_path=info.session_path,
                                phone=info.phone, username=info.username,
                                first_name=info.first_name, is_valid=True,
                            )
                            added += 1
                        else:
                            errors += 1
                else:
                    from workers.session_manager import delete_session_file
                    await delete_session_file(info.session_path)
                    errors += 1
    except zipfile.BadZipFile:
        await status.edit_text("❌ Это не ZIP-архив.")
        return

    await state.clear()
    await status.edit_text(
        f"✅ <b>Пакетная загрузка завершена</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Добавлено: <b>{added}</b>\n"
        f"❌ Ошибок: <b>{errors}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
    )
    log.info("User %d: пакетная загрузка — %d добавлено, %d ошибок", message.from_user.id, added, errors)
