import json

from app.config import settings as app_settings
from app.core import settings as core_settings


def test_embeddings_settings_custom_provider(monkeypatch):
    """Ensure provider overrides are parsed and expose API keys via env mapping."""
    core_settings.build_embeddings_settings.cache_clear()
    monkeypatch.setattr(app_settings, "EMBEDDINGS_PROVIDER_CONFIG_FILE", None, raising=False)
    monkeypatch.setattr(
        app_settings,
        "EMBEDDINGS_PROVIDER_CONFIG",
        json.dumps(
            {
                "custom": {
                    "model": "custom-embed-1",
                    "api_key_env": "CUSTOM_EMBED_KEY",
                    "batch_size": 10,
                    "rate_limit": 5,
                    "timeout": 15,
                    "enabled": True,
                }
            }
        ),
        raising=False,
    )
    monkeypatch.setattr(app_settings, "EMBEDDINGS_DEFAULT_PROVIDER", "custom", raising=False)
    monkeypatch.setenv("CUSTOM_EMBED_KEY", "test-key")

    embeddings_config = core_settings.build_embeddings_settings()
    provider = embeddings_config.get_provider("custom")

    assert embeddings_config.default_provider == "custom"
    assert provider is not None
    assert provider.model == "custom-embed-1"
    assert provider.resolve_api_key() == "test-key"
    assert provider.batch_size == 10

    core_settings.build_embeddings_settings.cache_clear()
    core_settings.embeddings_settings = core_settings.build_embeddings_settings()
