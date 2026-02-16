"""
Endpoints pour la gestion des tags
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api import dependencies
from app.crud import crud_tag
from app.db import models
from app.schemas.tag import Tag, TagCreate, TagUpdate

router = APIRouter()

@router.post("/{land_id}/tags/", response_model=Tag)
async def create_tag(
    land_id: int,
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    tag_in: TagCreate,
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    """
    Créer un nouveau tag pour un land spécifique.
    """
    # TODO: Vérifier que l'utilisateur a accès à ce land
    tag = await crud_tag.tag.create_with_land(db=db, obj_in=tag_in, land_id=land_id)
    return tag

@router.get("/{land_id}/tags/", response_model=List[Tag])
async def read_tags(
    land_id: int,
    db: AsyncSession = Depends(dependencies.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    """
    Récupérer les tags pour un land spécifique.
    """
    # TODO: Vérifier que l'utilisateur a accès à ce land
    tags = await crud_tag.tag.get_multi_by_land(
        db=db, land_id=land_id, skip=skip, limit=limit
    )
    return tags

@router.get("/{id}", response_model=Tag)
async def read_tag(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    id: int,
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    """
    Récupérer un tag par son ID.
    """
    tag = await crud_tag.tag.get(db=db, id=id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    # TODO: Check ownership based on land
    return tag

@router.put("/{id}", response_model=Tag)
async def update_tag(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    id: int,
    tag_in: TagUpdate,
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    """
    Mettre à jour un tag.
    """
    tag = await crud_tag.tag.get(db=db, id=id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    # TODO: Check ownership based on land
    tag = await crud_tag.tag.update(db=db, db_obj=tag, obj_in=tag_in)
    return tag

@router.delete("/{id}", response_model=Tag)
async def delete_tag(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    id: int,
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    """
    Supprimer un tag.
    """
    tag = await crud_tag.tag.get(db=db, id=id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    # TODO: Check ownership based on land
    tag = await crud_tag.tag.remove(db=db, id=id)
    return tag
