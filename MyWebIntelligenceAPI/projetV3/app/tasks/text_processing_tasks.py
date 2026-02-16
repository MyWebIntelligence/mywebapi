"""
Tâches Celery dédiées au traitement de texte (extraction & analyse).
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from app.core.celery_app import celery_app
from app.db.models import Expression
from app.db.session import get_session
from app.services.text_processor_service import TextProcessorService

logger = logging.getLogger(__name__)


def _get_text_processor() -> TextProcessorService:
    return TextProcessorService()


@celery_app.task(bind=True, name="text_processing.extract_paragraphs_for_expression")
def extract_paragraphs_for_expression_task(
    self,
    expression_id: int,
    force_reextract: bool = False,
    min_length: int = 50,
    max_length: int = 5000,
    requested_by: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Extrait les paragraphes pour une expression donnée.
    """

    logger.info(
        "Starting paragraph extraction for expression %s (force=%s, requested_by=%s)",
        expression_id,
        force_reextract,
        requested_by,
    )

    self.update_state(
        state="PROGRESS",
        meta={
            "expression_id": expression_id,
            "requested_by": requested_by,
            "status": "initializing",
            "message": "Fetching expression and preparing extraction...",
        },
    )

    db = get_session()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        expression = db.query(Expression).filter(Expression.id == expression_id).first()
        if not expression:
            raise ValueError(f"Expression {expression_id} not found")

        text_processor = _get_text_processor()

        result = loop.run_until_complete(
            text_processor.extract_paragraphs_for_expression(
                db,
                expression,
                force_reextract=force_reextract,
                min_length=min_length,
                max_length=max_length,
            )
        )

        self.update_state(
            state="SUCCESS",
            meta={
                "expression_id": expression_id,
                "requested_by": requested_by,
                "status": "completed",
                "message": "Paragraph extraction completed",
                "result": result,
            },
        )
        logger.info("Paragraph extraction finished for expression %s", expression_id)
        return result

    except Exception as exc:  # pragma: no cover - state reporting
        logger.error("Paragraph extraction failed for expression %s: %s", expression_id, exc)
        self.update_state(
            state="FAILURE",
            meta={
                "expression_id": expression_id,
                "requested_by": requested_by,
                "status": "failed",
                "error": str(exc),
            },
        )
        raise
    finally:
        loop.close()
        db.close()


@celery_app.task(bind=True, name="text_processing.analyze_text_content")
def analyze_text_content_task(
    self,
    text: str,
    requested_by: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Analyse des métriques textuelles sans interaction base de données.
    """

    logger.info(
        "Starting text analysis task (length=%s, requested_by=%s)",
        len(text) if text else 0,
        requested_by,
    )

    self.update_state(
        state="PROGRESS",
        meta={
            "requested_by": requested_by,
            "status": "processing",
            "message": "Analyzing text content...",
        },
    )

    try:
        text_processor = _get_text_processor()
        analysis = text_processor.analyze_text_content(text)

        self.update_state(
            state="SUCCESS",
            meta={
                "requested_by": requested_by,
                "status": "completed",
                "message": "Text analysis completed",
                "result": analysis,
            },
        )
        logger.info("Text analysis completed (requested_by=%s)", requested_by)
        return analysis

    except Exception as exc:  # pragma: no cover - state reporting
        logger.error("Text analysis failed: %s", exc)
        self.update_state(
            state="FAILURE",
            meta={
                "requested_by": requested_by,
                "status": "failed",
                "error": str(exc),
            },
        )
        raise
