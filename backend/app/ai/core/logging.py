"""Logging helper for AI modules — namespaced under the app's logging config."""
from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under 'sentinelai.ai'."""
    suffix = name.split(".")[-1]
    return logging.getLogger(f"sentinelai.ai.{suffix}")
