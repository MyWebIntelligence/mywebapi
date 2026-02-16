"""
Lands endpoints v2
Breaking changes: Mandatory pagination, enhanced response format
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db, get_current_active_user
from app.schemas.land import (
    Land,
    LandCreate,
    LandUpdate,
    LandAddTerms,
    LandAddUrls,
)
from app.schemas.media import MediaAnalysisRequest, MediaAnalysisResponse
from app.schemas.readable import ReadableRequestV2, ReadableProcessingResult
from app.crud.crud_land import land as crud_land
from app.schemas.job import CrawlRequest, CrawlJobResponse, CrawlStatus
from app.services.crawling_service import start_crawl_for_land
from app.schemas.user import User
from app.api.versioning import get_api_version_from_request
from pydantic import BaseModel
from app.core.media_processor import MediaProcessorSync
from app.crud import crud_media
from app.db import models
import time
import httpx
import logging
import traceback

logger = logging.getLogger(__name__)

router = APIRouter()


class PaginatedResponse(BaseModel):
    """Réponse paginée standardisée pour v2"""
    items: List[Land]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class V2ErrorResponse(BaseModel):
    """Format d'erreur standardisé pour v2"""
    error_code: str
    message: str
    details: Optional[dict] = None
    suggestion: Optional[str] = None


@router.get("/", response_model=PaginatedResponse)
async def list_lands_v2(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    name_filter: Optional[str] = Query(None, description="Filter by land name"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> PaginatedResponse:
    """
    List user's lands with mandatory pagination
    
    Breaking changes from v1:
    - Pagination is now mandatory (page and page_size required)
    - Enhanced response format with pagination metadata
    - Additional filtering options
    """
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get total count for pagination
    total = await crud_land.count_user_lands(db, user_id=current_user.id)
    
    # Get paginated lands
    lands = await crud_land.get_user_lands_paginated(
        db, 
        user_id=current_user.id,
        offset=offset,
        limit=page_size,
        name_filter=name_filter,
        status_filter=status_filter
    )
    
    # Calculate pagination metadata
    total_pages = (total + page_size - 1) // page_size
    has_next = page < total_pages
    has_previous = page > 1
    
    return PaginatedResponse(
        items=lands,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous
    )


@router.get("/{land_id}", response_model=Land)
async def get_land_v2(
    land_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Land:
    """
    Get a specific land by ID
    
    Enhanced error handling with v2 format
    """
    land = await crud_land.get(db, id=land_id)
    
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure you have access to this land"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to access this land",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or use lands you own"
            }
        )
    
    return land


@router.post("/", response_model=Land)
async def create_land_v2(
    land_data: LandCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Land:
    """
    Create a new land
    
    Enhanced validation and error handling
    """
    try:
        # Check if land name already exists for this user
        existing_land = await crud_land.get_by_name_and_user(
            db, name=land_data.name, user_id=current_user.id
        )
        
        if existing_land:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "LAND_NAME_EXISTS",
                    "message": f"Land with name '{land_data.name}' already exists",
                    "details": {"name": land_data.name},
                    "suggestion": "Choose a different name for your land"
                }
            )
        
        land = await crud_land.create(db, obj_in=land_data, owner_id=current_user.id)
        return land
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "LAND_CREATION_FAILED",
                "message": "Failed to create land",
                "details": {"error": str(e)},
                "suggestion": "Check your input data and try again"
            }
        )


@router.put("/{land_id}", response_model=Land)
async def update_land_v2(
    land_id: int,
    land_update: LandUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Land:
    """
    Update a land
    
    Enhanced error handling with v2 format
    """
    # Check if land exists and user has access
    land = await crud_land.get(db, id=land_id)
    
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure it exists"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to update this land",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or update lands you own"
            }
        )
    
    try:
        updated_land = await crud_land.update(db, db_obj=land, obj_in=land_update)
        return updated_land
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "LAND_UPDATE_FAILED",
                "message": "Failed to update land",
                "details": {"land_id": land_id, "error": str(e)},
                "suggestion": "Check your input data and try again"
            }
        )


