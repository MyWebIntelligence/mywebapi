from typing import cast, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.crud import crud_land, crud_job
from app.db.models import CrawlStatus as DBCrawlStatus
from app.schemas.job import (
    CrawlRequest,
    CrawlJobCreate,
    CrawlJobResponse,
    CrawlStatus as SchemaCrawlStatus,
)
from app.core.celery_app import celery_app
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

async def start_crawl_for_land(db: AsyncSession, land_id: int, crawl_request: CrawlRequest) -> CrawlJobResponse:
    """
    Creates a crawl job and dispatches it to a Celery worker with WebSocket progress tracking.
    """
    # Validate land exists
    land = await crud_land.land.get(db, id=land_id)
    if not land:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")

    # Validate crawl parameters
    if crawl_request.depth is not None and crawl_request.depth < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Depth must be a positive integer"
        )
    
    if crawl_request.limit is not None and crawl_request.limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Limit must be a positive integer"
        )

    # Create job record
    request_payload = crawl_request.model_dump()
    if request_payload.get("http_status") is not None:
        try:
            request_payload["http_status"] = int(request_payload["http_status"])
        except (TypeError, ValueError):
            request_payload["http_status"] = None

    job_create_schema = CrawlJobCreate(
        land_id=land_id,
        job_type="crawl",
        parameters=request_payload,
        task_id=""
    )
    db_job = await crud_job.job.create(db, obj_in=job_create_schema)

    # Commit the job to database BEFORE sending to Celery
    # This ensures the worker can fetch the job immediately
    await db.commit()
    await db.refresh(db_job)

    # Initialize job_id for exception handling
    job_id: int | None = None

    try:
        # Get the job ID - should be available after commit and refresh
        job_id = cast(int, db_job.id)
        if job_id is None:
            raise ValueError("Job ID could not be retrieved after creation")

        # Use Celery (sync crawler only in V2)
        logger.info(f"Using CELERY (sync crawler) for land {land_id}")

        # Dispatch task to Celery worker
        task = celery_app.send_task(
            "tasks.crawl_land_task",
            args=[job_id]
        )

        # Update job with Celery task ID
        db_job.celery_task_id = task.id
        await db.commit()
        await db.refresh(db_job)
        
        # Return job info including WebSocket channel
        status_value = db_job.status
        if isinstance(status_value, DBCrawlStatus):
            raw_status = status_value.value
        elif isinstance(status_value, str):
            raw_status = status_value
        else:
            raw_status = DBCrawlStatus.PENDING.value

        job_status = SchemaCrawlStatus(raw_status)

        return {
            "job_id": job_id,
            "celery_task_id": db_job.celery_task_id or "",
            "land_id": db_job.land_id,
            "status": job_status.value,
            "created_at": (db_job.created_at.isoformat() if getattr(db_job, "created_at", None) else datetime.utcnow().isoformat()),
            "parameters": db_job.parameters or {},
            "ws_channel": f"crawl_progress_{job_id}",
        }
    
    except Exception as e:
        # Handle task dispatch failure
        if job_id is not None:
            await crud_job.job.update_status(
                db, 
                job_id=job_id, 
                status=DBCrawlStatus.FAILED,
                result={"error": str(e)}
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Crawl task dispatch failed: {str(e)}"
        )


