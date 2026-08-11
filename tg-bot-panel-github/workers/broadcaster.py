from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    UserBannedInChannelError,
    ChatWriteForbiddenError,
    ChatAdminRequiredError,
    PeerFloodError,
    UserNotMutualContactError,
    UserPrivacyRestrictedError,
    InputUserDeactivatedError,
    ChatRestrictedError,
)

from core.config import config
from core.database import (
    async_session_factory,
    add_broadcast_result,
    update_broadcast_result,
    update_task_status,
    get_valid_accounts,
    mark_account_banned,
)
from core.logger import log


class Broadcaster:
    def __init__(self):
        self._running = False
        self._cancel_event = asyncio.Event()

    def cancel(self):
        self._cancel_event.set()

    @property
    def is_running(self) -> bool:
        return self._running

    async def broadcast(
        self,
        task_id: int,
        text: str,
        targets: list[str],
        user_id: int,
    ) -> dict:
        self._running = True
        self._cancel_event.clear()
        total_sent = 0
        total_errors = 0
        all_errors: list[str] = []

        async with async_session_factory() as db_session:
            accounts = await get_valid_accounts(db_session, user_id)

        if not accounts:
            log.warning("Task %d: нет аккаунтов user %d", task_id, user_id)
            await self._finish_task(task_id, "error")
            return {"sent": 0, "errors": 0, "error_details": ["Нет аккаунтов"]}

        if not targets:
            await self._finish_task(task_id, "error")
            return {"sent": 0, "errors": 0, "error_details": ["Нет целей"]}

        async with async_session_factory() as db:
            await update_task_status(db, task_id, "running")

        full_text = self._append_signature(text, config.BOT_ADVERTISEMENT)

        for account in accounts:
            if self._cancel_event.is_set():
                await self._finish_task(task_id, "cancelled")
                break

            result = await self._broadcast_from_account(task_id, account, full_text, targets)
            total_sent += result["sent"]
            total_errors += result["errors"]
            all_errors.extend(result.get("error_list", []))

        if not self._cancel_event.is_set():
            await self._finish_task(task_id, "done")

        self._running = False
        return {"sent": total_sent, "errors": total_errors, "error_details": all_errors[:20]}

    async def _broadcast_from_account(self, task_id, account, text, targets):
        session_stem = Path(account.session_path).with_suffix("")
        client = TelegramClient(str(session_stem), config.API_ID, config.API_HASH)
        sent = 0
        errors = 0
        error_list = []

        async with async_session_factory() as db:
            db_result = await add_broadcast_result(db, task_id, account.id)
            result_id = db_result.id

        try:
            await client.connect()
            if not await client.is_user_authorized():
                return {"sent": 0, "errors": 1, "error_list": ["Не авторизована"]}

            for target in targets:
                if self._cancel_event.is_set():
                    break
                try:
                    entity = await client.get_entity(target)
                    await client.send_message(entity, text)
                    sent += 1
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds + 1)
                    try:
                        entity = await client.get_entity(target)
                        await client.send_message(entity, text)
                        sent += 1
                    except Exception as e2:
                        errors += 1
                        error_list.append(f"{target}: {type(e2).__name__}")
                except UserBannedInChannelError:
                    async with async_session_factory() as db:
                        await mark_account_banned(db, account.id)
                    errors += 1
                    error_list.append(f"{target}: забанен")
                    break
                except (ChatWriteForbiddenError, ChatAdminRequiredError):
                    errors += 1
                    error_list.append(f"{target}: нет прав")
                except PeerFloodError:
                    async with async_session_factory() as db:
                        await mark_account_banned(db, account.id)
                    errors += 1
                    error_list.append(f"{target}: PeerFlood")
                    break
                except (UserPrivacyRestrictedError, UserNotMutualContactError, InputUserDeactivatedError, ChatRestrictedError):
                    errors += 1
                    error_list.append(f"{target}: ограничение")
                except Exception as e:
                    errors += 1
                    error_list.append(f"{target}: {type(e).__name__}")

                await asyncio.sleep(random.uniform(config.BROADCAST_DELAY_MIN, config.BROADCAST_DELAY_MAX))

        except Exception as e:
            errors += 1
            error_list.append(f"Ошибка: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

        async with async_session_factory() as db:
            await update_broadcast_result(db, result_id, sent, errors, error_list)
        return {"sent": sent, "errors": errors, "error_list": error_list}

    @staticmethod
    def _append_signature(text: str, signature: str) -> str:
        if not signature or not signature.strip():
            return text
        return f"{text}\n\n— {signature}"

    async def _finish_task(self, task_id, status):
        async with async_session_factory() as db:
            await update_task_status(db, task_id, status)

broadcaster = Broadcaster()
