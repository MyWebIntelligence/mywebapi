"""
Celery tasks for readable content processing.
Handles asynchronous processing with progress reporting via WebSocket.
"""
from datetime import datetime
from typing import Dict, Any, Optional

from celery import current_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.websocket import websocket_manager
from app.core.readable_simple import update_job_status_simple, get_readable_stats_simple
from app.schemas.readable import MergeStrategy, ReadableProcessingResult
from app.services.readable_simple_service import ReadableSimpleService
from app.utils.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, name="process_readable_task")
def process_readable_task(
    self,
    land_id: int,
    job_id: int,
    limit: Optional[int] = None,
    depth: Optional[int] = None,
    merge_strategy: str = "smart_merge",
    enable_llm: bool = False,
    batch_size: int = 10,
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """
    Process readable content for expressions in a land.
    
    Args:
        land_id: ID of the land to process
        job_id: ID of the crawl job for tracking
        limit: Maximum number of expressions to process
        depth: Maximum crawl depth to process
        merge_strategy: Strategy for merging content (smart_merge, mercury_priority, preserve_existing)
        enable_llm: Whether to enable LLM validation
        batch_size: Number of expressions to process per batch
        max_concurrent: Maximum number of concurrent batches
    
    Returns:
        Dictionary with processing results and statistics
    """
    task_id = self.request.id
    logger.info(f"Starting readable processing task {task_id} for land {land_id}")
    
    return _run_async_readable_processing(
        task_id=task_id,
        land_id=land_id,
        job_id=job_id,
        limit=limit,
        depth=depth,
        merge_strategy=merge_strategy,
        enable_llm=enable_llm,
        batch_size=batch_size,
        max_concurrent=max_concurrent
    )


def _run_async_readable_processing(
    task_id: str,
    land_id: int,
    job_id: int,
    limit: Optional[int] = None,
    depth: Optional[int] = None,
    merge_strategy: str = "smart_merge",
    enable_llm: bool = False,
    batch_size: int = 10,
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """Run the async readable processing in a sync context."""
    import asyncio
    
    # Create new event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _async_readable_processing(
                task_id=task_id,
                land_id=land_id,
                job_id=job_id,
                limit=limit,
                depth=depth,
                merge_strategy=merge_strategy,
                enable_llm=enable_llm,
                batch_size=batch_size,
                max_concurrent=max_concurrent
            )
        )
        return result
    finally:
        loop.close()


