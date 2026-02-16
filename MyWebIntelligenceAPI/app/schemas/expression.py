"""
Schémas Pydantic pour les Expressions
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .base import TimeStampedSchema

# Schéma de base pour une Expression
class ExpressionBase(BaseModel):
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    relevance: Optional[float] = None
    depth: Optional[int] = None
    lang: Optional[str] = None

# Schéma pour la création d'une Expression
class ExpressionCreate(ExpressionBase):
    land_id: int
    domain_id: int

# Schéma pour la mise à jour d'une Expression
class ExpressionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    content: Optional[str] = None  # HTML brut (legacy field)
    readable: Optional[str] = None
    relevance: Optional[float] = None
    http_status: Optional[int] = None  # Must match DB type (INTEGER)
    lang: Optional[str] = None
    language: Optional[str] = None  # Alias for lang
    crawled_at: Optional[datetime] = None
    readable_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    valid_llm: Optional[str] = None
    valid_model: Optional[str] = None
    seo_rank: Optional[str] = None

    # Sentiment Analysis fields
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    sentiment_confidence: Optional[float] = None
    sentiment_status: Optional[str] = None
    sentiment_model: Optional[str] = None
    sentiment_computed_at: Optional[datetime] = None

# Schéma pour l'affichage d'une Expression
class Expression(TimeStampedSchema):
    id: int
    land_id: int
    domain_id: int
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    readable: Optional[str] = None
    http_status: Optional[int] = None
    relevance: Optional[float] = None
    depth: Optional[int] = None
    lang: Optional[str] = None
    readable_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    valid_llm: Optional[str] = None
    valid_model: Optional[str] = None
    seo_rank: Optional[str] = None

    # Sentiment Analysis fields
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    sentiment_confidence: Optional[float] = None
    sentiment_status: Optional[str] = None
    sentiment_model: Optional[str] = None
    sentiment_computed_at: Optional[datetime] = None
