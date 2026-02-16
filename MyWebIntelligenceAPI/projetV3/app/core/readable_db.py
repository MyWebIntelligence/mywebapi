"""
Pool de connexions dédié pour les tâches readable Celery.
Utilise des connexions synchrones pour éviter les conflits AsyncSession + fork.
"""
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from sqlalchemy import create_engine, select, update, and_, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine.url import make_url
from datetime import datetime

from app.config import settings
from app.db.models import Expression, Land, CrawlJob, CrawlStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)

class ReadableDBPool:
    """Pool de connexions synchrones pour les tâches readable."""
    
    def __init__(self):
        # Créer l'URL synchrone à partir de l'URL async
        base_url = make_url(settings.DATABASE_URL)
        if "+asyncpg" in base_url.drivername:
            sync_driver = base_url.drivername.replace("+asyncpg", "+psycopg2")
        else:
            sync_driver = base_url.drivername
        
        sync_url = base_url.set(drivername=sync_driver)
        
        logger.info(f"Creating sync DB pool with URL: {str(sync_url).replace(base_url.password, '***')}")
        logger.info(f"Driver: {sync_driver}, Host: {base_url.host}, User: {base_url.username}")
        
        # Créer engine avec pool dédié pour Celery
        self.engine = create_engine(
            str(sync_url),
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
        
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
    
    @contextmanager
    def get_session(self):
        """Context manager pour obtenir une session."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def update_job_status(self, job_id: int, status: str, message: str, result_data: Optional[Dict[str, Any]] = None):
        """Met à jour le statut d'un job."""
        with self.get_session() as session:
            job = session.get(CrawlJob, job_id)
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
    
    def get_expressions_to_process(self, land_id: int, limit: Optional[int] = None, depth: Optional[int] = None) -> List[Expression]:
        """Récupère les expressions éligibles pour le traitement readable."""
        with self.get_session() as session:
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
            
            result = session.execute(query)
            return result.scalars().all()
    
    def get_readable_stats(self, land_id: int) -> Dict[str, Any]:
        """Récupère les statistiques readable pour un land."""
        with self.get_session() as session:
            # Stats totales
            query = select(
                func.count(Expression.id).label('total'),
                func.count(Expression.readable).label('with_readable'),
                func.max(Expression.readable_at).label('last_processed')
            ).where(Expression.land_id == land_id)
            
            result = session.execute(query)
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
            eligible_result = session.execute(eligible_query)
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
    
    def update_expression_readable(self, expression_id: int, readable_data: Dict[str, Any]):
        """Met à jour une expression avec le contenu readable."""
        with self.get_session() as session:
            expression = session.get(Expression, expression_id)
            if expression:
                # Mettre à jour les champs
                for field, value in readable_data.items():
                    if hasattr(expression, field) and value is not None:
                        setattr(expression, field, value)
                
                # Toujours marquer comme traité
                expression.readable_at = datetime.utcnow()
    
    def batch_update_expressions(self, updates: List[Dict[str, Any]]):
        """Met à jour plusieurs expressions en batch."""
        if not updates:
            return
            
        with self.get_session() as session:
            for update_data in updates:
                expression_id = update_data.pop('id')
                expression = session.get(Expression, expression_id)
                if expression:
                    for field, value in update_data.items():
                        if hasattr(expression, field) and value is not None:
                            setattr(expression, field, value)
                    
                    if 'readable_at' not in update_data:
                        expression.readable_at = datetime.utcnow()

# Instance globale du pool
readable_db_pool = ReadableDBPool()