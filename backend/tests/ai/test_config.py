from app.ai.core.config import load_ai_config
from app.ai.types.enums import Provider


def test_offline_when_no_key(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "", raising=False)
    monkeypatch.setattr(settings, "llm_base_url", "", raising=False)
    load_ai_config.cache_clear()
    cfg = load_ai_config()
    assert cfg.provider is Provider.OFFLINE
    assert cfg.model  # model always set


def test_openai_compatible_when_base_url(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "k", raising=False)
    monkeypatch.setattr(settings, "llm_base_url", "https://api.groq.com/openai/v1", raising=False)
    load_ai_config.cache_clear()
    cfg = load_ai_config()
    assert cfg.provider is Provider.OPENAI_COMPATIBLE
    load_ai_config.cache_clear()
