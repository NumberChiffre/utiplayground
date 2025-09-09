from __future__ import annotations

import logging
import os

import weave
from agents import set_default_openai_client, set_trace_processors
from openai import AsyncOpenAI
from weave.integrations.openai_agents.openai_agents import WeaveTracingProcessor

client: AsyncOpenAI | None = None
logger = logging.getLogger(__name__)


def ensure_openai_client(timeout: float = 600.0) -> bool:
    global client
    os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")
    client = AsyncOpenAI(timeout=timeout)
    set_default_openai_client(client)
    project_name = os.getenv("WEAVE_PROJECT", "uti-cli-agents")
    weave.init(project_name)
    set_trace_processors([WeaveTracingProcessor()])
    logger.info(f"Weave tracing initialized for project: {project_name}")
    return client is not None


def get_openai_client() -> AsyncOpenAI | None:
    return client
