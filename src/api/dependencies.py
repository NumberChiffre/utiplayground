from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ..client import ensure_openai_client

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class ConcurrencyLimiter:
    def __init__(self, global_limit: int) -> None:
        self._global = asyncio.Semaphore(max(1, global_limit))

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        await self._global.acquire()
        try:
            yield None
        finally:
            self._global.release()


_GLOBAL_LIMIT = int(os.getenv("LLM_GLOBAL_CONCURRENCY", "8"))
_LIMITER = ConcurrencyLimiter(_GLOBAL_LIMIT)


async def limiter() -> ConcurrencyLimiter:
    return _LIMITER


async def ensure_clients_ready() -> bool:
    try:
        return ensure_openai_client()
    except Exception as e:
        logger.warning("Client init failed: %s", e)
        return False


async def require_clients() -> None:
    ready = await ensure_clients_ready()
    if not ready:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Service unavailable")


