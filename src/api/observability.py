from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from fastapi.responses import PlainTextResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI, Request, Response

logger = logging.getLogger(__name__)

REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=("method", "path", "status"),
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=("method", "path"),
    buckets=(
        0.05,
        0.1,
        0.2,
        0.5,
        1.0,
        2.0,
        5.0,
        10.0,
    ),
)
IN_FLIGHT = Gauge(
    "http_in_flight_requests",
    "In-flight HTTP requests",
)


def register_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next: Callable):
        start = time.perf_counter()
        IN_FLIGHT.inc()
        try:
            response: Response = await call_next(request)
        finally:
            IN_FLIGHT.dec()
        try:
            duration = time.perf_counter() - start
            path = request.scope.get("path", "unknown")
            method = request.method
            REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
            REQUEST_COUNTER.labels(
                method=method, path=path, status=str(response.status_code),
            ).inc()
        except Exception as e:
            logger.warning("Metrics collection failed: %s", e)
        return response

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        data = generate_latest()
        return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


