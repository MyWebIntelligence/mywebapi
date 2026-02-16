"""
Schémas Pydantic pour le contenu taggé
"""

from pydantic import BaseModel
from typing import Optional
from .base import TimeStampedSchema

# Schéma de base pour le contenu taggé
class TaggedContentBase(BaseModel):
    tag_id: int
    expression_id: int
    text: str
    from_char: int
    to_char: int
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    confidence: Optional[float] = None

# Schéma pour la création de contenu taggé
class TaggedContentCreate(TaggedContentBase):
    pass

# Schéma pour la mise à jour de contenu taggé
class TaggedContentUpdate(BaseModel):
    tag_id: Optional[int] = None
    text: Optional[str] = None

# Schéma pour l'affichage de contenu taggé
class TaggedContent(TimeStampedSchema):
    id: int
    tag_id: int
    expression_id: int
    text: str
