"""
Readable Service - Main business logic for readable content processing.
Handles content extraction, merge strategies, and orchestration.
"""
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.content_extractor import ContentExtractor
from app.db.models import Expression, Land, Media, ExpressionLink, Domain
from app.schemas.readable import (
    MergeStrategy, ReadableProcessingResult, ExtractionResult,
    ReadableStats
)
from app.services.text_processor_service import TextProcessorService
from app.services.media_link_extractor import MediaLinkExtractor
from app.services.llm_validation_service import LLMValidationService
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ReadableService:
    """Service for processing readable content with Mercury-like extraction."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.content_extractor = ContentExtractor()
        self.text_processor = TextProcessorService(db)
        self.media_link_extractor = MediaLinkExtractor(db)
        self.llm_validation_service = LLMValidationService(db)
        
    async def get_readable_stats(self, land_id: int) -> ReadableStats:
        """Get statistics about readable processing for a land."""
        query = select(
            func.count(Expression.id).label('total'),
            func.count(Expression.readable).label('with_readable'),
            func.max(Expression.readable_at).label('last_processed')
        ).where(Expression.land_id == land_id)
        
        result = await self.db.execute(query)
        row = result.first()
        
        total = row.total or 0
        with_readable = row.with_readable or 0
        without_readable = total - with_readable
        
        # Count eligible expressions (fetched but not processed)
        eligible_query = select(func.count(Expression.id)).where(
            and_(
                Expression.land_id == land_id,
                Expression.crawled_at.isnot(None),
                Expression.readable_at.is_(None)
            )
        )
        eligible_result = await self.db.execute(eligible_query)
        eligible = eligible_result.scalar() or 0
        
        coverage = (with_readable / total * 100) if total > 0 else 0.0
        
        return ReadableStats(
            total_expressions=total,
            expressions_with_readable=with_readable,
            expressions_without_readable=without_readable,
            expressions_eligible=eligible,
            last_processed_at=row.last_processed,
            processing_coverage=coverage
        )
    
    async def get_expressions_to_process(
        self,
        land_id: int,
        limit: Optional[int] = None,
        depth: Optional[int] = None
    ) -> List[Expression]:
        """Get expressions eligible for readable processing."""
        query = select(Expression).options(
            selectinload(Expression.domain)
        ).where(
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
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def process_land_readable(
        self,
        land_id: int,
        limit: Optional[int] = None,
        depth: Optional[int] = None,
        merge_strategy: MergeStrategy = MergeStrategy.SMART_MERGE,
        enable_llm: bool = False,
        batch_size: int = 10
    ) -> ReadableProcessingResult:
        """Process readable content for a land."""
        start_time = datetime.utcnow()
        
        # Get expressions to process
        expressions = await self.get_expressions_to_process(land_id, limit, depth)
        
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
        
        # Process in batches
        results = []
        for i in range(0, len(expressions), batch_size):
            batch = expressions[i:i + batch_size]
            batch_results = await self._process_batch(
                batch, merge_strategy, enable_llm
            )
            results.extend(batch_results)
            
            # Small delay between batches to avoid overwhelming servers
            if i + batch_size < len(expressions):
                await asyncio.sleep(0.5)
        
        # Aggregate results
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
    
    async def _process_batch(
        self,
        expressions: List[Expression],
        merge_strategy: MergeStrategy,
        enable_llm: bool
    ) -> List[Dict[str, Any]]:
        """Process a batch of expressions concurrently."""
        tasks = [
            self._process_single_expression(expr, merge_strategy, enable_llm)
            for expr in expressions
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing expression {expressions[i].id}: {result}")
                processed_results.append({'error': True, 'expression_id': expressions[i].id})
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_expression(
        self,
        expression: Expression,
        merge_strategy: MergeStrategy,
        enable_llm: bool
    ) -> Dict[str, Any]:
        """Process a single expression for readable content."""
        try:
            # Extract content
            extraction_result = await self._extract_content(expression.url)
            
            if not extraction_result.success:
                # Mark as processed even if extraction failed
                expression.readable_at = datetime.utcnow()
                await self.db.commit()
                return {
                    'expression_id': expression.id,
                    'error': True,
                    'error_message': extraction_result.error_message
                }
            
            # Store original values for comparison
            original_values = {
                'title': expression.title,
                'description': expression.description,
                'readable': expression.readable,
                'language': expression.lang,
                'published_at': expression.published_at
            }
            
            # Apply merge strategy
            updated = self._apply_merge_strategy(
                expression, extraction_result, merge_strategy
            )
            
            # Always update readable_at
            expression.readable_at = datetime.utcnow()
            
            # Handle media and links if content was updated
            media_created = 0
            links_created = 0
            
            if updated and extraction_result.readable:
                media_created, links_created = await self.media_link_extractor.process_expression_media_and_links(
                    expression, extraction_result.readable
                )
            
            # Recalculate relevance if content changed
            if updated and expression.readable != original_values['readable']:
                await self._recalculate_relevance(expression)
            
            # LLM validation if enabled
            wayback_used = 1 if extraction_result.extraction_source == 'archive' else 0
            
            if enable_llm and updated and expression.readable:
                await self._validate_with_llm(expression)
            
            await self.db.commit()
            
            return {
                'expression_id': expression.id,
                'updated': updated,
                'media_created': media_created,
                'links_created': links_created,
                'wayback_used': wayback_used
            }
            
        except Exception as e:
            logger.error(f"Error processing expression {expression.id}: {e}")
            await self.db.rollback()
            return {
                'expression_id': expression.id,
                'error': True,
                'error_message': str(e)
            }
    
    async def _extract_content(self, url: str) -> ExtractionResult:
        """Extract readable content from URL."""
        try:
            # Use existing content extractor with fallbacks
            content_result = await self.content_extractor.get_readable_content_with_fallbacks(url)
            
            if not content_result or not content_result.get('readable'):
                return ExtractionResult(
                    url=url,
                    success=False,
                    extraction_source='none',
                    error_message="No readable content extracted"
                )
            
            # Metadata is already included in content_result
            metadata = {
                'title': content_result.get('title'),
                'description': content_result.get('description'),
                'language': content_result.get('language')
            }
            
            # Parse published date if available
            published_at = None
            if content_result.get('published_at'):
                try:
                    published_at = datetime.fromisoformat(content_result['published_at'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
            
            return ExtractionResult(
                url=url,
                title=content_result.get('title') or metadata.get('title'),
                description=content_result.get('description') or metadata.get('description'),
                readable=content_result['readable'],
                language=content_result.get('language') or metadata.get('language'),
                published_at=published_at,
                author=content_result.get('author'),
                media_urls=[],  # Will be extracted separately by MediaLinkExtractor
                link_urls=[],   # Will be extracted separately by MediaLinkExtractor
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
    
    def _apply_merge_strategy(
        self,
        expression: Expression,
        extraction: ExtractionResult,
        strategy: MergeStrategy
    ) -> bool:
        """Apply merge strategy to update expression. Returns True if any field was updated."""
        updated = False
        
        if strategy == MergeStrategy.MERCURY_PRIORITY:
            # Mercury always overwrites
            if extraction.title and extraction.title != expression.title:
                expression.title = extraction.title
                updated = True
            if extraction.description and extraction.description != expression.description:
                expression.description = extraction.description
                updated = True
            if extraction.readable and extraction.readable != expression.readable:
                expression.readable = extraction.readable
                updated = True
            if extraction.language and extraction.language != expression.lang:
                expression.lang = extraction.language
                updated = True
            if extraction.published_at and extraction.published_at != expression.published_at:
                expression.published_at = extraction.published_at
                updated = True
                
        elif strategy == MergeStrategy.PRESERVE_EXISTING:
            # Only fill empty fields
            if not expression.title and extraction.title:
                expression.title = extraction.title
                updated = True
            if not expression.description and extraction.description:
                expression.description = extraction.description
                updated = True
            if not expression.readable and extraction.readable:
                expression.readable = extraction.readable
                updated = True
            if not expression.lang and extraction.language:
                expression.lang = extraction.language
                updated = True
            if not expression.published_at and extraction.published_at:
                expression.published_at = extraction.published_at
                updated = True
                
        else:  # SMART_MERGE (default)
            # Intelligent merge based on field type
            
            # Title: prefer longer title
            if extraction.title:
                if not expression.title or len(extraction.title) > len(expression.title):
                    if extraction.title != expression.title:
                        expression.title = extraction.title
                        updated = True
            
            # Description: prefer longer description
            if extraction.description:
                if not expression.description or len(extraction.description) > len(expression.description):
                    if extraction.description != expression.description:
                        expression.description = extraction.description
                        updated = True
            
            # Readable: always prefer extracted content (cleaner)
            if extraction.readable and extraction.readable != expression.readable:
                expression.readable = extraction.readable
                updated = True
            
            # Language: prefer extracted language if not set
            if extraction.language and not expression.lang:
                expression.lang = extraction.language
                updated = True
            
            # Published date: prefer earlier date
            if extraction.published_at:
                if not expression.published_at or extraction.published_at < expression.published_at:
                    expression.published_at = extraction.published_at
                    updated = True
        
        return updated
    
    
    async def _recalculate_relevance(self, expression: Expression):
        """Recalculate relevance score after content update."""
        try:
            # Use text processor service to calculate relevance
            new_relevance = await self.text_processor.calculate_relevance(
                text=expression.readable,
                title=expression.title,
                land_id=expression.land_id
            )

            expression.relevance = new_relevance

            # approved_at is set whenever readable content is saved
            expression.approved_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error recalculating relevance for expression {expression.id}: {e}")
    
    async def _validate_with_llm(self, expression: Expression):
        """Validate expression relevance with LLM via OpenRouter."""
        try:
            # Get land context for validation
            land = await self.db.get(Land, expression.land_id)
            if not land:
                logger.error(f"Land {expression.land_id} not found for LLM validation")
                return
            
            # Perform LLM validation
            validation_result = await self.llm_validation_service.validate_expression_relevance(
                expression, land
            )
            
            # Update expression with validation results
            await self.llm_validation_service.update_expression_validation(
                expression, validation_result
            )
            
            logger.debug(
                f"LLM validation completed for expression {expression.id}: "
                f"relevant={validation_result.is_relevant}, model={validation_result.model_used}"
            )
            
        except Exception as e:
            logger.error(f"LLM validation failed for expression {expression.id}: {e}")
            # Mark validation as attempted but failed
            expression.valid_llm = 'error'
            expression.valid_model = 'openrouter_error'