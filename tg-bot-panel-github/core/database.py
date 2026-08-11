from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from core.config import config


class Base(DeclarativeBase):
    pass


# ──────────────────────── USER ────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    first_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    ref_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    referred_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signature_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ──────────────────── SUBSCRIPTION ────────────────────
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(32), default="trial", nullable=False)
    messages_limit: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    chats_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    messages_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chats_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ──────────────────── INVITE CODE ─────────────────────
class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="basic", nullable=False)
    uses_left: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ────────────────────── ACCOUNT ───────────────────────
class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session_path: Mapped[str] = mapped_column(String(512), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    username: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    first_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ──────────────────── BROADCAST TASK ──────────────────
class BroadcastTask(Base):
    __tablename__ = "broadcast_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    targets: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    broadcast_type: Mapped[str] = mapped_column(String(32), default="groups", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def get_targets(self) -> list[str]:
        return json.loads(self.targets)

    def set_targets(self, targets: list[str]) -> None:
        self.targets = json.dumps(targets)


# ──────────────────── BROADCAST RESULT ────────────────
class BroadcastResult(Base):
    __tablename__ = "broadcast_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ────────────────────── TEMPLATE ──────────────────────
class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ──────────────────── SCHEDULED BROADCAST ─────────────
class ScheduledBroadcast(Base):
    __tablename__ = "scheduled_broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    targets: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ────────────────────── BOT SETTINGS ──────────────────
class BotSettings(Base):
    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ──────────────────── AUTO REPLY RULE ─────────────────
class AutoReplyRule(Base):
    __tablename__ = "auto_reply_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(256), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ──────────────────── PARSED MEMBER ───────────────────
class ParsedMember(Base):
    __tablename__ = "parsed_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    telegram_id: Mapped[int] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    first_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    source_chat: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ──────────────────── TARGET FOLDER ───────────────────
class TargetFolder(Base):
    __tablename__ = "target_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    targets: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def get_targets(self) -> list[str]:
        return json.loads(self.targets)

    def set_targets(self, targets: list[str]) -> None:
        self.targets = json.dumps(targets)


# ──────────────────── ADMIN TOOL TASK ─────────────────
class AdminTask(Base):
    __tablename__ = "admin_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_log: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def get_config(self) -> dict:
        return json.loads(self.config_json)

    def set_config(self, cfg: dict) -> None:
        self.config_json = json.dumps(cfg, ensure_ascii=False)


# ──────────────────────── ENGINE ──────────────────────

engine = create_async_engine(
    f"sqlite+aiosqlite:///{config.DB_PATH}",
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ────────────────────── USER CRUD ─────────────────────

def _gen_ref_code() -> str:
    return secrets.token_hex(4).upper()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str = "",
    first_name: str = "",
    referred_by: int | None = None,
) -> User:
    from sqlalchemy import select

    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        if username:
            user.username = username
        if first_name:
            user.first_name = first_name
        await session.refresh(user)
        return user

    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        ref_code=_gen_ref_code(),
        referred_by=referred_by,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=config.TRIAL_DURATION_DAYS),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    sub = Subscription(
        user_id=telegram_id,
        plan="trial",
        messages_limit=50,
        chats_limit=5,
        expires_at=user.trial_ends_at,
    )
    session.add(sub)
    await session.commit()
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    from sqlalchemy import select
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_by_ref_code(session: AsyncSession, ref_code: str) -> User | None:
    from sqlalchemy import select
    result = await session.execute(select(User).where(User.ref_code == ref_code))
    return result.scalar_one_or_none()


async def get_all_users(session: AsyncSession, limit: int = 100, offset: int = 0) -> list[User]:
    from sqlalchemy import select
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def count_users(session: AsyncSession) -> int:
    from sqlalchemy import select, func as sqlfunc
    result = await session.execute(select(sqlfunc.count(User.id)))
    return result.scalar() or 0


async def ban_user(session: AsyncSession, telegram_id: int) -> None:
    from sqlalchemy import update
    await session.execute(update(User).where(User.telegram_id == telegram_id).values(is_banned=True))
    await session.commit()


async def unban_user(session: AsyncSession, telegram_id: int) -> None:
    from sqlalchemy import update
    await session.execute(update(User).where(User.telegram_id == telegram_id).values(is_banned=False))
    await session.commit()


