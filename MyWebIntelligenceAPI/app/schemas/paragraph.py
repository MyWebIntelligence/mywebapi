"""
Schémas Pydantic pour les paragraphes et embeddings
"""

from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class ParagraphBase(BaseModel):
    """Schéma de base pour les paragraphes."""
    text: str = Field(..., min_length=1, max_length=50000)
    position: int = Field(0, ge=0)
    language: Optional[str] = Field(None, pattern=r'^[a-z]{2}$')
    
    @validator('text')
    def validate_text(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty or whitespace only')
        return v.strip()

class ParagraphCreate(ParagraphBase):
    """Schéma pour créer un paragraphe."""
    expression_id: int = Field(..., gt=0)

class ParagraphUpdate(BaseModel):
    """Schéma pour mettre à jour un paragraphe."""
    text: Optional[str] = Field(None, min_length=1, max_length=50000)
    language: Optional[str] = Field(None, pattern=r'^[a-z]{2}$')

class ParagraphInDB(ParagraphBase):
    """Schéma pour paragraphe en base de données."""
    id: int
    expression_id: int
    text_hash: str
    word_count: Optional[int]
    char_count: Optional[int]
    sentence_count: Optional[int]
    reading_level: Optional[float]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class ParagraphWithEmbedding(ParagraphInDB):
    """Schéma pour paragraphe avec embedding."""
    embedding: Optional[List[float]]
    embedding_provider: Optional[str]
    embedding_model: Optional[str]
    embedding_dimensions: Optional[int]
    embedding_computed_at: Optional[datetime]
    
    @validator('embedding')
    def validate_embedding(cls, v):
        if v is not None:
            if len(v) == 0:
                raise ValueError('Embedding cannot be empty list')
            if not all(isinstance(x, (int, float)) for x in v):
                raise ValueError('Embedding must contain only numbers')
        return v

class ParagraphResponse(ParagraphWithEmbedding):
    """Schéma de réponse API pour paragraphe."""
    preview_text: str
    has_embedding: bool
    
    @validator('preview_text', pre=True, always=True)
    def set_preview_text(cls, v, values):
        text = values.get('text', '')
        return text[:100] + "..." if len(text) > 100 else text
    
    @validator('has_embedding', pre=True, always=True)
    def set_has_embedding(cls, v, values):
        embedding = values.get('embedding')
        return embedding is not None and len(embedding) > 0

class ParagraphStats(BaseModel):
    """Statistiques pour un paragraphe."""
    total_paragraphs: int
    paragraphs_with_embeddings: int
    embedding_coverage: float
    avg_word_count: Optional[float]
    avg_reading_level: Optional[float]
    languages: Dict[str, int]  # langue -> count

# Schémas pour embeddings
class EmbeddingRequest(BaseModel):
    """Requête pour générer des embeddings."""
    provider: str = Field("openai", pattern=r'^(openai|mistral|huggingface|ollama)$')
    model: Optional[str] = None
    force_regenerate: bool = False
    batch_size: int = Field(100, ge=1, le=500)

class EmbeddingResponse(BaseModel):
    """Réponse pour génération d'embeddings."""
    task_id: str
    status: str
    message: str
    estimated_time: Optional[int]  # en secondes

class EmbeddingProgress(BaseModel):
    """Progression de génération d'embeddings."""
    task_id: str
    status: str
    current: int
    total: int
    percentage: float
    message: str
    provider: Optional[str]
    errors: List[str] = []

# Schémas pour similarités
class SimilarityBase(BaseModel):
    """Schéma de base pour les similarités."""
    paragraph1_id: int
    paragraph2_id: int
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    method: str = Field("cosine", pattern=r'^(cosine|euclidean|manhattan|jaccard)$')

class SimilarityCreate(SimilarityBase):
    """Schéma pour créer une similarité."""
    pass

class SimilarityInDB(SimilarityBase):
    """Schéma pour similarité en base de données."""
    id: int
    computed_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SimilarityResponse(SimilarityInDB):
    """Schéma de réponse API pour similarité."""
    paragraph1_preview: Optional[str]
    paragraph2_preview: Optional[str]

class SimilarityRequest(BaseModel):
    """Requête pour calculer des similarités."""
    land_id: int
    threshold: float = Field(0.7, ge=0.0, le=1.0)
    method: str = Field("cosine", pattern=r'^(cosine|euclidean|manhattan)$')
    use_faiss: bool = True
    batch_size: int = Field(1000, ge=100, le=10000)

class SimilaritySearchRequest(BaseModel):
    """Requête pour rechercher des paragraphes similaires."""
    paragraph_id: int
    limit: int = Field(10, ge=1, le=100)
    threshold: float = Field(0.7, ge=0.0, le=1.0)
    include_text: bool = True

class SimilaritySearchResponse(BaseModel):
    """Réponse de recherche de similarité."""
    query_paragraph: ParagraphResponse
    similar_paragraphs: List[Dict[str, Any]]  # Contient paragraphe + score
    total_found: int
    search_time: float  # en secondes
