from datetime import datetime, timezone

from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from fan_experience.config import settings

# shared async engine and session factory
engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# lazily created sync engine for celery tasks
_sync_engine = None


def sync_session() -> Session:
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = sa_create_engine(
            settings.database_url.replace("+asyncpg", "+psycopg")
        )
    return Session(_sync_engine)


# normalizes naive datetimes to utc
def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
