"""
Endpoints CRUD des paragraphes pour l'API v1.

Ces routes couvrent les opérations de base prévues au Sprint 1-2
avant l'arrivée des fonctionnalités avancées de la v2.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_active_user
from app.db.models import Expression, Paragraph
from app.db.session import get_sync_db
from app.schemas.paragraph import (
    ParagraphCreate,
    ParagraphResponse,
    ParagraphUpdate,
)
from app.schemas.user import User
from app.crud.crud_paragraph import paragraph as paragraph_crud

router = APIRouter()


def _ensure_expression_access(db: Session, expression_id: int, user: User) -> Expression:
    expression = (
        db.query(Expression)
        .options(joinedload(Expression.land))
        .filter(Expression.id == expression_id)
        .first()
    )
    if not expression:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expression not found")

    land_owner_id = getattr(expression.land, "owner_id", None) if expression.land else None
    user_id = getattr(user, "id", None)
    if not getattr(user, "is_admin", False) and land_owner_id is not None and land_owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this expression")
    return expression


def _ensure_paragraph_access(db: Session, paragraph_id: int, user: User) -> Paragraph:
    paragraph = db.query(Paragraph).filter(Paragraph.id == paragraph_id).first()
    if not paragraph:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paragraph not found")

    _ensure_expression_access(db, paragraph.expression_id, user)
    return paragraph


@router.get(
    "/expression/{expression_id}/paragraphs",
    response_model=List[ParagraphResponse],
    summary="Lister les paragraphes d'une expression",
)
def list_paragraphs_by_expression(
    expression_id: int = Path(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_embeddings: bool = Query(False),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user),
):
    expression = _ensure_expression_access(db, expression_id, current_user)
    paragraphs = paragraph_crud.get_by_expression(
        db,
        expression.id,
        skip=skip,
        limit=limit,
        include_embeddings=include_embeddings,
    )
    return paragraphs


@router.get(
    "/paragraph/{paragraph_id}",
    response_model=ParagraphResponse,
    summary="Récupérer un paragraphe par son identifiant",
)
def get_paragraph(
    paragraph_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user),
):
    paragraph = _ensure_paragraph_access(db, paragraph_id, current_user)
    return paragraph


@router.post(
    "/expression/{expression_id}/paragraphs",
    response_model=ParagraphResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un paragraphe pour une expression",
)
def create_paragraph(
    paragraph_data: ParagraphCreate,
    expression_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user),
):
    expression = _ensure_expression_access(db, expression_id, current_user)

    # Forcer l'ID d'expression depuis le path pour éviter les incohérences
    paragraph_data.expression_id = expression.id
    created = paragraph_crud.create_with_analysis(db, paragraph_data, analyze_text=True)
    return created


@router.put(
    "/paragraph/{paragraph_id}",
    response_model=ParagraphResponse,
    summary="Mettre à jour un paragraphe",
)
def update_paragraph(
    paragraph_update: ParagraphUpdate,
    paragraph_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user),
):
    paragraph = _ensure_paragraph_access(db, paragraph_id, current_user)
    updated = paragraph_crud.update(db, db_obj=paragraph, obj_in=paragraph_update)
    return updated


@router.delete(
    "/paragraph/{paragraph_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un paragraphe",
)
def delete_paragraph(
    paragraph_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user),
):
    paragraph = _ensure_paragraph_access(db, paragraph_id, current_user)
    paragraph_crud.remove(db, id=paragraph.id)
    return None
