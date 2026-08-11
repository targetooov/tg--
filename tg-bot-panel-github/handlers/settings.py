from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.database import (
    async_session_factory,
    get_or_create_settings,
    update_signature,
)
from core.utils import safe_edit
from core.logger import log
from keyboards.main_menu import settings_menu_kb, back_to_menu_kb

router = Router()


class SettingsState(StatesGroup):
    editing_signature = State()


@router.callback_query(F.data == "menu_settings")
async def callback_settings(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    async with async_session_factory() as db_session:
        settings = await get_or_create_settings(
            db_session, callback.from_user.id
        )

    sig = settings.signature_text or "Не задана"
    await safe_edit(
        callback.message,
        f"⚙️ <b>Настройки подписи</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 Текущая подпись:\n<code>{sig}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Подпись автоматически добавляется к каждому сообщению при рассылке.",
        reply_markup=settings_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings_edit_signature")
async def callback_edit_signature(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsState.editing_signature)
    await safe_edit(
        callback.message,
        "✏️ <b>Изменение подписи</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте новый текст подписи.\n"
        "Подпись будет добавляться в конце каждого сообщения.\n\n"
        "Чтобы убрать подпись, отправьте <code>-</code>\n"
        "Для отмены нажмите «Назад».",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.message(F.text, SettingsState.editing_signature)
async def handle_new_signature(message: Message, state: FSMContext):
    text = message.text.strip()

    if text == "-":
        new_sig = ""
    else:
        new_sig = text

    async with async_session_factory() as db_session:
        await update_signature(
            db_session, message.from_user.id, new_sig
        )

    await state.clear()

    display = new_sig if new_sig else "Удалена"
    await message.answer(
        f"✅ <b>Подпись обновлена!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 Новая подпись: <code>{display}</code>",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    log.info(
        "User %d обновил подпись: %s",
        message.from_user.id,
        new_sig[:50],
    )
