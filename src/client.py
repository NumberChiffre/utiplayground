from __future__ import annotations

import logging
import os

import weave
from agents import set_default_openai_client, set_trace_processors
from openai import AsyncOpenAI
from weave.integrations.openai_agents.openai_agents import WeaveTracingProcessor

_client: AsyncOpenAI | None = None
_weave_initialized = False
logger = logging.getLogger(__name__)


def ensure_openai_client(
    timeout: float = 600.0, enable_weave: bool = True, weave_project: str | None = None
) -> bool:
    global _client, _weave_initialized
    if _client is None and os.getenv("OPENAI_API_KEY"):
        _client = AsyncOpenAI(timeout=timeout)
        try:
            set_default_openai_client(_client)

            # Initialize Weave tracing if enabled and available
            if enable_weave and not _weave_initialized:
                project_name = weave_project or os.getenv(
                    "WEAVE_PROJECT", "uti-cli-agents"
                )
                try:
                    weave.init(project_name)
                    set_trace_processors([WeaveTracingProcessor()])
                    _weave_initialized = True
                    logger.info(
                        f"W&B Weave tracing initialized for project: {project_name}"
                    )
                    logger.info("To view traces visit: https://wandb.ai/weave")
                except Exception as e:
                    logger.error(f"Failed to initialize W&B Weave: {e}")
            elif enable_weave:
                logger.warning(
                    "W&B Weave not available - install with 'pip install weave'"
                )
            elif not enable_weave:
                logger.info("W&B Weave tracing disabled")

        except Exception as e:
            logger.error(f"Error setting up OpenAI client: {e}")
    return _client is not None


def get_openai_client() -> AsyncOpenAI | None:
    return _client


def is_weave_initialized() -> bool:
    """Check if Weave tracing is initialized."""
    return _weave_initialized


def finish_weave_run() -> None:
    """Finish the current Weave run."""
    if weave:
        try:
            weave.finish()
            logger.info("W&B Weave run finished successfully")
        except Exception as e:
            logger.error(f"Error finishing W&B Weave run: {e}")


def reinitialize_weave(project_name: str) -> bool:
    """Reinitialize Weave with a new project."""
    global _weave_initialized

    try:
        # Finish current run if exists
        if _weave_initialized:
            finish_weave_run()

        # Initialize new project
        weave.init(project_name)
        set_trace_processors([WeaveTracingProcessor()])
        _weave_initialized = True
        logger.info(f"W&B Weave reinitialized for project: {project_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to reinitialize W&B Weave: {e}")
        return False
