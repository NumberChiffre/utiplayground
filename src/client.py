from __future__ import annotations

import logging
import os
from contextlib import suppress

import weave
from agents import set_default_openai_client, set_trace_processors
from openai import AsyncOpenAI
from weave.integrations.openai_agents.openai_agents import WeaveTracingProcessor

_client: AsyncOpenAI | None = None
logger = logging.getLogger(__name__)


def ensure_openai_client(timeout: float = 600.0) -> bool:
    global _client  # noqa: PLW0603
    os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        _client = None
        return False

    if _client is not None:
        return True

    _client = AsyncOpenAI(timeout=timeout)
    with suppress(Exception):
        set_default_openai_client(_client)

    project_name = os.getenv("WEAVE_PROJECT", "uti-cli-agents")
    if os.getenv("WEAVE_DISABLE_INIT", "0") != "1":
        weave.init(project_name)
        set_trace_processors([WeaveTracingProcessor()])
        logger.info(f"Weave tracing initialized for project: {project_name}")

    return _client is not None


def get_openai_client() -> AsyncOpenAI | None:
    return _client
