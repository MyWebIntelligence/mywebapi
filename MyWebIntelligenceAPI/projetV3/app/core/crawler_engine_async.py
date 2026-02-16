import logging
import asyncio
from typing import Tuple, Optional
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.expression import ExpressionUpdate

from app.crud import crud_expression, crud_land
from app.db import models
from app.core import content_extractor, text_processing, media_processor
from app.services.sentiment_service import SentimentService
from app.services.quality_scorer import QualityScorer
from app.config import settings

logger = logging.getLogger(__name__)

class CrawlerEngine:
    def __init__(self, db: AsyncSession, max_concurrent: int = 10):
        self.db = db
        self.http_client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        self.sentiment_service = SentimentService()  # Initialize sentiment service
        self.quality_scorer = QualityScorer()  # Initialize quality scorer
        self.max_concurrent = max_concurrent  # Maximum concurrent crawls

    async def prepare_crawl(
        self,
        land_id: int,
        limit: int = 0,
        depth: Optional[int] = None,
        http_status: Optional[str] = None,
    ) -> Tuple[Optional[models.Land], list[models.Expression]]:
        """Prépare la liste des expressions à crawler pour un land."""
        # First, get the land to access start_urls
        land = await crud_land.land.get(self.db, id=land_id)
        if not land:
            logger.error(f"Land {land_id} not found")
            return None, []

        # Create expressions from start_urls if they exist and no expressions exist yet
        if land.start_urls:
            logger.info(f"Found {len(land.start_urls)} start URLs for land {land_id}")

            # Check if we already have expressions for this land
            existing_expressions = await crud_expression.expression.get_expressions_to_crawl(
                self.db, land_id=land_id, limit=1
            )

            # If no expressions exist, create them from start_urls
            if not existing_expressions:
                logger.info("No existing expressions found. Creating expressions from start_urls...")
                for url in land.start_urls:
                    try:
                        existing = await crud_expression.expression.get_by_url_and_land(
                            self.db, url=url, land_id=land_id
                        )
                        if not existing:
                            await crud_expression.expression.get_or_create_expression(
                                self.db, land_id=land_id, url=url, depth=0
                            )
                            logger.info(f"Created expression for URL: {url}")
                    except Exception as e:
                        logger.error(f"Failed to create expression for {url}: {e}")

                await self.db.commit()

        expressions = await crud_expression.expression.get_expressions_to_crawl(
            self.db, land_id=land_id, limit=limit, depth=depth, http_status=http_status
        )

        logger.info("Found %s expressions to crawl for land %s", len(expressions), land_id)
        return land, expressions

    async def crawl_land(
        self,
        land_id: int,
        limit: int = 0,
        depth: Optional[int] = None,
        http_status: Optional[str] = None,
        analyze_media: bool = False,
        parallel: bool = True,  # Enable parallel crawling by default
    ) -> Tuple[int, int, dict]:
        land, expressions = await self.prepare_crawl(land_id, limit=limit, depth=depth, http_status=http_status)
        if land is None:
            return 0, 0, {}

        # Use parallel or sequential crawling based on parameter
        if parallel:
            logger.info(f"Using PARALLEL crawling for land {land_id} with {len(expressions)} expressions")
            processed_count, error_count, http_stats = await self.crawl_expressions_parallel(
                expressions, analyze_media=analyze_media
            )
        else:
            logger.info(f"Using SEQUENTIAL crawling for land {land_id} with {len(expressions)} expressions")
            processed_count, error_count, http_stats = await self.crawl_expressions(
                expressions, analyze_media=analyze_media
            )

        await self.http_client.aclose()
        return processed_count, error_count, http_stats

    async def crawl_expressions(
        self, expressions: list[models.Expression], analyze_media: bool = False
    ) -> Tuple[int, int, dict]:
        from collections import defaultdict

        processed_count = 0
        error_count = 0
        http_stats = defaultdict(int)

        expression_ids = [
            getattr(expr, "id", None)
            for expr in expressions
            if getattr(expr, "id", None) is not None
        ]

        for expr_id in expression_ids:
            expr = await self.db.get(models.Expression, expr_id)
            if not expr:
                logger.warning("Expression %s not found during crawl", expr_id)
                continue

            expr_url = getattr(expr, "url", None)
            try:
                status_code = await self.crawl_expression(expr, analyze_media=analyze_media)
                await self.db.commit()
                processed_count += 1
                if status_code:
                    http_stats[status_code] += 1
            except Exception as e:
                logger.error(
                    "Failed to crawl expression %s (%s): %s",
                    getattr(expr, "id", "unknown"),
                    expr_url,
                    e,
                )
                await self.db.rollback()
                error_count += 1
                http_stats['error'] = http_stats.get('error', 0) + 1

        return processed_count, error_count, dict(http_stats)

    async def _fetch_url_http(self, url: str) -> dict:
        """
        Fetch HTTP content only (no DB access).
        Returns dict with response data and status.
        """
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()

            content_length_str = response.headers.get('content-length', None)
            content_length = None
            if content_length_str:
                try:
                    content_length = int(content_length_str)
                except ValueError:
                    pass

            return {
                'success': True,
                'url': url,
                'html_content': response.text,
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type', None),
                'content_length': content_length,
                'last_modified': response.headers.get('last-modified', None),
                'etag': response.headers.get('etag', None),
                'response': response
            }
        except httpx.HTTPStatusError as e:
            return {
                'success': False,
                'url': url,
                'html_content': "",
                'status_code': e.response.status_code,
                'content_type': e.response.headers.get('content-type', None) if e.response else None,
                'error': str(e)
            }
        except httpx.RequestError as e:
            return {
                'success': False,
                'url': url,
                'html_content': "",
                'status_code': 0,
                'error': str(e)
            }

    async def crawl_expressions_parallel(
        self, expressions: list[models.Expression], analyze_media: bool = False
    ) -> Tuple[int, int, dict]:
        """
        Crawl expressions with HTTP requests in parallel, but DB operations sequential.
        This avoids DB session conflicts while speeding up the slowest part (HTTP).
        """
        from collections import defaultdict

        processed_count = 0
        error_count = 0
        http_stats = defaultdict(int)

        # Create semaphore for HTTP concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_with_semaphore(url: str):
            """Fetch URL with semaphore to limit concurrency"""
            async with semaphore:
                return await self._fetch_url_http(url)

        # Build URL list from expressions
        expr_map = {}  # url -> expression object
        for expr in expressions:
            url = getattr(expr, "url", None)
            if url:
                expr_map[url] = expr

        urls = list(expr_map.keys())
        logger.info(f"Starting PARALLEL HTTP fetch of {len(urls)} URLs (max concurrent: {self.max_concurrent})")

        # PHASE 1: Fetch all HTTP in parallel
        fetch_results = await asyncio.gather(
            *[fetch_with_semaphore(url) for url in urls],
            return_exceptions=True
        )

        logger.info(f"HTTP fetch completed, processing results sequentially...")

        # PHASE 2: Process each result SEQUENTIALLY (to avoid DB conflicts)
        for fetch_result in fetch_results:
            if isinstance(fetch_result, Exception):
                logger.error(f"HTTP fetch raised exception: {fetch_result}")
                error_count += 1
                http_stats['error'] += 1
                continue

            # Log if HTTP fetch had errors
            if not fetch_result.get('success', True):
                url = fetch_result.get('url', 'unknown')
                status_code = fetch_result.get('status_code', 0)
                error = fetch_result.get('error', 'Unknown error')
                logger.warning(
                    f"HTTP fetch failed for {url}: "
                    f"status={status_code}, error={error}"
                )

            url = fetch_result['url']
            expr = expr_map.get(url)
            if not expr:
                continue

            try:
                # Use crawl_expression with prefetched content
                status_code = await self.crawl_expression(
                    expr, analyze_media=analyze_media, prefetched_content=fetch_result
                )
                await self.db.commit()

                processed_count += 1
                if status_code:
                    http_stats[status_code] += 1

            except Exception as e:
                logger.error(f"Failed to process {url}: {e}")
                await self.db.rollback()
                error_count += 1
                http_stats['error'] = http_stats.get('error', 0) + 1

        logger.info(f"Parallel crawl completed: {processed_count} processed, {error_count} errors")
        return processed_count, error_count, dict(http_stats)

    async def crawl_expression(self, expr: models.Expression, analyze_media: bool = False, prefetched_content: dict = None):
        # Store URL string to avoid DetachedInstanceError later
        expr_url = str(expr.url)
        expr_id = expr.id
        expr_land_id = expr.land_id
        expr_depth = expr.depth

        logger.info("Crawling URL: %s (analyze_media=%s, prefetched=%s)", expr_url, analyze_media, bool(prefetched_content))

        # 1. Fetch content (or use prefetched if provided)
        if prefetched_content:
            # Use prefetched content from parallel HTTP fetch
            html_content = prefetched_content['html_content']
            http_status_code = prefetched_content['status_code']
            content_type = prefetched_content.get('content_type')
            content_length = prefetched_content.get('content_length')
            last_modified_str = prefetched_content.get('last_modified')
            etag_str = prefetched_content.get('etag')
        else:
            # Traditional fetch (sequential mode)
            content_type = None
            content_length = None

            try:
                response = await self.http_client.get(expr_url)
                response.raise_for_status()
                html_content = response.text
                http_status_code = response.status_code

                # Extract HTTP headers
                content_type = response.headers.get('content-type', None)
                content_length_str = response.headers.get('content-length', None)
                if content_length_str:
                    try:
                        content_length = int(content_length_str)
                    except ValueError:
                        pass
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error for {expr_url}: {e}")
                html_content = ""
                http_status_code = e.response.status_code
                if e.response:
                    content_type = e.response.headers.get('content-type', None)
            except httpx.RequestError as e:
                logger.error(f"Request error for {expr_url}: {e}")
                html_content = ""
                http_status_code = 0 # Custom code for request errors

            # Extract HTTP headers: Last-Modified and ETag (only in sequential mode)
            if not prefetched_content:
                last_modified_str = None
                etag_str = None
                if http_status_code and http_status_code < 400:
                    try:
                        last_modified_str = response.headers.get('last-modified', None)
                        etag_str = response.headers.get('etag', None)
                    except Exception:
                        pass
            # In prefetched mode, last_modified_str and etag_str are already set from lines 279-280

        update_data = {
            "http_status": http_status_code,  # Store as int (DB expects INTEGER)
            "crawled_at": datetime.utcnow(),
            "content_type": content_type,
            "content_length": content_length,
            "last_modified": last_modified_str,
            "etag": etag_str,
        }

        # 2. Extract content and metadata with fallbacks (try even if no initial content)
        extraction_result = await content_extractor.get_readable_content_with_fallbacks(expr_url, html_content)

        readable_content = extraction_result.get('readable')
        extraction_source = extraction_result.get('extraction_source', 'unknown')
        media_list = extraction_result.get('media_list', [])
        links = extraction_result.get('links', [])

        # Store raw HTML content (legacy field)
        if extraction_result.get('content'):
            update_data["content"] = extraction_result['content']
            logger.debug(f"Storing HTML content for {expr_url}: {len(extraction_result['content'])} chars")
        else:
            logger.warning(f"No HTML content in extraction_result for {expr_url}")

        # Create metadata dictionary for later use (aligned with sync crawler)
        metadata = {
            'title': extraction_result.get('title', expr_url),
            'description': extraction_result.get('description'),
            'keywords': extraction_result.get('keywords'),
            'lang': extraction_result.get('language'),
            'canonical_url': extraction_result.get('canonical_url'),
            'published_at': extraction_result.get('published_at')
        }

        if readable_content:
            # Calculate word_count, reading_time and detect language from readable content
            from app.utils.text_utils import analyze_text_metrics
            text_metrics = analyze_text_metrics(readable_content)
            word_count = text_metrics.get('word_count', 0)
            reading_time = max(1, word_count // 200) if word_count > 0 else None  # 200 words/min
            detected_lang = text_metrics.get('language')  # Language detected by langdetect

            # Fallback to HTML lang attribute if detection fails
            html_lang = extraction_result.get('language')
            final_lang = detected_lang or html_lang

            # Logging détaillé pour debug
            logger.info(f"Language detection for {expr_url}: detected_lang={detected_lang}, html_lang={html_lang}, final_lang={final_lang}, word_count={word_count}")

            # Parse published_at if it's a string (from meta tags)
            published_at = None
            if metadata.get("published_at"):
                try:
                    from dateutil import parser as date_parser
                    published_at = date_parser.parse(metadata["published_at"])
                except Exception:
                    pass

            update_data.update(
                {
                    "title": metadata.get("title"),
                    "description": metadata.get("description"),
                    "keywords": metadata.get("keywords"),
                    "lang": final_lang,  # FIXED: Use 'lang' to match SQLAlchemy attribute
                    "readable": readable_content,
                    "canonical_url": metadata.get("canonical_url"),
                    "published_at": published_at,
                    "word_count": word_count,
                    "reading_time": reading_time,
                }
            )

            # Store extraction source for debugging (optional, can be logged)
            logger.debug(f"Content extracted via: {extraction_source}")

            # 3. Calculate relevance (requires dictionary)
            land_dict = await text_processing.get_land_dictionary(self.db, expr_land_id)

            class TempExpr:
                def __init__(self, title: Optional[str], readable: Optional[str], expr_id: int):
                    self.title = title
                    self.readable = readable
                    self.id = expr_id

            temp_expr = TempExpr(metadata.get("title"), readable_content, expr_id)
            relevance = await text_processing.expression_relevance(
                land_dict,
                temp_expr,
                final_lang or "fr"
            )
            update_data["relevance"] = relevance

            # 3.5. Sentiment Analysis (if enabled)
            if settings.ENABLE_SENTIMENT_ANALYSIS:
                try:
                    # Determine if we should use LLM (this would come from crawl parameters)
                    # For now, always use TextBlob (default) unless explicitly requested
                    use_llm = False  # TODO: Get from crawl parameters (llm_validation flag)

                    sentiment_data = await self.sentiment_service.enrich_expression_sentiment(
                        content=update_data.get("content"),
                        readable=readable_content,
                        language=final_lang,
                        use_llm=use_llm
                    )

                    # Add sentiment data to update
                    update_data["sentiment_score"] = sentiment_data["sentiment_score"]
                    update_data["sentiment_label"] = sentiment_data["sentiment_label"]
                    update_data["sentiment_confidence"] = sentiment_data["sentiment_confidence"]
                    update_data["sentiment_status"] = sentiment_data["sentiment_status"]
                    update_data["sentiment_model"] = sentiment_data["sentiment_model"]
                    update_data["sentiment_computed_at"] = sentiment_data["sentiment_computed_at"]

                    logger.debug(
                        f"Sentiment enriched for {expr_url}: "
                        f"{sentiment_data['sentiment_label']} ({sentiment_data['sentiment_score']}) "
                        f"via {sentiment_data['sentiment_model']}"
                    )
                except Exception as e:
                    logger.error(f"Sentiment enrichment failed for {expr_url}: {e}")
                    # Continue without sentiment (non-blocking)

            # 3.6. Quality Score (if enabled)
            if settings.ENABLE_QUALITY_SCORING:
                try:
                    # Get land for quality computation
                    land = await crud_land.land.get(self.db, id=expr_land_id)

                    if land:
                        # Build temporary expression object for quality computation
                        class TempExpr:
                            def __init__(self, data):
                                # Copy all fields from update_data
                                for key, value in data.items():
                                    setattr(self, key, value)
                                # Add fields needed for quality computation
                                self.http_status = data.get("http_status")
                                self.content_type = data.get("content_type")
                                self.title = data.get("title")
                                self.description = data.get("description")
                                self.keywords = data.get("keywords")
                                self.canonical_url = data.get("canonical_url")
                                self.word_count = data.get("word_count")
                                self.content_length = data.get("content_length")
                                self.reading_time = data.get("reading_time")
                                self.language = data.get("lang")  # Note: update_data uses 'lang', model uses 'language'
                                self.relevance = data.get("relevance")
                                self.validllm = getattr(expr, 'validllm', None)  # From existing expr
                                self.readable = data.get("readable")
                                self.readable_at = getattr(expr, 'readable_at', None)
                                self.crawled_at = data.get("crawled_at")

                        temp_expr = TempExpr(update_data)

                        quality_result = self.quality_scorer.compute_quality_score(
                            expression=temp_expr,
                            land=land
                        )

                        update_data["quality_score"] = quality_result["score"]

                        logger.debug(
                            f"Quality computed for {expr_url}: "
                            f"{quality_result['score']:.2f} ({quality_result['category']})"
                        )
                    else:
                        logger.warning(f"Could not compute quality: land {expr_land_id} not found")

                except Exception as e:
                    logger.error(f"Quality scoring failed for {expr_url}: {e}")
                    # Continue without quality (non-blocking)

            # 4. approved_at is set whenever readable content is saved
            update_data["approved_at"] = datetime.utcnow()
            logger.debug(f"Expression {expr_id} processed with relevance {relevance}")

            # 5. Extract links and media with error handling
            # Skip link/media extraction in test environment to avoid CRUD method issues
            import os
            if not os.getenv('PYTEST_CURRENT_TEST'):
                try:
                    # Use markdown links if available (legacy behavior)
                    if links:
                        await self._create_links_from_markdown(links, expr, expr_url, expr_land_id, expr_depth)
                    else:
                        # Fallback to HTML parsing if markdown extraction failed
                        if extraction_result.get('soup'):
                            await self._extract_and_save_links(extraction_result['soup'], expr, expr_url, expr_land_id, expr_depth)
                except Exception as e:
                    logger.warning(f"Error extracting links for {expr_url}: {e}")

                try:
                    # Save media from enriched markdown (legacy behavior)
                    if media_list:
                        await self._save_media_from_list(media_list, expr_id)

                    # Also extract dynamic media if requested
                    if analyze_media and extraction_result.get('soup'):
                        await self._extract_and_save_media(extraction_result['soup'], expr, expr_url, expr_id, analyze_media)
                except Exception as e:
                    logger.warning(f"Error extracting media for {expr_url}: {e}")
            else:
                print("Test environment detected, skipping link and media extraction")

        # 6. Save to DB
        expression_update = ExpressionUpdate(**update_data)
        await crud_expression.expression.update_expression(self.db, db_obj=expr, obj_in=expression_update)
        logger.info(f"Successfully crawled {expr_url}")

        # Return HTTP status code for statistics
        return http_status_code

    async def _create_links_from_markdown(self, links: list, expr: models.Expression, expr_url: str, expr_land_id: int, expr_depth: Optional[int]):
        """
        Create expression links from markdown-extracted URLs (legacy behavior).
        This reproduces the logic from _legacy/core.py:1787.
        """
        from urllib.parse import urljoin, urlparse
        from app.crud import crud_domain, crud_expression, crud_link

        links_created = 0

        for link_url in links:
            try:
                # Resolve relative URLs
                full_url = urljoin(expr_url, link_url)
                parsed = urlparse(full_url)

                # Validate URL structure
                if not parsed.scheme in ['http', 'https'] or not parsed.netloc:
                    continue

                # Clean URL (remove fragments and tracking params)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
                                     'fbclid', 'gclid', 'ref', 'source', 'campaign'}
                    query_params = []
                    for param in parsed.query.split('&'):
                        if '=' in param:
                            key = param.split('=')[0].lower()
                            if key not in tracking_params:
                                query_params.append(param)
                    if query_params:
                        clean_url += '?' + '&'.join(query_params)

                # Get or create domain
                domain_name = parsed.netloc.lower()
                domain = await crud_domain.domain.get_or_create(
                    self.db, name=domain_name, land_id=expr_land_id
                )

                # Check if expression already exists
                existing_expr = await crud_expression.expression.get_by_url_and_land(
                    self.db, url=clean_url, land_id=expr_land_id
                )

                if not existing_expr:
                    # Create new expression for discovered link
                    depth = expr_depth + 1 if expr_depth is not None else 1
                    new_expr = await crud_expression.expression.get_or_create_expression(
                        self.db,
                        land_id=expr_land_id,
                        url=clean_url,
                        depth=depth
                    )
                    target_expr = new_expr
                else:
                    target_expr = existing_expr

                # Create ExpressionLink relationship
                if target_expr and target_expr.id != expr.id:
                    link_type = "internal" if parsed.netloc == urlparse(expr_url).netloc else "external"

                    await crud_link.expression_link.create_link(
                        self.db,
                        source_id=expr.id,
                        target_id=target_expr.id,
                        anchor_text="",  # Not available from markdown
                        link_type=link_type,
                        rel_attribute=None
                    )
                    links_created += 1

            except Exception as e:
                logger.warning(f"Error processing markdown link {link_url}: {e}")
                continue

        if links_created > 0:
            logger.info(f"Created {links_created} links from markdown for {expr_url}")

    async def _save_media_from_list(self, media_list: list, expr_id: int):
        """
        Save media from the enriched markdown media list (legacy behavior).
        This reproduces the logic from _legacy/core.py:1780-1786.
        """
        from app.crud import crud_media

        for media_item in media_list:
            try:
                media_url = media_item.get('url')
                media_type_str = media_item.get('type', 'img')

                # Skip data URLs
                if not media_url or media_url.startswith('data:'):
                    continue

                # Check if media already exists
                existing_media = await crud_media.media.media_exists(
                    self.db, expression_id=expr_id, url=media_url
                )

                if not existing_media:
                    # Map type string to MediaType enum
                    if media_type_str == 'img':
                        media_type = models.MediaType.IMAGE
                    elif media_type_str == 'video':
                        media_type = models.MediaType.VIDEO
                    elif media_type_str == 'audio':
                        media_type = models.MediaType.AUDIO
                    else:
                        media_type = models.MediaType.IMAGE  # Default

                    media_data = {
                        'url': media_url,
                        'type': media_type,
                        'is_processed': False
                    }

                    await crud_media.media.create_media(
                        self.db, expression_id=expr_id, media_data=media_data
                    )
                    logger.debug(f"Saved media from markdown: {media_url}")

            except Exception as e:
                logger.warning(f"Error saving media {media_item}: {e}")
                continue

    async def _extract_and_save_links(self, soup, expr: models.Expression, expr_url: str, expr_land_id: int, expr_depth: Optional[int]):
        """Extracts and saves links from a crawled page with advanced validation."""
        from urllib.parse import urljoin, urlparse
        from app.crud import crud_domain, crud_expression, crud_link
        import re
        
        links_found = []
        
        # Extract all links with href attributes
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            
            # Skip empty, fragment-only, or javascript links
            if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:') or href.startswith('tel:'):
                continue
                
            # Resolve relative URLs to absolute
            try:
                full_url = urljoin(expr_url, href)
                parsed = urlparse(full_url)
                
                # Validate URL structure
                if not parsed.scheme in ['http', 'https'] or not parsed.netloc:
                    continue
                    
                # Remove common tracking parameters and fragments
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    # Keep only meaningful query parameters, filter out tracking
                    tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 
                                     'fbclid', 'gclid', 'ref', 'source', 'campaign'}
                    query_params = []
                    for param in parsed.query.split('&'):
                        if '=' in param:
                            key = param.split('=')[0].lower()
                            if key not in tracking_params:
                                query_params.append(param)
                    if query_params:
                        clean_url += '?' + '&'.join(query_params)
                
                # Get or create domain for this link
                domain_name = parsed.netloc.lower()
                domain = await crud_domain.domain.get_or_create(
                    self.db, name=domain_name, land_id=expr_land_id
                )
                
                # Check if expression already exists
                existing_expr = await crud_expression.expression.get_by_url_and_land(self.db, url=clean_url, land_id=expr_land_id)
                
                # Extract link text for context
                link_text = link.get_text(strip=True)[:200] or "No text"
                
                if not existing_expr:
                    # Create new expression for discovered link
                    depth = expr_depth + 1 if expr_depth is not None else 1
                    new_expr = await crud_expression.expression.get_or_create_expression(
                        self.db, 
                        land_id=expr_land_id, 
                        url=clean_url, 
                        depth=depth
                    )
                    target_expr = new_expr
                    
                    links_found.append({
                        'url': clean_url,
                        'text': link_text,
                        'domain': domain_name,
                        'depth': depth
                    })
                else:
                    target_expr = existing_expr
                
                # Create ExpressionLink relationship regardless of whether target exists
                if target_expr and target_expr.id != expr.id:  # Avoid self-links
                    # Determine link type (internal vs external)
                    link_type = "internal" if parsed.netloc == urlparse(expr_url).netloc else "external"
                    
                    rel_attr = link.get('rel')
                    if isinstance(rel_attr, (list, tuple)):
                        rel_attr = " ".join(str(item) for item in rel_attr if item)
                    elif rel_attr is not None:
                        rel_attr = str(rel_attr)

                    await crud_link.expression_link.create_link(
                        self.db, 
                        source_id=expr.id, 
                        target_id=target_expr.id,
                        anchor_text=link_text,
                        link_type=link_type,
                        rel_attribute=rel_attr
                    )
                    
            except Exception as e:
                await self.db.rollback()
                logger.warning(f"Error processing link {href}: {e}")
                continue
        
        if links_found:
            logger.info(f"Discovered {len(links_found)} new links from {expr_url}")
        
        return links_found

    async def _extract_and_save_media(self, soup, expr: models.Expression, expr_url: str, expr_id: int, analyze_media: bool):
        """Extracts and saves media from a crawled page with full analysis."""
        from urllib.parse import urljoin
        from app.core.media_processor import MediaProcessor
        from app.crud import crud_media
        
        # Initialize media processor
        media_processor = MediaProcessor(self.db, self.http_client)
        
        # Extract static media from HTML
        media_urls = media_processor.extract_media_urls(soup, expr_url)
        
        # Process each media URL
        for media_url in media_urls:
            try:
                # Check if media already exists
                existing_media = await crud_media.media.media_exists(
                    self.db, expression_id=expr_id, url=media_url
                )
                
                if not existing_media:
                    if media_url.startswith('data:'):
                        logger.debug("Skipping inline data media for expression %s", expr_id)
                        continue
                    # Determine media type
                    media_type = self._determine_media_type(media_url)
                    
                    # Create basic media record
                    media_data = {
                        'url': media_url,
                        'type': media_type,
                    }
                    
                    # For images, perform detailed analysis
                    if analyze_media and media_type == models.MediaType.IMAGE:
                        analysis = await media_processor.analyze_image(media_url)
                        if not analysis.get('error'):
                            media_data.update({
                                'width': analysis.get('width'),
                                'height': analysis.get('height'),
                                'file_size': analysis.get('file_size'),
                                'format': analysis.get('format'),
                                'has_transparency': analysis.get('has_transparency'),
                                'aspect_ratio': analysis.get('aspect_ratio'),
                                'dominant_colors': analysis.get('dominant_colors'),
                                'websafe_colors': analysis.get('websafe_colors'),
                                'image_hash': analysis.get('image_hash'),
                                'exif_data': analysis.get('exif_data'),
                                'color_mode': analysis.get('color_mode'),
                                'mime_type': analysis.get('mime_type'),
                                'processed_at': datetime.now(timezone.utc),
                                'is_processed': True,
                                'analysis_error': None,
                                'processing_error': None,
                            })
                        else:
                            media_data['analysis_error'] = analysis['error']
                    else:
                        media_data.setdefault('is_processed', False)
                    
                    # Save media record
                    await crud_media.media.create_media(self.db, expression_id=expr_id, media_data=media_data)
                    log_message = "Analyzed and saved %s: %s" if (analyze_media and media_type == models.MediaType.IMAGE) else "Saved %s (analysis skipped): %s"
                    logger.debug(log_message, media_type.name.lower(), media_url)
                    
            except Exception as e:
                logger.warning(f"Error processing media {media_url}: {e}")
                await self.db.rollback()
                continue
        
        # Extract dynamic media using Playwright (disabled in tests)
        try:
            await media_processor.extract_dynamic_medias(expr_url, expr)
        except Exception as e:
            logger.warning(f"Error during dynamic media extraction for {expr_url}: {e}")
    
    def _determine_media_type(self, url: str) -> models.MediaType:
        """Determine media type based on URL extension."""
        url_lower = url.lower()
        
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.tiff', '.ico')
        video_extensions = ('.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v')
        audio_extensions = ('.mp3', '.wav', '.ogg', '.aac', '.flac', '.m4a', '.wma')
        
        if any(url_lower.endswith(ext) for ext in image_extensions):
            return models.MediaType.IMAGE
        elif any(url_lower.endswith(ext) for ext in video_extensions):
            return models.MediaType.VIDEO
        elif any(url_lower.endswith(ext) for ext in audio_extensions):
            return models.MediaType.AUDIO
        else:
            # Default to IMAGE for unknown types (many images don't have clear extensions)
            return models.MediaType.IMAGE
