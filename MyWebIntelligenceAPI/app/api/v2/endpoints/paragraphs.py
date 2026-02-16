"""
API endpoints pour la gestion des paragraphes et embeddings
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from app.api.dependencies import get_current_active_user
# V2 Simplification: embedding_service moved to projetV3
# from app.services.embedding_service import EmbeddingService
from app.services.text_processor_service import TextProcessorService
from app.crud.crud_paragraph import paragraph as paragraph_crud
from app.db.session import get_sync_db
from app.db.models import Land, Expression, Paragraph
from app.schemas.user import User
from app.schemas.paragraph import (
    ParagraphResponse,
    ParagraphStats,
    ParagraphCreate,
    ParagraphUpdate
)
from app.schemas.embedding import (
    EmbeddingGenerateRequest,
    EmbeddingGenerateResponse,
    EmbeddingStats,
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingHealthCheck
)
from app.core.settings import embeddings_settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Services
# V2: Embedding disabled (moved to projetV3)
# embedding_service = EmbeddingService()


def _ensure_land_access(db: Session, land_id: int, user: User) -> Land:
    land = db.query(Land).filter(Land.id == land_id).first()
    if not land:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    if not getattr(user, "is_admin", False) and land.owner_id != getattr(user, "id", None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this land")
    return land


def _ensure_expression_access(db: Session, expression_id: int, user: User) -> Expression:
    expression = db.query(Expression).filter(Expression.id == expression_id).first()
    if not expression:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expression not found")
    _ensure_land_access(db, expression.land_id, user)
    return expression


def _ensure_paragraph_access(db: Session, paragraph_id: int, user: User) -> Paragraph:
    paragraph = db.query(Paragraph).filter(Paragraph.id == paragraph_id).first()
    if not paragraph:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paragraph not found")
    _ensure_expression_access(db, paragraph.expression_id, user)
    return paragraph

@router.get("/land/{land_id}/paragraphs", response_model=List[ParagraphResponse])
async def get_paragraphs_by_land(
    land_id: int = Path(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    with_embeddings_only: bool = Query(False),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Récupère les paragraphes d'un land"""
    try:
        _ensure_land_access(db, land_id, current_user)
        paragraphs = paragraph_crud.get_by_land(
            db, 
            land_id, 
            skip=skip, 
            limit=limit,
            with_embeddings_only=with_embeddings_only
        )
        return paragraphs
    except Exception as e:
        logger.error(f"Error retrieving paragraphs for land {land_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/expression/{expression_id}/paragraphs", response_model=List[ParagraphResponse])
