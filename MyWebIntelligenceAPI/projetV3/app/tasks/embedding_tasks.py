"""
Tâches Celery pour les embeddings et l'analyse de texte
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.embedding_service import EmbeddingService
from app.services.text_processor_service import TextProcessorService

logger = logging.getLogger(__name__)

def get_db() -> Session:
    """Obtient une session de base de données pour les tâches Celery"""
    return SessionLocal()

@celery_app.task(bind=True, name="extract_paragraphs_for_land")
def extract_paragraphs_for_land_task(
    self,
    land_id: int,
    force_reextract: bool = False,
    min_length: int = 50,
    max_length: int = 5000,
    requested_by: Optional[int] = None
) -> Dict[str, Any]:
    """
    Tâche Celery pour extraire les paragraphes d'un land
    
    Args:
        land_id: ID du land à traiter
        force_reextract: Force la réextraction des paragraphes existants
        min_length: Longueur minimale d'un paragraphe
        max_length: Longueur maximale d'un paragraphe
        
    Returns:
        Statistiques de l'extraction
    """
    
    try:
        logger.info(
            "Starting paragraph extraction task for land %s (requested_by=%s)",
            land_id,
            requested_by
        )
        
        # Mettre à jour le statut de la tâche
        self.update_state(
            state='PROGRESS',
            meta={
                'land_id': land_id,
                'requested_by': requested_by,
                'status': 'initializing',
                'message': 'Initializing paragraph extraction...'
            }
        )
        
        db = get_db()
        text_processor = TextProcessorService()
        
        # Exécuter l'extraction de manière asynchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                text_processor.extract_paragraphs_for_land(
                    db, land_id, force_reextract, min_length, max_length
                )
            )
        finally:
            loop.close()
            db.close()
        
        # Mettre à jour le statut final
        self.update_state(
            state='SUCCESS',
            meta={
                'land_id': land_id,
                'requested_by': requested_by,
                'status': 'completed',
                'result': result,
                'message': f"Extraction completed: {result.get('created_paragraphs', 0)} paragraphs created"
            }
        )
        
        logger.info(f"Paragraph extraction completed for land {land_id}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Paragraph extraction failed for land {land_id}: {e}")
        
        self.update_state(
            state='FAILURE',
            meta={
                'land_id': land_id,
                'requested_by': requested_by,
                'status': 'failed',
                'error': str(e),
                'message': f"Extraction failed: {str(e)}"
            }
        )
        
        raise

@celery_app.task(bind=True, name="generate_embeddings_for_land")
def generate_embeddings_for_land_task(
    self,
    land_id: int,
    provider_name: str = "openai",
    model: str = None,
    force_regenerate: bool = False,
    batch_size: int = 100,
    extract_paragraphs: bool = True,
    requested_by: Optional[int] = None
) -> Dict[str, Any]:
    """
    Tâche Celery pour générer les embeddings d'un land
    
    Args:
        land_id: ID du land à traiter
        provider_name: Nom du provider d'embeddings
        model: Modèle spécifique à utiliser
        force_regenerate: Force la régénération des embeddings existants
        batch_size: Taille des batches pour le traitement
        extract_paragraphs: Extrait les paragraphes avant génération
        
    Returns:
        Statistiques de la génération
    """
    
    try:
        logger.info(
            "Starting embedding generation task for land %s with provider %s (requested_by=%s)",
            land_id,
            provider_name,
            requested_by
        )
        
        # Mettre à jour le statut initial
        self.update_state(
            state='PROGRESS',
            meta={
                'land_id': land_id,
                'provider': provider_name,
                'requested_by': requested_by,
                'status': 'initializing',
                'progress': 0,
                'message': 'Initializing embedding generation...'
            }
        )
        
        db = get_db()
        embedding_service = EmbeddingService()
        
        # Exécuter la génération de manière asynchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Hook pour mettre à jour le progrès pendant l'exécution
            async def progress_callback(current: int, total: int, message: str = ""):
                progress = (current / total * 100) if total > 0 else 0
                self.update_state(
                    state='PROGRESS',
                    meta={
                'land_id': land_id,
                'provider': provider_name,
                'requested_by': requested_by,
                'status': 'processing',
                'progress': progress,
                'current': current,
                'total': total,
                        'message': message or f"Processing {current}/{total}"
                    }
                )
            
            result = loop.run_until_complete(
                embedding_service.generate_embeddings_for_land(
                    db, land_id, provider_name, model, force_regenerate, batch_size, extract_paragraphs
                )
            )
            
        finally:
            loop.close()
            db.close()
        
        # Mettre à jour le statut final
        self.update_state(
            state='SUCCESS',
            meta={
                'land_id': land_id,
                'provider': provider_name,
                'requested_by': requested_by,
                'status': 'completed',
                'progress': 100,
                'result': result,
                'message': f"Generation completed: {result.get('updated_paragraphs', 0)} paragraphs processed"
            }
        )
        
        logger.info(f"Embedding generation completed for land {land_id}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Embedding generation failed for land {land_id}: {e}")
        
        self.update_state(
            state='FAILURE',
            meta={
                'land_id': land_id,
                'provider': provider_name,
                'requested_by': requested_by,
                'status': 'failed',
                'error': str(e),
                'message': f"Generation failed: {str(e)}"
            }
        )
        
        raise

@celery_app.task(bind=True, name="generate_embeddings_for_expressions")
def generate_embeddings_for_expressions_task(
    self,
    expression_ids: List[int],
    provider_name: str = "openai",
    force_regenerate: bool = False,
    requested_by: Optional[int] = None
) -> Dict[str, Any]:
    """
    Tâche Celery pour générer les embeddings d'expressions spécifiques
    
    Args:
        expression_ids: Liste des IDs d'expressions à traiter
        provider_name: Nom du provider d'embeddings
        force_regenerate: Force la régénération des embeddings existants
        
    Returns:
        Statistiques de la génération
    """
    
    try:
        logger.info(
            "Starting embedding generation task for %d expressions with provider %s (requested_by=%s)",
            len(expression_ids),
            provider_name,
            requested_by
        )
        
        # Mettre à jour le statut initial
        self.update_state(
            state='PROGRESS',
            meta={
                'expression_ids': expression_ids,
                'provider': provider_name,
                'requested_by': requested_by,
                'status': 'initializing',
                'progress': 0,
                'message': f'Initializing embedding generation for {len(expression_ids)} expressions...'
            }
        )
        
        db = get_db()
        embedding_service = EmbeddingService()
        
        # Exécuter la génération de manière asynchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                embedding_service.generate_embeddings_for_expressions(
                    db, expression_ids, provider_name, force_regenerate
                )
            )
            
        finally:
            loop.close()
            db.close()
        
        # Mettre à jour le statut final
        self.update_state(
            state='SUCCESS',
            meta={
                'expression_ids': expression_ids,
                'provider': provider_name,
                'requested_by': requested_by,
                'status': 'completed',
                'progress': 100,
                'result': result,
                'message': f"Generation completed: {result.get('successful_paragraphs', 0)} paragraphs processed"
            }
        )
        
        logger.info(f"Embedding generation completed for {len(expression_ids)} expressions: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Embedding generation failed for expressions {expression_ids}: {e}")
        
        self.update_state(
            state='FAILURE',
            meta={
                'expression_ids': expression_ids,
                'provider': provider_name,
                'requested_by': requested_by,
                'status': 'failed',
                'error': str(e),
                'message': f"Generation failed: {str(e)}"
            }
        )
        
        raise

@celery_app.task(bind=True, name="compute_similarities_for_land")
def compute_similarities_for_land_task(
    self,
    land_id: int,
    threshold: float = 0.7,
    method: str = "cosine",
    provider_filter: str = None
) -> Dict[str, Any]:
    """
    Tâche Celery pour calculer les similarités entre paragraphes d'un land
    
    Args:
        land_id: ID du land à traiter
        threshold: Seuil de similarité minimum
        method: Méthode de calcul (cosine, euclidean, manhattan)
        provider_filter: Filtrer par provider d'embedding
        
    Returns:
        Statistiques du calcul de similarités
    """
    
    try:
        logger.info(f"Starting similarity computation task for land {land_id}")
        
        # Mettre à jour le statut initial
        self.update_state(
            state='PROGRESS',
            meta={
                'land_id': land_id,
                'method': method,
                'threshold': threshold,
                'status': 'initializing',
                'progress': 0,
                'message': 'Initializing similarity computation...'
            }
        )
        
        # TODO: Implémenter le service de similarité
        # Pour l'instant, retourner un placeholder
        
        result = {
            'land_id': land_id,
            'method': method,
            'threshold': threshold,
            'computed_similarities': 0,
            'processing_time': 0.0,
            'message': 'Similarity computation not yet implemented'
        }
        
        # Mettre à jour le statut final
        self.update_state(
            state='SUCCESS',
            meta={
                'land_id': land_id,
                'status': 'completed',
                'progress': 100,
                'result': result,
                'message': "Similarity computation completed (placeholder)"
            }
        )
        
        logger.info(f"Similarity computation completed for land {land_id}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Similarity computation failed for land {land_id}: {e}")
        
        self.update_state(
            state='FAILURE',
            meta={
                'land_id': land_id,
                'status': 'failed',
                'error': str(e),
                'message': f"Similarity computation failed: {str(e)}"
            }
        )
        
        raise

@celery_app.task(bind=True, name="health_check_providers")
def health_check_providers_task(self) -> Dict[str, Any]:
    """
    Tâche Celery pour vérifier la santé des providers d'embeddings
    
    Returns:
        Statut de santé de tous les providers
    """
    
    try:
        logger.info("Starting providers health check task")
        
        # Mettre à jour le statut initial
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'checking',
                'message': 'Checking providers health...'
            }
        )
        
        embedding_service = EmbeddingService()
        
        # Exécuter le health check de manière asynchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                embedding_service.health_check_providers()
            )
        finally:
            loop.close()
        
        # Compter les providers disponibles
        available_count = sum(1 for status in result.values() if status.is_available)
        total_count = len(result)
        
        # Mettre à jour le statut final
        self.update_state(
            state='SUCCESS',
            meta={
                'status': 'completed',
                'result': result,
                'available_providers': available_count,
                'total_providers': total_count,
                'message': f"Health check completed: {available_count}/{total_count} providers available"
            }
        )
        
        logger.info(f"Providers health check completed: {available_count}/{total_count} available")
        return result
        
    except Exception as e:
        logger.error(f"Providers health check failed: {e}")
        
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'failed',
                'error': str(e),
                'message': f"Health check failed: {str(e)}"
            }
        )
        
        raise

# Tâches périodiques (à configurer avec Celery Beat)
@celery_app.task(name="periodic_providers_health_check")
def periodic_providers_health_check() -> Dict[str, Any]:
    """
    Tâche périodique pour vérifier la santé des providers
    """
    return health_check_providers_task.delay().get()

@celery_app.task(name="cleanup_old_task_results")
def cleanup_old_task_results() -> Dict[str, Any]:
    """
    Tâche de nettoyage des anciens résultats de tâches
    """
    try:
        # TODO: Implémenter le nettoyage des résultats de tâches
        # Pour l'instant, placeholder
        
        result = {
            'cleaned_results': 0,
            'message': 'Task cleanup not yet implemented'
        }
        
        logger.info("Task cleanup completed (placeholder)")
        return result
        
    except Exception as e:
        logger.error(f"Task cleanup failed: {e}")
        raise