async def make_admin(session: AsyncSession, telegram_id: int) -> None:
    from sqlalchemy import update
    await session.execute(update(User).where(User.telegram_id == telegram_id).values(is_admin=True))
    sub_result = await session.execute(select(Subscription).where(Subscription.user_id == telegram_id))
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.plan = "admin"
        sub.messages_limit = 999999
        sub.chats_limit = 999999
    await session.commit()


# ──────────────────── SUBSCRIPTION CRUD ───────────────

async def get_subscription(session: AsyncSession, user_id: int) -> Subscription | None:
    from sqlalchemy import select
    result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_subscription(session: AsyncSession, user_id: int) -> Subscription:
    sub = await get_subscription(session, user_id)
    if sub:
        return sub
    sub = Subscription(user_id=user_id, plan="trial", messages_limit=50, chats_limit=5)
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


async def reset_daily_limits(session: AsyncSession) -> None:
    from sqlalchemy import update
    await session.execute(
        update(Subscription).values(messages_used=0, chats_used=0)
    )
    await session.commit()


async def increment_messages_used(session: AsyncSession, user_id: int, count: int = 1) -> None:
    from sqlalchemy import update
    await session.execute(
        update(Subscription)
        .where(Subscription.user_id == user_id)
        .values(messages_used=Subscription.messages_used + count)
    )
    await session.commit()


async def increment_chats_used(session: AsyncSession, user_id: int, count: int = 1) -> None:
    from sqlalchemy import update
    await session.execute(
        update(Subscription)
        .where(Subscription.user_id == user_id)
        .values(chats_used=Subscription.chats_used + count)
    )
    await session.commit()


async def set_subscription_plan(
    session: AsyncSession, user_id: int, plan: str, duration_days: int | None = None
) -> None:
    from core.config import SUBSCRIPTION_PLANS
    from sqlalchemy import update

    p = SUBSCRIPTION_PLANS.get(plan)
    if not p:
        return
    expires = None
    if duration_days:
        expires = datetime.now(timezone.utc) + timedelta(days=duration_days)
    await session.execute(
        update(Subscription)
        .where(Subscription.user_id == user_id)
        .values(
            plan=plan,
            messages_limit=p.messages_per_day,
            chats_limit=p.chats_limit,
            messages_used=0,
            chats_used=0,
            expires_at=expires,
        )
    )
    await session.commit()


# ──────────────────── INVITE CODE CRUD ────────────────

async def create_invite_code(
    session: AsyncSession, created_by: int, plan: str = "basic", uses: int = 1
) -> InviteCode:
    code = secrets.token_hex(4).upper()
    inv = InviteCode(code=code, created_by=created_by, plan=plan, uses_left=uses)
    session.add(inv)
    await session.commit()
    await session.refresh(inv)
    return inv


async def use_invite_code(session: AsyncSession, code: str) -> InviteCode | None:
    from sqlalchemy import select, update
    result = await session.execute(select(InviteCode).where(InviteCode.code == code))
    inv = result.scalar_one_or_none()
    if not inv or inv.uses_left <= 0:
        return None
    inv.uses_left -= 1
    await session.commit()
    return inv


# ──────────────────── ACCOUNT CRUD (per-user) ─────────

async def add_account(
    session: AsyncSession,
    user_id: int,
    session_path: str,
    phone: str = "",
    username: str = "",
    first_name: str = "",
    is_valid: bool = True,
) -> Account:
    acc = Account(
        user_id=user_id,
        session_path=session_path,
        phone=phone,
        username=username,
        first_name=first_name,
        is_valid=is_valid,
    )
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return acc


async def get_user_accounts(session: AsyncSession, user_id: int) -> list[Account]:
    from sqlalchemy import select
    result = await session.execute(
        select(Account).where(Account.user_id == user_id).order_by(Account.added_at.desc())
    )
    return list(result.scalars().all())


async def get_valid_accounts(session: AsyncSession, user_id: int | None = None) -> list[Account]:
    from sqlalchemy import select
    q = select(Account).where(Account.is_valid == True, Account.is_banned == False)
    if user_id is not None:
        q = q.where(Account.user_id == user_id)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_all_accounts_admin(session: AsyncSession) -> list[Account]:
    from sqlalchemy import select
    result = await session.execute(select(Account).order_by(Account.added_at.desc()))
    return list(result.scalars().all())


