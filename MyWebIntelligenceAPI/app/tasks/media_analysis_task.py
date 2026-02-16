"""
Tache Celery pour l'analyse de medias (V2 sync).
Telecharge et analyse les images associees aux expressions d'un land.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import httpx

from app.core.celery_app import celery_app
from app.core.media_processor import MediaProcessorSync
from app.db import models
from app.db.models import CrawlStatus
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.analyze_land_media_task", bind=True)
def analyze_land_media_task(
    self,
    job_id: int,
    land_id: int,
    depth: int = 999,
    minrel: float = 0.0,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """
    Analyse les medias d'un land en arriere-plan (sync V2).

    Selectionne les medias non traites des expressions correspondant aux filtres,
    telecharge et analyse chaque image (dimensions, couleurs, hash, EXIF).
    """
    db = SessionLocal()
    start_time = datetime.now(timezone.utc)

    logger.info("=" * 60)
    logger.info("[MEDIA] START - land=%s job=%s depth=%s minrel=%s",
                land_id, job_id, depth, minrel)
    logger.info("=" * 60)

    job: Optional[models.CrawlJob] = None
    stats = {
        "total_media": 0,
        "analyzed": 0,
        "failed": 0,
        "skipped": 0,
    }

    try:
        # Marquer le job comme running
        job = db.query(models.CrawlJob).filter(models.CrawlJob.id == job_id).first()
        if job:
            job.status = CrawlStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            db.commit()

        # Recuperer les expression_ids filtres
        expr_query = (
            db.query(models.Expression.id)
            .filter(
                models.Expression.land_id == land_id,
                models.Expression.approved_at.isnot(None),
                models.Expression.http_status == 200,
            )
        )
        if depth is not None and depth < 999:
            expr_query = expr_query.filter(models.Expression.depth <= depth)
        if minrel > 0:
            expr_query = expr_query.filter(models.Expression.relevance >= minrel)

        expression_ids = [row[0] for row in expr_query.all()]

        if not expression_ids:
            logger.info("[MEDIA] Aucune expression correspondante pour land %s", land_id)
            result = {**stats, "status": "completed", "message": "No matching expressions"}
            if job:
                job.status = CrawlStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
                job.result_data = result
                db.commit()
            db.close()
            return result

        # Recuperer les medias non traites (images)
        media_items = (
            db.query(models.Media)
            .filter(
                models.Media.expression_id.in_(expression_ids),
                models.Media.type == "img",
                (models.Media.is_processed.is_(None)) | (models.Media.is_processed == False),
            )
            .order_by(models.Media.id.asc())
            .all()
        )

        stats["total_media"] = len(media_items)

        if not media_items:
            logger.info("[MEDIA] Aucun media non traite pour land %s", land_id)
            result = {**stats, "status": "completed", "message": "No unprocessed media"}
            if job:
                job.status = CrawlStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
                job.result_data = result
                db.commit()
            db.close()
            return result

        logger.info("[MEDIA] %d medias a analyser", len(media_items))

        # Traiter les medias avec un client HTTP synchrone
        with httpx.Client(timeout=30.0, follow_redirects=True) as http_client:
            processor = MediaProcessorSync(db, http_client)

            for i, media in enumerate(media_items):
                try:
                    logger.info("[MEDIA] [%d/%d] %s", i + 1, len(media_items), media.url)

                    analysis = processor.analyze_image(media.url)

                    if analysis.get("error"):
                        stats["failed"] += 1
                        logger.warning("[MEDIA] FAIL %s: %s", media.url, analysis["error"])
                    else:
                        # Mettre a jour le media
                        media.width = analysis.get("width")
                        media.height = analysis.get("height")
                        media.file_size = analysis.get("file_size")
                        media.metadata_ = {
                            "format": analysis.get("format"),
                            "color_mode": analysis.get("color_mode"),
                            "has_transparency": analysis.get("has_transparency"),
                            "aspect_ratio": analysis.get("aspect_ratio"),
                            "mime_type": analysis.get("mime_type"),
                            "exif_data": analysis.get("exif_data"),
                            "image_hash": analysis.get("image_hash"),
                        }
                        media.dominant_colors = analysis.get("dominant_colors", [])
                        media.is_processed = True
                        media.analyzed_at = datetime.now(timezone.utc)

                        db.commit()
                        stats["analyzed"] += 1
                        logger.info("[MEDIA] OK %s (%dx%d)", media.url,
                                    analysis.get("width", 0), analysis.get("height", 0))

                    # Update job progress
                    if job and len(media_items) > 0:
                        job.progress = (i + 1) / len(media_items)
                        db.commit()

                except Exception as e:
                    db.rollback()
                    stats["failed"] += 1
                    logger.error("[MEDIA] ERROR %s: %s", media.url, e)

        # Finaliser
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("[MEDIA] DONE - land=%s analyzed=%d failed=%d duration=%.1fs",
                    land_id, stats["analyzed"], stats["failed"], duration)
        logger.info("=" * 60)

        result_data = {
            **stats,
            "status": "completed",
            "land_id": land_id,
            "duration_seconds": duration,
            "filters": {"depth": depth, "minrel": minrel},
        }

        if job:
            job.status = CrawlStatus.COMPLETED
            job.completed_at = end_time
            job.progress = 1.0
            job.result_data = result_data
            db.commit()

        return result_data

    except Exception as exc:
        logger.exception("[MEDIA] FAILED job=%s: %s", job_id, exc)
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
