"""
Tache Celery pour l'enrichissement SEO Rank des expressions (V2 sync).

Appelle l'API SEO Rank (seo-rank.my-addr.com) pour chaque expression d'un land
et stocke le payload JSON brut dans le champ seorank.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import quote

import httpx

from app.core.celery_app import celery_app
from app.config import settings
from app.db import models
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _fetch_seorank(url: str, api_key: str, base_url: str, timeout: int) -> Optional[dict]:
    """Call the SEO Rank API for a single URL and return the JSON payload."""
    safe_url = quote(url, safe=":/?&=%")
    request_url = f"{base_url.rstrip('/')}/{api_key}/{safe_url}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(request_url)
        if response.status_code != 200:
            logger.warning("[SEORANK] HTTP %s for %s", response.status_code, url)
            return None
        return response.json()
    except httpx.HTTPError as exc:
        logger.warning("[SEORANK] HTTP error for %s: %s", url, exc)
        return None
    except Exception as exc:
        logger.warning("[SEORANK] JSON/other error for %s: %s", url, exc)
        return None


@celery_app.task(name="seorank_task", bind=True)
def seorank_task(
    self,
    land_id: int,
    limit: int = 0,
    depth: Optional[int] = None,
    min_relevance: int = 1,
    force_refresh: bool = False,
    api_key_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch SEO Rank data for expressions in a land.

    Args:
        land_id: Land to process.
        limit: Max expressions (0 = unlimited).
        depth: Filter by crawl depth (None = all).
        min_relevance: Minimum relevance (default 1).
        force_refresh: Re-fetch even if seorank already exists.
        api_key_override: Use this API key instead of settings.

    Returns:
        Dict with processing statistics.
    """
    db = SessionLocal()
    start_time = datetime.now(timezone.utc)

    api_key = api_key_override or settings.SEORANK_API_KEY
    if not api_key:
        return {"status": "failed", "error": "No SEORANK_API_KEY configured"}

    base_url = settings.SEORANK_API_BASE_URL or "https://seo-rank.my-addr.com/api2/moz+sr+fb"
    timeout = settings.SEORANK_TIMEOUT or 15
    delay = max(0.0, settings.SEORANK_REQUEST_DELAY)

    logger.info("=" * 60)
    logger.info(
        "[SEORANK] START - land=%s limit=%s depth=%s minrel=%s force=%s",
        land_id, limit, depth, min_relevance, force_refresh,
    )
    logger.info("=" * 60)

    stats = {"processed": 0, "updated": 0, "errors": 0, "skipped": 0}

    try:
        land = db.query(models.Land).filter(models.Land.id == land_id).first()
        if not land:
            return {"status": "failed", "error": f"Land {land_id} not found"}

        # Build query
        query = (
            db.query(models.Expression)
            .filter(
                models.Expression.land_id == land_id,
                models.Expression.http_status == 200,
            )
        )

        if min_relevance > 0:
            query = query.filter(models.Expression.relevance >= min_relevance)

        if depth is not None:
            query = query.filter(models.Expression.depth == depth)

        if not force_refresh:
            query = query.filter(models.Expression.seo_rank.is_(None))

        query = query.order_by(models.Expression.id)
        if limit > 0:
            query = query.limit(limit)

        expressions = query.all()
        total = len(expressions)

        if not expressions:
            logger.info("[SEORANK] No expressions to process")
            return {**stats, "status": "completed", "message": "No expressions to process"}

        logger.info("[SEORANK] %d expressions to process", total)

        for i, expr in enumerate(expressions):
            try:
                if not expr.url:
                    stats["skipped"] += 1
                    continue

                payload = _fetch_seorank(expr.url, api_key, base_url, timeout)
                stats["processed"] += 1

                if payload is not None:
                    expr.seo_rank = json.dumps(payload)
                    db.commit()
                    stats["updated"] += 1
                else:
                    stats["errors"] += 1

                if delay > 0:
                    time.sleep(delay)

                if (i + 1) % 20 == 0:
                    logger.info(
                        "[SEORANK] [%d/%d] processed=%d updated=%d errors=%d",
                        i + 1, total, stats["processed"], stats["updated"], stats["errors"],
                    )
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "progress": int((i + 1) / total * 100),
                            "message": f"Processing {i + 1}/{total}",
                            **stats,
                        },
                    )

            except Exception as e:
                stats["errors"] += 1
                logger.error("[SEORANK] ERROR expr=%s: %s", expr.id, e)
                db.rollback()

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(
            "[SEORANK] DONE - land=%s processed=%d updated=%d errors=%d duration=%.1fs",
            land_id, stats["processed"], stats["updated"], stats["errors"], duration,
        )
        logger.info("=" * 60)

        return {**stats, "status": "completed", "duration_seconds": duration}

    except Exception as exc:
        logger.exception("[SEORANK] FAILED land=%s: %s", land_id, exc)
        db.rollback()
        return {**stats, "status": "failed", "error": str(exc)}
    finally:
        db.close()
