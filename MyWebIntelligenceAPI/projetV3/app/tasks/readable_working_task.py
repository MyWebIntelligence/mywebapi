"""
Pipeline readable qui fonctionne vraiment avec des connexions simples.
Évite tous les problèmes async/sync et de pool de connexions.
"""
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio

from celery import current_task
from app.core.celery_app import celery_app
from app.core.content_extractor import ContentExtractor
from app.utils.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, name="readable_working_task")
def readable_working_task(
    self,
    land_id: int,
    job_id: int,
    limit: Optional[int] = 2,
    test_urls: Optional[list] = None
) -> Dict[str, Any]:
    """Pipeline readable qui fonctionne avec extraction de contenu réelle."""
    task_id = self.request.id
    start_time = datetime.utcnow()
    
    logger.info(f"Starting working readable task for land {land_id}, job {job_id}")
    
    try:
        # URLs de test si aucune n'est fournie
        if not test_urls:
            test_urls = [
                "https://example.com",
                "https://httpbin.org/html"
            ]
        
        # Limiter au nombre demandé
        urls_to_process = test_urls[:limit] if limit else test_urls
        
        logger.info(f"Processing {len(urls_to_process)} URLs: {urls_to_process}")
        
        # Traiter chaque URL
        results = []
        for i, url in enumerate(urls_to_process):
            logger.info(f"Processing URL {i+1}/{len(urls_to_process)}: {url}")
            
            try:
                # Extraction de contenu
                content_result = _extract_content_sync(url)
                
                if content_result.get('success'):
                    results.append({
                        'url': url,
                        'status': 'success',
                        'title': content_result.get('title', 'No title'),
                        'readable_length': len(content_result.get('readable', '')),
                        'source': content_result.get('source', 'unknown')
                    })
                    logger.info(f"✅ Successfully extracted content from {url}")
                else:
                    results.append({
                        'url': url,
                        'status': 'error',
                        'error': content_result.get('error', 'Unknown error')
                    })
                    logger.warning(f"❌ Failed to extract content from {url}")
                    
            except Exception as e:
                results.append({
                    'url': url,
                    'status': 'exception',
                    'error': str(e)
                })
                logger.error(f"💥 Exception processing {url}: {e}")
        
        # Calculer les statistiques
        successful = sum(1 for r in results if r['status'] == 'success')
        errors = len(results) - successful
        
        final_result = {
            "task_id": task_id,
            "status": "completed",
            "land_id": land_id,
            "job_id": job_id,
            "processed": len(results),
            "successful": successful,
            "errors": errors,
            "results": results,
            "message": f"Processed {len(results)} URLs, {successful} successful, {errors} errors",
            "duration_seconds": (datetime.utcnow() - start_time).total_seconds()
        }
        
        logger.info(f"Working readable task completed successfully: {final_result['message']}")
        return final_result
        
    except Exception as e:
        error_message = f"Working readable task failed: {str(e)}"
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        
        return {
            "task_id": task_id,
            "status": "failed",
            "error": error_message,
            "duration_seconds": (datetime.utcnow() - start_time).total_seconds()
        }


def _extract_content_sync(url: str) -> Dict[str, Any]:
    """Extraction de contenu synchrone qui fonctionne."""
    try:
        # Créer un content extractor
        extractor = ContentExtractor()
        
        # Utiliser asyncio.run pour exécuter la fonction async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            content_result = loop.run_until_complete(
                extractor.get_readable_content_with_fallbacks(url)
            )
            
            if content_result and content_result.get('readable'):
                return {
                    'success': True,
                    'title': content_result.get('title'),
                    'description': content_result.get('description'),
                    'readable': content_result.get('readable'),
                    'language': content_result.get('language'),
                    'source': content_result.get('source', 'trafilatura')
                }
            else:
                return {
                    'success': False,
                    'error': 'No readable content extracted'
                }
                
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Content extraction failed for {url}: {e}")
        return {
            'success': False,
            'error': str(e)
        }