"""Meta/placeholder endpoints: service status and a projects stub."""
from __future__ import annotations

import time

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import ServiceStatus

router = APIRouter(tags=["meta"])

_STARTED_AT = time.time()


@router.get("/status", response_model=ServiceStatus)
def status_() -> ServiceStatus:
    return ServiceStatus(
        version="0.1.0",
        environment=settings.environment,
        uptime_seconds=round(time.time() - _STARTED_AT, 1),
    )


@router.get("/projects")
def projects_placeholder() -> dict[str, list]:
    # Placeholder until the Projects feature is wired (Phase 1 prompt 004/008).
    return {"items": []}
