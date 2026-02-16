"""
Typed settings helpers for advanced configuration domains.

This module keeps the parsing logic for rich configuration blocks out of the
generic Pydantic settings so that application code can rely on validated
objects (e.g. embeddings providers definitions).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field, ValidationError

from app.config import settings


class EmbeddingProviderSettings(BaseModel):
    """Configuration d'un provider d'embeddings."""

    name: str
    model: str = "text-embedding-3-small"
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    batch_size: int = Field(default=100, ge=1, le=1000)
    rate_limit: int = Field(default=100, ge=1)
    timeout: int = Field(default=30, ge=5, le=300)
    enabled: bool = True

    def resolve_api_key(self) -> Optional[str]:
        """Retourne la clé API associée au provider si elle est exportée."""
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None


class EmbeddingsSettings(BaseModel):
    """Bloc de configuration pour l'écosystème d'embeddings."""

    enabled: bool = True
    default_provider: str = "openai"
    allow_external_providers: bool = True
    require_user_confirmation: bool = True
    providers: Dict[str, EmbeddingProviderSettings] = Field(default_factory=dict)

    def get_provider(self, name: str) -> Optional[EmbeddingProviderSettings]:
        """Retourne la configuration d'un provider actif."""
        provider = self.providers.get(name)
        if provider and provider.enabled:
            return provider
        return None

    @property
    def enabled_providers(self) -> Dict[str, EmbeddingProviderSettings]:
        """Providers activés uniquement."""
        return {
            name: provider for name, provider in self.providers.items() if provider.enabled
        }


def _load_provider_overrides(raw_json: Optional[str], file_path: Optional[str]) -> Dict[str, Dict]:
    """Charge les overrides de providers à partir d'une chaîne JSON ou d'un fichier."""
    payload = raw_json

    if not payload and file_path:
        try:
            payload = Path(file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ValueError(f"Embedding provider config file not found: {file_path}")

    if not payload:
        return {}

    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("Embedding provider config must be a JSON object")
        return data
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid EMBEDDINGS_PROVIDER_CONFIG JSON: {exc}") from exc


@lru_cache()
def build_embeddings_settings() -> EmbeddingsSettings:
    """Construit l'objet de configuration embeddings validé."""
    overrides = _load_provider_overrides(
        settings.EMBEDDINGS_PROVIDER_CONFIG,
        settings.EMBEDDINGS_PROVIDER_CONFIG_FILE,
    )

    default_providers: Dict[str, Dict] = {
        "openai": {
            "model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            "api_key_env": "OPENAI_API_KEY",
            "batch_size": int(os.getenv("OPENAI_BATCH_SIZE", "100")),
            "rate_limit": int(os.getenv("OPENAI_RATE_LIMIT", "100")),
            "timeout": int(os.getenv("OPENAI_TIMEOUT", "30")),
            "base_url": os.getenv("OPENAI_BASE_URL"),
        },
        "mistral": {
            "model": os.getenv("MISTRAL_EMBEDDING_MODEL", "mistral-embed"),
            "api_key_env": "MISTRAL_API_KEY",
            "batch_size": int(os.getenv("MISTRAL_BATCH_SIZE", "50")),
            "rate_limit": int(os.getenv("MISTRAL_RATE_LIMIT", "50")),
            "timeout": int(os.getenv("MISTRAL_TIMEOUT", "30")),
            "base_url": os.getenv("MISTRAL_BASE_URL"),
        },
    }

    provider_payloads: Dict[str, Dict] = {**default_providers, **overrides}
    providers: Dict[str, EmbeddingProviderSettings] = {}

    for name, payload in provider_payloads.items():
        if not isinstance(payload, dict):
            raise ValueError(f"Provider override for {name} must be a JSON object")
        payload.setdefault("name", name)
        try:
            providers[name] = EmbeddingProviderSettings(**payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid provider settings for {name}: {exc}") from exc

    settings_payload = {
        "enabled": settings.EMBEDDINGS_ENABLED,
        "default_provider": settings.EMBEDDINGS_DEFAULT_PROVIDER,
        "allow_external_providers": settings.EMBEDDINGS_ALLOW_EXTERNAL_PROVIDERS,
        "require_user_confirmation": settings.EMBEDDINGS_REQUIRE_USER_CONFIRMATION,
        "providers": providers,
    }

    try:
        return EmbeddingsSettings(**settings_payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid embeddings settings: {exc}") from exc


# Instance globale cachée derrière un cache pour éviter les re-parsings.
embeddings_settings = build_embeddings_settings()


def resolve_provider_api_key(provider_name: str) -> Optional[str]:
    """Retourne la clé API déclarée pour un provider si disponible."""
    provider = embeddings_settings.get_provider(provider_name)
    if not provider:
        return None
    return provider.resolve_api_key()
