"""
Service readable optimisé pour Celery avec pool de connexions dédié.
Évite les problèmes AsyncSession + fork.
"""
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.core.readable_db import readable_db_pool
from app.core.content_extractor import ContentExtractor
from app.schemas.readable import MergeStrategy, ReadableProcessingResult, ExtractionResult
from app.utils.logging import get_logger

logger = get_logger(__name__)

class ReadableCeleryService:
    """Service readable optimisé pour les tâches Celery."""
    
    def __init__(self):
        self.content_extractor = ContentExtractor()
        self.db_pool = readable_db_pool
    
    def get_readable_stats(self, land_id: int) -> Dict[str, Any]:
        """Récupère les statistiques readable."""
        return self.db_pool.get_readable_stats(land_id)
    
    def get_expressions_to_process(self, land_id: int, limit: Optional[int] = None, depth: Optional[int] = None):
        """Récupère les expressions à traiter."""
        return self.db_pool.get_expressions_to_process(land_id, limit, depth)
    
    async def process_land_readable(
        self,
        land_id: int,
        limit: Optional[int] = None,
        depth: Optional[int] = None,
        merge_strategy: MergeStrategy = MergeStrategy.SMART_MERGE,
        enable_llm: bool = False,
        batch_size: int = 10
    ) -> ReadableProcessingResult:
        """Traite le contenu readable pour un land."""
        start_time = datetime.utcnow()
        
        # Récupérer les expressions à traiter
        expressions = self.get_expressions_to_process(land_id, limit, depth)
        
        if not expressions:
            logger.info(f"No expressions eligible for readable processing in land {land_id}")
            return ReadableProcessingResult(
                processed=0, updated=0, errors=0, skipped=0,
                media_created=0, links_created=0,
                duration_seconds=0.0,
                merge_strategy_used=merge_strategy,
                llm_validation_used=enable_llm
            )
        
        logger.info(f"Processing {len(expressions)} expressions for readable content")
        
        # Traiter en batches
        results = []
        for i in range(0, len(expressions), batch_size):
            batch = expressions[i:i + batch_size]
            batch_results = await self._process_batch(batch, merge_strategy, enable_llm)
            results.extend(batch_results)
            
            # Pause entre batches
            if i + batch_size < len(expressions):
                await asyncio.sleep(0.5)
        
        # Agréger les résultats
        processed = len(results)
        updated = sum(1 for r in results if r.get('updated', False))
        errors = sum(1 for r in results if r.get('error', False))
        skipped = processed - updated - errors
        media_created = sum(r.get('media_created', 0) for r in results)
        links_created = sum(r.get('links_created', 0) for r in results)
        wayback_fallbacks = sum(r.get('wayback_used', 0) for r in results)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            f"Readable processing completed: {updated}/{processed} updated, "
            f"{errors} errors, {media_created} media, {links_created} links created"
        )
        
        return ReadableProcessingResult(
            processed=processed,
            updated=updated,
            errors=errors,
            skipped=skipped,
            media_created=media_created,
            links_created=links_created,
            duration_seconds=duration,
            merge_strategy_used=merge_strategy,
            llm_validation_used=enable_llm,
            wayback_fallbacks=wayback_fallbacks
        )
    
    async def _process_batch(self, expressions, merge_strategy: MergeStrategy, enable_llm: bool) -> List[Dict[str, Any]]:
        """Traite un batch d'expressions."""
        tasks = [
            self._process_single_expression(expr, merge_strategy, enable_llm)
            for expr in expressions
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Gérer les exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing expression {expressions[i].id}: {result}")
                processed_results.append({'error': True, 'expression_id': expressions[i].id})
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_expression(self, expression, merge_strategy: MergeStrategy, enable_llm: bool) -> Dict[str, Any]:
        """Traite une expression unique."""
        try:
            # Extraire le contenu
            extraction_result = await self._extract_content(expression.url)
            
            if not extraction_result.success:
                # Marquer comme traité même si extraction échoue
                self.db_pool.update_expression_readable(expression.id, {'readable_at': datetime.utcnow()})
                return {
                    'expression_id': expression.id,
                    'error': True,
                    'error_message': extraction_result.error_message
                }
            
            # Appliquer la stratégie de merge
            updated_data = self._apply_merge_strategy(expression, extraction_result, merge_strategy)
            updated_data['readable_at'] = datetime.utcnow()
            
            # Mettre à jour l'expression
            self.db_pool.update_expression_readable(expression.id, updated_data)
            
            # Pour l'instant, skip media/links/LLM validation pour simplifier
            updated = bool(updated_data.get('readable') or updated_data.get('title') or updated_data.get('description'))
            wayback_used = 1 if extraction_result.extraction_source == 'archive_org' else 0
            
            return {
                'expression_id': expression.id,
                'updated': updated,
                'media_created': 0,  # TODO: implémenter si nécessaire
                'links_created': 0,  # TODO: implémenter si nécessaire
                'wayback_used': wayback_used
            }
            
        except Exception as e:
            logger.error(f"Error processing expression {expression.id}: {e}")
            return {
                'expression_id': expression.id,
                'error': True,
                'error_message': str(e)
            }
    
    async def _extract_content(self, url: str) -> ExtractionResult:
        """Extrait le contenu readable d'une URL."""
        try:
            content_result = await self.content_extractor.get_readable_content_with_fallbacks(url)
            
            if not content_result or not content_result.get('readable'):
                return ExtractionResult(
                    url=url,
                    success=False,
                    extraction_source='none',
                    error_message="No readable content extracted"
                )
            
            # Parser la date de publication si disponible
            published_at = None
            if content_result.get('published_at'):
                try:
                    published_at = datetime.fromisoformat(content_result['published_at'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
            
            return ExtractionResult(
                url=url,
                title=content_result.get('title'),
                description=content_result.get('description'),
                readable=content_result['readable'],
                language=content_result.get('language'),
                published_at=published_at,
                author=content_result.get('author'),
                media_urls=[],
                link_urls=[],
                extraction_source=content_result.get('source', 'trafilatura'),
                success=True
            )
            
        except Exception as e:
            logger.error(f"Content extraction failed for {url}: {e}")
            return ExtractionResult(
                url=url,
                success=False,
                extraction_source='error',
                error_message=str(e)
            )
    
    def _apply_merge_strategy(self, expression, extraction: ExtractionResult, strategy: MergeStrategy) -> Dict[str, Any]:
        """Applique la stratégie de merge et retourne les données à mettre à jour."""
        update_data = {}
        
        if strategy == MergeStrategy.MERCURY_PRIORITY:
            # Mercury écrase toujours
            if extraction.title and extraction.title != expression.title:
                update_data['title'] = extraction.title
            if extraction.description and extraction.description != expression.description:
                update_data['description'] = extraction.description
            if extraction.readable and extraction.readable != expression.readable:
                update_data['readable'] = extraction.readable
            if extraction.language and extraction.language != expression.lang:
                update_data['lang'] = extraction.language
            if extraction.published_at and extraction.published_at != expression.published_at:
                update_data['published_at'] = extraction.published_at
                
        elif strategy == MergeStrategy.PRESERVE_EXISTING:
            # Remplir seulement les champs vides
            if not expression.title and extraction.title:
                update_data['title'] = extraction.title
            if not expression.description and extraction.description:
                update_data['description'] = extraction.description
            if not expression.readable and extraction.readable:
                update_data['readable'] = extraction.readable
            if not expression.lang and extraction.language:
                update_data['lang'] = extraction.language
            if not expression.published_at and extraction.published_at:
                update_data['published_at'] = extraction.published_at
                
        else:  # SMART_MERGE (défaut)
            # Merge intelligent
            if extraction.title:
                if not expression.title or len(extraction.title) > len(expression.title):
                    if extraction.title != expression.title:
                        update_data['title'] = extraction.title
            
            if extraction.description:
                if not expression.description or len(extraction.description) > len(expression.description):
                    if extraction.description != expression.description:
                        update_data['description'] = extraction.description
            
            # Readable: toujours préférer le contenu extrait
            if extraction.readable and extraction.readable != expression.readable:
                update_data['readable'] = extraction.readable
            
            # Language: préférer extrait si pas défini
            if extraction.language and not expression.lang:
                update_data['lang'] = extraction.language
            
            # Date: préférer date plus ancienne
            if extraction.published_at:
                if not expression.published_at or extraction.published_at < expression.published_at:
                    update_data['published_at'] = extraction.published_at
        
        return update_data