async def _async_readable_processing(
    task_id: str,
    land_id: int,
    job_id: int,
    limit: Optional[int] = None,
    depth: Optional[int] = None,
    merge_strategy: str = "smart_merge",
    enable_llm: bool = False,
    batch_size: int = 10,
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """Main async function for readable processing using dedicated pool."""
    start_time = datetime.utcnow()
    
    try:
        # Update job status using simple approach
        await update_job_status_simple(job_id, "running", "Starting readable processing...")
        
        # Send initial progress
        await _send_progress(
            task_id, land_id, job_id, 0, 0, "Initializing readable processing..."
        )
        
        # Initialize readable service with simple approach
        readable_service = ReadableSimpleService()
        
        # Get stats using simple approach
        stats = await readable_service.get_readable_stats(land_id)
        
        await _send_progress(
            task_id, land_id, job_id, 0, stats.get('expressions_eligible', 0),
            f"Found {stats.get('expressions_eligible', 0)} expressions eligible for processing"
        )
        
        # Validate merge strategy
        try:
            strategy_enum = MergeStrategy(merge_strategy)
        except ValueError:
            strategy_enum = MergeStrategy.SMART_MERGE
            logger.warning(f"Invalid merge strategy '{merge_strategy}', using smart_merge")
        
        # Process readable content
        result = await readable_service.process_land_readable(
            land_id=land_id,
            limit=limit,
            depth=depth,
            merge_strategy=strategy_enum,
            enable_llm=enable_llm,
            batch_size=batch_size
        )
        
        # Update job with final results
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        success_message = (
            f"Readable processing completed: {result.updated}/{result.processed} expressions updated, "
            f"{result.media_created} media created, {result.links_created} links created"
        )
        
        # Update job status using simple approach
        await update_job_status_simple(job_id, "completed", success_message, result.dict())
        
        # Send final progress
        await _send_progress(
            task_id, land_id, job_id, result.processed, result.processed,
            success_message, True
        )
        
        logger.info(f"Readable processing task {task_id} completed successfully")
        
        return {
            "task_id": task_id,
            "status": "completed",
            "result": result.dict(),
            "duration_seconds": duration,
            "message": success_message
        }
        
    except Exception as e:
        error_message = f"Readable processing failed: {str(e)}"
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        
        # Update job status using simple approach
        await update_job_status_simple(job_id, "failed", error_message)
        
        # Send error progress
        await _send_progress(
            task_id, land_id, job_id, 0, 0, error_message, True
        )
        
        return {
            "task_id": task_id,
            "status": "failed",
            "error": error_message,
            "duration_seconds": (datetime.utcnow() - start_time).total_seconds()
        }


# Fonction supprimée - utilise maintenant readable_db_pool.update_job_status

# Ancienne fonction async supprimée - remplacée par le pool dédié


async def _send_progress(
    task_id: str,
    land_id: int,
    job_id: int,
    current: int,
    total: int,
    message: str,
    completed: bool = False
):
    """Send progress update via WebSocket."""
    try:
        progress_data = {
            "task_id": task_id,
            "land_id": land_id,
            "job_id": job_id,
            "current": current,
            "total": total,
            "percentage": (current / total * 100) if total > 0 else 0,
            "message": message,
            "completed": completed,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to both specific job channel and general land channel
        await websocket_manager.send_crawl_progress(f"job_{job_id}", processed=progress_data.get('processed', 0), total=progress_data.get('total', 0), message=progress_data.get('message', ''))
        await websocket_manager.send_crawl_progress(f"land_{land_id}", processed=progress_data.get('processed', 0), total=progress_data.get('total', 0), message=progress_data.get('message', ''))
        
    except Exception as e:
        logger.error(f"Failed to send progress update: {e}")


@celery_app.task(bind=True, name="readable_stats_task")
def readable_stats_task(self, land_id: int) -> Dict[str, Any]:
    """Get readable processing statistics for a land."""
    import asyncio
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(_get_readable_stats_async(land_id))
    finally:
        loop.close()


async def _get_readable_stats_async(land_id: int) -> Dict[str, Any]:
    """Get readable stats asynchronously."""
    async with AsyncSessionLocal() as db:
        readable_service = ReadableService(db)
        stats = await readable_service.get_readable_stats(land_id)
        return stats.dict()


@celery_app.task(bind=True, name="validate_single_expression_task")
def validate_single_expression_task(
    self,
    expression_id: int,
    enable_llm: bool = True
) -> Dict[str, Any]:
    """Validate a single expression with LLM (for individual testing)."""
    import asyncio
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(
            _validate_single_expression_async(expression_id, enable_llm)
        )
    finally:
        loop.close()


async def _validate_single_expression_async(
    expression_id: int,
    enable_llm: bool = True
) -> Dict[str, Any]:
    """Validate single expression asynchronously."""
    from sqlalchemy import select
    from app.db.models import Expression
    
    async with AsyncSessionLocal() as db:
        try:
            # Get expression
            query = select(Expression).where(Expression.id == expression_id)
            result = await db.execute(query)
            expression = result.scalar_one_or_none()
            
            if not expression:
                return {
                    "success": False,
                    "error": f"Expression {expression_id} not found"
                }
            
            # Initialize service and process
            readable_service = ReadableService(db)
            
            # Process single expression
            process_result = await readable_service._process_single_expression(
                expression, MergeStrategy.SMART_MERGE, enable_llm
            )
            
            await db.commit()
            
            return {
                "success": True,
                "expression_id": expression_id,
                "result": process_result
            }
            
        except Exception as e:
            logger.error(f"Failed to validate expression {expression_id}: {e}")
            await db.rollback()
            return {
                "success": False,
                "error": str(e)
            }