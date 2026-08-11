from __future__ import annotations

import asyncio
import random
from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import config
from core.database import (
    async_session_factory,
    get_valid_accounts,
    create_admin_task,
    update_admin_task,
)
from keyboards.admin_tools import tool_confirm_kb, tool_back_kb
from core.logger import log
from core.utils import is_admin as _is_admin

router = Router()


class NeuroCommentState(StatesGroup):
    waiting_channel = State()
    waiting_prompt = State()
    confirming = State()


SAMPLE_COMMENTS = [
    "Отличный пост! 🔥",
    "Согласен на 100%",
    "Интересная мысль, спасибо!",
    "Контент на высоте 👍",
    "Полезная информация, сохраню",
    "Всегда рад видеть такие посты",
    "Хорошая тема для обсуждения",
    "Добавлю в избранное ⭐",
    "Жду продолжения!",
    "Очень актуально, спасибо автору",
    "Класс, подписался!",
    "Наконец-то нормальный контент",
    "Пост гуд, лайк поставил",
    "Так держать! 💪",
    "Мне понравилось, рекомендую",
]


@router.callback_query(F.data == "tool_neuro_comment")
async def callback_neuro_comment(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.set_state(NeuroCommentState.waiting_channel)
    await callback.message.edit_text(
        "🧠 <b>AI-комментарии</b>\n\n"
        "Генерация AI-комментариев к постам в канале.\n\n"
        "Отправьте ссылку на канал:\n"
        "• <code>@channel_name</code>\n"
        "• <code>https://t.me/channel_name</code>",
        reply_markup=tool_back_kb(), parse_mode="HTML",
    )
    await callback.answer()


@router.message(F.text, NeuroCommentState.waiting_channel)
async def handle_neuro_channel(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    channel = message.text.strip()
    channel = channel.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "")
    if not channel.startswith("@") and not channel.startswith("-"):
        channel = f"@{channel}"

    await state.update_data(nc_channel=channel)
    await state.set_state(NeuroCommentState.waiting_prompt)
    await message.answer(
        f"🧠 Канал: <code>{channel}</code>\n\n"
        "📝 Введите тему/стиль комментариев (или «стандарт»):\n"
        "Например: «Восторженные комментарии про крипту»\n"
        "«Юмористические комментарии»\n"
        "«Серьёзные экспертные отзывы»",
        reply_markup=tool_back_kb(), parse_mode="HTML",
    )


@router.message(F.text, NeuroCommentState.waiting_prompt)
async def handle_neuro_prompt(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    prompt = message.text.strip()

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)

    if not accounts:
        await message.answer("❌ Нет аккаунтов.", reply_markup=tool_back_kb())
        await state.clear()
        return

    await state.update_data(nc_prompt=prompt)
    await state.set_state(NeuroCommentState.confirming)

    text = (
        f"🧠 <b>Подтверждение AI-комментариев</b>\n\n"
        f"📡 Канал: <code>{message.text}</code>\n"
        f"📝 Стиль: {prompt}\n"
        f"🟢 Аккаунтов: <b>{len(accounts)}</b>\n\n"
        f"Запустить?"
    )
    await message.answer(text, reply_markup=tool_confirm_kb("neuro_comment"), parse_mode="HTML")


@router.callback_query(F.data == "tool_confirm_neuro_comment", NeuroCommentState.confirming)
async def callback_confirm_neuro_comment(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    channel = data.get("nc_channel", "")
    prompt = data.get("nc_prompt", "стандарт")

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)
        task = await create_admin_task(db, "neuro_comment", {
            "channel": channel, "prompt": prompt,
        }, total=len(accounts) * 3)

    await state.clear()
    await callback.message.edit_text(
        f"🧠 <b>AI-комментарии запущены!</b>\n\n🆔 Задача: #{task.id}",
        reply_markup=tool_back_kb(), parse_mode="HTML",
    )

    asyncio.create_task(_run_neuro_comment(task.id, channel, prompt))
    log.info("Admin: запущены AI-комментарии #%d", task.id)
    await callback.answer()


async def _generate_comment(prompt: str) -> str:
    if prompt.lower() == "стандарт":
        return random.choice(SAMPLE_COMMENTS)

    try:
        import openai
        client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты — пользователь Telegram. Напиши короткий комментарий (1-2 предложения) к посту в канале. Будь естественным, используй эмодзи."},
                {"role": "user", "content": f"Напиши комментарий в стиле: {prompt}"}
            ],
            max_tokens=100,
            temperature=0.9,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return random.choice(SAMPLE_COMMENTS)


async def _run_neuro_comment(task_id: int, channel: str, prompt: str):
    from telethon import TelegramClient

    async with async_session_factory() as db:
        accounts = await get_valid_accounts(db)
        await update_admin_task(db, task_id, status="running")

    total_done = 0
    total_errors = 0
    error_log = []

    for account in accounts:
        session_stem = Path(account.session_path).with_suffix("")
        client = TelegramClient(str(session_stem), config.API_ID, config.API_HASH)

        try:
            await client.connect()
            if not await client.is_user_authorized():
                continue

            try:
                entity = await client.get_entity(channel)
            except Exception as e:
                total_errors += 1
                error_log.append(f"{channel}: {e}")
                break

            try:
                messages = await client.get_messages(entity, limit=5)
            except Exception as e:
                total_errors += 1
                error_log.append(f"Получение постов: {type(e).__name__}")
                continue

            for msg in messages:
                if not msg.message:
                    continue
                try:
                    comment = await _generate_comment(prompt)
                    await client.send_message(entity, comment, comment_to=msg.id)
                    total_done += 1
                except Exception as e:
                    total_errors += 1
                    error_log.append(f"Комментарий #{msg.id}: {type(e).__name__}")

                await asyncio.sleep(random.uniform(10, 30))

        except Exception as e:
            total_errors += 1
            error_log.append(f"Ошибка: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async with async_session_factory() as db:
        await update_admin_task(db, task_id, status="done", done=total_done, errors=total_errors, error_log=error_log[:50])

    log.info("AI-комментарии #%d завершены: done=%d errors=%d", task_id, total_done, total_errors)
