"""Seed a default account so there's a ready-made login.

Idempotent: running it repeatedly will not create duplicates. Credentials can be
overridden via SEED_EMAIL / SEED_PASSWORD environment variables.

Usage:
    python -m app.seed
"""
from __future__ import annotations

import os

from sqlalchemy import select

import app.models  # noqa: F401  (register models on Base.metadata)
from app.core.security import hash_password
from app.db.session import Base, get_db, get_engine
from app.models.user import Role, User

DEFAULT_EMAIL = os.getenv("SEED_EMAIL", "admin@sentinelai.app")
DEFAULT_PASSWORD = os.getenv("SEED_PASSWORD", "admin12345")


def seed() -> None:
    # Ensure tables exist (safe if the app already created them).
    Base.metadata.create_all(bind=get_engine())

    db = next(get_db())
    try:
        existing = db.scalar(select(User).where(User.email == DEFAULT_EMAIL))
        if existing:
            print(f"User already exists: {DEFAULT_EMAIL}")
            return
        db.add(User(
            email=DEFAULT_EMAIL,
            hashed_password=hash_password(DEFAULT_PASSWORD),
            role=Role.ADMINISTRATOR,
        ))
        db.commit()
        print(f"Seeded default account: {DEFAULT_EMAIL} / {DEFAULT_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
