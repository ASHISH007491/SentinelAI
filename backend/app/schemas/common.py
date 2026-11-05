"""Shared response models used across the API."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Message(BaseModel):
    """Simple message envelope for acks and confirmations."""
    message: str


class ErrorResponse(BaseModel):
    """Consistent error shape returned by the global exception handlers."""
    detail: str
    code: str = "error"


class Envelope(BaseModel, Generic[T]):
    """Generic data envelope for endpoints that opt into a wrapped response."""
    data: T


class HealthStatus(BaseModel):
    status: str = "ok"
    service: str = "sentinelai"


class ServiceStatus(BaseModel):
    status: str = "operational"
    version: str
    environment: str
    uptime_seconds: float
