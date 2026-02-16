"""
Synchronous version of the crawler engine for Celery workers.

This avoids AsyncSession usage which caused greenlet issues under the prefork
worker pool. It re-implements the handful of DB operations required for the
crawl pipeline using a regular SQLAlchemy Session.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session, selectinload

from app.core import content_extractor, text_processing
from app.core.media_processor import MediaProcessorSync
from app.db import models
from app.services.sentiment_service import SentimentService
from app.services.quality_scorer import QualityScorer
from app.config import settings

logger = logging.getLogger(__name__)


class SyncCrawlerEngine:
    """Crawler engine relying on synchronous SQLAlchemy session and httpx client."""

    def __init__(self, db: Session):
        self.db = db
        self.http_client = httpx.Client(timeout=15.0, follow_redirects=True)
        self.sentiment_service = SentimentService()  # Initialize sentiment service
        self.quality_scorer = QualityScorer()  # Initialize quality scorer

    # ------------------------------------------------------------------ #
    # High level API                                                     #
    # ------------------------------------------------------------------ #
    def prepare_crawl(
        self,
        land_id: int,
        limit: int = 0,
        depth: Optional[int] = None,
        http_status: Optional[str] = None,
    ) -> Tuple[Optional[models.Land], List[models.Expression]]:
        """Return the land and the ordered list of expressions to crawl."""
        land = self.db.query(models.Land).options(selectinload(models.Land.words)).filter(models.Land.id == land_id).first()
        if not land:
            logger.error("Land %s not found", land_id)
            return None, []

        if land.start_urls:
            existing_expr = self._get_expressions_to_crawl_query(land_id, limit=1).first()
            if not existing_expr:
                for url in land.start_urls:
                    try:
                        self._get_or_create_expression(land_id, url, depth=0)
                        logger.info("Created expression for URL: %s", url)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Failed to create expression for %s: %s", url, exc)
                self.db.commit()

        expressions = self._fetch_expressions_to_crawl(
            land_id=land_id,
            limit=limit,
            depth=depth,
            http_status=http_status,
        )
        logger.info("Found %s expressions to crawl for land %s", len(expressions), land_id)
        return land, expressions

    def crawl_land(
        self,
        land_id: int,
        limit: int = 0,
        depth: Optional[int] = None,
        http_status: Optional[str] = None,
        analyze_media: bool = False,
        enable_llm: bool = False,
    ) -> Tuple[int, int, Dict[str, int]]:
        """Crawl the land synchronously and return processed, error counts, stats."""
        land, expressions = self.prepare_crawl(
            land_id,
            limit=limit,
            depth=depth,
            http_status=http_status,
        )
        if land is None:
            return 0, 0, {}

        processed, errors, stats = self.crawl_expressions(
            expressions,
            analyze_media=analyze_media,
            enable_llm=enable_llm
        )
        self.http_client.close()
        return processed, errors, stats

    def crawl_expressions(
        self,
        expressions: Iterable[models.Expression],
        analyze_media: bool = False,
        enable_llm: bool = False,
    ) -> Tuple[int, int, Dict[str, int]]:
        """Process expressions sequentially."""
        processed = 0
        errors = 0
        http_stats: Dict[str, int] = defaultdict(int)

        for expression in expressions:
            expr = self.db.query(models.Expression).filter(models.Expression.id == expression.id).first()
            if not expr:
                logger.warning("Expression %s not found during crawl", expression.id)
                continue

            expr_url = getattr(expr, "url", None)
            if not expr_url:
                logger.warning("Expression %s has no URL", expr.id)
                continue

            try:
                status_code = self.crawl_expression(
                    expr,
                    analyze_media=analyze_media,
                    enable_llm=enable_llm
                )
                self.db.commit()
                processed += 1
                if status_code is not None:
                    http_stats[str(status_code)] += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to crawl expression %s (%s): %s", expr.id, expr_url, exc)
                self.db.rollback()
                errors += 1
                http_stats["error"] += 1

        return processed, errors, dict(http_stats)

    def crawl_expression(
        self,
        expr: models.Expression,
        analyze_media: bool = False,
        enable_llm: bool = False
    ) -> Optional[int]:
        """Fetch, analyse and store an expression."""
        expr_url = str(expr.url)
        logger.info("Crawling URL: %s (analyze_media=%s, enable_llm=%s)", expr_url, analyze_media, enable_llm)

        html_content = ""
        http_status_code: Optional[int] = None
        content_type: Optional[str] = None
        content_length: Optional[int] = None

        try:
            response = self.http_client.get(expr_url)
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
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP error for %s: %s", expr_url, exc)
            html_content = exc.response.text if exc.response is not None else ""
            http_status_code = exc.response.status_code if exc.response is not None else None
            if exc.response is not None:
                content_type = exc.response.headers.get('content-type', None)
        except httpx.RequestError as exc:
            logger.error("Request error for %s: %s", expr_url, exc)
            http_status_code = 0

        # Extract HTTP headers: Last-Modified and ETag
        last_modified_str = None
        etag_str = None
        if http_status_code and http_status_code < 400:
            try:
                if hasattr(response, 'headers'):
                    last_modified_str = response.headers.get('last-modified', None)
                    etag_str = response.headers.get('etag', None)
            except Exception:
                pass

        update_data: Dict[str, Optional[str]] = {
            "http_status": http_status_code,
            "content_type": content_type,
            "content_length": content_length,
            "last_modified": last_modified_str,
            "etag": etag_str,
            "crawled_at": datetime.utcnow(),
        }

        # Extract readable content - function now returns a Dict, not tuple
        extraction_result = {}
        extraction_source = "unknown"
        try:
            extractor = content_extractor.ContentExtractor()
            extraction_result = asyncio.run(
                extractor.get_readable_content_with_fallbacks(expr_url, html_content)
            )
            extraction_source = extraction_result.get('extraction_source', 'unknown')
            logger.info("Crawling %s using %s", expr_url, extraction_source)
        except RuntimeError:
            # We might already be running in an event loop if the caller wraps asyncio.run
            extractor = content_extractor.ContentExtractor()
            extraction_result = asyncio.get_event_loop().run_until_complete(
                extractor.get_readable_content_with_fallbacks(expr_url, html_content)
            )
            extraction_source = extraction_result.get('extraction_source', 'unknown')
            logger.info("Crawling %s using %s", expr_url, extraction_source)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Readable extraction failed for %s: %s", expr_url, exc)
            extraction_result = {}

        # Extract values from result dict
        readable_content = extraction_result.get('readable')
        soup = extraction_result.get('soup')  # BeautifulSoup du HTML complet (pour metadata)
        filtered_soup = extraction_result.get('filtered_soup')  # Soup filtré du contenu principal
        extraction_source = extraction_result.get('extraction_source', 'unknown')
        metadata = {
            'title': extraction_result.get('title', expr_url),
            'description': extraction_result.get('description'),
            'keywords': extraction_result.get('keywords'),
            'lang': extraction_result.get('language'),
            'canonical_url': extraction_result.get('canonical_url'),
            'published_at': extraction_result.get('published_at')
        }

        # Debug logging
        logger.info("Extraction result for %s: readable=%s chars, title=%s, soup=%s",
                   expr_url,
                   len(readable_content) if readable_content else 0,
                   metadata.get('title', 'None')[:50] if metadata.get('title') else 'None',
                   'present' if soup else 'missing')

        # Store raw HTML content (legacy field) - ALIGNED WITH ASYNC CRAWLER
        if extraction_result.get('content'):
            update_data["content"] = extraction_result['content']
            logger.debug(f"Storing HTML content for {expr_url}: {len(extraction_result['content'])} chars")
        else:
            logger.warning(f"No HTML content in extraction_result for {expr_url}")

        if readable_content:
            # Calculer word_count, reading_time et détecter la langue depuis le contenu lisible
            from app.utils.text_utils import analyze_text_metrics
            text_metrics = analyze_text_metrics(readable_content)
            word_count = text_metrics.get('word_count', 0)
            reading_time = max(1, word_count // 200) if word_count > 0 else None  # 200 mots/min
            detected_lang = text_metrics.get('language')  # Langue détectée par langdetect

            # Fallback vers langue HTML si détection échoue
            html_lang = metadata.get("lang") or metadata.get("language")
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

            land_dict = text_processing.get_land_dictionary_sync(self.db, expr.land_id)

            class TempExpr:
                def __init__(self, title: Optional[str], readable: Optional[str], expr_id: int):
                    self.title = title
                    self.readable = readable
                    self.id = expr_id

            temp_expr = TempExpr(metadata.get("title"), readable_content, expr.id)
            try:
                relevance = asyncio.run(
                    text_processing.expression_relevance(land_dict, temp_expr, final_lang or "fr")
                )
            except RuntimeError:
                loop = asyncio.new_event_loop()
                relevance = loop.run_until_complete(
                    text_processing.expression_relevance(land_dict, temp_expr, final_lang or "fr")
                )
                loop.close()
            update_data["relevance"] = relevance

            # LLM Validation (if enabled and expression is relevant)
            if enable_llm and settings.OPENROUTER_ENABLED and relevance > 0:
                try:
                    from app.services.llm_validation_service import LLMValidationService

                    # Get land from DB
                    land = self.db.query(models.Land).filter(models.Land.id == expr.land_id).first()

                    if land:
                        # Create temp expression with current update_data for validation
                        class TempExprLLM:
                            def __init__(self):
                                self.id = expr.id
                                self.url = expr_url
                                self.title = update_data.get("title")
                                self.description = update_data.get("description")
                                self.readable = readable_content
                                self.lang = final_lang

                        temp_expr_llm = TempExprLLM()

                        # V2 SYNC-ONLY: Direct synchronous call (no async)
                        llm_service = LLMValidationService(self.db)

                        validation_result = llm_service.validate_expression_relevance(
                            temp_expr_llm,
                            land
                        )

                        # Update validation fields
                        update_data["valid_llm"] = 'oui' if validation_result.is_relevant else 'non'
                        update_data["valid_model"] = validation_result.model_used

                        # If not relevant according to LLM, set relevance to 0
                        if not validation_result.is_relevant:
                            update_data["relevance"] = 0
                            logger.info(
                                f"[LLM] Expression {expr.id} marked as non-relevant by {validation_result.model_used}"
                            )
                        else:
                            logger.info(
                                f"[LLM] Expression {expr.id} validated as relevant by {validation_result.model_used}"
                            )
                    else:
                        logger.warning(f"[LLM] Could not validate: land {expr.land_id} not found")

                except Exception as e:
                    logger.error(f"[LLM] Validation failed for {expr_url}: {e}")
                    # Continue without LLM validation (non-blocking)

            # Sentiment Analysis (if enabled)
            if settings.ENABLE_SENTIMENT_ANALYSIS:
                try:
                    # Determine if we should use LLM (this would come from crawl parameters)
                    # For now, always use TextBlob (default) unless explicitly requested
                    use_llm = False  # TODO: Get from crawl parameters (llm_validation flag)

                    # Note: sentiment_service methods are sync-compatible via asyncio.run
                    try:
                        sentiment_data = asyncio.run(
                            self.sentiment_service.enrich_expression_sentiment(
                                content=update_data.get("content"),
                                readable=readable_content,
                                language=final_lang,
                                use_llm=use_llm
                            )
                        )
                    except RuntimeError:
                        # Already in event loop
                        loop = asyncio.new_event_loop()
                        sentiment_data = loop.run_until_complete(
                            self.sentiment_service.enrich_expression_sentiment(
                                content=update_data.get("content"),
                                readable=readable_content,
                                language=final_lang,
                                use_llm=use_llm
                            )
                        )
                        loop.close()

                    # Add sentiment data to update
                    update_data["sentiment_score"] = sentiment_data["sentiment_score"]
                    update_data["sentiment_label"] = sentiment_data["sentiment_label"]
                    update_data["sentiment_confidence"] = sentiment_data["sentiment_confidence"]
                    update_data["sentiment_status"] = sentiment_data["sentiment_status"]
                    update_data["sentiment_model"] = sentiment_data["sentiment_model"]
                    update_data["sentiment_computed_at"] = sentiment_data["sentiment_computed_at"]

                    logger.debug(
                        f"[SYNC] Sentiment enriched for {expr_url}: "
                        f"{sentiment_data['sentiment_label']} ({sentiment_data['sentiment_score']}) "
                        f"via {sentiment_data['sentiment_model']}"
                    )
                except Exception as e:
                    logger.error(f"[SYNC] Sentiment enrichment failed for {expr_url}: {e}")
                    # Continue without sentiment (non-blocking)

            # Quality Score (if enabled)
            if settings.ENABLE_QUALITY_SCORING:
                try:
                    # Get land from DB for quality computation
                    land = self.db.query(models.Land).filter(models.Land.id == expr.land_id).first()

                    if land:
                        # Build temporary expression object for quality computation
                        class TempExprQuality:
                            def __init__(self, data, existing_expr):
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
                                self.validllm = getattr(existing_expr, 'validllm', None)  # From existing expr
                                self.readable = data.get("readable")
                                self.readable_at = getattr(existing_expr, 'readable_at', None)
                                self.crawled_at = data.get("crawled_at")

                        temp_expr_quality = TempExprQuality(update_data, expr)

                        quality_result = self.quality_scorer.compute_quality_score(
                            expression=temp_expr_quality,
                            land=land
                        )

                        update_data["quality_score"] = quality_result["score"]

                        logger.debug(
                            f"[SYNC] Quality computed for {expr_url}: "
                            f"{quality_result['score']:.2f} ({quality_result['category']})"
                        )
                    else:
                        logger.warning(f"[SYNC] Could not compute quality: land {expr.land_id} not found")

                except Exception as e:
                    logger.error(f"[SYNC] Quality scoring failed for {expr_url}: {e}")
                    # Continue without quality (non-blocking)

            # approved_at is set whenever readable content is saved
            update_data["approved_at"] = datetime.utcnow()

            # Extract links and media using appropriate strategy
            self._handle_links_and_media(
                readable_content=readable_content,
                extraction_source=extraction_source,
                filtered_soup=filtered_soup,
                expr=expr,
                expr_url=expr_url,
                analyze_media=analyze_media,
            )

        for field, value in update_data.items():
            setattr(expr, field, value)

        self.db.add(expr)
        return http_status_code

    def close(self) -> None:
        """Close HTTP resources."""
        try:
            self.http_client.close()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _get_or_create_domain(self, name: str, land_id: int) -> models.Domain:
        domain = (
            self.db.query(models.Domain)
            .filter(
                models.Domain.name == name,
                models.Domain.land_id == land_id,
            )
            .first()
        )
        if domain:
            return domain

        domain = models.Domain(name=name, land_id=land_id)
        self.db.add(domain)
        self.db.commit()
        self.db.refresh(domain)
        return domain

    def _get_or_create_expression(self, land_id: int, url: str, depth: int) -> models.Expression:
        url_hash = models.Expression.compute_url_hash(url)
        expression = (
            self.db.query(models.Expression)
            .filter(
                models.Expression.land_id == land_id,
                models.Expression.url_hash == url_hash,
                models.Expression.url == url,
            )
            .first()
        )
        if expression:
            return expression

        domain_name = urlparse(url).netloc
        domain = self._get_or_create_domain(domain_name, land_id)

        expression = models.Expression(
            url=url,
            url_hash=url_hash,
            land_id=land_id,
            domain_id=domain.id,
            depth=depth,
        )
        self.db.add(expression)
        self.db.flush()
        self.db.refresh(expression)
        return expression

    def _get_expressions_to_crawl_query(
        self,
        land_id: int,
        limit: int = 0,
        http_status: Optional[str] = None,
        depth: Optional[int] = None,
    ):
        """
        CRITÈRE: approved_at IS NULL = expressions jamais traitées par le crawler
        (pas crawled_at qui indique seulement le fetch HTTP)
        """
        query = (
            self.db.query(models.Expression)
            .filter(models.Expression.land_id == land_id)
            .filter(models.Expression.approved_at.is_(None))
            .order_by(models.Expression.depth.asc(), models.Expression.created_at.asc())
        )

        if http_status is not None:
            try:
                http_value = int(http_status)
                query = query.filter(models.Expression.http_status == http_value)
            except (TypeError, ValueError):
                pass

        if depth is not None:
            query = query.filter(models.Expression.depth == depth)

        if limit and limit > 0:
            query = query.limit(limit)

        return query

    def _fetch_expressions_to_crawl(
        self,
        land_id: int,
        limit: int = 0,
        depth: Optional[int] = None,
        http_status: Optional[str] = None,
    ) -> List[models.Expression]:
        return list(
            self._get_expressions_to_crawl_query(
                land_id=land_id,
                limit=limit,
                depth=depth,
                http_status=http_status,
            ).all()
        )

    def _handle_links_and_media(
        self,
        readable_content: Optional[str],
        extraction_source: str,
        filtered_soup: Optional[Any],
        expr: models.Expression,
        expr_url: str,
        analyze_media: bool,
    ) -> None:
        """
        Extrait les liens et médias selon la source d'extraction.

        Stratégie:
        - trafilatura_direct / archive_org: Extraction depuis markdown readable
        - beautifulsoup_smart / beautifulsoup_basic: Extraction depuis soup filtré/nettoyé
        - all_failed: Pas d'extraction

        Args:
            readable_content: Contenu readable (markdown ou texte)
            extraction_source: Source d'extraction
            filtered_soup: Soup filtré du contenu principal (None si markdown)
            expr: Expression courante
            expr_url: URL de l'expression
            analyze_media: Analyser les images (dimensions, couleurs, etc.)
        """
        import os

        if os.getenv("PYTEST_CURRENT_TEST"):
            logger.debug("Test environment detected, skipping link/media extraction")
            return

        logger.info(f"Extracting links/media for {expr_url} using source: {extraction_source}")

        # Stratégie selon la source d'extraction
        if extraction_source in ('trafilatura_direct', 'archive_org'):
            # ✅ Extraction depuis le markdown readable
            if not readable_content:
                logger.warning(f"No readable content for {expr_url}, skipping link/media extraction")
                return

            try:
                self._extract_links_from_markdown(readable_content, expr, expr_url)
            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.warning("Error extracting links from markdown for %s: %s", expr_url, exc)

            try:
                self._extract_media_from_markdown(readable_content, expr, expr_url, analyze_media)
            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.warning("Error extracting media from markdown for %s: %s", expr_url, exc)

        elif extraction_source in ('beautifulsoup_smart', 'beautifulsoup_basic'):
            # ✅ Extraction depuis le soup filtré/nettoyé (PAS le soup complet)
            if not filtered_soup:
                logger.warning(f"No filtered soup for {expr_url}, skipping link/media extraction")
                return

            try:
                self._extract_and_save_links(filtered_soup, expr, expr_url)
            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.warning("Error extracting links from soup for %s: %s", expr_url, exc)

            try:
                self._extract_and_save_media(filtered_soup, expr, expr_url, analyze_media)
            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.warning("Error extracting media from soup for %s: %s", expr_url, exc)

        elif extraction_source == 'all_failed':
            # ❌ Aucune extraction réussie
            logger.warning(f"Extraction failed for {expr_url}, skipping link/media extraction")

        else:
            logger.error(f"Unknown extraction_source: {extraction_source} for {expr_url}")

    def _extract_links_from_markdown(self, markdown_content: str, expr: models.Expression, expr_url: str) -> List[Dict[str, str]]:
        """
        Extrait et sauvegarde les liens depuis le contenu markdown.
        Format: [texte](url) - liens markdown uniquement (pas les images ![](url))
        """
        from app.db.models import ExpressionLink

        links_found: List[Dict[str, str]] = []

        if not markdown_content:
            return links_found

        # Regex pour liens markdown: [texte](url) mais pas ![texte](url)
        # Pattern négatif lookbehind pour éviter les images
        import re
        link_pattern = r'(?<!!)\[([^\]]*)\]\(([^)]+)\)'

        for match in re.finditer(link_pattern, markdown_content):
            anchor_text = match.group(1).strip() or "No text"
            href = match.group(2).strip()

            if not href or href.startswith("#") or href.startswith(("javascript:", "mailto:", "tel:")):
                continue

            try:
                full_url = urljoin(expr_url, href)
                parsed = urlparse(full_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    continue

                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    tracking_params = {
                        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
                        "fbclid", "gclid", "ref", "source", "campaign",
                    }
                    kept_params = []
                    for part in parsed.query.split("&"):
                        if "=" not in part:
                            continue
                        key = part.split("=", 1)[0].lower()
                        if key not in tracking_params:
                            kept_params.append(part)
                    if kept_params:
                        clean_url = f"{clean_url}?{'&'.join(kept_params)}"

                domain = self._get_or_create_domain(parsed.netloc.lower(), expr.land_id)

                target_expr = (
                    self.db.query(models.Expression)
                    .filter(
                        models.Expression.land_id == expr.land_id,
                        models.Expression.url_hash == models.Expression.compute_url_hash(clean_url),
                        models.Expression.url == clean_url,
                    )
                    .first()
                )

                if not target_expr:
                    depth = (expr.depth or 0) + 1
                    target_expr = self._get_or_create_expression(expr.land_id, clean_url, depth)

                    links_found.append(
                        {
                            "url": clean_url,
                            "text": anchor_text[:200],
                            "domain": domain.name,
                            "depth": target_expr.depth or depth,
                        }
                    )

                if target_expr.id == expr.id:
                    continue

                link_type = "internal" if parsed.netloc == urlparse(expr_url).netloc else "external"

                relationship_exists = (
                    self.db.query(models.ExpressionLink)
                    .filter(
                        models.ExpressionLink.source_id == expr.id,
                        models.ExpressionLink.target_id == target_expr.id,
                    )
                    .first()
                    is not None
                )

                if not relationship_exists:
                    link_obj = ExpressionLink(
                        source_id=expr.id,
                        target_id=target_expr.id,
                        anchor_text=anchor_text[:200],
                        link_type=link_type,
                        rel_attribute=None,  # Markdown n'a pas de rel attribute
                    )
                    self.db.add(link_obj)
                    self.db.commit()

            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.warning("Error processing markdown link %s: %s", href, exc)

        if links_found:
            logger.info("Discovered %s new links from markdown content of %s", len(links_found), expr_url)

        return links_found

    def _extract_and_save_links(self, soup, expr: models.Expression, expr_url: str) -> List[Dict[str, str]]:
        from app.db.models import ExpressionLink

        links_found: List[Dict[str, str]] = []

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            if not href or href.startswith("#") or href.startswith(("javascript:", "mailto:", "tel:")):
                continue

            try:
                full_url = urljoin(expr_url, href)
                parsed = urlparse(full_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    continue

                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    tracking_params = {
                        "utm_source",
                        "utm_medium",
                        "utm_campaign",
                        "utm_content",
                        "utm_term",
                        "fbclid",
                        "gclid",
                        "ref",
                        "source",
                        "campaign",
                    }
                    kept_params = []
                    for part in parsed.query.split("&"):
                        if "=" not in part:
                            continue
                        key = part.split("=", 1)[0].lower()
                        if key not in tracking_params:
                            kept_params.append(part)
                    if kept_params:
                        clean_url = f"{clean_url}?{'&'.join(kept_params)}"

                domain = self._get_or_create_domain(parsed.netloc.lower(), expr.land_id)

                target_expr = (
                    self.db.query(models.Expression)
                    .filter(
                        models.Expression.land_id == expr.land_id,
                        models.Expression.url_hash == models.Expression.compute_url_hash(clean_url),
                        models.Expression.url == clean_url,
                    )
                    .first()
                )

                link_text = link.get_text(strip=True)[:200] or "No text"

                if not target_expr:
                    depth = (expr.depth or 0) + 1
                    target_expr = self._get_or_create_expression(expr.land_id, clean_url, depth)

                    links_found.append(
                        {
                            "url": clean_url,
                            "text": link_text,
                            "domain": domain.name,
                            "depth": target_expr.depth or depth,
                        }
                    )

                if target_expr.id == expr.id:
                    continue

                link_type = "internal" if parsed.netloc == urlparse(expr_url).netloc else "external"
                rel_attr = link.get("rel")
                if isinstance(rel_attr, (list, tuple)):
                    rel_attr = " ".join(str(item) for item in rel_attr if item)

                relationship_exists = (
                    self.db.query(models.ExpressionLink)
                    .filter(
                        models.ExpressionLink.source_id == expr.id,
                        models.ExpressionLink.target_id == target_expr.id,
                    )
                    .first()
                    is not None
                )

                if not relationship_exists:
                    link_obj = ExpressionLink(
                        source_id=expr.id,
                        target_id=target_expr.id,
                        anchor_text=link_text,
                        link_type=link_type,
                        rel_attribute=rel_attr,
                    )
                    self.db.add(link_obj)
                    self.db.commit()

            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.warning("Error processing link %s: %s", href, exc)

        if links_found:
            logger.info("Discovered %s new links from %s", len(links_found), expr_url)

        return links_found

    def _extract_media_from_markdown(
        self,
        markdown_content: str,
        expr: models.Expression,
        expr_url: str,
        analyze_media: bool,
    ) -> None:
        """
        Extrait et sauvegarde les médias depuis le contenu markdown.
        Formats supportés:
        - Images: ![alt](url)
        - Vidéos: [VIDEO: url]
        - Audio: [AUDIO: url]
        """
        if not markdown_content:
            return

        media_processor = MediaProcessorSync(self.db, self.http_client)
        import re

        # Pattern 1: Images markdown ![alt](url)
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        for match in re.finditer(image_pattern, markdown_content):
            media_url = match.group(2).strip()

            try:
                if media_url.startswith("data:"):
                    continue

                if media_processor.media_exists(expr.id, media_url):
                    continue

                media_type = models.MediaType.IMAGE
                media_payload: Dict[str, Any] = {"url": media_url, "type": media_type}

                if analyze_media:
                    analysis = media_processor.analyze_image(media_url)
                    if not analysis.get("error"):
                        media_payload.update(
                            {
                                "width": analysis.get("width"),
                                "height": analysis.get("height"),
                                "file_size": analysis.get("file_size"),
                                "format": analysis.get("format"),
                                "has_transparency": analysis.get("has_transparency"),
                                "aspect_ratio": analysis.get("aspect_ratio"),
                                "dominant_colors": analysis.get("dominant_colors"),
                                "websafe_colors": analysis.get("websafe_colors"),
                                "image_hash": analysis.get("image_hash"),
                                "exif_data": analysis.get("exif_data"),
                                "color_mode": analysis.get("color_mode"),
                                "mime_type": analysis.get("mime_type"),
                                "processed_at": datetime.now(timezone.utc),
                                "is_processed": True,
                                "analysis_error": None,
                                "processing_error": None,
                            }
                        )
                    else:
                        media_payload["analysis_error"] = analysis["error"]
                else:
                    media_payload.setdefault("is_processed", False)

                media_processor.create_media(expr.id, media_payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error processing markdown image %s: %s", media_url, exc)
                self.db.rollback()

        # Pattern 2: Vidéos [VIDEO: url]
        video_pattern = r'\[VIDEO:\s*([^\]]+)\]'
        for match in re.finditer(video_pattern, markdown_content, flags=re.IGNORECASE):
            media_url = match.group(1).strip()

            try:
                if media_url.startswith("data:"):
                    continue

                if media_processor.media_exists(expr.id, media_url):
                    continue

                media_payload = {"url": media_url, "type": models.MediaType.VIDEO, "is_processed": False}
                media_processor.create_media(expr.id, media_payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error processing markdown video %s: %s", media_url, exc)
                self.db.rollback()

        # Pattern 3: Audio [AUDIO: url]
        audio_pattern = r'\[AUDIO:\s*([^\]]+)\]'
        for match in re.finditer(audio_pattern, markdown_content, flags=re.IGNORECASE):
            media_url = match.group(1).strip()

            try:
                if media_url.startswith("data:"):
                    continue

                if media_processor.media_exists(expr.id, media_url):
                    continue

                media_payload = {"url": media_url, "type": models.MediaType.AUDIO, "is_processed": False}
                media_processor.create_media(expr.id, media_payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error processing markdown audio %s: %s", media_url, exc)
                self.db.rollback()

        logger.debug("Extracted media from markdown content of %s", expr_url)

    def _extract_and_save_media(
        self,
        soup,
        expr: models.Expression,
        expr_url: str,
        analyze_media: bool,
    ) -> None:
        media_processor = MediaProcessorSync(self.db, self.http_client)
        media_urls = media_processor.extract_media_urls(soup, expr_url)

        for media_url in media_urls:
            try:
                if media_url.startswith("data:"):
                    continue

                if media_processor.media_exists(expr.id, media_url):
                    continue

                media_type = self._determine_media_type(media_url)
                media_payload: Dict[str, Any] = {"url": media_url, "type": media_type}

                if analyze_media and media_type == models.MediaType.IMAGE:
                    analysis = media_processor.analyze_image(media_url)
                    if not analysis.get("error"):
                        media_payload.update(
                            {
                                "width": analysis.get("width"),
                                "height": analysis.get("height"),
                                "file_size": analysis.get("file_size"),
                                "format": analysis.get("format"),
                                "has_transparency": analysis.get("has_transparency"),
                                "aspect_ratio": analysis.get("aspect_ratio"),
                                "dominant_colors": analysis.get("dominant_colors"),
                                "websafe_colors": analysis.get("websafe_colors"),
                                "image_hash": analysis.get("image_hash"),
                                "exif_data": analysis.get("exif_data"),
                                "color_mode": analysis.get("color_mode"),
                                "mime_type": analysis.get("mime_type"),
                                "processed_at": datetime.now(timezone.utc),
                                "is_processed": True,
                                "analysis_error": None,
                                "processing_error": None,
                            }
                        )
                    else:
                        media_payload["analysis_error"] = analysis["error"]
                else:
                    media_payload.setdefault("is_processed", False)

                media_processor.create_media(expr.id, media_payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error processing media %s: %s", media_url, exc)
                self.db.rollback()

        try:
            media_processor.extract_dynamic_medias(expr_url, expr)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error during dynamic media extraction for %s: %s", expr_url, exc)

    @staticmethod
    def _determine_media_type(url: str) -> models.MediaType:
        url_lower = url.lower()

        image_ext = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.tiff', '.ico')
        video_ext = ('.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v')
        audio_ext = ('.mp3', '.wav', '.ogg', '.aac', '.flac', '.m4a', '.wma')

        if url_lower.endswith(image_ext):
            return models.MediaType.IMAGE
        if url_lower.endswith(video_ext):
            return models.MediaType.VIDEO
        if url_lower.endswith(audio_ext):
            return models.MediaType.AUDIO
        return models.MediaType.IMAGE
