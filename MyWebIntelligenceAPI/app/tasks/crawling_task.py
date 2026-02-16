import logging
from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.core.crawler_engine import SyncCrawlerEngine
from app.db import models
from app.db.models import CrawlStatus
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# WebSocket support removed in V2 (moved to projetV3)
# Crawl progress can be monitored by polling the job status endpoint
def _send_progress(ws_channel: str | None, processed: int, total: int, message: str) -> None:
    """Placeholder - WebSocket support removed in V2."""
    pass


@celery_app.task(name="tasks.crawl_land_task", bind=True)
def crawl_land_task(self, job_id: int, ws_channel: str | None = None) -> None:
    """
    Celery entry point for crawling a land using the synchronous pipeline.
    """
    db = SessionLocal()
    engine: SyncCrawlerEngine | None = None

    start_time = datetime.now(timezone.utc)
    logger.info("=" * 80)
    logger.info("CRAWL STARTED - Job ID: %s", job_id)
    logger.info("Start Time: %s UTC", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 80)

    job: models.CrawlJob | None = None
    land_id_for_logging: int | None = None

    try:
        job = db.query(models.CrawlJob).filter(models.CrawlJob.id == job_id).first()
        if not job:
            logger.error("Crawl job with id %s not found.", job_id)
            return

        land_id_for_logging = job.land_id

        job.status = CrawlStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        db.commit()
        db.refresh(job)

        params = job.parameters or {}
        limit = params.get("limit", 0) if isinstance(params, dict) else 0
        depth = params.get("depth") if isinstance(params, dict) else None
        http_status = params.get("http_status") if isinstance(params, dict) else None
        analyze_media = bool(params.get("analyze_media")) if isinstance(params, dict) else False
        enable_llm = bool(params.get("enable_llm")) if isinstance(params, dict) else False

        logger.info(
            "Land ID: %s | limit=%s depth=%s http_status=%s analyze_media=%s enable_llm=%s",
            land_id_for_logging,
            limit,
            depth,
            http_status,
            analyze_media,
            enable_llm,
        )

        engine = SyncCrawlerEngine(db)

        land, expressions = engine.prepare_crawl(
            land_id_for_logging,
            limit=limit,
            depth=depth,
            http_status=http_status,
        )

        total_expressions = len(expressions)
        if total_expressions == 0:
            _send_progress(ws_channel, 0, 0, "Aucune expression à crawler")
            job.status = CrawlStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.result_data = {
                "processed": 0,
                "errors": 0,
                "http_status_codes": {},
                "message": "Aucune expression à crawler",
                "start_time": start_time.isoformat(),
                "end_time": job.completed_at.isoformat(),
                "duration_seconds": 0,
                "speed_urls_per_second": 0,
            }
            db.commit()
            return

        _send_progress(ws_channel, 0, total_expressions, "Début du crawling...")

        processed, errors, http_stats = engine.crawl_expressions(
            expressions,
            analyze_media=analyze_media,
            enable_llm=enable_llm,
        )

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        speed = processed / duration if duration > 0 else 0

        logger.info("=" * 80)
        logger.info(
            "CRAWL COMPLETED - Job ID: %s, Land ID: %s",
            job_id,
            land_id_for_logging,
        )
        logger.info("Start Time: %s UTC", start_time.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("End Time: %s UTC", end_time.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("Duration: %.2f seconds", duration)
        logger.info("URLs Processed: %s", processed)
        logger.info("Errors: %s", errors)
        logger.info("HTTP Status Codes: %s", http_stats)
        logger.info("=" * 80)

        _send_progress(
            ws_channel,
            processed,
            total_expressions,
            f"Crawl terminé: {processed} traités, {errors} erreurs",
        )

        job.status = CrawlStatus.COMPLETED
        job.completed_at = end_time
        job.progress = 1.0
        job.result_data = {
            "processed": processed,
            "errors": errors,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "speed_urls_per_second": speed,
            "http_status_codes": http_stats,
        }
        db.commit()

    except Exception as exc:  # noqa: BLE001
        logger.exception("Crawl failed for job %s: %s", job_id, exc)
        end_time = datetime.now(timezone.utc)

        if job:
            db.rollback()
            job.status = CrawlStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = end_time
            job.result_data = job.result_data or {}
            job.result_data.update(
                {
                    "error": str(exc),
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_seconds": (end_time - start_time).total_seconds(),
                }
            )
            db.commit()
        else:
            db.rollback()

        _send_progress(
            ws_channel,
            0,
            0,
            f"Erreur lors du crawling: {exc}",
        )
    finally:
        if engine:
            engine.close()
        db.close()