@router.delete("/{land_id}")
async def delete_land_v2(
    land_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Delete a land
    
    Enhanced response format for v2
    """
    # Check if land exists and user has access
    land = await crud_land.get(db, id=land_id)
    
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure it exists"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to delete this land",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or delete lands you own"
            }
        )
    
    try:
        await crud_land.remove(db, id=land_id)
        
        return {
            "success": True,
            "message": f"Land {land_id} deleted successfully",
            "details": {
                "land_id": land_id,
                "name": land.name,
                "deleted_at": "2025-07-04T00:00:00Z"  # In real implementation, use actual timestamp
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "LAND_DELETION_FAILED",
                "message": "Failed to delete land",
                "details": {"land_id": land_id, "error": str(e)},
                "suggestion": "Try again or contact support if the problem persists"
            }
        )


@router.post("/{land_id}/media-analysis-async", response_model=Dict[str, Any])
async def analyze_land_media_async_v2(
    land_id: int,
    analysis_request: MediaAnalysisRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Lance une analyse asynchrone de médias via Celery (recommandé pour des milliers d'images).
    
    Cette version utilise Celery pour traiter les médias en arrière-plan, permettant
    de gérer de gros volumes sans timeout. Retourne immédiatement un job_id pour 
    suivre le progrès.
    
    Args:
        land_id: ID du land à analyser
        analysis_request: Paramètres d'analyse (depth, minrel)
        
    Returns:
        Dict contenant job_id et informations de suivi
    """
    # Verify land exists and user has access
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure it exists"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to analyze media for this land",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or analyze lands you own"
            }
        )
    
    try:
        # Launch async task first to get task ID
        from app.tasks.media_analysis_task import analyze_land_media_task
        
        task = analyze_land_media_task.delay(
            job_id=0,  # Will be updated later
            land_id=land_id,
            depth=analysis_request.depth if analysis_request.depth is not None else 0,
            minrel=analysis_request.minrel if analysis_request.minrel is not None else 0.0,
            batch_size=50
        )
        
        # Create job record with task ID
        from app.crud import crud_job
        from app.schemas.job import CrawlJobCreate
        
        job_data = CrawlJobCreate(
            job_type="media_analysis",
            land_id=land_id,
            task_id=task.id,
            parameters={
                "depth": analysis_request.depth if analysis_request.depth is not None else 999,
                "minrel": analysis_request.minrel if analysis_request.minrel is not None else 0.0,
                "batch_size": 50
            }
        )
        
        job = await crud_job.job.create(db, obj_in=job_data)
        
        # Update task with correct job_id (revoke and restart with correct ID)
        task.revoke()
        task = analyze_land_media_task.delay(
            job_id=job.id,
            land_id=land_id,
            depth=analysis_request.depth if analysis_request.depth is not None else 999,
            minrel=analysis_request.minrel if analysis_request.minrel is not None else 0.0,
            batch_size=50
        )
        
        return {
            "job_id": job.id,
            "celery_task_id": task.id,
            "land_id": land_id,
            "land_name": land.name,
            "status": "pending",
            "message": "Media analysis task started in background",
            "parameters": job_data.parameters,
            "check_status_url": f"/api/v2/jobs/{job.id}",
            "websocket_url": f"/api/v1/ws/jobs/{job.id}",
            "estimated_time": "2-10 minutes depending on media count"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "MEDIA_ANALYSIS_JOB_FAILED",
                "message": "Failed to start media analysis job",
                "details": {"land_id": land_id, "error": str(e)},
                "suggestion": "Check system status and try again"
            }
        )


