"""
Schémas Pydantic pour les Médias
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .base import TimeStampedSchema
from ..db.models import MediaType


class MediaBase(BaseModel):
    """Données communes des médias exposées par l'API."""

    url: str
    type: MediaType
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    alt_text: Optional[str] = None
    format: Optional[str] = None
    color_mode: Optional[str] = None
    has_transparency: Optional[bool] = None
    aspect_ratio: Optional[float] = None
    dominant_colors: Optional[List[Dict[str, Any]]] = None
    websafe_colors: Optional[Dict[str, float]] = None
    image_hash: Optional[str] = None
    exif_data: Optional[Dict[str, Any]] = None
    analysis_error: Optional[str] = None
    processing_error: Optional[str] = None
    is_processed: Optional[bool] = None
    processed_at: Optional[datetime] = None


class MediaCreate(MediaBase):
    """Schéma pour la création d'un média."""

    expression_id: int


class MediaUpdate(BaseModel):
    """Schéma pour la mise à jour partielle d'un média."""

    alt_text: Optional[str] = None


class Media(TimeStampedSchema, MediaBase):
    """Schéma renvoyé par l'API pour un média."""

    id: int
    expression_id: int


class MediaAnalysisRequest(BaseModel):
    """Schéma pour la demande d'analyse de médias."""
    
    depth: Optional[int] = None
    minrel: Optional[float] = None


class MediaAnalysisResponse(BaseModel):
    """Schéma de réponse pour l'analyse de médias."""
    
    land_id: int
    land_name: str
    total_expressions: int
    filtered_expressions: int
    total_media: int
    analyzed_media: int
    failed_analysis: int
    results: List[Dict[str, Any]]
    processing_time: float
    filters_applied: Dict[str, Any]
