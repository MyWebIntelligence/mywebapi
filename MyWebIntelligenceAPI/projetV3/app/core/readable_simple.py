"""
Approche simplifiée pour les tâches readable sans pool dédié.
Utilise asyncio.run pour exécuter les sessions async dans le contexte sync de Celery.
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.db.base import AsyncSessionLocal
from app.db.models import Expression, CrawlJob, CrawlStatus
from app.utils.logging import get_logger
from sqlalchemy import select, and_, func

logger = get_logger(__name__)

async def update_job_status_simple(job_id: int, status: str, message: str, result_data: Optional[Dict[str, Any]] = None):
    """Met à jour le statut d'un job en utilisant la session async existante."""
    async with AsyncSessionLocal() as db:
        try:
            job = await db.get(CrawlJob, job_id)
            if job:
                if status == "running":
                    job.status = CrawlStatus.RUNNING
                    job.started_at = datetime.utcnow()
                    job.current_step = message
                elif status == "completed":
                    job.status = CrawlStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                    job.current_step = message
                    if result_data:
                        job.result_data = result_data
                elif status == "failed":
                    job.status = CrawlStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    job.error_message = message
                    if result_data:
                        job.result_data = {"error": message}
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            await db.rollback()

async def get_expressions_to_process_simple(land_id: int, limit: Optional[int] = None, depth: Optional[int] = None) -> List[Expression]:
    """Récupère les expressions à traiter."""
    async with AsyncSessionLocal() as db:
        query = select(Expression).where(
            and_(
                Expression.land_id == land_id,
                Expression.crawled_at.isnot(None),
                Expression.readable_at.is_(None)
            )
        )
        
        if depth is not None:
            query = query.where(Expression.depth <= depth)
        
        query = query.order_by(Expression.crawled_at, Expression.depth)
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

async def get_readable_stats_simple(land_id: int) -> Dict[str, Any]:
    """Récupère les stats readable."""
    async with AsyncSessionLocal() as db:
        # Stats totales
        query = select(
            func.count(Expression.id).label('total'),
            func.count(Expression.readable).label('with_readable'),
            func.max(Expression.readable_at).label('last_processed')
        ).where(Expression.land_id == land_id)
        
        result = await db.execute(query)
        row = result.first()
        
        total = row.total or 0
        with_readable = row.with_readable or 0
        without_readable = total - with_readable
        
        # Expressions éligibles
        eligible_query = select(func.count(Expression.id)).where(
            and_(
                Expression.land_id == land_id,
                Expression.crawled_at.isnot(None),
                Expression.readable_at.is_(None)
            )
        )
        eligible_result = await db.execute(eligible_query)
        eligible = eligible_result.scalar() or 0
        
        coverage = (with_readable / total * 100) if total > 0 else 0.0
        
        return {
            'total_expressions': total,
            'expressions_with_readable': with_readable,
            'expressions_without_readable': without_readable,
            'expressions_eligible': eligible,
            'last_processed_at': row.last_processed,
            'processing_coverage': coverage
        }

async def update_expression_readable_simple(expression_id: int, readable_data: Dict[str, Any]):
    """Met à jour une expression avec le contenu readable."""
    async with AsyncSessionLocal() as db:
        try:
            expression = await db.get(Expression, expression_id)
            if expression:
                # Mettre à jour les champs
                for field, value in readable_data.items():
                    if hasattr(expression, field) and value is not None:
                        setattr(expression, field, value)
                
                # Toujours marquer comme traité
                expression.readable_at = datetime.utcnow()
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update expression {expression_id}: {e}")
            await db.rollback()