@router.post("/{land_id}/readable", response_model=Dict[str, Any])
async def process_readable_v2(
    land_id: int,
    request: ReadableRequestV2 = ReadableRequestV2(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Process readable content for expressions in a land (v2).
    
    Enhanced version with standardized error handling, progress tracking,
    and comprehensive parameter validation.
    
    Features:
    - Mercury-like content extraction with fallbacks
    - Three merge strategies: smart_merge, mercury_priority, preserve_existing
    - Optional LLM validation via OpenRouter
    - Automatic media and link extraction from markdown
    - WebSocket progress updates
    
    Args:
        land_id: ID of the land to process
        request: Processing parameters (limit, depth, merge strategy, etc.)
        
    Returns:
        Job tracking information with standardized v2 format
    """
    # Verify land exists and user has access
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Verify the land ID and ensure you have access to it"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to process this land",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner for access"
            }
        )
    
    try:
        # Import here to avoid circular imports
        from app.crud import crud_job
        from app.schemas.job import CrawlJobCreate
        from app.tasks.readable_working_task import readable_working_task
        
        # Create job record for tracking
        job_data = CrawlJobCreate(
            land_id=land_id,
            job_type="readable_processing",
            task_id="",  # Will be set after task creation
            parameters={
                "limit": request.limit,
                "depth": request.depth,
                "merge_strategy": request.merge_strategy.value,
                "enable_llm": request.enable_llm,
                "batch_size": request.batch_size,
                "max_concurrent": request.max_concurrent
            }
        )
        
        job = await crud_job.job.create(db, obj_in=job_data)
        
        # Start readable processing task
        task_result = readable_working_task.delay(
            land_id=land_id,
            job_id=job.id,
            limit=request.limit or 10
        )
        
        # Update job with task ID
        await crud_job.job.update(db, db_obj=job, obj_in={"task_id": task_result.id})
        
        return {
            "success": True,
            "message": f"Readable processing started for land '{land.name}'",
            "job_id": job.id,
            "task_id": task_result.id,
            "celery_task_id": task_result.id,
            "ws_channel": f"job_{job.id}",
            "parameters": {
                "limit": request.limit or 10,
                "test_mode": True
            },
            "tracking": {
                "job_status_endpoint": f"/api/v2/jobs/{job.id}",
                "websocket_channel": f"job_{job.id}",
                "land_channel": f"land_{land_id}"
            },
            "estimated_time": "Test task - should complete in under 1 minute"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "READABLE_PROCESSING_JOB_FAILED",
                "message": "Failed to start readable processing job",
                "details": {"land_id": land_id, "error": str(e)},
                "suggestion": "Check system status and try again"
            }
        )


@router.post("/{land_id}/populate-dictionary", response_model=Dict[str, Any])
async def populate_land_dictionary_v2(
    land_id: int,
    request: Request,
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Peuple automatiquement le dictionnaire de mots-clés d'un land.
    
    Résout le problème de Dictionary Starvation en créant les entrées
    de dictionnaire nécessaires pour le calcul de pertinence.
    
    Args:
        land_id: ID du land à traiter
        force_refresh: Si True, recrée le dictionnaire même s'il existe
        
    Returns:
        Dict avec les statistiques de création du dictionnaire
    """
    # Verify land exists and user has access
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND", 
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id}
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to modify this land's dictionary",
                "details": {"land_id": land_id, "owner_id": land.owner_id}
            }
        )
    
    try:
        from app.services.dictionary_service import DictionaryService
        
        dict_service = DictionaryService(db)
        result = await dict_service.populate_land_dictionary(land_id, force_refresh)
        
        # Obtenir les statistiques du dictionnaire
        stats = await dict_service.get_land_dictionary_stats(land_id)
        
        return {
            **result,
            "dictionary_stats": stats,
            "land_name": land.name,
            "message": f"Dictionary {'updated' if result['action'] == 'created' else result['action']} successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "DICTIONARY_POPULATION_FAILED",
                "message": "Failed to populate land dictionary",
                "details": {"land_id": land_id, "error": str(e)}
            }
        )


