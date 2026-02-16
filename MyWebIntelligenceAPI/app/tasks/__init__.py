"""
Module des taches Celery (V2 - Sync only)
"""

from .crawling_task import crawl_land_task
from .consolidation_task import consolidate_land_task
from .domain_crawl_task import domain_crawl_task, domain_recrawl_task, domain_crawl_batch_task
from .export_tasks import create_export_task
from .readable_working_task import readable_working_task
from .media_analysis_task import analyze_land_media_task
from .heuristic_update_task import heuristic_update_task
from .seorank_task import seorank_task

__all__ = [
    "crawl_land_task",
    "consolidate_land_task",
    "domain_crawl_task",
    "domain_recrawl_task",
    "domain_crawl_batch_task",
    "create_export_task",
    "readable_working_task",
    "analyze_land_media_task",
    "heuristic_update_task",
    "seorank_task",
]
