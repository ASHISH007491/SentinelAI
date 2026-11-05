"""Security config: production must reject the insecure default JWT secret (OWASP F1)."""
import pytest

from app.core.config import Settings


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError):
        Settings(environment="production", jwt_secret="change-me")


def test_production_rejects_empty_jwt_secret():
    with pytest.raises(ValueError):
        Settings(environment="production", jwt_secret="")


def test_production_accepts_strong_secret():
    s = Settings(environment="production", jwt_secret="s3cret-strong-value-0123456789abcdef")
    assert s.jwt_secret


def test_development_allows_default_secret():
    s = Settings(environment="development", jwt_secret="change-me")
    assert s.environment == "development"