@router.get("/{land_id}/dictionary-stats", response_model=Dict[str, Any])
async def get_land_dictionary_stats_v2(
    land_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Récupère les statistiques du dictionnaire d'un land.
    
    Permet de diagnostiquer les problèmes de Dictionary Starvation.
    """
    # Verify land exists and user has access
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    
    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        from app.services.dictionary_service import DictionaryService
        
        dict_service = DictionaryService(db)
        stats = await dict_service.get_land_dictionary_stats(land_id)
        
        return {
            **stats,
            "land_name": land.name,
            "land_words": land.words or [],
            "diagnosis": {
                "has_dictionary": stats["total_entries"] > 0,
                "problem": "Dictionary Starvation" if stats["total_entries"] == 0 else None,
                "solution": "Run populate-dictionary endpoint" if stats["total_entries"] == 0 else None
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dictionary stats: {str(e)}"
        )


@router.post("/{land_id}/crawl", response_model=CrawlJobResponse)
async def crawl_land_v2(
    land_id: int,
    crawl_request: CrawlRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> CrawlJobResponse:
    """
    Start a crawl job for a specific land
    
    Enhanced error handling with v2 format
    """
    # Check if user has permission to crawl this land
    land_obj = await crud_land.get(db, id=land_id)
    
    if not land_obj:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure it exists"
            }
        )
    
    if land_obj.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to crawl this land",
                "details": {"land_id": land_id, "owner_id": land_obj.owner_id},
                "suggestion": "Contact the land owner or crawl lands you own"
            }
        )
    
    try:
        job_payload = await start_crawl_for_land(db, land_id, crawl_request)

        job_status = job_payload.get("status")
        if isinstance(job_status, CrawlStatus):
            status_enum = job_status
        elif hasattr(job_status, "name"):
            status_enum = CrawlStatus[job_status.name]
        else:
            status_str = str(job_status)
            if "CrawlStatus." in status_str:
                status_str = status_str.split(".", 1)[1]
            status_enum = CrawlStatus[status_str.upper()]

        return CrawlJobResponse(
            job_id=job_payload.get("job_id"),
            celery_task_id=job_payload.get("celery_task_id", ""),
            land_id=job_payload.get("land_id"),
            status=status_enum,
            created_at=job_payload.get("created_at"),
            parameters=job_payload.get("parameters") or {},
        )
        
    except Exception as e:
        logger.error(f"Error starting crawl for land {land_id}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "CRAWL_START_FAILED",
                "message": "Failed to start crawl job",
                "details": {"land_id": land_id, "error": str(e), "type": type(e).__name__},
                "suggestion": "Check crawl parameters and try again"
            }
        )


@router.get("/{land_id}/stats")
async def get_land_stats_v2(
    land_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Get enhanced statistics for a land
    
    New endpoint in v2 with detailed analytics
    """
    # Check if land exists and user has access
    land = await crud_land.get(db, id=land_id)
    
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure you have access to this land"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to access this land's statistics",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or access lands you own"
            }
        )
    
    # Get enhanced statistics (mock data for now)
    return {
        "land_id": land_id,
        "name": land.name,
        "crawl_stats": {
            "total_crawls": 5,
            "successful_crawls": 4,
            "failed_crawls": 1,
            "last_crawl_date": "2025-07-03T14:30:00Z",
            "avg_crawl_duration": "00:15:30"
        },
        "content_stats": {
            "total_pages": 1250,
            "total_expressions": 3400,
            "total_media": 850,
            "content_types": {
                "html": 1200,
                "pdf": 35,
                "images": 850,
                "other": 15
            }
        },
        "export_stats": {
            "total_exports": 12,
            "recent_exports": [
                {"format": "csv", "date": "2025-07-02T10:15:00Z", "records": 1250},
                {"format": "gexf", "date": "2025-07-01T16:45:00Z", "records": 3400}
            ]
        },
        "performance_metrics": {
            "avg_response_time": "200ms",
            "success_rate": "94.2%",
            "data_quality_score": "87%"
        }
    }


@router.post("/{land_id}/terms", response_model=Land)
async def add_terms_to_land_v2(
    land_id: int,
    payload: LandAddTerms,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Land:
    """
    Add keywords to a land dictionary (replaces legacy `land addterm`).
    """
    land = await crud_land.get(db, id=land_id)
    if not land or land.owner_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found or inaccessible",
                "details": {"land_id": land_id},
                "suggestion": "Ensure the land exists and you are the owner",
            },
        )

    updated = await crud_land.add_terms_to_land(db, land_id, payload.terms)
    if not updated:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "LAND_TERMS_UPDATE_FAILED",
                "message": "Failed to add terms to land",
            },
        )
    return updated


@router.post("/{land_id}/urls", response_model=Land)
async def add_urls_to_land_v2(
    land_id: int,
    payload: LandAddUrls,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Land:
    """
    Append start URLs to a land (replaces legacy `land addurl`).
    """
    land = await crud_land.get(db, id=land_id)
    if not land or land.owner_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found or inaccessible",
                "details": {"land_id": land_id},
                "suggestion": "Ensure the land exists and you are the owner",
            },
        )

    updated = await crud_land.add_urls_to_land(db, land_id, payload.urls)
    if not updated:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "LAND_URLS_UPDATE_FAILED",
                "message": "Failed to add URLs to land",
            },
        )
    return updated


