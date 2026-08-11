import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from core.config import config
from core.database import create_tables
from core.logger import log
from core.middleware_auth import AuthMiddleware
from middleware.force_sub import ForceSubMiddleware
from workers.task_queue import task_queue

from handlers.start import router as start_router
from handlers.dashboard import router as dashboard_router
from handlers.referral import router as referral_router
from handlers.subscription import router as subscription_router
from handlers.sessions import router as sessions_router
from handlers.accounts import router as accounts_router
from handlers.broadcast import router as broadcast_router
from handlers.templates import router as templates_router
from handlers.scheduled import router as scheduled_router
from handlers.dm_broadcast import router as dm_broadcast_router
from handlers.settings import router as settings_router
from handlers.auto_reply import router as auto_reply_router
from handlers.batch_sessions import router as batch_sessions_router
from handlers.queue_view import router as queue_view_router
from handlers.parser import router as parser_router
from handlers.folders import router as folders_router
from handlers.admin.dashboard import router as admin_dashboard_router
from handlers.admin.users import router as admin_users_router
from handlers.admin.global_broadcast import router as admin_global_router
from handlers.admin.monitor import router as admin_monitor_router
from handlers.admin.settings import router as admin_settings_router
from handlers.admin.tools import router as admin_tools_router
from handlers.admin.autowarmup import router as admin_autowarmup_router
from handlers.admin.shadow_invite import router as admin_shadow_invite_router
from handlers.admin.mass_looking import router as admin_mass_looking_router
from handlers.admin.mass_liking import router as admin_mass_liking_router
from handlers.admin.mass_target import router as admin_mass_target_router
from handlers.admin.neuro_comment import router as admin_neuro_comment_router


async def on_startup(bot: Bot):
    log.info("=== Запуск бота ===")
    log.info("Admin ID: %d", config.SUPER_ADMIN_ID)
    log.info("Force-Sub: %s", "ВКЛ" if config.force_sub_enabled else "ВЫКЛ")

    await create_tables()
    log.info("Таблицы БД созданы")

    await task_queue.start()
    log.info("Очередь задач запущена")

    me = await bot.get_me()
    log.info("Бот: @%s (ID: %d)", me.username, me.id)


async def on_shutdown(bot: Bot):
    log.info("=== Остановка ===")
    await task_queue.stop()
    await bot.session.close()


async def main():
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    auth = AuthMiddleware()
    dp.message.middleware(auth)
    dp.callback_query.middleware(auth)

    if config.force_sub_enabled:
        force_sub = ForceSubMiddleware(
            channel_id=config.CHANNEL_ID,
            channel_url=config.CHANNEL_URL,
        )
        dp.message.middleware(force_sub)
        dp.callback_query.middleware(force_sub)

    dp.include_router(start_router)
    dp.include_router(dashboard_router)
    dp.include_router(referral_router)
    dp.include_router(subscription_router)
    dp.include_router(sessions_router)
    dp.include_router(accounts_router)
    dp.include_router(broadcast_router)
    dp.include_router(templates_router)
    dp.include_router(scheduled_router)
    dp.include_router(dm_broadcast_router)
    dp.include_router(settings_router)
    dp.include_router(auto_reply_router)
    dp.include_router(batch_sessions_router)
    dp.include_router(queue_view_router)
    dp.include_router(parser_router)
    dp.include_router(folders_router)
    dp.include_router(admin_dashboard_router)
    dp.include_router(admin_users_router)
    dp.include_router(admin_global_router)
    dp.include_router(admin_monitor_router)
    dp.include_router(admin_settings_router)
    dp.include_router(admin_tools_router)
    dp.include_router(admin_autowarmup_router)
    dp.include_router(admin_shadow_invite_router)
    dp.include_router(admin_mass_looking_router)
    dp.include_router(admin_mass_liking_router)
    dp.include_router(admin_mass_target_router)
    dp.include_router(admin_neuro_comment_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Остановлен")
