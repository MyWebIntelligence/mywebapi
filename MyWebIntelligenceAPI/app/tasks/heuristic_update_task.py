"""
Tache Celery pour la mise a jour heuristique des domaines (V2 sync).

Recalcule les noms de domaine de toutes les expressions d'un land
en utilisant les regles heuristiques configurees, et met a jour
les foreign keys domain_id si le domaine a change.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.core.celery_app import celery_app
from app.db import models
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _get_domain_name_sync(url: str, heuristics: Dict[str, str]) -> str:
    """Extract domain name from URL, applying heuristic patterns."""
    try:
        domain_name = urlparse(url).netloc
        for key, pattern in heuristics.items():
            if domain_name.endswith(key):
                matches = re.findall(pattern, url)
                if matches:
                    domain_name = matches[0]
                break
        return domain_name
    except Exception:
        return ""


@celery_app.task(name="heuristic_update_task", bind=True)
def heuristic_update_task(
    self,
    land_id: Optional[int] = None,
    heuristics_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Recalculate domain names for expressions using heuristic patterns.

    Args:
        land_id: If provided, only update expressions for this land.
                 If None, update all expressions.
        heuristics_override: JSON string of heuristics to use instead of settings.
                             Format: {"domain_suffix": "regex_pattern", ...}

    Returns:
        Dict with update statistics.
    """
    db = SessionLocal()
    start_time = datetime.now(timezone.utc)

    # Load heuristics
    if heuristics_override:
        try:
            heuristics = json.loads(heuristics_override)
        except Exception as e:
            return {"status": "failed", "error": f"Invalid heuristics JSON: {e}"}
    else:
        from app.config import settings
        try:
            heuristics = json.loads(settings.HEURISTICS)
        except Exception:
            heuristics = {}

    if not heuristics:
        return {"status": "completed", "updated": 0, "message": "No heuristics configured"}

    logger.info("=" * 60)
    logger.info("[HEURISTIC] START - land=%s heuristics=%s", land_id, list(heuristics.keys()))
    logger.info("=" * 60)

    stats = {"updated": 0, "errors": 0, "domains_created": 0, "processed": 0}

    try:
        # Build domain name cache {id: name}
        if land_id:
            domains = db.query(models.Domain).filter(models.Domain.land_id == land_id).all()
        else:
            domains = db.query(models.Domain).all()
        domain_cache = {d.id: d.name for d in domains}

        # Select expressions
        query = db.query(models.Expression)
        if land_id:
            query = query.filter(models.Expression.land_id == land_id)
        expressions = query.all()

        total = len(expressions)
        logger.info("[HEURISTIC] %d expressions to process", total)

        for i, expr in enumerate(expressions):
            try:
                if not expr.url:
                    continue

                new_domain_name = _get_domain_name_sync(expr.url, heuristics)
                if not new_domain_name:
                    continue

                current_domain_name = domain_cache.get(expr.domain_id, "")

                if new_domain_name != current_domain_name:
                    # Find or create the target domain
                    expr_land_id = expr.land_id
                    target_domain = (
                        db.query(models.Domain)
                        .filter(
                            models.Domain.land_id == expr_land_id,
                            models.Domain.name == new_domain_name,
                        )
                        .first()
                    )

                    if not target_domain:
                        target_domain = models.Domain(
                            land_id=expr_land_id,
                            name=new_domain_name,
                        )
                        db.add(target_domain)
                        db.flush()
                        domain_cache[target_domain.id] = new_domain_name
                        stats["domains_created"] += 1

                    expr.domain_id = target_domain.id
                    stats["updated"] += 1

                stats["processed"] += 1

                if (i + 1) % 100 == 0:
                    db.commit()
                    logger.info(
                        "[HEURISTIC] [%d/%d] %d updated, %d domains created",
                        i + 1, total, stats["updated"], stats["domains_created"],
                    )

            except Exception as e:
                stats["errors"] += 1
                logger.error("[HEURISTIC] ERROR expr=%s: %s", expr.id, e)
                db.rollback()

        db.commit()

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(
            "[HEURISTIC] DONE - updated=%d domains_created=%d errors=%d duration=%.1fs",
            stats["updated"], stats["domains_created"], stats["errors"], duration,
        )
        logger.info("=" * 60)

        return {
            **stats,
            "status": "completed",
            "duration_seconds": duration,
        }

    except Exception as exc:
        logger.exception("[HEURISTIC] FAILED: %s", exc)
        db.rollback()
        return {**stats, "status": "failed", "error": str(exc)}
    finally:
        db.close()
