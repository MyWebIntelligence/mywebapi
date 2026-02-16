"""
Schémas Pydantic de base
"""

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class BaseSchema(BaseModel):
    """Schéma de base avec configuration ORM"""
    model_config = ConfigDict(from_attributes=True)

class TimeStampedSchema(BaseSchema):
    """Schéma avec timestamps"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