async def get_crawl_pipeline_stats(db: AsyncSession, land_id: int) -> Dict[str, Any]:
    """
    Récupère les statistiques du pipeline de crawl selon la logique legacy.
    
    Implémente la logique des dates du pipeline:
    1. created_at: Date de création de l'expression  
    2. fetched_at: Date de récupération du contenu (crawled_at)
    3. approved_at: Date d'approbation (si pertinence > 0)
    """
    try:
        # Statistiques générales du land
        land_stats_query = await db.execute(text("""
            SELECT 
                COUNT(*) as total_expressions,
                COUNT(CASE WHEN crawled_at IS NOT NULL THEN 1 END) as fetched_expressions,
                COUNT(CASE WHEN approved_at IS NOT NULL THEN 1 END) as approved_expressions,
                COUNT(CASE WHEN relevance > 0 THEN 1 END) as relevant_expressions,
                AVG(relevance) as avg_relevance,
                MAX(relevance) as max_relevance,
                COUNT(CASE WHEN depth = 0 THEN 1 END) as start_url_expressions,
                COUNT(CASE WHEN depth = 1 THEN 1 END) as depth_1_expressions,
                COUNT(CASE WHEN depth >= 2 THEN 1 END) as deeper_expressions
            FROM expressions 
            WHERE land_id = :land_id
        """), {"land_id": land_id})
        
        land_stats = land_stats_query.fetchone()
        
        # Statistiques par profondeur
        depth_stats_query = await db.execute(text("""
            SELECT 
                depth,
                COUNT(*) as count,
                COUNT(CASE WHEN approved_at IS NOT NULL THEN 1 END) as approved_count,
                AVG(relevance) as avg_relevance
            FROM expressions 
            WHERE land_id = :land_id
            GROUP BY depth
            ORDER BY depth
        """), {"land_id": land_id})
        
        depth_stats = [dict(row._mapping) for row in depth_stats_query.fetchall()]
        
        # Progression temporelle
        timeline_query = await db.execute(text("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as created_count,
                COUNT(CASE WHEN crawled_at IS NOT NULL THEN 1 END) as crawled_count,
                COUNT(CASE WHEN approved_at IS NOT NULL THEN 1 END) as approved_count
            FROM expressions 
            WHERE land_id = :land_id
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) DESC
            LIMIT 10
        """), {"land_id": land_id})
        
        timeline = [dict(row._mapping) for row in timeline_query.fetchall()]
        
        # Expressions non traitées (respectant la logique du pipeline)
        unprocessed_query = await db.execute(text("""
            SELECT 
                COUNT(CASE WHEN crawled_at IS NULL THEN 1 END) as not_fetched,
                COUNT(CASE WHEN crawled_at IS NOT NULL AND approved_at IS NULL AND relevance = 0 THEN 1 END) as fetched_not_relevant,
                COUNT(CASE WHEN crawled_at IS NOT NULL AND relevance > 0 AND approved_at IS NULL THEN 1 END) as relevant_not_approved
            FROM expressions 
            WHERE land_id = :land_id
        """), {"land_id": land_id})
        
        unprocessed = unprocessed_query.fetchone()
        
        return {
            "land_id": land_id,
            "pipeline_stats": {
                "total_expressions": land_stats.total_expressions if land_stats else 0,
                "fetched_expressions": land_stats.fetched_expressions if land_stats else 0,
                "approved_expressions": land_stats.approved_expressions if land_stats else 0,
                "relevant_expressions": land_stats.relevant_expressions if land_stats else 0,
                "avg_relevance": float(land_stats.avg_relevance) if land_stats and land_stats.avg_relevance else 0.0,
                "max_relevance": float(land_stats.max_relevance) if land_stats and land_stats.max_relevance else 0.0,
                "completion_rate": (land_stats.approved_expressions / land_stats.total_expressions * 100) if land_stats and land_stats.total_expressions > 0 else 0.0
            },
            "depth_distribution": depth_stats,
            "processing_timeline": timeline,
            "unprocessed_breakdown": {
                "not_fetched": unprocessed.not_fetched if unprocessed else 0,
                "fetched_not_relevant": unprocessed.fetched_not_relevant if unprocessed else 0,
                "relevant_not_approved": unprocessed.relevant_not_approved if unprocessed else 0
            },
            "health_indicators": {
                "dictionary_populated": await _check_dictionary_health(db, land_id),
                "pipeline_consistent": await _check_pipeline_consistency(db, land_id)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting pipeline stats for land {land_id}: {e}")
        raise


async def _check_dictionary_health(db: AsyncSession, land_id: int) -> bool:
    """Vérifie si le dictionnaire du land est peuplé (évite Dictionary Starvation)"""
    try:
        dict_query = await db.execute(text("""
            SELECT COUNT(*) as dict_count
            FROM land_dictionaries ld
            WHERE ld.land_id = :land_id
        """), {"land_id": land_id})
        
        dict_count = dict_query.scalar()
        return dict_count > 0
        
    except Exception as e:
        logger.error(f"Error checking dictionary health for land {land_id}: {e}")
        return False


async def _check_pipeline_consistency(db: AsyncSession, land_id: int) -> bool:
    """Vérifie la cohérence du pipeline (approved_at seulement si relevance > 0)"""
    try:
        inconsistency_query = await db.execute(text("""
            SELECT COUNT(*) as inconsistent_count
            FROM expressions 
            WHERE land_id = :land_id 
            AND (
                (approved_at IS NOT NULL AND relevance = 0) OR
                (approved_at IS NULL AND relevance > 0 AND crawled_at IS NOT NULL)
            )
        """), {"land_id": land_id})
        
        inconsistent_count = inconsistency_query.scalar()
        return inconsistent_count == 0
        
    except Exception as e:
        logger.error(f"Error checking pipeline consistency for land {land_id}: {e}")
        return False


async def fix_pipeline_inconsistencies(db: AsyncSession, land_id: int) -> Dict[str, Any]:
    """
    Répare les incohérences du pipeline crawl pour un land.
    
    Applique la logique legacy:
    - approved_at = NOW() si relevance > 0 ET crawled_at IS NOT NULL 
    - approved_at = NULL si relevance = 0
    """
    try:
        # 1. Approuver les expressions pertinentes non approuvées
        approve_query = await db.execute(text("""
            UPDATE expressions 
            SET approved_at = :now
            WHERE land_id = :land_id 
            AND relevance > 0 
            AND crawled_at IS NOT NULL 
            AND approved_at IS NULL
        """), {"land_id": land_id, "now": datetime.utcnow()})
        
        approved_count = approve_query.rowcount
        
        # 2. Désapprouver les expressions non pertinentes
        disapprove_query = await db.execute(text("""
            UPDATE expressions 
            SET approved_at = NULL
            WHERE land_id = :land_id 
            AND relevance = 0 
            AND approved_at IS NOT NULL
        """), {"land_id": land_id})
        
        disapproved_count = disapprove_query.rowcount
        
        await db.commit()
        
        result = {
            "land_id": land_id,
            "approved_expressions": approved_count,
            "disapproved_expressions": disapproved_count,
            "total_fixes": approved_count + disapproved_count,
            "fixed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Fixed pipeline inconsistencies for land {land_id}: {result}")
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error fixing pipeline inconsistencies for land {land_id}: {e}")
        raise

async def consolidate_land(db: AsyncSession, land_id: int) -> Dict[str, Any]:
    """
    Consolidation des données d'un land - porte du legacy
    Implémentation placeholder pour la compatibilité des tâches Celery
    """
    try:
        # TODO: Implémenter la logique de consolidation du legacy
        # Pour l'instant, on fait juste les réparations d'incohérences
        result = await fix_pipeline_inconsistencies(db, land_id)
        
        return {
            "success": True,
            "message": f"Consolidation (placeholder) terminée pour land {land_id}",
            "repairs": result
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la consolidation pour land {land_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }
