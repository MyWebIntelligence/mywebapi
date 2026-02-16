"""
Base abstract class pour les providers d'embeddings
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingResult:
    """Résultat d'embedding pour un texte"""
    text: str
    embedding: List[float]
    model: str
    provider: str
    tokens_used: Optional[int] = None
    processing_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass 
class ProviderConfig:
    """Configuration d'un provider"""
    name: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    batch_size: int = 100
    rate_limit: int = 100  # requests per minute
    timeout: int = 30
    dimensions: Optional[int] = None
    max_tokens: Optional[int] = None
    extra_params: Optional[Dict[str, Any]] = None

@dataclass
class ProviderStatus:
    """Statut d'un provider"""
    name: str
    is_available: bool
    last_check: datetime
    error_message: Optional[str] = None
    response_time: Optional[float] = None
    rate_limit_remaining: Optional[int] = None

class BaseEmbeddingProvider(ABC):
    """Classe de base abstraite pour tous les providers d'embeddings"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name
        self.model = config.model
        self._status = ProviderStatus(
            name=config.name,
            is_available=False,
            last_check=datetime.now()
        )
    
    @property
    def status(self) -> ProviderStatus:
        """Retourne le statut actuel du provider"""
        return self._status
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> EmbeddingResult:
        """
        Génère un embedding pour un texte unique
        
        Args:
            text: Le texte à encoder
            
        Returns:
            EmbeddingResult avec l'embedding généré
            
        Raises:
            ProviderError: En cas d'erreur du provider
        """
        pass
    
    @abstractmethod
    async def generate_embeddings_batch(
        self, 
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[EmbeddingResult]:
        """
        Génère des embeddings pour une liste de textes
        
        Args:
            texts: Liste des textes à encoder
            batch_size: Taille du batch (optionnel, utilise config par défaut)
            
        Returns:
            Liste des EmbeddingResult
            
        Raises:
            ProviderError: En cas d'erreur du provider
        """
        pass
    
    @abstractmethod
    async def check_health(self) -> ProviderStatus:
        """
        Vérifie la santé du provider
        
        Returns:
            ProviderStatus avec les informations de santé
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Retourne les informations sur le modèle utilisé
        
        Returns:
            Dictionnaire avec les informations du modèle
        """
        pass
    
    def clean_text(self, text: str) -> str:
        """Nettoie le texte avant embedding"""
        from app.utils.text_utils import clean_text_for_embedding
        return clean_text_for_embedding(text)
    
    def validate_text(self, text: str) -> bool:
        """Valide qu'un texte peut être traité"""
        if not text or not text.strip():
            return False
        
        max_tokens = self.config.max_tokens
        if max_tokens and len(text.split()) > max_tokens:
            logger.warning(f"Text too long: {len(text.split())} tokens > {max_tokens}")
            return False
            
        return True
    
    def estimate_tokens(self, text: str) -> int:
        """Estimation approximative du nombre de tokens"""
        # Approximation simple : 1 token ≈ 4 caractères
        return len(text) // 4
    
    def update_status(self, is_available: bool, error_message: Optional[str] = None, response_time: Optional[float] = None):
        """Met à jour le statut du provider"""
        self._status = ProviderStatus(
            name=self.name,
            is_available=is_available,
            last_check=datetime.now(),
            error_message=error_message,
            response_time=response_time
        )

class ProviderError(Exception):
    """Exception pour les erreurs de provider"""
    
    def __init__(self, message: str, provider: str, error_code: Optional[str] = None):
        self.message = message
        self.provider = provider
        self.error_code = error_code
        super().__init__(f"{provider}: {message}")

class RateLimitError(ProviderError):
    """Exception pour les erreurs de rate limiting"""
    
    def __init__(self, message: str, provider: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(message, provider, "RATE_LIMIT")

class ConfigurationError(ProviderError):
    """Exception pour les erreurs de configuration"""
    
    def __init__(self, message: str, provider: str):
        super().__init__(message, provider, "CONFIG_ERROR")

class ModelNotFoundError(ProviderError):
    """Exception pour les modèles non trouvés"""
    
    def __init__(self, message: str, provider: str, model: str):
        self.model = model
        super().__init__(message, provider, "MODEL_NOT_FOUND")