async def get_account_by_session_path(session: AsyncSession, session_path: str) -> Account | None:
    from sqlalchemy import select
    result = await session.execute(select(Account).where(Account.session_path == session_path))
    return result.scalar_one_or_none()


async def mark_account_banned(session: AsyncSession, account_id: int) -> None:
    from sqlalchemy import update
    await session.execute(update(Account).where(Account.id == account_id).values(is_banned=True))
    await session.commit()


async def delete_account(session: AsyncSession, account_id: int) -> None:
    from sqlalchemy import delete
    await session.execute(delete(Account).where(Account.id == account_id))
    await session.commit()


async def count_user_accounts(session: AsyncSession, user_id: int) -> int:
    from sqlalchemy import select, func as sqlfunc
    result = await session.execute(
        select(sqlfunc.count(Account.id)).where(Account.user_id == user_id)
    )
    return result.scalar() or 0


async def count_user_referrals(session: AsyncSession, telegram_id: int) -> int:
    from sqlalchemy import select, func as sqlfunc
    result = await session.execute(
        select(sqlfunc.count(User.id)).where(User.referred_by == telegram_id)
    )
    return result.scalar() or 0


# ──────────────────── BROADCAST TASK CRUD ─────────────

async def create_broadcast_task(
    session: AsyncSession,
    user_id: int,
    text: str,
    targets: list[str],
    broadcast_type: str = "groups",
) -> BroadcastTask:
    task = BroadcastTask(user_id=user_id, text=text, broadcast_type=broadcast_type)
    task.set_targets(targets)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task_status(session: AsyncSession, task_id: int, status: str) -> None:
    from sqlalchemy import update
    values: dict = {"status": status}
    if status in ("done", "cancelled", "error"):
        values["finished_at"] = datetime.now(timezone.utc)
    await session.execute(update(BroadcastTask).where(BroadcastTask.id == task_id).values(**values))
    await session.commit()


