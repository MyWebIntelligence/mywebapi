"""
Task de test simple pour le readable sans complexité.
Test basique qui évite tous les problèmes de session/pool.
"""
from datetime import datetime
from typing import Dict, Any, Optional

from celery import current_task
from app.core.celery_app import celery_app
from app.utils.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, name="test_readable_simple")
def test_readable_simple(
    self,
    land_id: int,
    job_id: int,
    limit: Optional[int] = 2
) -> Dict[str, Any]:
    """Test simple du pipeline readable sans complexité."""
    task_id = self.request.id
    start_time = datetime.utcnow()
    
    logger.info(f"Starting simple readable test for land {land_id}, job {job_id}")
    
    try:
        # Simuler le traitement
        import time
        time.sleep(2)  # Simule 2 secondes de travail
        
        # Simuler des résultats
        result = {
            "task_id": task_id,
            "status": "completed",
            "land_id": land_id,
            "job_id": job_id,
            "processed": limit or 2,
            "updated": 1,
            "errors": 0,
            "message": f"Simple readable test completed for {limit or 2} expressions",
            "duration_seconds": (datetime.utcnow() - start_time).total_seconds()
        }
        
        logger.info(f"Simple readable test completed successfully: {result}")
        return result
        
    except Exception as e:
        error_message = f"Simple readable test failed: {str(e)}"
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        
        return {
            "task_id": task_id,
            "status": "failed",
            "error": error_message,
            "duration_seconds": (datetime.utcnow() - start_time).total_seconds()
        }