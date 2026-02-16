"""
Tache Celery pour le pipeline readable (V2 sync).
Extrait le contenu lisible des expressions crawlees via Trafilatura/fallbacks.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.core.celery_app import celery_app
from app.core.content_extractor import get_readable_content_with_fallbacks
from app.db import models
from app.db.models import CrawlStatus
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _apply_merge(expr: models.Expression, result: Dict[str, Any], strategy: str) -> Dict[str, str]:
    """
    Applique la strategie de merge sur une expression.
    Retourne un dict des champs modifies.
    """
    changes = {}

    new_readable = result.get("readable")
    new_title = result.get("title")
    new_description = result.get("description")
    new_lang = result.get("language")
    new_published = result.get("published_at")

    if strategy == "mercury_priority":
        # Le contenu extrait ecrase toujours
        if new_readable:
            expr.readable = new_readable
            changes["readable"] = "overwritten"
        if new_title:
            expr.title = new_title
            changes["title"] = "overwritten"
        if new_description:
            expr.description = new_description
            changes["description"] = "overwritten"
        if new_lang:
            expr.lang = new_lang
            changes["lang"] = "overwritten"

    elif strategy == "preserve_existing":
        # Ne remplit que les champs vides
        if new_readable and not expr.readable:
            expr.readable = new_readable
            changes["readable"] = "filled"
        if new_title and not expr.title:
            expr.title = new_title
            changes["title"] = "filled"
        if new_description and not expr.description:
            expr.description = new_description
            changes["description"] = "filled"
        if new_lang and not expr.lang:
            expr.lang = new_lang
            changes["lang"] = "filled"

    else:
        # smart_merge (defaut)
        if new_readable:
            if not expr.readable or len(new_readable) > len(expr.readable or ""):
                expr.readable = new_readable
                changes["readable"] = "smart_merged"
        if new_title:
            if not expr.title or len(new_title) > len(expr.title or ""):
                expr.title = new_title
                changes["title"] = "smart_merged"
        if new_description:
            if not expr.description or len(new_description) > len(expr.description or ""):
                expr.description = new_description
                changes["description"] = "smart_merged"
        if new_lang and not expr.lang:
            expr.lang = new_lang
            changes["lang"] = "smart_merged"

    return changes


def _extract_content_sync(url: str, html: Optional[str] = None) -> Dict[str, Any]:
    """Extraction de contenu synchrone via asyncio.run."""
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                get_readable_content_with_fallbacks(url, html)
            )
            return result
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Content extraction failed for {url}: {e}")
        return {
            "readable": None,
            "extraction_source": "error",
            "media_list": [],
            "links": [],
        }


@celery_app.task(name="readable_working_task", bind=True)
def readable_working_task(
    self,
    land_id: int,
    job_id: int,
    limit: Optional[int] = 10,
    depth: Optional[int] = None,
    merge_strategy: str = "smart_merge",
    enable_llm: bool = False,
) -> Dict[str, Any]:
    """
    Pipeline readable V2 sync : extrait le contenu lisible des expressions.
    Selectionne les expressions crawlees sans readable, applique content_extractor,
    met a jour la base.
    """
    db = SessionLocal()
    start_time = datetime.now(timezone.utc)

    logger.info("=" * 60)
    logger.info("[READABLE] START - land=%s job=%s limit=%s depth=%s strategy=%s",
                land_id, job_id, limit, depth, merge_strategy)
    logger.info("=" * 60)

    job: Optional[models.CrawlJob] = None
    stats = {
        "processed": 0,
        "updated": 0,
        "errors": 0,
        "skipped": 0,
        "media_created": 0,
        "links_created": 0,
        "wayback_fallbacks": 0,
    }

    try:
        # Marquer le job comme running
        job = db.query(models.CrawlJob).filter(models.CrawlJob.id == job_id).first()
        if job:
            job.status = CrawlStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            db.commit()

        # Selectionner les expressions candidates
        query = (
            db.query(models.Expression)
            .filter(
                models.Expression.land_id == land_id,
                models.Expression.approved_at.isnot(None),  # Deja crawlee
                models.Expression.http_status == 200,        # Reponse OK
            )
        )

        # Filtrer celles sans readable OU avec readable vide
        query = query.filter(
            (models.Expression.readable.is_(None))
            | (models.Expression.readable == "")
        )

        if depth is not None:
            query = query.filter(models.Expression.depth <= depth)

        query = query.order_by(models.Expression.depth.asc(), models.Expression.id.asc())

        if limit:
            query = query.limit(limit)

        expressions = query.all()

        if not expressions:
            logger.info("[READABLE] Aucune expression a traiter pour land %s", land_id)
            if job:
                job.status = CrawlStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
                job.result_data = {**stats, "message": "Aucune expression a traiter"}
                db.commit()
            db.close()
            return {**stats, "status": "completed", "message": "Aucune expression a traiter"}

        total = len(expressions)
        logger.info("[READABLE] %d expressions a traiter", total)

        for i, expr in enumerate(expressions):
            try:
                logger.info("[READABLE] [%d/%d] %s", i + 1, total, expr.url)

                # Extraction
                result = _extract_content_sync(expr.url, expr.content)

                if not result.get("readable"):
                    stats["skipped"] += 1
                    logger.info("[READABLE] Skipped (no content): %s", expr.url)
                    continue

                # Appliquer merge
                changes = _apply_merge(expr, result, merge_strategy)

                if result.get("extraction_source") == "archive_org":
                    stats["wayback_fallbacks"] += 1

                # Mettre a jour readable_at
                expr.readable_at = datetime.now(timezone.utc)

                # Creer media si presents
                media_list = result.get("media_list", [])
                for media_info in media_list:
                    media_url = media_info.get("url") if isinstance(media_info, dict) else getattr(media_info, "url", None)
                    media_type = media_info.get("type", "img") if isinstance(media_info, dict) else getattr(media_info, "type", "img")
                    if not media_url:
                        continue
                    # Verifier doublon
                    existing = (
                        db.query(models.Media)
                        .filter(
                            models.Media.expression_id == expr.id,
                            models.Media.url == media_url,
                        )
                        .first()
                    )
                    if not existing:
                        db.add(models.Media(
                            expression_id=expr.id,
                            url=media_url,
                            type=media_type,
                        ))
                        stats["media_created"] += 1

                # Creer links si presents
                links = result.get("links", [])
                for link_url in links:
                    if not link_url or not isinstance(link_url, str):
                        continue
                    # Chercher l'expression cible
                    target = (
                        db.query(models.Expression)
                        .filter(
                            models.Expression.land_id == land_id,
                            models.Expression.url == link_url,
                        )
                        .first()
                    )
                    if target and target.id != expr.id:
                        existing_link = (
                            db.query(models.ExpressionLink)
                            .filter(
                                models.ExpressionLink.source_id == expr.id,
                                models.ExpressionLink.target_id == target.id,
                            )
                            .first()
                        )
                        if not existing_link:
                            db.add(models.ExpressionLink(
                                source_id=expr.id,
                                target_id=target.id,
                                link_type="internal",
                            ))
                            stats["links_created"] += 1

                db.commit()
                stats["processed"] += 1
                if changes:
                    stats["updated"] += 1

                logger.info("[READABLE] OK %s source=%s changes=%s",
                            expr.url, result.get("extraction_source"), changes)

                # Update job progress
                if job and total > 0:
                    job.progress = (i + 1) / total
                    db.commit()

            except Exception as e:
                db.rollback()
                stats["errors"] += 1
                stats["processed"] += 1
                logger.error("[READABLE] ERROR %s: %s", expr.url, e)

        # Finaliser le job
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("[READABLE] DONE - land=%s processed=%d updated=%d errors=%d duration=%.1fs",
                    land_id, stats["processed"], stats["updated"], stats["errors"], duration)
        logger.info("=" * 60)

        result_data = {
            **stats,
            "status": "completed",
            "duration_seconds": duration,
            "merge_strategy": merge_strategy,
        }

        if job:
            job.status = CrawlStatus.COMPLETED
            job.completed_at = end_time
            job.progress = 1.0
            job.result_data = result_data
            db.commit()

        return result_data

    except Exception as exc:
        logger.exception("[READABLE] FAILED job=%s: %s", job_id, exc)
        if job:
            db.rollback()
            job.status = CrawlStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        else:
            db.rollback()
        return {**stats, "status": "failed", "error": str(exc)}
    finally:
        db.close()