@router.post("/{land_id}/media-analysis", response_model=MediaAnalysisResponse, deprecated=True)
async def analyze_land_media_v2(
    land_id: int,
    analysis_request: MediaAnalysisRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> MediaAnalysisResponse:
    """
    [DEPRECATED] Synchronous media analysis - use /media-analysis-async instead.
    
    This synchronous endpoint is deprecated due to timeout issues with large datasets.
    Use the async version (/media-analysis-async) which processes media via Celery tasks.
    
    Args:
        land_id: ID of the land to analyze media for
        analysis_request: Parameters including depth and minrel filters
        
    Returns:
        MediaAnalysisResponse with analysis results and statistics
        
    Deprecated:
        Use POST /{land_id}/media-analysis-async for better performance and reliability.
    """
    start_time = time.time()
    
    # Verify land exists and user has access
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure it exists"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to analyze media for this land",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or analyze lands you own"
            }
        )
    
    try:
        # Get expressions based on filters
        from sqlalchemy import text
        expressions_query = await db.execute(
            text("""
            SELECT e.id, e.url, e.depth, e.relevance
            FROM expressions e 
            WHERE e.land_id = :land_id
            AND (:depth = 0 OR e.depth <= :depth)
            AND e.relevance >= :minrel
            ORDER BY e.relevance DESC
            """),
            {
                "land_id": land_id,
                "depth": analysis_request.depth if analysis_request.depth is not None else 999,
                "minrel": analysis_request.minrel if analysis_request.minrel is not None else 0.0
            }
        )
        
        expressions = expressions_query.fetchall()
        total_expressions = await db.execute(
            text("SELECT COUNT(*) FROM expressions WHERE land_id = :land_id"),
            {"land_id": land_id}
        )
        total_count = total_expressions.scalar()
        
        # Get media for filtered expressions
        expression_ids = [exp.id for exp in expressions]
        if not expression_ids:
            return MediaAnalysisResponse(
                land_id=land_id,
                land_name=land.name,
                total_expressions=total_count,
                filtered_expressions=0,
                total_media=0,
                analyzed_media=0,
                failed_analysis=0,
                results=[],
                processing_time=time.time() - start_time,
                filters_applied={
                    "depth": analysis_request.depth,
                    "minrel": analysis_request.minrel
                }
            )
        
        # Get media for these expressions
        media_query = await db.execute(
            text("""
            SELECT m.id, m.url, m.type, m.expression_id, m.is_processed
            FROM media m
            WHERE m.expression_id = ANY(:expression_ids)
            AND m.type = 'IMAGE'
            ORDER BY m.created_at DESC
            """),
            {"expression_ids": expression_ids}
        )
        
        media_list = media_query.fetchall()
        total_media = len(media_list)
        
        # Initialize media processor
        async with httpx.AsyncClient() as http_client:
            media_processor = MediaProcessor(db, http_client)
            
            analyzed_count = 0
            failed_count = 0
            analysis_results = []
            
            # Process each media item
            for media_item in media_list:
                try:
                    # If already processed, get existing analysis data
                    if media_item.is_processed:
                        analyzed_count += 1
                        
                        # Get full media record with analysis data
                        full_media_query = await db.execute(
                            text("""
                            SELECT id, url, width, height, format, file_size, dominant_colors, 
                                   websafe_colors, has_transparency, aspect_ratio, image_hash,
                                   processing_error, analysis_error
                            FROM media 
                            WHERE id = :media_id
                            """),
                            {"media_id": media_item.id}
                        )
                        full_media = full_media_query.fetchone()
                        
                        if full_media:
                            analysis_results.append({
                                "media_id": full_media.id,
                                "url": full_media.url,
                                "status": "success" if not full_media.processing_error and not full_media.analysis_error else "failed",
                                "width": full_media.width,
                                "height": full_media.height,
                                "format": full_media.format,
                                "file_size": full_media.file_size,
                                "dominant_colors": full_media.dominant_colors or [],
                                "websafe_colors": full_media.websafe_colors or {},
                                "has_transparency": full_media.has_transparency,
                                "aspect_ratio": full_media.aspect_ratio,
                                "image_hash": full_media.image_hash,
                                "error": full_media.processing_error or full_media.analysis_error
                            })
                        continue
                    
                    # Analyze the media (for unprocessed media)
                    analysis_result = await media_processor.analyze_image(media_item.url)
                    
                    if analysis_result.get('error'):
                        failed_count += 1
                        analysis_results.append({
                            "media_id": media_item.id,
                            "url": media_item.url,
                            "status": "failed",
                            "error": analysis_result['error']
                        })
                    else:
                        analyzed_count += 1
                        
                        # Update media record with analysis results
                        await crud_media.media.update_media_analysis(
                            db,
                            media_id=media_item.id,
                            analysis_data=analysis_result
                        )
                        
                        analysis_results.append({
                            "media_id": media_item.id,
                            "url": media_item.url,
                            "status": "success",
                            "width": analysis_result.get('width'),
                            "height": analysis_result.get('height'),
                            "format": analysis_result.get('format'),
                            "file_size": analysis_result.get('file_size'),
                            "dominant_colors": analysis_result.get('dominant_colors', []),
                            "websafe_colors": analysis_result.get('websafe_colors', {}),
                            "has_transparency": analysis_result.get('has_transparency'),
                            "aspect_ratio": analysis_result.get('aspect_ratio'),
                            "image_hash": analysis_result.get('image_hash')
                        })
                        
                except Exception as e:
                    failed_count += 1
                    analysis_results.append({
                        "media_id": media_item.id,
                        "url": media_item.url,
                        "status": "failed",
                        "error": str(e)
                    })
        
        processing_time = time.time() - start_time
        
        return MediaAnalysisResponse(
            land_id=land_id,
            land_name=land.name,
            total_expressions=total_count,
            filtered_expressions=len(expressions),
            total_media=total_media,
            analyzed_media=analyzed_count,
            failed_analysis=failed_count,
            results=analysis_results,
            processing_time=round(processing_time, 2),
            filters_applied={
                "depth": analysis_request.depth,
                "minrel": analysis_request.minrel
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "MEDIA_ANALYSIS_FAILED",
                "message": "Failed to analyze media for land",
                "details": {"land_id": land_id, "error": str(e)},
                "suggestion": "Check analysis parameters and try again"
            }
        )


