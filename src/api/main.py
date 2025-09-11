from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

from .observability import register_metrics
from .routes import router as api_router

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="UTI Assessment API",
    version=os.getenv("API_VERSION", "0.1.0"),
)

app.include_router(api_router, prefix="/api")
register_metrics(app)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "1") in {"1", "true", "yes", "on"},
    )


if __name__ == "__main__":
    main()