async def get_user_tasks(session: AsyncSession, user_id: int, limit: int = 20) -> list[BroadcastTask]:
    from sqlalchemy import select
    result = await session.execute(
        select(BroadcastTask).where(BroadcastTask.user_id == user_id).order_by(BroadcastTask.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_all_tasks_admin(session: AsyncSession, limit: int = 50) -> list[BroadcastTask]:
    from sqlalchemy import select
    result = await session.execute(
        select(BroadcastTask).order_by(BroadcastTask.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def count_total_tasks(session: AsyncSession) -> int:
    from sqlalchemy import select, func as sqlfunc
    result = await session.execute(select(sqlfunc.count(BroadcastTask.id)))
    return result.scalar() or 0


async def count_total_sent(session: AsyncSession) -> int:
    from sqlalchemy import select, func as sqlfunc
    result = await session.execute(select(sqlfunc.coalesce(sqlfunc.sum(BroadcastResult.sent_count), 0)))
    return result.scalar() or 0


# ──────────────────── BROADCAST RESULT CRUD ───────────

async def add_broadcast_result(session: AsyncSession, task_id: int, account_id: int) -> BroadcastResult:
    r = BroadcastResult(task_id=task_id, account_id=account_id)
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return r


async def update_broadcast_result(
    session: AsyncSession, result_id: int, sent: int, errors: int, error_list: list[str], status: str = "done"
) -> None:
    from sqlalchemy import update
    await session.execute(
        update(BroadcastResult)
        .where(BroadcastResult.id == result_id)
        .values(sent_count=sent, error_count=errors, errors=json.dumps(error_list), status=status, finished_at=datetime.now(timezone.utc))
    )
    await session.commit()


# ────────────────────── TEMPLATE CRUD ─────────────────

async def add_template(session: AsyncSession, user_id: int, name: str, text: str) -> Template:
    t = Template(user_id=user_id, name=name, text=text)
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


async def get_user_templates(session: AsyncSession, user_id: int) -> list[Template]:
    from sqlalchemy import select
    result = await session.execute(
        select(Template).where(Template.user_id == user_id).order_by(Template.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_template(session: AsyncSession, template_id: int) -> None:
    from sqlalchemy import delete
    await session.execute(delete(Template).where(Template.id == template_id))
    await session.commit()


# ──────────────────── SCHEDULED BROADCAST CRUD ────────

async def add_scheduled_broadcast(
    session: AsyncSession, user_id: int, text: str, targets: list[str], run_at: datetime
) -> ScheduledBroadcast:
    sb = ScheduledBroadcast(user_id=user_id, text=text, run_at=run_at)
    sb.targets = json.dumps(targets)
    session.add(sb)
    await session.commit()
    await session.refresh(sb)
    return sb


async def get_pending_scheduled(session: AsyncSession) -> list[ScheduledBroadcast]:
    from sqlalchemy import select
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(ScheduledBroadcast).where(
            ScheduledBroadcast.status == "pending",
            ScheduledBroadcast.run_at <= now,
        )
    )
    return list(result.scalars().all())


async def update_scheduled_status(session: AsyncSession, sched_id: int, status: str) -> None:
    from sqlalchemy import update
    await session.execute(
        update(ScheduledBroadcast).where(ScheduledBroadcast.id == sched_id).values(status=status)
    )
    await session.commit()


# ──────────────────── BOT SETTINGS CRUD ───────────────

async def get_setting(session: AsyncSession, key: str) -> str | None:
    from sqlalchemy import select
    result = await session.execute(select(BotSettings).where(BotSettings.key == key))
    s = result.scalar_one_or_none()
    return s.value if s else None


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    from sqlalchemy import select
    result = await session.execute(select(BotSettings).where(BotSettings.key == key))
    s = result.scalar_one_or_none()
    if s:
        s.value = value
    else:
        s = BotSettings(key=key, value=value)
        session.add(s)
    await session.commit()


# ──────────────── USER SETTINGS / SIGNATURE CRUD ────────

async def get_or_create_settings(session: AsyncSession, telegram_id: int) -> User:
    from sqlalchemy import select
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = await get_or_create_user(session, telegram_id)
    return user


async def update_signature(session: AsyncSession, telegram_id: int, new_signature: str) -> None:
    from sqlalchemy import update
    await session.execute(
        update(User).where(User.telegram_id == telegram_id).values(signature_text=new_signature)
    )
    await session.commit()


# ──────────────── AUTO REPLY RULE CRUD ────────────────

async def add_auto_reply_rule(
    session: AsyncSession, user_id: int, keyword: str, response_text: str
) -> AutoReplyRule:
    rule = AutoReplyRule(user_id=user_id, keyword=keyword, response_text=response_text)
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def get_user_auto_reply_rules(session: AsyncSession, user_id: int) -> list[AutoReplyRule]:
    from sqlalchemy import select
    result = await session.execute(
        select(AutoReplyRule).where(AutoReplyRule.user_id == user_id).order_by(AutoReplyRule.created_at.desc())
    )
    return list(result.scalars().all())


async def toggle_auto_reply_rule(session: AsyncSession, rule_id: int) -> None:
    from sqlalchemy import select
    result = await session.execute(select(AutoReplyRule).where(AutoReplyRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule:
        rule.is_active = not rule.is_active
        await session.commit()


async def delete_auto_reply_rule(session: AsyncSession, rule_id: int) -> None:
    from sqlalchemy import delete
    await session.execute(delete(AutoReplyRule).where(AutoReplyRule.id == rule_id))
    await session.commit()


# ──────────────── PARSED MEMBER CRUD ──────────────────

async def add_parsed_member(
    session: AsyncSession,
    user_id: int,
    telegram_id: int | None,
    username: str,
    first_name: str,
    last_name: str,
    phone: str,
    source_chat: str,
) -> ParsedMember:
    m = ParsedMember(
        user_id=user_id,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        source_chat=source_chat,
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


async def get_user_parsed_members(
    session: AsyncSession, user_id: int, limit: int = 100
) -> list[ParsedMember]:
    from sqlalchemy import select
    result = await session.execute(
        select(ParsedMember)
        .where(ParsedMember.user_id == user_id)
        .order_by(ParsedMember.parsed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_user_parsed_members(session: AsyncSession, user_id: int) -> int:
    from sqlalchemy import select, func as sqlfunc
    result = await session.execute(
        select(sqlfunc.count(ParsedMember.id)).where(ParsedMember.user_id == user_id)
    )
    return result.scalar() or 0


async def delete_parsed_members(session: AsyncSession, user_id: int) -> None:
    from sqlalchemy import delete
    await session.execute(delete(ParsedMember).where(ParsedMember.user_id == user_id))
    await session.commit()


# ──────────────── TARGET FOLDER CRUD ──────────────────

async def add_target_folder(
    session: AsyncSession, user_id: int, name: str, targets: list[str]
) -> TargetFolder:
    folder = TargetFolder(user_id=user_id, name=name)
    folder.set_targets(targets)
    session.add(folder)
    await session.commit()
    await session.refresh(folder)
    return folder


async def get_user_folders(session: AsyncSession, user_id: int) -> list[TargetFolder]:
    from sqlalchemy import select
    result = await session.execute(
        select(TargetFolder).where(TargetFolder.user_id == user_id).order_by(TargetFolder.created_at.desc())
    )
    return list(result.scalars().all())


async def get_folder_by_id(session: AsyncSession, folder_id: int) -> TargetFolder | None:
    from sqlalchemy import select
    result = await session.execute(select(TargetFolder).where(TargetFolder.id == folder_id))
    return result.scalar_one_or_none()


async def update_target_folder(
    session: AsyncSession, folder_id: int, name: str | None = None, targets: list[str] | None = None
) -> None:
    from sqlalchemy import select
    result = await session.execute(select(TargetFolder).where(TargetFolder.id == folder_id))
    folder = result.scalar_one_or_none()
    if folder:
        if name is not None:
            folder.name = name
        if targets is not None:
            folder.set_targets(targets)
        await session.commit()


async def delete_target_folder(session: AsyncSession, folder_id: int) -> None:
    from sqlalchemy import delete
    await session.execute(delete(TargetFolder).where(TargetFolder.id == folder_id))
    await session.commit()


# ──────────────── BROADCAST RESULT READ ───────────────

async def get_broadcast_results_by_task(
    session: AsyncSession, task_id: int
) -> list[BroadcastResult]:
    from sqlalchemy import select
    result = await session.execute(
        select(BroadcastResult).where(BroadcastResult.task_id == task_id)
    )
    return list(result.scalars().all())


async def get_task_by_id(session: AsyncSession, task_id: int) -> BroadcastTask | None:
    from sqlalchemy import select
    result = await session.execute(select(BroadcastTask).where(BroadcastTask.id == task_id))
    return result.scalar_one_or_none()


# ──────────────── ADMIN TOOL TASK CRUD ────────────────

async def create_admin_task(
    session: AsyncSession, tool: str, config: dict, total: int = 0
) -> AdminTask:
    task = AdminTask(tool=tool, total=total)
    task.set_config(config)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_admin_tasks(
    session: AsyncSession, tool: str | None = None, limit: int = 20
) -> list[AdminTask]:
    from sqlalchemy import select
    q = select(AdminTask).order_by(AdminTask.created_at.desc())
    if tool:
        q = q.where(AdminTask.tool == tool)
    q = q.limit(limit)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_admin_task_by_id(session: AsyncSession, task_id: int) -> AdminTask | None:
    from sqlalchemy import select
    result = await session.execute(select(AdminTask).where(AdminTask.id == task_id))
    return result.scalar_one_or_none()


async def update_admin_task(
    session: AsyncSession,
    task_id: int,
    status: str | None = None,
    done: int | None = None,
    errors: int | None = None,
    error_log: list[str] | None = None,
) -> None:
    from sqlalchemy import update
    values: dict = {}
    if status is not None:
        values["status"] = status
    if done is not None:
        values["done"] = done
    if errors is not None:
        values["errors"] = errors
    if error_log is not None:
        values["error_log"] = json.dumps(error_log, ensure_ascii=False)
    if status in ("done", "error", "cancelled"):
        values["finished_at"] = datetime.now(timezone.utc)
    if values:
        await session.execute(
            update(AdminTask).where(AdminTask.id == task_id).values(**values)
        )
        await session.commit()
