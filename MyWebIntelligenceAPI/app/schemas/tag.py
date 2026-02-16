"""
Schémas Pydantic pour les Tags
"""

from pydantic import BaseModel
from typing import Optional, List
from .base import TimeStampedSchema

# Schéma de base pour un Tag
class TagBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    parent_id: Optional[int] = None

# Schéma pour la création d'un Tag
class TagCreate(TagBase):
    land_id: int

# Schéma pour la mise à jour d'un Tag
class TagUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    parent_id: Optional[int] = None
    sorting: Optional[int] = None

# Schéma pour l'affichage d'un Tag
class Tag(TimeStampedSchema):
    id: int
    land_id: int
    parent_id: Optional[int] = None
    name: str
    color: Optional[str] = None
    children: List['Tag'] = []

# Mise à jour de la référence avant
Tag.model_rebuild()
