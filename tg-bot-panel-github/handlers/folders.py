from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.database import (
    async_session_factory,
    add_target_folder,
    get_user_folders,
    get_folder_by_id,
    update_target_folder,
    delete_target_folder,
)
from keyboards.folders import folders_list_kb, folder_detail_kb, folder_confirm_delete_kb
from keyboards.main_menu import back_to_menu_kb, cancel_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class FolderState(StatesGroup):
    waiting_name = State()
    waiting_targets = State()
    renaming = State()
    editing_targets = State()


@router.callback_query(F.data == "menu_folders")
async def callback_folders(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    async with async_session_factory() as db:
        folders = await get_user_folders(db, callback.from_user.id)

    if not folders:
        text = (
            "📂 <b>Папки целей</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 У вас нет папок.\n"
            "Создайте папку для сохранения списков целей."
        )
    else:
        text = (
            f"📂 <b>Папки целей</b> ({len(folders)})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for f in folders:
            targets = f.get_targets()
            text += f"  📂 <b>{f.name}</b> — {len(targets)} целей\n"
        text += "\n━━━━━━━━━━━━━━━━━━━━━━"

    await safe_edit(callback.message, text, reply_markup=folders_list_kb(folders))
    await callback.answer()


@router.callback_query(F.data == "folder_create")
async def callback_folder_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FolderState.waiting_name)
    await safe_edit(
        callback.message,
        "➕ <b>Новая папка</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 Введите название папки:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(F.text, FolderState.waiting_name)
async def handle_folder_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 128:
        await message.answer("⚠️ Название: 1-128 символов.")
        return
    await state.update_data(folder_name=name)
    await state.set_state(FolderState.waiting_targets)
    await message.answer(
        f"📂 Папка: <b>{name}</b>\n\n"
        "📋 Введите список целей (каждый с новой строки):\n"
        "• <code>@username</code>\n"
        "• <code>-1001234567890</code>\n"
        "• <code>https://t.me/username</code>",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )


@router.message(F.text, FolderState.waiting_targets)
async def handle_folder_targets(message: Message, state: FSMContext):
    raw = message.text.strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        await message.answer("⚠️ Список пуст.")
        return

    targets = []
    for line in lines:
        line = line.replace("https://t.me/", "").replace("http://t.me/", "")
        line = line.replace("t.me/", "")
        if not line:
            continue
        if not line.startswith("@") and not line.startswith("-"):
            if line.isdigit():
                line = f"-100{line}"
            elif line.lstrip("-").isdigit():
                pass
            else:
                line = f"@{line}"
        targets.append(line)

    data = await state.get_data()
    name = data.get("folder_name", "Без названия")

    async with async_session_factory() as db:
        folder = await add_target_folder(db, message.from_user.id, name, targets)

    await state.clear()
    await message.answer(
        f"✅ <b>Папка создана!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📂 Название: <b>{name}</b>\n"
        f"🎯 Целей: <b>{len(targets)}</b>",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    log.info("User %d: создал папку '%s' (%d целей)", message.from_user.id, name, len(targets))


@router.callback_query(F.data.startswith("folder_view_"))
async def callback_folder_view(callback: CallbackQuery):
    folder_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        folder = await get_folder_by_id(db, folder_id)
    if not folder or folder.user_id != callback.from_user.id:
        await callback.answer("Папка не найдена", show_alert=True)
        return

    targets = folder.get_targets()
    text = (
        f"📂 <b>{folder.name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 Целей: <b>{len(targets)}</b>\n\n"
    )
    for t in targets[:20]:
        text += f"  • <code>{t}</code>\n"
    if len(targets) > 20:
        text += f"  ... и ещё {len(targets) - 20}\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━"

    await safe_edit(callback.message, text, reply_markup=folder_detail_kb(folder_id))
    await callback.answer()


@router.callback_query(F.data.startswith("folder_rename_"))
async def callback_folder_rename(callback: CallbackQuery, state: FSMContext):
    folder_id = int(callback.data.split("_")[-1])
    await state.update_data(rename_folder_id=folder_id)
    await state.set_state(FolderState.renaming)
    await safe_edit(
        callback.message,
        "✏️ <b>Переименовать папку</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 Введите новое название:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(F.text, FolderState.renaming)
async def handle_folder_rename(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 128:
        await message.answer("⚠️ Название: 1-128 символов.")
        return
    data = await state.get_data()
    folder_id = data.get("rename_folder_id", 0)

    async with async_session_factory() as db:
        await update_target_folder(db, folder_id, name=name)

    await state.clear()
    await message.answer(
        f"✅ Папка переименована в <b>{name}</b>",
        reply_markup=back_to_menu_kb(), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("folder_edit_targets_"))
async def callback_folder_edit_targets(callback: CallbackQuery, state: FSMContext):
    folder_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_folder_id=folder_id)
    await state.set_state(FolderState.editing_targets)
    await safe_edit(
        callback.message,
        "📝 <b>Изменить цели папки</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте новый список целей (каждый с новой строки):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(F.text, FolderState.editing_targets)
async def handle_folder_edit_targets(message: Message, state: FSMContext):
    raw = message.text.strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        await message.answer("⚠️ Список пуст.")
        return

    targets = []
    for line in lines:
        line = line.replace("https://t.me/", "").replace("http://t.me/", "")
        line = line.replace("t.me/", "")
        if not line:
            continue
        if not line.startswith("@") and not line.startswith("-"):
            if line.isdigit():
                line = f"-100{line}"
            elif line.lstrip("-").isdigit():
                pass
            else:
                line = f"@{line}"
        targets.append(line)

    data = await state.get_data()
    folder_id = data.get("edit_folder_id", 0)

    async with async_session_factory() as db:
        await update_target_folder(db, folder_id, targets=targets)

    await state.clear()
    await message.answer(
        f"✅ Цели обновлены! ({len(targets)} целей)",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("folder_delete_"))
async def callback_folder_delete(callback: CallbackQuery):
    folder_id = int(callback.data.split("_")[-1])
    await safe_edit(
        callback.message,
        "⚠️ <b>Удалить папку?</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Это действие необратимо.",
        reply_markup=folder_confirm_delete_kb(folder_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("folder_confirm_delete_"))
async def callback_folder_confirm_delete(callback: CallbackQuery):
    folder_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        await delete_target_folder(db, folder_id)
    await callback.answer("🗑 Папка удалена", show_alert=True)
    async with async_session_factory() as db:
        folders = await get_user_folders(db, callback.from_user.id)
    if not folders:
        await safe_edit(
            callback.message,
            "📂 <b>Папки целей</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 У вас нет папок.",
            reply_markup=folders_list_kb(folders),
        )
    else:
        text = (
            f"📂 <b>Папки целей</b> ({len(folders)})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for f in folders:
            targets = f.get_targets()
            text += f"  📂 <b>{f.name}</b> — {len(targets)} целей\n"
        text += "\n━━━━━━━━━━━━━━━━━━━━━━"
        await safe_edit(callback.message, text, reply_markup=folders_list_kb(folders))
