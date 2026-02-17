"""
Endpoints pour la gestion des tags et du contenu taggé
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from app.api import dependencies
from app.crud import crud_tag
from app.db import models
from app.db.models import TaggedContent, Tag, Expression
from app.schemas.tag import Tag as TagSchema, TagCreate, TagUpdate

router = APIRouter()


# ──────────────────────────────────────────────────
# Tag CRUD
# ──────────────────────────────────────────────────

@router.post("/{land_id}/tags/", response_model=TagSchema)
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
    tag = await crud_tag.tag.create_with_land(db=db, obj_in=tag_in, land_id=land_id)
    return tag

@router.get("/{land_id}/tags/", response_model=List[TagSchema])
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
    tags = await crud_tag.tag.get_multi_by_land(
        db=db, land_id=land_id, skip=skip, limit=limit
    )
    return tags


# ──────────────────────────────────────────────────
# Tagged Content CRUD
# ──────────────────────────────────────────────────

@router.get("/tagged-content")
async def get_tagged_content(
    expression_id: Optional[int] = Query(None),
    tag_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Récupérer le contenu taggé par expression ou par tag.
    """
    q = select(TaggedContent, Tag.name, Tag.color).join(
        Tag, Tag.id == TaggedContent.tag_id
    )
    if expression_id is not None:
        q = q.filter(TaggedContent.expression_id == expression_id)
    if tag_id is not None:
        q = q.filter(TaggedContent.tag_id == tag_id)

    result = await db.execute(q)
    rows = result.all()

    return [
        {
            "id": tc.id,
            "tag_id": tc.tag_id,
            "tag_name": tag_name,
            "tag_color": tag_color,
            "expression_id": tc.expression_id,
            "text": tc.text,
            "start_position": tc.from_char,
            "end_position": tc.to_char,
            "from_char": tc.from_char,
            "to_char": tc.to_char,
        }
        for tc, tag_name, tag_color in rows
    ]


@router.get("/{land_id}/tagged-content")
async def get_land_tagged_content(
    land_id: int,
    db: AsyncSession = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Récupérer tout le contenu taggé d'un land.
    """
    q = (
        select(TaggedContent, Tag.name, Tag.color, Expression.title)
        .join(Tag, Tag.id == TaggedContent.tag_id)
        .join(Expression, Expression.id == TaggedContent.expression_id)
        .filter(Expression.land_id == land_id)
    )

    result = await db.execute(q)
    rows = result.all()

    return [
        {
            "id": tc.id,
            "tag_id": tc.tag_id,
            "tag_name": tag_name,
            "tag_color": tag_color,
            "expression_id": tc.expression_id,
            "expression_title": expr_title,
            "text": tc.text,
            "start_position": tc.from_char,
            "end_position": tc.to_char,
            "from_char": tc.from_char,
            "to_char": tc.to_char,
        }
        for tc, tag_name, tag_color, expr_title in rows
    ]


@router.post("/tagged-content")
async def create_tagged_content(
    data: dict,
    db: AsyncSession = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Créer un contenu taggé (annotation de texte).
    Accepte start_position/end_position ou from_char/to_char.
    """
    tag_id = data.get("tag_id")
    expression_id = data.get("expression_id")
    text = data.get("text", "")
    from_char = data.get("from_char") or data.get("start_position", 0)
    to_char = data.get("to_char") or data.get("end_position", 0)

    if not tag_id or not expression_id:
        raise HTTPException(status_code=422, detail="tag_id and expression_id are required")

    tc = TaggedContent(
        tag_id=tag_id,
        expression_id=expression_id,
        text=text,
        from_char=from_char,
        to_char=to_char,
    )
    db.add(tc)
    await db.commit()
    await db.refresh(tc)

    return {
        "id": tc.id,
        "tag_id": tc.tag_id,
        "expression_id": tc.expression_id,
        "text": tc.text,
        "from_char": tc.from_char,
        "to_char": tc.to_char,
    }


@router.put("/tagged-content/{tc_id}")
async def update_tagged_content(
    tc_id: int,
    data: dict,
    db: AsyncSession = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Mettre à jour un contenu taggé.
    """
    result = await db.execute(
        select(TaggedContent).filter(TaggedContent.id == tc_id)
    )
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(status_code=404, detail="Tagged content not found")

    if "tag_id" in data:
        tc.tag_id = data["tag_id"]
    if "text" in data:
        tc.text = data["text"]

    await db.commit()
    await db.refresh(tc)

    return {
        "id": tc.id,
        "tag_id": tc.tag_id,
        "expression_id": tc.expression_id,
        "text": tc.text,
        "from_char": tc.from_char,
        "to_char": tc.to_char,
    }


@router.delete("/tagged-content/{tc_id}", status_code=204)
async def delete_tagged_content(
    tc_id: int,
    db: AsyncSession = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Supprimer un contenu taggé.
    """
    result = await db.execute(
        select(TaggedContent).filter(TaggedContent.id == tc_id)
    )
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(status_code=404, detail="Tagged content not found")

    await db.delete(tc)
    await db.commit()
    return None


# ──────────────────────────────────────────────────
# Single Tag CRUD (must be AFTER /tagged-content routes)
# ──────────────────────────────────────────────────

@router.get("/{id}", response_model=TagSchema)
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
    return tag

@router.put("/{id}", response_model=TagSchema)
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
    tag = await crud_tag.tag.update(db=db, db_obj=tag, obj_in=tag_in)
    return tag

@router.delete("/{id}", response_model=TagSchema)
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
    tag = await crud_tag.tag.remove(db=db, id=id)
    return tag
