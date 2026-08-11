from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    AuthKeyUnregisteredError,
    AuthKeyError,
    FloodWaitError,
    SessionPasswordNeededError,
)

from core.config import config, SESSIONS_DIR
from core.logger import log


@dataclass
class SessionInfo:
    session_path: str
    phone: str
    username: str
    first_name: str
    user_id: int
    is_valid: bool
    error: str = ""


async def validate_session_file(
    file_path: str | Path,
) -> SessionInfo:
    file_path = Path(file_path)
    session_stem = file_path.stem
    client = TelegramClient(
        str(file_path.with_suffix("")),
        config.API_ID,
        config.API_HASH,
    )
    try:
        await client.connect()
        me = await client.get_me()
        if me is None:
            return SessionInfo(
                session_path=str(file_path),
                phone="",
                username="",
                first_name="",
                user_id=0,
                is_valid=False,
                error="Сессия не авторизована (get_me вернул None)",
            )
        return SessionInfo(
            session_path=str(file_path),
            phone=getattr(me, "phone", "") or "",
            username=getattr(me, "username", "") or "",
            first_name=getattr(me, "first_name", "") or "",
            user_id=me.id,
            is_valid=True,
        )
    except AuthKeyUnregisteredError:
        return SessionInfo(
            session_path=str(file_path),
            phone="",
            username="",
            first_name="",
            user_id=0,
            is_valid=False,
            error="Сессия истекла / авторизационный ключ недействителен",
        )
    except AuthKeyError:
        return SessionInfo(
            session_path=str(file_path),
            phone="",
            username="",
            first_name="",
            user_id=0,
            is_valid=False,
            error="Недействительный авторизационный ключ",
        )
    except FloodWaitError as e:
        return SessionInfo(
            session_path=str(file_path),
            phone="",
            username="",
            first_name="",
            user_id=0,
            is_valid=False,
            error=f"FloodWait: подождите {e.seconds} секунд",
        )
    except SessionPasswordNeededError:
        return SessionInfo(
            session_path=str(file_path),
            phone="",
            username="",
            first_name="",
            user_id=0,
            is_valid=False,
            error="Аккаунт защищён 2FA паролем — загрузите сессию без 2FA",
        )
    except Exception as e:
        return SessionInfo(
            session_path=str(file_path),
            phone="",
            username="",
            first_name="",
            user_id=0,
            is_valid=False,
            error=f"Ошибка: {type(e).__name__}: {e}",
        )
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def save_session_file(
    file_content: bytes,
    original_filename: str,
) -> Path:
    safe_name = original_filename.replace("/", "_").replace("\\", "_")
    if not safe_name.endswith(".session"):
        safe_name += ".session"
    dest = SESSIONS_DIR / safe_name
    dest.write_bytes(file_content)
    return dest


async def delete_session_file(session_path: str) -> bool:
    path = Path(session_path)
    try:
        if path.exists():
            os.remove(path)
        session_db = path.with_suffix(".session")
        if session_db.exists():
            os.remove(session_db)
        return True
    except OSError as e:
        log.error("Не удалось удалить сессию %s: %s", session_path, e)
        return False


def list_session_files() -> list[Path]:
    return sorted(SESSIONS_DIR.glob("*.session"))
