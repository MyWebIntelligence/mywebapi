"""
Media API Endpoints V2 SYNC

Endpoint de suppression de media pour le client V2.

Endpoints:
- DELETE /api/v2/media/{media_id} - Suppression d'un media
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from app.db.session import get_sync_db
from app.api.dependencies import get_current_active_user_sync
from app.schemas.user import User
from app.db.models import Media

logger = logging.getLogger(__name__)

router = APIRouter()


@router.delete("/{media_id}", status_code=204)
def delete_media(
    media_id: int,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync),
):
    """Suppression d'un media."""

    media = db.query(Media).filter(Media.id == media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail=f"Media {media_id} not found")

    db.delete(media)
    db.commit()
    return None
