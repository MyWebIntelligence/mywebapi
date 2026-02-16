#!/usr/bin/env python3
"""
Script de reprocessing de la validation LLM pour expressions existantes.

Usage:
    # Dry-run (simulation)
    python -m app.scripts.reprocess_llm_validation --dry-run

    # Reprocess toutes les expressions pertinentes sans validation LLM
    python -m app.scripts.reprocess_llm_validation

    # Reprocess un land spécifique
    python -m app.scripts.reprocess_llm_validation --land-id 15

    # Reprocess avec limite
    python -m app.scripts.reprocess_llm_validation --limit 100

    # Forcer la revalidation même si valid_llm existe
    python -m app.scripts.reprocess_llm_validation --force

    # Mode batch (commit toutes les N expressions)
    python -m app.scripts.reprocess_llm_validation --batch-size 50
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import models
from app.services.llm_validation_service import LLMValidationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_engine():
    """Create synchronous DB engine."""
    # Convert async URL to sync URL
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    return create_engine(sync_url, echo=False)


def reprocess_llm_validation(
    land_id: Optional[int] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    force: bool = False,
    batch_size: int = 100
) -> dict:
    """
    Reprocess LLM validation for existing expressions.

    Args:
        land_id: Filter by specific land (None = all lands)
        limit: Max number of expressions to process
        dry_run: If True, simulate without writing to DB
        force: If True, revalidate even if valid_llm exists
        batch_size: Commit after N expressions (0 = commit all at end)

    Returns:
        Statistics dict with processed, updated, errors counts
    """
    engine = get_db_engine()

    # Check if OpenRouter is enabled
    if not settings.OPENROUTER_ENABLED:
        logger.error("OpenRouter is not enabled. Set OPENROUTER_ENABLED=True in .env")
        return {
            "error": "OpenRouter not enabled",
            "total_candidates": 0,
            "processed": 0,
            "validated": 0,
            "rejected": 0,
            "errors": 0
        }

    if not settings.OPENROUTER_API_KEY:
        logger.error("OpenRouter API key not configured. Set OPENROUTER_API_KEY in .env")
        return {
            "error": "OpenRouter API key missing",
            "total_candidates": 0,
            "processed": 0,
            "validated": 0,
            "rejected": 0,
            "errors": 0
        }

    stats = {
        "total_candidates": 0,
        "processed": 0,
        "validated": 0,  # "oui"
        "rejected": 0,   # "non"
        "skipped": 0,
        "errors": 0,
        "start_time": datetime.now(),
        "api_calls": 0,
        "total_tokens": 0
    }

    with Session(engine) as session:
        # Build query for candidate expressions
        query = session.query(models.Expression).options(
            selectinload(models.Expression.land)
        )

        # Filter by land
        if land_id:
            query = query.filter(models.Expression.land_id == land_id)

        # Filter: only relevant expressions (relevance > 0)
        query = query.filter(models.Expression.relevance > 0)

        # Filter: only expressions without LLM validation (unless force)
        if not force:
            query = query.filter(models.Expression.valid_llm.is_(None))

        # Apply limit
        if limit:
            query = query.limit(limit)

        # Get candidates
        expressions = query.all()
        stats["total_candidates"] = len(expressions)

        logger.info("=" * 80)
        logger.info("LLM VALIDATION REPROCESSING")
        logger.info("=" * 80)
        logger.info("Mode: %s", "DRY-RUN" if dry_run else "ACTIVE")
        logger.info("Land filter: %s", land_id if land_id else "ALL")
        logger.info("Force revalidation: %s", force)
        logger.info("Batch size: %s", batch_size)
        logger.info("Total candidates: %s", stats["total_candidates"])
        logger.info("=" * 80)

        if stats["total_candidates"] == 0:
            logger.info("No expressions to process")
            return stats

        # Create LLM service (None for session as we use sync method)
        llm_service = LLMValidationService(None)

        # Process expressions
        for i, expr in enumerate(expressions, 1):
            try:
                # Get land
                land = expr.land
                if not land:
                    logger.warning(f"Expression {expr.id}: Land not found, skipping")
                    stats["skipped"] += 1
                    continue

                # Skip if no readable content
                if not expr.readable or len(expr.readable.strip()) < 50:
                    logger.warning(f"Expression {expr.id}: No readable content, skipping")
                    stats["skipped"] += 1
                    continue

                logger.info(
                    f"[{i}/{stats['total_candidates']}] Processing expression {expr.id} "
                    f"(land={land.id}, relevance={expr.relevance:.2f})"
                )

                # Validate with LLM (V2 SYNC-ONLY: no async)
                validation_result = llm_service.validate_expression_relevance(
                    expr,
                    land
                )

                stats["api_calls"] += 1
                if validation_result.prompt_tokens:
                    stats["total_tokens"] += validation_result.prompt_tokens
                if validation_result.completion_tokens:
                    stats["total_tokens"] += validation_result.completion_tokens

                # Update stats
                if validation_result.is_relevant:
                    stats["validated"] += 1
                    result_label = "✅ VALIDATED"
                else:
                    stats["rejected"] += 1
                    result_label = "❌ REJECTED"

                logger.info(
                    f"  {result_label} by {validation_result.model_used} "
                    f"(tokens: {validation_result.prompt_tokens or 0})"
                )

                # Update expression (unless dry-run)
                if not dry_run:
                    expr.valid_llm = 'oui' if validation_result.is_relevant else 'non'
                    expr.valid_model = validation_result.model_used

                    # If not relevant, set relevance to 0
                    if not validation_result.is_relevant:
                        expr.relevance = 0

                    # Batch commit
                    if batch_size > 0 and (i % batch_size == 0):
                        session.commit()
                        logger.info(f"  💾 Committed batch at {i} expressions")

                stats["processed"] += 1

            except Exception as e:
                logger.error(f"Expression {expr.id}: Validation failed - {e}")
                stats["errors"] += 1
                if not dry_run:
                    session.rollback()
                continue

        # Final commit
        if not dry_run and batch_size != 0:
            session.commit()
            logger.info("💾 Final commit completed")

        # Calculate duration
        stats["end_time"] = datetime.now()
        stats["duration_seconds"] = (stats["end_time"] - stats["start_time"]).total_seconds()

        # Print summary
        print("\n" + "=" * 80)
        print("REPROCESSING SUMMARY")
        print("=" * 80)
        print(f"Total candidates:     {stats['total_candidates']}")
        print(f"Processed:            {stats['processed']}")
        print(f"  - Validated (oui):  {stats['validated']} ({stats['validated']/stats['processed']*100:.1f}%)" if stats['processed'] > 0 else "  - Validated (oui):  0")
        print(f"  - Rejected (non):   {stats['rejected']} ({stats['rejected']/stats['processed']*100:.1f}%)" if stats['processed'] > 0 else "  - Rejected (non):   0")
        print(f"Skipped:              {stats['skipped']}")
        print(f"Errors:               {stats['errors']}")
        print(f"Duration:             {stats['duration_seconds']:.1f}s")
        print(f"API calls:            {stats['api_calls']}")
        print(f"Total tokens:         {stats['total_tokens']}")
        if stats['api_calls'] > 0:
            estimated_cost = stats['total_tokens'] * 0.000015  # ~$0.015 per 1K tokens for Claude 3.5 Sonnet
            print(f"Estimated cost:       ${estimated_cost:.4f}")
        print("=" * 80)

        return stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Reprocess LLM validation for expressions"
    )
    parser.add_argument(
        "--land-id",
        type=int,
        help="Filter by specific land ID"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of expressions to process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without writing to database"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Revalidate even if valid_llm exists"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Commit after N expressions (default: 100, 0 = commit all at end)"
    )

    args = parser.parse_args()

    try:
        stats = reprocess_llm_validation(
            land_id=args.land_id,
            limit=args.limit,
            dry_run=args.dry_run,
            force=args.force,
            batch_size=args.batch_size
        )

        if stats.get("error"):
            sys.exit(1)

        # Exit with error if there were processing errors
        if stats["errors"] > 0:
            logger.warning(f"Completed with {stats['errors']} errors")
            sys.exit(1)

        logger.info("✅ Reprocessing completed successfully")
        sys.exit(0)

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
