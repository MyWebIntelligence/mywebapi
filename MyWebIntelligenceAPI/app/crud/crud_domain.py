"""
Fonctions CRUD pour les Domaines
"""
import json
import re
from urllib.parse import urlparse
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import models
from app.schemas.domain import DomainCreate


def _load_heuristics() -> Dict[str, str]:
    """Load heuristics from settings. Returns {domain_suffix: regex_pattern}."""
    from app.config import settings
    try:
        return json.loads(settings.HEURISTICS)
    except Exception:
        return {}


class CRUDDomain:
    def get_domain_name(self, url: str, heuristics: Optional[Dict[str, str]] = None) -> str:
        """
        Extrait le nom de domaine d'une URL, en appliquant des heuristiques.

        Args:
            url: URL a analyser
            heuristics: dict {domain_suffix: regex_pattern}. Si None, charge depuis settings.
        """
        try:
            domain_name = urlparse(url).netloc
            if heuristics is None:
                heuristics = _load_heuristics()
            for key, pattern in heuristics.items():
                if domain_name.endswith(key):
                    matches = re.findall(pattern, url)
                    if matches:
                        domain_name = matches[0]
                    break
            return domain_name
        except Exception:
            return ""

    async def get_or_create(self, db: AsyncSession, name: str, land_id: int) -> models.Domain:
        """
        Récupère un domaine par nom ET land_id ou le crée s'il n'existe pas.
        """
        query = select(models.Domain).where(
            models.Domain.name == name,
            models.Domain.land_id == land_id  # FIX: Filter by land_id too!
        )
        result = await db.execute(query)
        db_domain = result.scalar_one_or_none()

        if db_domain:
            return db_domain

        domain_in = DomainCreate(name=name, land_id=land_id)
        new_domain = models.Domain(**domain_in.model_dump())
        db.add(new_domain)
        await db.flush()  # FIX: Use flush instead of commit to avoid nested transactions
        await db.refresh(new_domain)
        return new_domain

    async def get_by_id(self, db: AsyncSession, domain_id: int) -> Optional[models.Domain]:
        """Récupère un domaine par ID"""
        return await db.get(models.Domain, domain_id)

    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[models.Domain]:
        """Récupère un domaine par nom"""
        query = select(models.Domain).where(models.Domain.name == name)
        result = await db.execute(query)
        return result.scalar_one_or_none()

domain = CRUDDomain()
