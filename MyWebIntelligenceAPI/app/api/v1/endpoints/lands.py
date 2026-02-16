from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db, get_current_active_user
from app.schemas.land import Land, LandCreate, LandUpdate
from app.crud.crud_land import land as crud_land
from app.schemas.job import CrawlRequest, CrawlJobResponse
from app.services import crawling_service
from app.schemas.user import User
from app.tasks.consolidation_task import consolidate_land_task
from typing import Dict, Any, Optional

# V2 Simplification: Async tasks moved to projetV3
# - WebSocket support removed
# - Media analysis async removed
# - Readable async pipeline removed

router = APIRouter()

@router.post("/{land_id}/crawl", response_model=CrawlJobResponse)
async def crawl_land(
    land_id: int,
    crawl_request: CrawlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Start a crawl job for a specific land.
    """
    # Check if user has permission to crawl this land
    land_obj = await crud_land.get(db, id=land_id)
    if not land_obj or land_obj.owner_id != getattr(current_user, 'id', None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found or you don't have permission"
        )
    
    return await crawling_service.start_crawl_for_land(db, land_id, crawl_request)

@router.post("/{land_id}/consolidate")
async def consolidate_land(
    land_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Consolidate data for a specific land.
    """
    # Check if user has permission
    land_obj = await crud_land.get(db, id=land_id)
    if not land_obj or land_obj.owner_id != getattr(current_user, 'id', None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found or you don't have permission"
        )
    
    # Start consolidation task (V2 sync - full legacy logic)
    task_result = consolidate_land_task.delay(land_id=land_id)
    return {
        "message": f"Consolidation started for land {land_id}",
        "task_id": task_result.id
    }

# REMOVED in V2: /readable endpoint (moved to projetV3)
# REMOVED in V2: /medianalyse endpoint (moved to projetV3)

@router.post("/{land_id}/seorank")
async def analyze_seo_rank(
    land_id: int,
    limit: int = 0,
    min_relevance: int = 1,
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Fetch SEO Rank data for expressions in a land.
    """
    from app.tasks.seorank_task import seorank_task

    land_obj = await crud_land.get(db, id=land_id)
    if not land_obj or land_obj.owner_id != getattr(current_user, 'id', None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found or you don't have permission"
        )

    task_result = seorank_task.delay(
        land_id=land_id,
        limit=limit,
        min_relevance=min_relevance,
        force_refresh=force_refresh,
    )
    return {
        "message": f"SEO Rank enrichment started for land {land_id}",
        "task_id": task_result.id,
    }

