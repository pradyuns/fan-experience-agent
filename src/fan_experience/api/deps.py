import inspect
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from fan_experience.db.engine import async_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


# awaits coroutines, passes through plain values (sync session compat)
async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value
