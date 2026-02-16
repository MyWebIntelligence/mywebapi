"""
Registry pour gérer les providers d'embeddings
"""

import logging
from typing import Dict, List, Optional, Type, Any
from datetime import datetime

from .base_provider import BaseEmbeddingProvider, ProviderConfig, ProviderStatus, ConfigurationError
from .openai_provider import OpenAIEmbeddingProvider  
from .mistral_provider import MistralEmbeddingProvider
from app.core.settings import embeddings_settings

logger = logging.getLogger(__name__)

class EmbeddingProviderRegistry:
    """Registry centralisé pour tous les providers d'embeddings"""
    
    # Mapping des providers disponibles
    AVAILABLE_PROVIDERS: Dict[str, Type[BaseEmbeddingProvider]] = {
        "openai": OpenAIEmbeddingProvider,
        "mistral": MistralEmbeddingProvider,
    }
    
    # Configuration par défaut des modèles
    DEFAULT_MODELS = {
        "openai": "text-embedding-3-small",
        "mistral": "mistral-embed"
    }
    
    def __init__(self):
        self._providers: Dict[str, BaseEmbeddingProvider] = {}
        self._configs: Dict[str, ProviderConfig] = {}
        self._initialized = False
    
    async def initialize(self, auto_configure: bool = True):
        """Initialise le registry avec la configuration automatique"""
        if self._initialized:
            return
        
        logger.info("Initializing embedding provider registry...")
        
        if auto_configure:
            await self._auto_configure_providers()
        
        self._initialized = True
        logger.info(f"Registry initialized with {len(self._providers)} providers")
    
    async def _auto_configure_providers(self):
        """Configure automatiquement les providers à partir des variables d'environnement"""
        if not embeddings_settings.enabled:
            logger.info("Embeddings disabled in configuration; skipping provider registration")
            return
        
        for name, provider_settings in embeddings_settings.enabled_providers.items():
            api_key = provider_settings.resolve_api_key()
            if not api_key:
                logger.warning(
                    "Provider %s enabled but API key not found (env=%s)",
                    name,
                    provider_settings.api_key_env,
                )
                continue

            model = provider_settings.model or self.DEFAULT_MODELS.get(name, "")
            if not model:
                model = self.DEFAULT_MODELS.get(name)

            try:
                await self.register_provider(
                    name=name,
                    config=ProviderConfig(
                        name=name,
                        model=model,
                        api_key=api_key,
                        base_url=provider_settings.base_url,
                        batch_size=provider_settings.batch_size,
                        rate_limit=provider_settings.rate_limit,
                        timeout=provider_settings.timeout,
                    ),
                )
                logger.info("Provider %s configured successfully", name)
            except Exception as e:
                logger.error("Failed to configure %s provider: %s", name, e)
    
    async def register_provider(self, name: str, config: ProviderConfig) -> bool:
        """
        Enregistre un nouveau provider
        
        Args:
            name: Nom unique du provider
            config: Configuration du provider
            
        Returns:
            True si l'enregistrement a réussi
        """
        try:
            if name not in self.AVAILABLE_PROVIDERS:
                raise ConfigurationError(f"Provider type '{name}' not available", name)
            
            provider_class = self.AVAILABLE_PROVIDERS[name]
            provider = provider_class(config)
            
            # Test de santé initial
            status = await provider.check_health()
            if not status.is_available:
                logger.warning(f"Provider {name} registered but not healthy: {status.error_message}")
            
            self._providers[name] = provider
            self._configs[name] = config
            
            logger.info(f"Provider {name} registered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register provider {name}: {e}")
            return False
    
    def get_provider(self, name: str) -> Optional[BaseEmbeddingProvider]:
        """Récupère un provider par nom"""
        return self._providers.get(name)
    
    def get_default_provider(self) -> Optional[BaseEmbeddingProvider]:
        """Récupère le provider par défaut (le premier disponible)"""
        for provider in self._providers.values():
            if provider.status.is_available:
                return provider
        return None
    
    def list_providers(self) -> List[str]:
        """Liste tous les providers enregistrés"""
        return list(self._providers.keys())
    
    def list_available_providers(self) -> List[str]:
        """Liste les providers disponibles (en bonne santé)"""
        available = []
        for name, provider in self._providers.items():
            if provider.status.is_available:
                available.append(name)
        return available
    
    async def health_check_all(self) -> Dict[str, ProviderStatus]:
        """Vérifie la santé de tous les providers"""
        results = {}
        for name, provider in self._providers.items():
            try:
                status = await provider.check_health()
                results[name] = status
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = ProviderStatus(
                    name=name,
                    is_available=False,
                    last_check=datetime.now(),
                    error_message=str(e)
                )
        return results
    
    def get_provider_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'un provider"""
        provider = self.get_provider(name)
        if not provider:
            return None
        
        model_info = provider.get_model_info()
        status = provider.status
        
        return {
            "name": name,
            "model_info": model_info,
            "status": {
                "is_available": status.is_available,
                "last_check": status.last_check,
                "error_message": status.error_message,
                "response_time": status.response_time
            },
            "config": {
                "model": provider.config.model,
                "batch_size": provider.config.batch_size,
                "rate_limit": provider.config.rate_limit,
                "timeout": provider.config.timeout
            }
        }
    
    def get_all_providers_info(self) -> Dict[str, Dict[str, Any]]:
        """Récupère les informations de tous les providers"""
        result = {}
        for name in self._providers.keys():
            info = self.get_provider_info(name)
            if info:
                result[name] = info
        return result
    
    async def close_all(self):
        """Ferme toutes les connexions des providers"""
        for provider in self._providers.values():
            if hasattr(provider, 'close'):
                try:
                    await provider.close()
                except Exception as e:
                    logger.error(f"Error closing provider {provider.name}: {e}")
        
        logger.info("All providers closed")

# Instance globale du registry
_registry_instance: Optional[EmbeddingProviderRegistry] = None

def get_provider_registry() -> EmbeddingProviderRegistry:
    """Récupère l'instance globale du registry (singleton)"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = EmbeddingProviderRegistry()
    return _registry_instance

async def initialize_providers(auto_configure: bool = True) -> EmbeddingProviderRegistry:
    """
    Initialise et retourne le registry des providers
    
    Args:
        auto_configure: Si True, configure automatiquement à partir des variables d'env
        
    Returns:
        L'instance du registry initialisée
    """
    registry = get_provider_registry()
    await registry.initialize(auto_configure=auto_configure)
    return registry
