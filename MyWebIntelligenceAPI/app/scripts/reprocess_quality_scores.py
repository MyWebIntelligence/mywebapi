#!/usr/bin/env python3
"""
Script de reprocessing des quality_scores pour expressions existantes.

Usage:
    # Dry-run (simulation)
    python -m app.scripts.reprocess_quality_scores --dry-run

    # Reprocess toutes les expressions sans quality_score
    python -m app.scripts.reprocess_quality_scores

    # Reprocess un land spécifique
    python -m app.scripts.reprocess_quality_scores --land-id 15

    # Reprocess avec limite
    python -m app.scripts.reprocess_quality_scores --limit 100

    # Forcer le recalcul même si quality_score existe
    python -m app.scripts.reprocess_quality_scores --force

    # Mode batch (commit toutes les N expressions)
    python -m app.scripts.reprocess_quality_scores --batch-size 50
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import models
from app.services.quality_scorer import QualityScorer

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


def reprocess_quality_scores(
    land_id: Optional[int] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    force: bool = False,
    batch_size: int = 100
) -> dict:
    """
    Reprocess quality scores for existing expressions.

    Args:
        land_id: Filter by specific land (None = all lands)
        limit: Max number of expressions to process
        dry_run: If True, simulate without writing to DB
        force: If True, recalculate even if quality_score exists
        batch_size: Commit after N expressions (0 = commit all at end)

    Returns:
        Statistics dict with processed, updated, errors counts
    """
    engine = get_db_engine()
    scorer = QualityScorer()

    stats = {
        "total_candidates": 0,
        "processed": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "start_time": datetime.now(),
        "score_distribution": {
            "Excellent": 0,
            "Bon": 0,
            "Moyen": 0,
            "Faible": 0,
            "Très faible": 0
        }
    }

    with Session(engine) as session:
        # Build query
        query = session.query(models.Expression).options(
            selectinload(models.Expression.land)
        )

        # Filter by land
        if land_id:
            query = query.filter(models.Expression.land_id == land_id)
            logger.info(f"Filtering by land_id={land_id}")

        # Filter by quality_score status
        if not force:
            query = query.filter(models.Expression.quality_score.is_(None))
            logger.info("Processing only expressions with NULL quality_score")
        else:
            logger.info("FORCE mode: reprocessing ALL expressions")

        # Order by ID for deterministic processing (BEFORE limit)
        query = query.order_by(models.Expression.id)

        # Apply limit (AFTER order_by)
        if limit:
            query = query.limit(limit)
            logger.info(f"Limited to {limit} expressions")

        # Count candidates
        stats["total_candidates"] = query.count()
        logger.info(f"Found {stats['total_candidates']} expressions to process")

        if stats["total_candidates"] == 0:
            logger.info("No expressions to process. Exiting.")
            return stats

        if dry_run:
            logger.info("DRY-RUN mode: Simulating without DB writes")

        # Process expressions
        batch_counter = 0
        for expr in query:
            try:
                # Check if expression has minimum required data
                if not expr.http_status:
                    logger.debug(f"Expression {expr.id}: Skipping (no http_status)")
                    stats["skipped"] += 1
                    continue

                # Get land for computation
                if not expr.land:
                    logger.warning(f"Expression {expr.id}: Land not found")
                    stats["errors"] += 1
                    continue

                # Compute quality score
                quality_result = scorer.compute_quality_score(
                    expression=expr,
                    land=expr.land
                )

                old_score = expr.quality_score
                new_score = quality_result["score"]
                category = quality_result["category"]

                # Update statistics
                stats["processed"] += 1
                stats["score_distribution"][category] += 1

                # Log result
                if old_score is not None:
                    logger.debug(
                        f"Expression {expr.id}: {old_score:.3f} -> {new_score:.3f} ({category})"
                    )
                else:
                    logger.debug(
                        f"Expression {expr.id}: {new_score:.3f} ({category})"
                    )

                # Update expression (unless dry-run)
                if not dry_run:
                    expr.quality_score = new_score
                    session.add(expr)
                    stats["updated"] += 1

                    batch_counter += 1

                    # Batch commit
                    if batch_size > 0 and batch_counter >= batch_size:
                        session.commit()
                        logger.info(
                            f"Progress: {stats['processed']}/{stats['total_candidates']} "
                            f"({100.0 * stats['processed'] / stats['total_candidates']:.1f}%)"
                        )
                        batch_counter = 0

            except Exception as e:
                logger.error(f"Expression {expr.id}: Error computing quality - {e}")
                stats["errors"] += 1
                continue

        # Final commit
        if not dry_run and batch_counter > 0:
            session.commit()
            logger.info("Final batch committed")

    # Summary
    stats["end_time"] = datetime.now()
    stats["duration_seconds"] = (stats["end_time"] - stats["start_time"]).total_seconds()

    return stats


def print_summary(stats: dict):
    """Print summary statistics."""
    print("\n" + "="*60)
    print("REPROCESSING SUMMARY")
    print("="*60)
    print(f"Total candidates:     {stats['total_candidates']}")
    print(f"Processed:            {stats['processed']}")
    print(f"Updated:              {stats['updated']}")
    print(f"Skipped:              {stats['skipped']}")
    print(f"Errors:               {stats['errors']}")
    print(f"Duration:             {stats['duration_seconds']:.1f}s")

    if stats['processed'] > 0:
        print("\nQuality Distribution:")
        for category, count in stats['score_distribution'].items():
            pct = 100.0 * count / stats['processed']
            print(f"  {category:15s}: {count:4d} ({pct:5.1f}%)")

    print("="*60 + "\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Reprocess quality_scores for existing expressions"
    )
    parser.add_argument(
        "--land-id",
        type=int,
        help="Process only expressions from this land"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Max number of expressions to process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without writing to DB"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recalculate even if quality_score already exists"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Commit after N expressions (default: 100, 0 = commit all at end)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Display configuration
    logger.info("Quality Score Reprocessing Script")
    logger.info(f"Configuration:")
    logger.info(f"  Land ID:     {args.land_id or 'ALL'}")
    logger.info(f"  Limit:       {args.limit or 'NONE'}")
    logger.info(f"  Dry-run:     {args.dry_run}")
    logger.info(f"  Force:       {args.force}")
    logger.info(f"  Batch size:  {args.batch_size}")
    logger.info("")

    # Confirm if not dry-run
    if not args.dry_run:
        response = input("This will modify the database. Continue? [y/N] ")
        if response.lower() != 'y':
            logger.info("Aborted by user")
            sys.exit(0)

    # Run reprocessing
    try:
        stats = reprocess_quality_scores(
            land_id=args.land_id,
            limit=args.limit,
            dry_run=args.dry_run,
            force=args.force,
            batch_size=args.batch_size
        )

        # Print summary
        print_summary(stats)

        # Exit code
        if stats["errors"] > 0:
            logger.warning(f"Completed with {stats['errors']} errors")
            sys.exit(1)
        else:
            logger.info("Completed successfully")
            sys.exit(0)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
