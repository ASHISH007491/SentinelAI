"""Application configuration loaded from environment / .env."""
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SentinelAI"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelai"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_base_url: str = ""  # set for OpenAI-compatible providers (Groq, Gemini, ...)
    llm_provider: str = ""  # offline | openai | ollama (blank = auto-detect)
    llm_temperature: float = 0.0
    cors_origins: list[str] = ["http://localhost:3000"]
    storage_dir: str = "./var/uploads"
    log_format: str = "json"  # json | text
    redis_url: str = "redis://localhost:6379/0"  # reserved for future use

    @model_validator(mode="after")
    def _validate_security(self) -> "Settings":
        # Fail fast rather than run production with a forgeable, well-known key.
        if self.environment.lower() == "production" and self.jwt_secret in ("", "change-me"):
            raise ValueError(
                "JWT_SECRET must be set to a strong, unique value in production; "
                "the default 'change-me' is insecure. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return self


settings = Settings()
