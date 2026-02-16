from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

#
# NOTE: Ce fichier a été généré en se basant sur l'analyse des endpoints
# et du plan de développement. Il représente une structure plausible
# pour les schémas Pydantic de l'application.
#

# --- Schémas pour la création/mise à jour ---

# Attributs de base partagés pour un Land
class LandBase(BaseModel):
    name: str
    description: Optional[str] = None

# Schéma pour la création d'un Land (utilisé dans le body de POST)
class LandCreate(LandBase):
    lang: List[str] = ["fr"]

# --- Schéma pour la réponse de l'API ---
# C'est le modèle utilisé pour sérialiser les objets Land depuis la base de données
# et les renvoyer dans les réponses API (ex: GET /lands/{id}).
class Land(LandBase):
    id: int
    owner_id: int
    lang: List[str] 
    crawl_status: str
    total_expressions: int
    total_domains: int
    last_crawl: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True