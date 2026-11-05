"""Versioned API router. All application routes live under /api/v1."""
from fastapi import APIRouter

from app.api.routes import auth, health, meta, runs

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health.router)
api_v1.include_router(meta.router)
api_v1.include_router(auth.router)
api_v1.include_router(runs.router)
