"""Register, login, refresh, logout, and profile (OAuth2 password flow → JWT)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.auth import AccessToken, RefreshRequest, Token, UserCreate, UserRead
from app.schemas.common import Message

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.email, role=user.role.value),
        refresh_token=create_refresh_token(user.email),
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=400, detail="Email already registered")
    # New users default to Analyst; elevate via admin tooling.
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=Role.ANALYST,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _tokens(user)


@router.post("/refresh", response_model=AccessToken)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> AccessToken:
    data = decode_token(payload.refresh_token, expected_type="refresh")
    if data is None or "sub" not in data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.scalar(select(User).where(User.email == data["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return AccessToken(access_token=create_access_token(user.email, role=user.role.value))


@router.post("/logout", response_model=Message)
def logout(_: User = Depends(get_current_user)) -> Message:
    # JWT is stateless: the client discards its tokens. Endpoint exists for parity
    # and as the hook point for future server-side token revocation (denylist).
    return Message(message="Logged out")


@router.get("/me", response_model=UserRead)
def me(current: User = Depends(get_current_user)) -> User:
    return current
