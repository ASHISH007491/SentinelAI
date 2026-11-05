"""Local filesystem storage for uploaded artefacts.

Swappable for object storage (S3/MinIO) later; the interface stays the same.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import settings


def _root() -> Path:
    root = Path(settings.storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_bytes(run_id: int, filename: str, data: bytes) -> tuple[str, int]:
    """Persist bytes under the run's directory. Returns (storage_path, size_bytes)."""
    run_dir = _root() / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    # Prefix with a uuid to avoid collisions while keeping the original name readable.
    safe_name = Path(filename).name
    dest = run_dir / f"{uuid.uuid4().hex}_{safe_name}"
    dest.write_bytes(data)
    return str(dest), len(data)
