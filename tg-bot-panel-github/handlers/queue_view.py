from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.database import (
    async_session_factory,
    get_user_tasks,
    get_task_by_id,
    get_broadcast_results_by_task,
    update_task_status,
)
from keyboards.main_menu import queue_list_kb, task_detail_kb, back_to_menu_kb
from core.utils import safe_edit
from core.logger import log

router = Router()


@router.callback_query(F.data == "menu_queue")
async def callback_queue(callback: CallbackQuery):
    async with async_session_factory() as db:
        tasks = await get_user_tasks(db, callback.from_user.id, limit=20)

    pending = [t for t in tasks if t.status in ("pending", "running")]
    done = [t for t in tasks if t.status == "done"]
    errors = [t for t in tasks if t.status == "error"]

    text = (
        f"⏰ <b>Очередь рассылок</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ В очереди: <b>{len(pending)}</b>\n"
        f"✅ Выполнено: <b>{len(done)}</b>\n"
        f"❌ Ошибки: <b>{len(errors)}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    if tasks:
        text += "<b>Последние задачи:</b>\n"
        for t in tasks[:10]:
            icon = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}.get(t.status, "❓")
            text += f"  {icon} #{t.id} — {t.status} ({len(t.get_targets())} целей)\n"
    else:
        text += "Пока нет задач."

    await safe_edit(callback.message, text, reply_markup=queue_list_kb(tasks))
    await callback.answer()


@router.callback_query(F.data.startswith("task_view_"))
async def callback_task_view(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        task = await get_task_by_id(db, task_id)
        if not task or task.user_id != callback.from_user.id:
            await callback.answer("Задача не найдена", show_alert=True)
            return
        results = await get_broadcast_results_by_task(db, task_id)

    targets = task.get_targets()
    status_icon = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}.get(task.status, "❓")
    display_text = task.text[:300] + "..." if len(task.text) > 300 else task.text

    text = (
        f"{status_icon} <b>Задача #{task.id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Статус: <b>{task.status}</b>\n"
        f"🎯 Целей: <b>{len(targets)}</b>\n"
        f"📅 Создана: {task.created_at.strftime('%d.%m.%Y %H:%M') if task.created_at else '—'}\n"
    )
    if task.finished_at:
        text += f"✅ Завершена: {task.finished_at.strftime('%d.%m.%Y %H:%M')}\n"

    text += f"\n<b>Текст:</b>\n<code>{display_text}</code>\n"

    if results:
        text += "\n━━━━━━━━━━━━━━━━━━━━━━\n<b>Результаты по аккаунтам:</b>\n"
        total_sent = 0
        total_errors = 0
        for r in results:
            text += f"  📨 Отправлено: <b>{r.sent_count}</b> | ❌ Ошибок: <b>{r.error_count}</b>\n"
            total_sent += r.sent_count
            total_errors += r.error_count
            if r.errors and r.errors != "[]":
                import json
                try:
                    err_list = json.loads(r.errors)
                    for err in err_list[:5]:
                        text += f"    ⚠️ {err}\n"
                except Exception:
                    pass
        text += f"\n━━━━━━━━━━━━━━━━━━━━━━\n<b>Итого:</b> 📨 {total_sent} | ❌ {total_errors}\n"

    if targets:
        text += "\n<b>Цели:</b>\n"
        for t in targets[:15]:
            text += f"  • <code>{t}</code>\n"
        if len(targets) > 15:
            text += f"  ... и ещё {len(targets) - 15}\n"

    is_running = task.status in ("pending", "running")
    await safe_edit(callback.message, text, reply_markup=task_detail_kb(task_id, is_running))
    await callback.answer()


@router.callback_query(F.data.startswith("task_cancel_"))
async def callback_task_cancel(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[-1])
    async with async_session_factory() as db:
        task = await get_task_by_id(db, task_id)
        if not task or task.user_id != callback.from_user.id:
            await callback.answer("Задача не найдена", show_alert=True)
            return
        if task.status not in ("pending", "running"):
            await callback.answer("Задачу нельзя отменить", show_alert=True)
            return
        await update_task_status(db, task_id, "cancelled")

    await callback.answer("❌ Задача отменена", show_alert=True)
    log.info("User %d: отменил задачу %d", callback.from_user.id, task_id)

    async with async_session_factory() as db:
        task = await get_task_by_id(db, task_id)
        results = await get_broadcast_results_by_task(db, task_id)

    if task:
        targets = task.get_targets()
        text = (
            f"❌ <b>Задача #{task.id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 Статус: <b>cancelled</b>\n"
            f"🎯 Целей: <b>{len(targets)}</b>\n"
        )
        display_text = task.text[:300] + "..." if len(task.text) > 300 else task.text
        text += f"\n<b>Текст:</b>\n<code>{display_text}</code>"
        await safe_edit(callback.message, text, reply_markup=task_detail_kb(task_id, False))