@router.get("/{land_id}/pipeline-stats", response_model=Dict[str, Any])
async def get_land_pipeline_stats_v2(
    land_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Récupère les statistiques détaillées du pipeline de crawl pour un land.
    
    Fournit des métriques sur:
    - Expressions créées, crawlées, approuvées
    - Distribution par profondeur
    - Progression temporelle
    - Santé du dictionnaire
    """
    # Verify land exists and user has access
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    
    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        from app.services.crawling_service import get_crawl_pipeline_stats
        
        stats = await get_crawl_pipeline_stats(db, land_id)
        
        return {
            **stats,
            "land_name": land.name,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get pipeline stats: {str(e)}"
        )


@router.post("/{land_id}/fix-pipeline", response_model=Dict[str, Any])
async def fix_land_pipeline_v2(
    land_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Répare les incohérences du pipeline de crawl pour un land.
    
    Applique la logique legacy:
    - approved_at = NOW() pour les expressions pertinentes (relevance > 0)
    - approved_at = NULL pour les expressions non pertinentes (relevance = 0)
    """
    # Verify land exists and user has access
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    
    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        from app.services.crawling_service import fix_pipeline_inconsistencies
        
        result = await fix_pipeline_inconsistencies(db, land_id)
        
        return {
            **result,
            "land_name": land.name,
            "message": f"Pipeline fixed: {result['total_fixes']} expressions updated"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fix pipeline: {str(e)}"
        )


@router.post("/{land_id}/llm-validate", response_model=Dict[str, Any])
async def llm_validate_land_v2(
    land_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    limit: Optional[int] = Query(None, description="Max number of expressions to validate"),
    force: bool = Query(False, description="Force revalidation even if valid_llm exists")
) -> Dict[str, Any]:
    """
    Start LLM validation reprocessing for a land's expressions.

    Validates expressions that:
    - Have relevance > 0 (are considered relevant by keyword matching)
    - Don't have valid_llm set (unless force=True)
    - Have readable content

    This uses OpenRouter API and requires:
    - OPENROUTER_ENABLED=True
    - OPENROUTER_API_KEY=<your-key>

    Returns:
        Statistics about the validation process
    """
    # Verify land exists and user has access
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")

    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if OpenRouter is enabled
    from app.config import settings
    if not settings.OPENROUTER_ENABLED:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "OPENROUTER_DISABLED",
                "message": "LLM validation is not enabled",
                "details": {"land_id": land_id},
                "suggestion": "Set OPENROUTER_ENABLED=True in .env"
            }
        )

    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "OPENROUTER_NOT_CONFIGURED",
                "message": "OpenRouter API key is not configured",
                "details": {"land_id": land_id},
                "suggestion": "Set OPENROUTER_API_KEY in .env"
            }
        )

    try:
        from app.scripts.reprocess_llm_validation import reprocess_llm_validation
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SyncSession

        # Create sync engine for the reprocessing script
        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        engine = create_engine(sync_url, echo=False)

        # Run reprocessing in background
        # Note: For production, this should be a Celery task
        stats = reprocess_llm_validation(
            land_id=land_id,
            limit=limit,
            dry_run=False,
            force=force,
            batch_size=50
        )

        return {
            "land_id": land_id,
            "land_name": land.name,
            "stats": stats,
            "message": f"LLM validation completed: {stats['validated']} validated, {stats['rejected']} rejected"
        }

    except Exception as e:
        logger.error(f"LLM validation failed for land {land_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run LLM validation: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────
# SerpAPI URL gathering
# ─────────────────────────────────────────────────────────────

class SerpAPIRequest(BaseModel):
    """Request body for SerpAPI URL gathering."""
    query: str
    engine: str = "google"
    lang: str = "fr"
    datestart: Optional[str] = None
    dateend: Optional[str] = None
    timestep: str = "week"
    sleep: float = 1.0


@router.post("/{land_id}/serpapi-urls", response_model=Dict[str, Any])
async def gather_serpapi_urls_v2(
    land_id: int,
    payload: SerpAPIRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Gather URLs from SerpAPI (Google/Bing/DuckDuckGo) and add them to the land.
    Replaces legacy `land urlist` command.
    """
    from app.config import settings
    from app.services.serpapi_service import fetch_serpapi_url_list, SerpApiError

    land = await crud_land.get(db, id=land_id)
    if not land or land.owner_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land {land_id} not found or inaccessible",
            },
        )

    api_key = settings.SERPAPI_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "SERPAPI_NOT_CONFIGURED",
                "message": "SERPAPI_API_KEY is not configured",
                "suggestion": "Set SERPAPI_API_KEY in your .env file",
            },
        )

    try:
        results = fetch_serpapi_url_list(
            api_key=api_key,
            query=payload.query,
            engine=payload.engine,
            lang=payload.lang,
            datestart=payload.datestart,
            dateend=payload.dateend,
            timestep=payload.timestep,
            sleep_seconds=payload.sleep,
        )

        # Add discovered URLs to the land
        urls_to_add = [r["url"] for r in results if r.get("url")]
        added_count = 0
        if urls_to_add:
            updated = await crud_land.add_urls_to_land(db, land_id, urls_to_add)
            if updated:
                added_count = len(urls_to_add)

        return {
            "land_id": land_id,
            "query": payload.query,
            "engine": payload.engine,
            "total_results": len(results),
            "urls_added": added_count,
            "results": results[:20],  # Return first 20 for preview
        }

    except SerpApiError as e:
        raise HTTPException(status_code=400, detail={"error_code": "SERPAPI_ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"SerpAPI failed for land {land_id}: {e}")
        raise HTTPException(status_code=500, detail=f"SerpAPI request failed: {str(e)}")


# ─────────────────────────────────────────────────────────────
# Delete expressions by maxrel
# ─────────────────────────────────────────────────────────────

@router.delete("/{land_id}/expressions", response_model=Dict[str, Any])
async def delete_expressions_by_relevance_v2(
    land_id: int,
    maxrel: float = Query(..., description="Delete expressions with relevance below this threshold"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Delete expressions below a relevance threshold.
    Replaces legacy `land delete --maxrel=X`.
    """
    from sqlalchemy import text as sql_text

    land = await crud_land.get(db, id=land_id)
    if not land or land.owner_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land {land_id} not found or inaccessible",
            },
        )

    try:
        # Count before delete
        count_result = await db.execute(
            sql_text(
                "SELECT COUNT(*) FROM expressions WHERE land_id = :lid AND relevance < :maxrel"
            ),
            {"lid": land_id, "maxrel": maxrel},
        )
        to_delete = count_result.scalar() or 0

        if to_delete == 0:
            return {
                "land_id": land_id,
                "deleted": 0,
                "message": f"No expressions with relevance < {maxrel}",
            }

        # Delete related records first (links, media)
        await db.execute(
            sql_text("""
                DELETE FROM expression_links
                WHERE source_id IN (SELECT id FROM expressions WHERE land_id = :lid AND relevance < :maxrel)
                   OR target_id IN (SELECT id FROM expressions WHERE land_id = :lid AND relevance < :maxrel)
            """),
            {"lid": land_id, "maxrel": maxrel},
        )
        await db.execute(
            sql_text("""
                DELETE FROM media
                WHERE expression_id IN (SELECT id FROM expressions WHERE land_id = :lid AND relevance < :maxrel)
            """),
            {"lid": land_id, "maxrel": maxrel},
        )
        # Delete expressions
        await db.execute(
            sql_text("DELETE FROM expressions WHERE land_id = :lid AND relevance < :maxrel"),
            {"lid": land_id, "maxrel": maxrel},
        )
        await db.commit()

        return {
            "land_id": land_id,
            "deleted": to_delete,
            "threshold": maxrel,
            "message": f"Deleted {to_delete} expressions with relevance < {maxrel}",
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Delete by maxrel failed for land {land_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# ─────────────────────────────────────────────────────────────
# Consolidation V2
# ─────────────────────────────────────────────────────────────

@router.post("/{land_id}/consolidate", response_model=Dict[str, Any])
async def consolidate_land_v2(
    land_id: int,
    limit: int = Query(0, ge=0, description="Max expressions to process (0=unlimited)"),
    depth: Optional[int] = Query(None, ge=0, description="Only process at this depth"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Consolidate a land : recalculate relevance, rebuild links and media.
    Replaces legacy `land consolidate`.
    """
    from app.tasks.consolidation_task import consolidate_land_task

    land = await crud_land.get(db, id=land_id)
    if not land or land.owner_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "LAND_NOT_FOUND", "message": f"Land {land_id} not found"},
        )

    task_result = consolidate_land_task.delay(land_id=land_id, limit=limit, depth=depth)
    return {
        "message": f"Consolidation started for land {land_id}",
        "task_id": task_result.id,
        "parameters": {"limit": limit, "depth": depth},
    }


# ─────────────────────────────────────────────────────────────
# Heuristic update : recalculate domain names using heuristic patterns
# ─────────────────────────────────────────────────────────────

class HeuristicUpdateRequest(BaseModel):
    """Request body for heuristic update."""
    heuristics: Optional[Dict[str, str]] = None  # {"twitter.com": "twitter\\.com/([a-zA-Z0-9_]+)"}


@router.post("/{land_id}/heuristic-update", response_model=Dict[str, Any])
async def heuristic_update_v2(
    land_id: int,
    payload: Optional[HeuristicUpdateRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Recalculate domain names for all expressions in a land using heuristic patterns.
    Replaces legacy `heuristic update`.

    If heuristics are provided in the request body, they override the global settings.
    Format: {"domain_suffix": "regex_pattern_to_extract_new_domain"}
    Example: {"twitter.com": "twitter\\\\.com/([a-zA-Z0-9_]+)"}
    """
    import json
    from app.tasks.heuristic_update_task import heuristic_update_task

    land = await crud_land.get(db, id=land_id)
    if not land or land.owner_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail="Land not found or access denied",
        )

    heuristics_json = None
    if payload and payload.heuristics:
        heuristics_json = json.dumps(payload.heuristics)

    task_result = heuristic_update_task.delay(
        land_id=land_id,
        heuristics_override=heuristics_json,
    )
    return {
        "message": f"Heuristic update started for land {land_id}",
        "task_id": task_result.id,
    }


# ─────────────────────────────────────────────────────────────
# SEO Rank : fetch SEO metrics for expressions from seo-rank.my-addr.com
# ─────────────────────────────────────────────────────────────

class SeoRankRequest(BaseModel):
    """Request body for SEO Rank enrichment."""
    limit: int = 0
    depth: Optional[int] = None
    min_relevance: int = 1
    force_refresh: bool = False


@router.post("/{land_id}/seorank", response_model=Dict[str, Any])
async def seorank_land_v2(
    land_id: int,
    payload: Optional[SeoRankRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Fetch SEO Rank data for expressions in a land.
    Replaces legacy `land seorank`.

    Calls the SEO Rank API (seo-rank.my-addr.com) for each qualifying expression
    and stores the raw JSON metrics in the seorank field.
    """
    from app.tasks.seorank_task import seorank_task

    land = await crud_land.get(db, id=land_id)
    if not land or land.owner_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail="Land not found or access denied",
        )

    p = payload or SeoRankRequest()
    task_result = seorank_task.delay(
        land_id=land_id,
        limit=p.limit,
        depth=p.depth,
        min_relevance=p.min_relevance,
        force_refresh=p.force_refresh,
    )
    return {
        "message": f"SEO Rank enrichment started for land {land_id}",
        "task_id": task_result.id,
        "parameters": {
            "limit": p.limit,
            "depth": p.depth,
            "min_relevance": p.min_relevance,
            "force_refresh": p.force_refresh,
        },
    }
