"""
Schémas Pydantic pour les embeddings et providers
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class EmbeddingProviderStatus(str, Enum):
    """Statuts des providers d'embeddings."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"

class EmbeddingProviderInfo(BaseModel):
    """Informations sur un provider d'embeddings."""
    name: str
    model: str
    dimensions: int
    batch_size: int
    rate_limit: int
    status: EmbeddingProviderStatus
    last_error: Optional[str] = None

class EmbeddingModelInfo(BaseModel):
    """Informations sur un modèle d'embedding."""
    name: str
    dimensions: int
    max_tokens: int
    provider: str
    description: Optional[str] = None

class EmbeddingGenerateRequest(BaseModel):
    """Requête pour générer des embeddings."""
    land_id: int = Field(..., gt=0)
    provider: str = Field("openai", pattern=r'^(openai|mistral|huggingface|ollama)$')
    model: Optional[str] = None
    force_regenerate: bool = False
    batch_size: int = Field(100, ge=1, le=500)
    extract_paragraphs: bool = True  # Extraire les paragraphes si pas déjà fait
    confirm_external_processing: bool = Field(
        False,
        description="Doit être activé pour autoriser l'envoi du contenu vers un provider externe"
    )

class EmbeddingGenerateResponse(BaseModel):
    """Réponse pour génération d'embeddings."""
    task_id: str
    status: str
    message: str
    estimated_time: Optional[int]  # en secondes
    land_id: int
    provider: str
    total_expressions: Optional[int] = None

class EmbeddingProgress(BaseModel):
    """Progression de génération d'embeddings."""
    task_id: str
    status: str
    current: int
    total: int
    percentage: float
    message: str
    provider: Optional[str]
    model: Optional[str]
    batch_info: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None

class EmbeddingResult(BaseModel):
    """Résultat d'embedding pour un texte."""
    text: str
    embedding: List[float]
    model: str
    provider: str
    tokens_used: Optional[int] = None
    processing_time: Optional[float] = None

class BatchEmbeddingResult(BaseModel):
    """Résultat d'embedding pour un batch de textes."""
    results: List[EmbeddingResult]
    total_texts: int
    successful_texts: int
    failed_texts: int
    total_tokens: Optional[int] = None
    total_processing_time: float
    errors: List[str] = []

class EmbeddingStats(BaseModel):
    """Statistiques des embeddings pour un land."""
    land_id: int
    total_expressions: int
    total_paragraphs: int
    paragraphs_with_embeddings: int
    embedding_coverage: float
    providers_used: Dict[str, int]  # provider -> count
    models_used: Dict[str, int]     # model -> count
    avg_embedding_dimensions: Optional[float]
    total_tokens_used: Optional[int]
    last_updated: Optional[datetime]

class EmbeddingHealthCheck(BaseModel):
    """Résultat du health check des providers."""
    providers: Dict[str, Dict[str, Any]]
    total_available: int
    total_configured: int
    overall_status: str
    checked_at: datetime

class EmbeddingBatchRequest(BaseModel):
    """Requête pour traitement en lot des embeddings."""
    expression_ids: List[int] = Field(..., min_items=1, max_items=1000)
    provider: str = Field("openai", pattern=r'^(openai|mistral|huggingface|ollama)$')
    model: Optional[str] = None
    force_regenerate: bool = False
    extract_paragraphs_first: bool = True
    confirm_external_processing: bool = Field(
        False,
        description="Doit être activé pour autoriser l'envoi du contenu vers un provider externe"
    )

class EmbeddingBatchResponse(BaseModel):
    """Réponse pour traitement en lot."""
    task_id: str
    status: str
    total_expressions: int
    estimated_paragraphs: Optional[int]
    estimated_time: Optional[int]
    message: str

class EmbeddingSimilarityRequest(BaseModel):
    """Requête pour calcul de similarités après embeddings."""
    land_id: int = Field(..., gt=0)
    threshold: float = Field(0.7, ge=0.0, le=1.0)
    method: str = Field("cosine", pattern=r'^(cosine|euclidean|manhattan)$')
    use_faiss: bool = True
    max_comparisons: Optional[int] = Field(None, gt=0)
    provider_filter: Optional[str] = None  # Filtrer par provider d'embedding

class EmbeddingSimilarityResponse(BaseModel):
    """Réponse pour calcul de similarités."""
    task_id: str
    status: str
    land_id: int
    total_paragraphs: int
    estimated_comparisons: int
    method: str
    threshold: float
    message: str

class ProviderConfigRequest(BaseModel):
    """Requête pour configurer un provider."""
    name: str = Field(..., pattern=r'^[a-z_]+$')
    model: str
    api_key: Optional[str] = None  # Pour les tests, en production utiliser variables d'env
    base_url: Optional[str] = None
    batch_size: int = Field(100, ge=1, le=1000)
    rate_limit: int = Field(100, ge=1)
    timeout: int = Field(30, ge=5, le=300)

class ProviderConfigResponse(BaseModel):
    """Réponse pour configuration de provider."""
    name: str
    status: str
    message: str
    info: Optional[EmbeddingProviderInfo] = None
