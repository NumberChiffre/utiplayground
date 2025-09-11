from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import redis
from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from collections.abc import Callable

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_REDIS = redis.Redis.from_url(_REDIS_URL, decode_responses=True)


class RateLimiter:
    def __init__(self, limit_per_minute: int, key_func: Callable[[Request], str] | None = None) -> None:
        self.limit = max(1, limit_per_minute)
        self.key_func = key_func or (lambda req: req.client.host if req.client else "anon")

    def _bucket_key(self, request: Request) -> str:
        now = int(time.time() // 60)
        ident = self.key_func(request)
        return f"ratelimit:{ident}:{now}"

    def allow(self, request: Request) -> bool:
        key = self._bucket_key(request)
        with _REDIS.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, 70)
            count, _ = pipe.execute()
        return int(count) <= self.limit


_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
_RL = RateLimiter(_LIMIT_PER_MIN)


def rate_limiter(request: Request) -> None:
    if not _RL.allow(request):
        raise HTTPException(status_code=429, detail="rate_limited")


