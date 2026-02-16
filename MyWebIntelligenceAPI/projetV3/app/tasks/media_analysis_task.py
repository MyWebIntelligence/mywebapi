"""
Tâche Celery pour l'analyse de médias asynchrone.
"""
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
from celery import group
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.crud import crud_job, crud_media
from app.crud.crud_land import land as crud_land
from app.db.models import CrawlStatus
from app.core.media_processor import MediaProcessor
from app.schemas.media import MediaAnalysisResponse

logger = logging.getLogger(__name__)


async def _async_analyze_land_media_task(
    job_id: int, 
    land_id: int, 
    depth: int = 999, 
    minrel: float = 0.0,
    batch_size: int = 50
) -> Dict[str, Any]:
    """
    Analyse asynchrone des médias d'un land avec traitement par batch.
    
    Args:
        job_id: ID du job Celery
        land_id: ID du land
        depth: Profondeur max des expressions
        minrel: Score de pertinence minimum
        batch_size: Nombre de médias par batch
    """
    start_time = datetime.now(timezone.utc)
    
    logger.info(f"=" * 80)
    logger.info(f"MEDIA ANALYSIS STARTED - Job ID: {job_id}, Land ID: {land_id}")
    logger.info(f"Parameters: depth={depth}, minrel={minrel}, batch_size={batch_size}")
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info(f"=" * 80)

    async with AsyncSessionLocal() as db:
        try:
            # Update job status
            await crud_job.job.update_status(db, job_id=job_id, status=CrawlStatus.RUNNING)
            
            # Get land info
            land = await crud_land.get(db, id=land_id)
            if not land:
                raise ValueError(f"Land {land_id} not found")
            
            # Get filtered expressions
            from sqlalchemy import text
            expressions_query = await db.execute(
                text("""
                SELECT e.id, e.url, e.depth, e.relevance
                FROM expressions e 
                WHERE e.land_id = :land_id
                AND e.depth <= :depth
                AND e.relevance >= :minrel
                ORDER BY e.relevance DESC
                """),
                {
                    "land_id": land_id,
                    "depth": depth if depth is not None else 999,
                    "minrel": minrel if minrel is not None else 0.0
                }
            )
            
            expressions = expressions_query.fetchall()
            expression_ids = [exp.id for exp in expressions]
            
            if not expression_ids:
                result = {
                    "land_id": land_id,
                    "land_name": land.name,
                    "total_expressions": 0,
                    "filtered_expressions": 0,
                    "total_media": 0,
                    "analyzed_media": 0,
                    "failed_analysis": 0,
                    "processing_time": 0,
                    "message": "No expressions found with given filters"
                }
                await crud_job.job.update_status(
                    db, job_id=job_id, status=CrawlStatus.COMPLETED, result=result
                )
                return result
            
            # Get unprocessed media for these expressions
            media_query = await db.execute(
                text("""
                SELECT m.id, m.url, m.type, m.expression_id, m.is_processed
                FROM media m
                WHERE m.expression_id = ANY(:expression_ids)
                AND m.type = 'IMAGE'
                AND (m.is_processed IS NULL OR m.is_processed = false)
                ORDER BY m.created_at DESC
                """),
                {"expression_ids": expression_ids}
            )
            
            media_list = media_query.fetchall()
            total_media = len(media_list)
            
            logger.info(f"Found {total_media} unprocessed media items")
            
            if total_media == 0:
                result = {
                    "land_id": land_id,
                    "land_name": land.name,
                    "total_expressions": len(expressions),
                    "filtered_expressions": len(expressions),
                    "total_media": 0,
                    "analyzed_media": 0,
                    "failed_analysis": 0,
                    "processing_time": 0,
                    "message": "No unprocessed media found"
                }
                await crud_job.job.update_status(
                    db, job_id=job_id, status=CrawlStatus.COMPLETED, result=result
                )
                return result
            
            # Process in batches if large number of media
            if total_media <= batch_size:
                # Process directly
                media_ids = [m.id for m in media_list]
                analyzed, failed = await _process_media_batch(media_ids)
            else:
                # Split into batches and process via Celery
                media_ids = [m.id for m in media_list]
                batches = [
                    media_ids[i:i + batch_size] 
                    for i in range(0, len(media_ids), batch_size)
                ]
                
                logger.info(f"Processing {len(batches)} batches of {batch_size} media each")
                
                # Create batch tasks
                batch_tasks = [
                    celery_app.signature(
                        "tasks.analyze_media_batch_task",
                        args=[batch]
                    )
                    for batch in batches
                ]
                
                # Execute batches
                group_result = group(batch_tasks).apply_async()
                batch_results = await asyncio.to_thread(
                    group_result.get, disable_sync_subtasks=False
                )
                
                # Aggregate results
                analyzed = sum(r.get("analyzed", 0) for r in batch_results)
                failed = sum(r.get("failed", 0) for r in batch_results)
            
            # Calculate final metrics
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            result = {
                "land_id": land_id,
                "land_name": land.name,
                "total_expressions": len(expressions),
                "filtered_expressions": len(expressions),
                "total_media": total_media,
                "analyzed_media": analyzed,
                "failed_analysis": failed,
                "processing_time": round(duration, 2),
                "filters_applied": {"depth": depth, "minrel": minrel}
            }
            
            logger.info(f"=" * 80)
            logger.info(f"MEDIA ANALYSIS COMPLETED - Job ID: {job_id}, Land ID: {land_id}")
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info(f"Media Analyzed: {analyzed}/{total_media}")
            logger.info(f"Failed: {failed}")
            logger.info(f"Success Rate: {(analyzed/(analyzed+failed)*100):.1f}%" if (analyzed+failed) > 0 else "N/A")
            logger.info(f"=" * 80)
            
            await crud_job.job.update_status(
                db, job_id=job_id, status=CrawlStatus.COMPLETED, result=result
            )
            
            return result
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"=" * 80)
            logger.error(f"MEDIA ANALYSIS FAILED - Job ID: {job_id}, Land ID: {land_id}")
            logger.error(f"Duration: {duration:.2f} seconds")
            logger.error(f"Error: {str(e)}")
            logger.error(f"=" * 80)
            logger.exception("Full traceback:")
            
            error_result = {
                "error": str(e),
                "land_id": land_id,
                "duration_seconds": duration,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
            await crud_job.job.update_status(
                db, job_id=job_id, status=CrawlStatus.FAILED, result=error_result
            )
            
            raise


async def _process_media_batch(media_ids: List[int]) -> tuple[int, int]:
    """
    Traite un batch de médias.
    
    Returns:
        tuple: (analyzed_count, failed_count)
    """
    analyzed = 0
    failed = 0
    
    async with AsyncSessionLocal() as db:
        async with httpx.AsyncClient() as http_client:
            media_processor = MediaProcessor(db, http_client)
            
            # Get media details
            from sqlalchemy import text
            media_query = await db.execute(
                text("SELECT id, url FROM media WHERE id = ANY(:media_ids)"),
                {"media_ids": media_ids}
            )
            media_items = media_query.fetchall()
            
            for media_item in media_items:
                try:
                    # Analyze the media
                    analysis_result = await media_processor.analyze_image(media_item.url)
                    
                    if analysis_result.get('error'):
                        failed += 1
                        logger.warning(f"Media {media_item.id} analysis failed: {analysis_result['error']}")
                    else:
                        analyzed += 1
                        
                        # Update media record
                        await crud_media.media.update_media_analysis(
                            db,
                            media_id=media_item.id,
                            analysis_data=analysis_result
                        )
                        
                        logger.debug(f"Media {media_item.id} analyzed successfully")
                        
                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing media {media_item.id}: {str(e)}")
    
    return analyzed, failed


@celery_app.task(name="tasks.analyze_land_media_task", bind=True)
def analyze_land_media_task(
    self, 
    job_id: int, 
    land_id: int, 
    depth: int = 999, 
    minrel: float = 0.0,
    batch_size: int = 50
):
    """
    Tâche Celery pour analyser les médias d'un land (wrapper synchrone).
    
    Args:
        job_id: ID du job Celery
        land_id: ID du land à analyser
        depth: Profondeur max des expressions (0 = URLs initiales uniquement)
        minrel: Score de pertinence minimum des expressions
        batch_size: Nombre de médias par batch pour traitement parallèle
    """
    # Setup event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run async task
    try:
        return loop.run_until_complete(
            _async_analyze_land_media_task(job_id, land_id, depth, minrel, batch_size)
        )
    finally:
        pass


@celery_app.task(name="tasks.analyze_media_batch_task", bind=True)
def analyze_media_batch_task(self, media_ids: List[int]):
    """
    Tâche Celery pour analyser un batch de médias.
    
    Args:
        media_ids: Liste des IDs de médias à analyser
        
    Returns:
        dict: Résultats du batch (analyzed, failed)
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        analyzed, failed = loop.run_until_complete(_process_media_batch(media_ids))
        return {"analyzed": analyzed, "failed": failed}
    except Exception as e:
        logger.exception(f"Batch media analysis failed for IDs {media_ids}: {str(e)}")
        return {"analyzed": 0, "failed": len(media_ids)}