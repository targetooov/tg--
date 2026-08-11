from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import config
from core.database import (
    async_session_factory,
    create_invite_code,
    get_setting,
    set_setting,
)
from keyboards.admin import admin_panel_kb, admin_invite_kb, admin_settings_kb, cancel_admin_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


class AdminSettingsState(StatesGroup):
    set_channel_id = State()
    set_channel_url = State()
    set_signature = State()
    set_delays_min = State()
    set_delays_max = State()
    gen_invite_code = State()


def _is_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "admin_invite")
async def callback_admin_invite(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await safe_edit(
        callback.message,
        "🎫 <b>Инвайт-коды</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Генерируйте коды для получения подписки.",
        reply_markup=admin_invite_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_invite_gen")
async def callback_invite_gen(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.set_state(AdminSettingsState.gen_invite_code)
    await safe_edit(
        callback.message,
        "🎫 <b>Генерация инвайт-кода</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте план и кол-во использований:\n"
        "<code>basic 5</code> — 5 использований плана Basic\n"
        "<code>pro 1</code> — 1 использование плана Pro",
        reply_markup=cancel_admin_kb(),
    )
    await callback.answer()


@router.message(F.text, AdminSettingsState.gen_invite_code)
async def handle_invite_gen(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("⚠️ Формат: <code>plan count</code>\nНапример: <code>basic 5</code>", parse_mode="HTML")
        return

    plan = parts[0].lower()
    try:
        count = int(parts[1])
    except ValueError:
        await message.answer("⚠️ Количество должно быть числом.")
        return

    if plan not in ("basic", "pro", "trial"):
        await message.answer("⚠️ Доступные планы: basic, pro, trial")
        return

    async with async_session_factory() as db:
        codes = []
        for _ in range(min(count, 20)):
            inv = await create_invite_code(db, created_by=message.from_user.id, plan=plan)
            codes.append(inv.code)

    await state.clear()
    codes_text = "\n".join(f"  <code>{c}</code>" for c in codes)
    await message.answer(
        f"✅ <b>Создано {len(codes)} инвайт-кодов:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n{codes_text}",
        reply_markup=admin_panel_kb(),
        parse_mode="HTML",
    )
    log.info("Admin создал %d инвайт-кодов плана %s", len(codes), plan)


@router.callback_query(F.data == "admin_settings")
async def callback_admin_settings(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    ch_id = await _get_cfg("channel_id", str(config.CHANNEL_ID))
    ch_url = await _get_cfg("channel_url", config.CHANNEL_URL)
    sig = await _get_cfg("bot_advertisement", config.BOT_ADVERTISEMENT)
    d_min = await _get_cfg("broadcast_delay_min", str(config.BROADCAST_DELAY_MIN))
    d_max = await _get_cfg("broadcast_delay_max", str(config.BROADCAST_DELAY_MAX))

    text = (
        f"⚙️ <b>Настройки бота</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📢 Канал: <code>{ch_id}</code>\n"
        f"🔗 URL: {ch_url}\n"
        f"✍️ Подпись: {sig}\n"
        f"⏱ Задержка: {d_min}-{d_max} сек\n"
        f"🎁 Trial: {config.TRIAL_DURATION_DAYS} дн.\n"
        f"👥 Реферал: +{config.REF_REWARD_DAYS} дн.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_edit(callback.message, text, reply_markup=admin_settings_kb())
    await callback.answer()


# ──── ADMIN SET CHANNEL ────

@router.callback_query(F.data == "admin_set_channel")
async def callback_admin_set_channel(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.set_state(AdminSettingsState.set_channel_id)
    await safe_edit(
        callback.message,
        "📢 <b>Настройка канала</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте ID канала (число):\n"
        "Например: <code>-1001234567890</code>",
        reply_markup=cancel_admin_kb(),
    )
    await callback.answer()


@router.message(F.text, AdminSettingsState.set_channel_id)
async def handle_set_channel_id(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text.lstrip("-").isdigit():
        await message.answer("⚠️ ID канала должен быть числом.")
        return
    await state.update_data(new_channel_id=text)
    await state.set_state(AdminSettingsState.set_channel_url)
    await message.answer(
        f"📢 Канал ID: <code>{text}</code>\n\n"
        "Отправьте URL канала:\n"
        "Например: <code>https://t.me/channel_name</code>",
        reply_markup=cancel_admin_kb(),
        parse_mode="HTML",
    )


@router.message(F.text, AdminSettingsState.set_channel_url)
async def handle_set_channel_url(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    url = message.text.strip()
    if not url.startswith("http") and not url.startswith("t.me/"):
        await message.answer("⚠️ Отправьте корректную ссылку.")
        return
    data = await state.get_data()
    ch_id = data.get("new_channel_id", "")

    async with async_session_factory() as db:
        await set_setting(db, "channel_id", ch_id)
        await set_setting(db, "channel_url", url)

    await state.clear()
    await message.answer(
        f"✅ <b>Канал обновлён!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📢 ID: <code>{ch_id}</code>\n"
        f"🔗 URL: {url}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Перезапустите бота для применения.",
        reply_markup=admin_panel_kb(),
        parse_mode="HTML",
    )
    log.info("Admin: канал обновлён — ID=%s URL=%s", ch_id, url)


# ──── ADMIN SET SIGNATURE ────

@router.callback_query(F.data == "admin_set_signature")
async def callback_admin_set_signature(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    current = await _get_cfg("bot_advertisement", config.BOT_ADVERTISEMENT)
    await state.set_state(AdminSettingsState.set_signature)
    await safe_edit(
        callback.message,
        "✍️ <b>Подпись по умолчанию</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Текущая: <code>{current}</code>\n\n"
        "Отправьте новую подпись.\n"
        "Для удаления отправьте <code>-</code>",
        reply_markup=cancel_admin_kb(),
    )
    await callback.answer()


@router.message(F.text, AdminSettingsState.set_signature)
async def handle_set_signature(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    sig = message.text.strip()
    if sig == "-":
        sig = ""

    async with async_session_factory() as db:
        await set_setting(db, "bot_advertisement", sig)

    await state.clear()
    display = sig if sig else "Удалена"
    await message.answer(
        f"✅ <b>Подпись обновлена!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✍️ Новая: <code>{display}</code>",
        reply_markup=admin_panel_kb(),
        parse_mode="HTML",
    )
    log.info("Admin: подпись обновлена — %s", sig[:50])


# ──── ADMIN SET DELAYS ────

@router.callback_query(F.data == "admin_set_delays")
async def callback_admin_set_delays(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.set_state(AdminSettingsState.set_delays_min)
    await safe_edit(
        callback.message,
        "⏱ <b>Задержки рассылки</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте минимальную задержку (в секундах):",
        reply_markup=cancel_admin_kb(),
    )
    await callback.answer()


@router.message(F.text, AdminSettingsState.set_delays_min)
async def handle_set_delays_min(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    text = message.text.strip()
    try:
        val = float(text)
        if val < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Отправьте положительное число.")
        return
    await state.update_data(new_delay_min=text)
    await state.set_state(AdminSettingsState.set_delays_max)
    await message.answer(
        f"⏱ Мин: <code>{text}</code> сек\n\n"
        "Отправьте максимальную задержку (в секундах):",
        reply_markup=cancel_admin_kb(),
        parse_mode="HTML",
    )


@router.message(F.text, AdminSettingsState.set_delays_max)
async def handle_set_delays_max(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    text = message.text.strip()
    try:
        val = float(text)
        if val < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Отправьте положительное число.")
        return

    data = await state.get_data()
    d_min = data.get("new_delay_min", "3")

    async with async_session_factory() as db:
        await set_setting(db, "broadcast_delay_min", d_min)
        await set_setting(db, "broadcast_delay_max", text)

    await state.clear()
    await message.answer(
        f"✅ <b>Задержки обновлены!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱ Мин: <code>{d_min}</code> сек\n"
        f"⏱ Макс: <code>{text}</code> сек",
        reply_markup=admin_panel_kb(),
        parse_mode="HTML",
    )
    log.info("Admin: задержки обновлены — %s-%s", d_min, text)


async def _get_cfg(key: str, default: str) -> str:
    async with async_session_factory() as db:
        val = await get_setting(db, key)
    return val if val is not None else default
