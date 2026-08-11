import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class SubscriptionPlan:
    name: str
    messages_per_day: int
    chats_limit: int
    has_signature: bool
    duration_days: int | None = None


SUBSCRIPTION_PLANS: dict[str, SubscriptionPlan] = {
    "trial": SubscriptionPlan(
        name="Trial",
        messages_per_day=50,
        chats_limit=5,
        has_signature=True,
        duration_days=3,
    ),
    "basic": SubscriptionPlan(
        name="Basic",
        messages_per_day=200,
        chats_limit=20,
        has_signature=True,
    ),
    "pro": SubscriptionPlan(
        name="Pro",
        messages_per_day=1000,
        chats_limit=100,
        has_signature=False,
    ),
    "admin": SubscriptionPlan(
        name="Admin",
        messages_per_day=999999,
        chats_limit=999999,
        has_signature=False,
    ),
}


@dataclass(frozen=True)
class Config:
    BOT_TOKEN: str
    API_ID: int
    API_HASH: str
    SUPER_ADMIN_ID: int
    CHANNEL_ID: int
    CHANNEL_URL: str
    DB_PATH: str
    BROADCAST_DELAY_MIN: float
    BROADCAST_DELAY_MAX: float
    TRIAL_DURATION_DAYS: int
    REF_REWARD_DAYS: int
    BOT_ADVERTISEMENT: str
    OPENAI_API_KEY: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
            API_ID=int(os.getenv("API_ID", "0")),
            API_HASH=os.getenv("API_HASH", ""),
            SUPER_ADMIN_ID=int(os.getenv("SUPER_ADMIN_ID", "0")),
            CHANNEL_ID=int(os.getenv("CHANNEL_ID", "0")),
            CHANNEL_URL=os.getenv("CHANNEL_URL", ""),
            DB_PATH=os.getenv("DB_PATH", str(BASE_DIR / "bot_database.db")),
            BROADCAST_DELAY_MIN=float(os.getenv("BROADCAST_DELAY_MIN", "3")),
            BROADCAST_DELAY_MAX=float(os.getenv("BROADCAST_DELAY_MAX", "7")),
            TRIAL_DURATION_DAYS=int(os.getenv("TRIAL_DURATION_DAYS", "3")),
            REF_REWARD_DAYS=int(os.getenv("REF_REWARD_DAYS", "1")),
            BOT_ADVERTISEMENT=os.getenv(
                "BOT_ADVERTISEMENT", "Рассылается через бота @YourBot"
            ),
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
        )

    @property
    def force_sub_enabled(self) -> bool:
        return self.CHANNEL_ID != 0 and self.CHANNEL_URL != ""


config = Config.from_env()
