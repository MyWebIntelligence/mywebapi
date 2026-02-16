"""
Opérations CRUD pour les médias avec normalisation des métadonnées d'analyse.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models

logger = logging.getLogger(__name__)


class CRUDMedia:
    def __init__(self) -> None:
        self._allowed_fields = {column.key for column in models.Media.__table__.columns}

    async def create_media(
        self,
        db: AsyncSession,
        expression_id: int,
        media_data: Dict[str, Any],
    ) -> models.Media:
        """
        Crée un nouvel enregistrement de média dans la base de données en filtrant
        et en normalisant les métadonnées fournies par le moteur de crawl.
        """
        prepared_data = self._prepare_media_data(media_data)
        media_obj = models.Media(expression_id=expression_id, **prepared_data)
        db.add(media_obj)
        await db.commit()
        await db.refresh(media_obj)
        return media_obj

    async def media_exists(self, db: AsyncSession, expression_id: int, url: str) -> bool:
        """
        Vérifie si un média existe déjà pour une expression donnée.
        """
        url_hash = models.Media.compute_url_hash(url)
        query = select(models.Media).where(
            models.Media.expression_id == expression_id,
            models.Media.url_hash == url_hash,
            models.Media.url == url,
        )
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    async def delete_media_for_expression(self, db: AsyncSession, expression_id: int) -> None:
        """
        Supprime tous les médias associés à une expression.
        """
        stmt = delete(models.Media).where(models.Media.expression_id == expression_id)
        await db.execute(stmt)
        await db.commit()

    def _prepare_media_data(self, media_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Nettoie et enrichit les données d'un média avant insertion.
        """
        data = dict(media_data)

        url_value = data.get("url")
        if url_value:
            data["url_hash"] = models.Media.compute_url_hash(url_value)

        # Harmonise le type de média
        media_type_value = data.pop("media_type", None)
        data["type"] = self._normalize_media_type(data.get("type") or media_type_value)

        # Détermine l'état de traitement
        if data.get("analysis_error"):
            data.setdefault("is_processed", False)
            data.setdefault("processing_error", data["analysis_error"])
        else:
            has_analysis_payload = any(
                data.get(key) is not None
                for key in ("width", "height", "file_size", "format", "dominant_colors", "image_hash")
            )
            if has_analysis_payload:
                data.setdefault("is_processed", True)
                data.setdefault("processed_at", datetime.now(timezone.utc))
                data.setdefault("processing_error", None)

        # Filtre les champs inconnus pour éviter les erreurs SQLAlchemy
        filtered_data = {key: value for key, value in data.items() if key in self._allowed_fields}
        unexpected_keys = set(data.keys()) - self._allowed_fields
        if unexpected_keys:
            logger.debug("Ignored non model fields for media: %s", ", ".join(sorted(unexpected_keys)))

        return filtered_data

    @staticmethod
    def _normalize_media_type(media_type: Any) -> models.MediaType:
        """
        Transforme différents formats de type (enum, str, None) en MediaType cohérent.
        """
        if isinstance(media_type, models.MediaType):
            return media_type

        if isinstance(media_type, str):
            candidate = media_type.strip()
            if not candidate:
                return models.MediaType.IMAGE

            # Essaye d'abord sur le nom de l'enum (IMAGE, VIDEO...)
            upper_candidate = candidate.upper()
            if upper_candidate in models.MediaType.__members__:
                return models.MediaType[upper_candidate]

            # Puis sur la valeur ('img', 'video'...)
            lower_candidate = candidate.lower()
            for enum_value in models.MediaType:
                if enum_value.value == lower_candidate:
                    return enum_value

        return models.MediaType.IMAGE
    
    async def update_media_analysis(
        self,
        db: AsyncSession,
        media_id: int,
        analysis_data: Dict[str, Any]
    ) -> models.Media:
        """
        Met à jour un média avec les résultats d'analyse.
        """
        prepared_data = self._prepare_media_data(analysis_data)
        prepared_data['is_processed'] = True
        prepared_data['processed_at'] = datetime.now(timezone.utc)
        
        query = select(models.Media).where(models.Media.id == media_id)
        result = await db.execute(query)
        media_obj = result.scalar_one_or_none()
        
        if media_obj:
            for key, value in prepared_data.items():
                if hasattr(media_obj, key):
                    setattr(media_obj, key, value)
            
            await db.commit()
            await db.refresh(media_obj)
        
        return media_obj


media = CRUDMedia()