async def get_paragraphs_by_expression(
    expression_id: int = Path(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_embeddings: bool = Query(False),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Récupère les paragraphes d'une expression"""
    try:
        _ensure_expression_access(db, expression_id, current_user)
        
        paragraphs = paragraph_crud.get_by_expression(
            db, 
            expression_id, 
            skip=skip, 
            limit=limit,
            include_embeddings=include_embeddings
        )
        return paragraphs
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving paragraphs for expression {expression_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/paragraph/{paragraph_id}", response_model=ParagraphResponse)
async def get_paragraph(
    paragraph_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Récupère un paragraphe spécifique"""
    paragraph = _ensure_paragraph_access(db, paragraph_id, current_user)
    return paragraph

@router.post("/expression/{expression_id}/paragraphs", response_model=ParagraphResponse)
async def create_paragraph(
    paragraph_data: ParagraphCreate,
    expression_id: int = Path(..., gt=0),
    analyze_text: bool = Query(True),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Crée un nouveau paragraphe"""
    try:
        _ensure_expression_access(db, expression_id, current_user)
        
        # Mettre à jour l'ID d'expression
        paragraph_data.expression_id = expression_id
        
        paragraph = paragraph_crud.create_with_analysis(
            db, 
            paragraph_data, 
            analyze_text=analyze_text
        )
        return paragraph
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating paragraph: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/paragraph/{paragraph_id}", response_model=ParagraphResponse)
async def update_paragraph(
    paragraph_update: ParagraphUpdate,
    paragraph_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Met à jour un paragraphe"""
    try:
        paragraph = _ensure_paragraph_access(db, paragraph_id, current_user)
        
        updated_paragraph = paragraph_crud.update(db, db_obj=paragraph, obj_in=paragraph_update)
        return updated_paragraph
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating paragraph {paragraph_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/paragraph/{paragraph_id}")
async def delete_paragraph(
    paragraph_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Supprime un paragraphe"""
    try:
        _ensure_paragraph_access(db, paragraph_id, current_user)
        
        paragraph_crud.remove(db, id=paragraph_id)
        return {"message": "Paragraph deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting paragraph {paragraph_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/land/{land_id}/paragraphs/stats", response_model=ParagraphStats)
async def get_paragraph_stats(
    land_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Récupère les statistiques des paragraphes pour un land"""
    try:
        _ensure_land_access(db, land_id, current_user)
        stats = paragraph_crud.get_stats_by_land(db, land_id)
        
        return ParagraphStats(
            total_paragraphs=stats.get('total_paragraphs', 0),
            paragraphs_with_embeddings=stats.get('paragraphs_with_embeddings', 0),
            embedding_coverage=stats.get('embedding_coverage', 0.0),
            avg_word_count=stats.get('avg_word_count'),
            avg_reading_level=stats.get('avg_reading_level'),
            languages=stats.get('languages', {})
        )
    except Exception as e:
        logger.error(f"Error retrieving paragraph stats for land {land_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/land/{land_id}/extract-paragraphs")
async def extract_paragraphs_for_land(
    land_id: int = Path(..., gt=0),
    force_reextract: bool = Query(False),
    min_length: int = Query(50, ge=10),
    max_length: int = Query(5000, le=10000),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lance l'extraction de paragraphes pour un land"""
    try:
        from app.tasks.embedding_tasks import extract_paragraphs_for_land_task
        
        _ensure_land_access(db, land_id, current_user)
        
        # Lancer la tâche Celery
        task = extract_paragraphs_for_land_task.delay(
            land_id, force_reextract, min_length, max_length, getattr(current_user, "id", None)
        )
        
        return {
            "task_id": task.id,
            "message": "Paragraph extraction started",
            "land_id": land_id,
            "status": "processing"
        }
    except Exception as e:
        logger.error(f"Error starting paragraph extraction for land {land_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task/{task_id}/status")
async def get_task_status(
    task_id: str = Path(...),
    current_user: User = Depends(get_current_active_user)
):
    """Récupère le statut d'une tâche Celery"""
    try:
        result = AsyncResult(task_id)
        
        if result.state == 'PENDING':
            response = {
                'task_id': task_id,
                'status': 'pending',
                'message': 'Task is waiting to be processed'
            }
        elif result.state == 'PROGRESS':
            progress_meta = result.info if isinstance(result.info, dict) else {}
            response = {
                'task_id': task_id,
                'status': 'processing',
                **progress_meta
            }
        elif result.state == 'SUCCESS':
            response = {
                'task_id': task_id,
                'status': 'completed',
                'result': result.result
            }
        elif result.state == 'FAILURE':
            raw_error = str(result.info)
            safe_error = raw_error if getattr(current_user, "is_admin", False) else "Task failed"
            response = {
                'task_id': task_id,
                'status': 'failed',
                'error': safe_error,
                'message': safe_error
            }
        else:
            response = {
                'task_id': task_id,
                'status': result.state.lower(),
                'message': f"Task is in {result.state} state"
            }
        
        return response
    except Exception as e:
        logger.error(f"Error retrieving task status for {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/task/{task_id}/cancel")
async def cancel_task(
    task_id: str = Path(...),
    current_user: User = Depends(get_current_active_user)
):
    """Annule une tâche Celery"""
    try:
        from app.core.celery_app import celery_app
        
        if not getattr(current_user, "is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can cancel tasks"
            )
        
        celery_app.control.revoke(task_id, terminate=True)
        
        return {
            'task_id': task_id,
            'status': 'cancelled',
            'message': 'Task cancellation requested'
        }
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/land/{land_id}/generate-embeddings", response_model=EmbeddingGenerateResponse)
async def generate_embeddings_for_land(
    request: EmbeddingGenerateRequest,
    land_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lance la génération d'embeddings pour un land"""
    try:
        from app.tasks.embedding_tasks import generate_embeddings_for_land_task
        
        # Mettre à jour le land_id de la requête
        request.land_id = land_id
        
        land = _ensure_land_access(db, land_id, current_user)
        
        # Valider le provider
        available_providers = await embedding_service.get_available_providers()
        if request.provider not in available_providers:
            raise HTTPException(
                status_code=400, 
                detail=f"Provider {request.provider} not available. Available: {available_providers}"
            )
        
        if (
            embeddings_settings.require_user_confirmation
            and not getattr(current_user, "is_admin", False)
            and not request.confirm_external_processing
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="External processing must be explicitly confirmed"
            )
        
        # Estimer le nombre d'expressions
        total_expressions = db.query(Expression).filter(Expression.land_id == land_id).count()
        
        logger.info(
            "User %s requested embedding generation for land %s using provider %s",
            getattr(current_user, "id", None),
            land.id,
            request.provider
        )
        
        # Lancer la tâche Celery
        task = generate_embeddings_for_land_task.delay(
            land_id,
            request.provider,
            request.model,
            request.force_regenerate,
            request.batch_size,
            request.extract_paragraphs,
            getattr(current_user, "id", None)
        )
        
        return EmbeddingGenerateResponse(
            task_id=task.id,
            status="started",
            message=f"Embedding generation started for land {land_id} with provider {request.provider}",
            estimated_time=total_expressions * 2,  # 2 secondes par expression (estimation)
            land_id=land_id,
            provider=request.provider,
            total_expressions=total_expressions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting embedding generation for land {land_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/expressions/generate-embeddings", response_model=EmbeddingBatchResponse)
async def generate_embeddings_batch(
    request: EmbeddingBatchRequest,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lance la génération d'embeddings pour un batch d'expressions"""
    try:
        from app.tasks.embedding_tasks import generate_embeddings_for_expressions_task
        
        # Valider les IDs d'expression
        for expr_id in request.expression_ids:
            _ensure_expression_access(db, expr_id, current_user)
        
        # Valider le provider
        available_providers = await embedding_service.get_available_providers()
        if request.provider not in available_providers:
            raise HTTPException(
                status_code=400, 
                detail=f"Provider {request.provider} not available"
            )
        
        if (
            embeddings_settings.require_user_confirmation
            and not getattr(current_user, "is_admin", False)
            and not request.confirm_external_processing
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="External processing must be explicitly confirmed"
            )
        
        logger.info(
            "User %s requested batch embedding generation (%d expressions) via %s",
            getattr(current_user, "id", None),
            len(request.expression_ids),
            request.provider
        )
        
        # Lancer la tâche Celery
        task = generate_embeddings_for_expressions_task.delay(
            request.expression_ids,
            request.provider,
            request.force_regenerate,
            getattr(current_user, "id", None)
        )
        
        return EmbeddingBatchResponse(
            task_id=task.id,
            status="started",
            total_expressions=len(request.expression_ids),
            estimated_paragraphs=len(request.expression_ids) * 3,  # Estimation
            estimated_time=len(request.expression_ids) * 5,
            message=f"Batch embedding generation started for {len(request.expression_ids)} expressions"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting batch embedding generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/embedding-providers", response_model=List[str])
async def get_available_providers(current_user: User = Depends(get_current_active_user)):
    """Récupère la liste des providers d'embeddings disponibles"""
    try:
        return await embedding_service.get_available_providers()
    except Exception as e:
        logger.error(f"Error retrieving available providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/embedding-providers/health", response_model=EmbeddingHealthCheck)
async def check_providers_health(
    current_user: User = Depends(get_current_active_user)
):
    """Vérifie la santé de tous les providers d'embeddings"""
    try:
        if not getattr(current_user, "is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator privileges required"
            )
        health_results = await embedding_service.health_check_providers()
        
        available_count = sum(1 for status in health_results.values() if status.is_available)
        total_count = len(health_results)
        
        return EmbeddingHealthCheck(
            providers={
                name: {
                    "is_available": status.is_available,
                    "last_check": status.last_check,
                    "error_message": status.error_message,
                    "response_time": status.response_time
                }
                for name, status in health_results.items()
            },
            total_available=available_count,
            total_configured=total_count,
            overall_status="healthy" if available_count > 0 else "unhealthy",
            checked_at=health_results[list(health_results.keys())[0]].last_check if health_results else None
        )
    except Exception as e:
        logger.error(f"Error checking providers health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/embedding-providers/{provider_name}")
async def get_provider_info(
    provider_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """Récupère les informations d'un provider spécifique"""
    try:
        if not getattr(current_user, "is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator privileges required"
            )
        info = await embedding_service.get_provider_info(provider_name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} not found")
        return info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving provider info for {provider_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/land/{land_id}/embedding-stats", response_model=EmbeddingStats)
async def get_embedding_stats(
    land_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Récupère les statistiques d'embeddings pour un land"""
    try:
        _ensure_land_access(db, land_id, current_user)
        stats = embedding_service.get_embedding_stats(db, land_id)
        return stats
    except Exception as e:
        logger.error(f"Error retrieving embedding stats for land {land_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/land/{land_id}/text-processing-stats")
async def get_text_processing_stats(
    land_id: int = Path(..., gt=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user)
):
    """Récupère les statistiques de traitement de texte pour un land"""
    try:
        _ensure_land_access(db, land_id, current_user)
        # TODO: Fix this - get_processing_stats needs AsyncSession but this endpoint uses Session
        # This needs architectural review to align session types
        # text_processor = TextProcessorService(db)
        # stats = text_processor.get_processing_stats(db, land_id)
        stats = {"error": "Processing stats temporarily unavailable - session type mismatch"}
        return stats
    except Exception as e:
        logger.error(f"Error retrieving text processing stats for land {land_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/text/analyze")
async def analyze_text_content(
    text: str = Query(..., min_length=1),
    max_length: int = Query(5000, le=20000),
    current_user: User = Depends(get_current_active_user)
):
    """Analyse un contenu textuel"""
    try:
        if len(text) > max_length:
            raise HTTPException(status_code=400, detail=f"Text too long (max {max_length} characters)")
        if len(text) > 20000:
            raise HTTPException(status_code=400, detail="Payload too large")
        
        # Use static method for text analysis (no DB needed)
        analysis = TextProcessorService.analyze_text_content(text)
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing text content: {e}")
        raise HTTPException(status_code=500, detail=str(e))
