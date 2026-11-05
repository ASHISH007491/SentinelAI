"""SentinelAI backend entrypoint and application factory."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (register models on Base.metadata)
from app.api.router import api_v1
from app.api.routes import health
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging

configure_logging()
logger = logging.getLogger("sentinelai")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema is owned by Alembic migrations — run `alembic upgrade head` first
    # (start-all.ps1 and the Docker entrypoint do this automatically).
    logger.info("startup environment=%s", settings.environment)
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    """Application factory: assemble middleware, handlers, and routes."""
    application = FastAPI(title="SentinelAI API", version="0.1.0", lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_logger(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "rid=%s %s %s -> %d (%.1fms)",
            request_id, request.method, request.url.path, response.status_code, elapsed_ms,
        )
        response.headers["X-Request-Id"] = request_id
        return response

    register_exception_handlers(application)

    # Root health for infra/Docker healthchecks; versioned API for the app.
    application.include_router(health.router)
    application.include_router(api_v1)
    return application


app = create_app()
