"""
Tâche Celery pour Domain Crawl V2 SYNC

⚠️ V2 = SYNC UNIQUEMENT (voir AGENTS.md)
- ✅ Celery workers sont SYNC par défaut
- ✅ Pas d'async/await
- ✅ Utilise Session sync pour DB

Tâche background pour crawler les domaines en batch.
"""

from typing import Optional
from datetime import datetime
import logging

from app.core.celery_app import celery_app
from app.db.session import get_sync_db_context
from app.db.models import Domain
from app.core.domain_crawler import DomainCrawler
from app.services.domain_crawl_service import DomainCrawlService

logger = logging.getLogger(__name__)


@celery_app.task(name="domain_crawl", bind=True)
def domain_crawl_task(
    self,
    job_id: int,
    land_id: Optional[int] = None,
    limit: int = 100,
    only_unfetched: bool = True
):
    """
    Tâche Celery pour crawler des domaines (SYNC).

    Args:
        self: Instance de la tâche Celery (bind=True)
        job_id: ID du job dans la table jobs
        land_id: ID du land (None = tous)
        limit: Nombre max de domaines à crawler
        only_unfetched: Si True, seulement les non-fetchés

    Returns:
        Dict avec résultats du crawl
    """
    logger.info(
        f"🕷️  Starting domain crawl task (job_id={job_id}, "
        f"land_id={land_id}, limit={limit})"
    )

    start_time = datetime.now()
    crawler = None

    # Résultats
    stats = {
        "total": 0,
        "processed": 0,
        "success": 0,
        "errors": 0,
        "by_source": {
            "trafilatura": 0,
            "archive_org": 0,
            "http_direct": 0,
            "error": 0
        },
        "start_time": start_time.isoformat(),
        "end_time": None
    }

    try:
        # Ouvrir session DB
        with get_sync_db_context() as db:
            service = DomainCrawlService(db)

            # Mettre le job à "running"
            service.update_job_status(job_id, "running")

            # Sélectionner les domaines à crawler
            domains = service.select_domains_to_crawl(
                land_id=land_id,
                limit=limit,
                only_unfetched=only_unfetched
            )

            stats["total"] = len(domains)

            if not domains:
                logger.warning("No domains to crawl")
                service.update_job_status(
                    job_id,
                    "completed",
                    result=stats
                )
                return stats

            # Initialiser le crawler
            crawler = DomainCrawler()

            # Crawler chaque domaine
            for i, domain in enumerate(domains, 1):
                try:
                    logger.info(f"Crawling {i}/{len(domains)}: {domain.name}")

                    # Fetch le domaine
                    fetch_result = crawler.fetch_domain(domain.name)

                    # Mettre à jour directement le domain object
                    domain.title = fetch_result.title
                    domain.description = fetch_result.description
                    domain.keywords = fetch_result.keywords
                    domain.language = fetch_result.language
                    domain.http_status = str(fetch_result.http_status) if fetch_result.http_status else None
                    domain.fetched_at = fetch_result.fetched_at
                    domain.last_crawled = fetch_result.fetched_at

                    service.db.commit()
                    logger.info(f"Saved fetch result for {domain.name}")

                    # Mettre à jour les stats
                    stats["processed"] += 1

                    if fetch_result.http_status == 200:
                        stats["success"] += 1
                    else:
                        stats["errors"] += 1

                    stats["by_source"][fetch_result.source_method] += 1

                    # Mettre à jour la progression du job
                    progress = int((i / len(domains)) * 100)
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i,
                            'total': len(domains),
                            'percent': progress,
                            'domain': domain.name,
                            'http_status': fetch_result.http_status,
                            'source': fetch_result.source_method
                        }
                    )

                    logger.info(
                        f"✅ {domain.name} - HTTP {fetch_result.http_status} "
                        f"via {fetch_result.source_method} ({i}/{len(domains)})"
                    )

                except Exception as e:
                    logger.error(f"❌ Error crawling {domain.name}: {e}", exc_info=True)
                    stats["errors"] += 1
                    stats["by_source"]["error"] += 1
                    continue

            # Fermer le crawler
            if crawler:
                crawler.close()

            # Mettre à jour le job à "completed"
            end_time = datetime.now()
            stats["end_time"] = end_time.isoformat()

            service.update_job_status(
                job_id,
                "completed",
                result=stats
            )

            logger.info(
                f"✅ Domain crawl completed: {stats['success']}/{stats['total']} successful "
                f"({stats['errors']} errors)"
            )

            return stats

    except Exception as e:
        logger.error(f"❌ Domain crawl task failed: {e}", exc_info=True)

        # Fermer le crawler en cas d'erreur
        if crawler:
            try:
                crawler.close()
            except:
                pass

        # Mettre le job à "failed"
        try:
            with get_sync_db_context() as db:
                service = DomainCrawlService(db)
                service.update_job_status(
                    job_id,
                    "failed",
                    error_message=str(e)
                )
        except Exception as db_error:
            logger.error(f"Failed to update job status: {db_error}")

        # Re-raise pour que Celery enregistre l'erreur
        raise


@celery_app.task(name="domain_recrawl", bind=True)
def domain_recrawl_task(
    self,
    domain_id: int
):
    """
    Tâche Celery pour re-crawler un seul domaine (SYNC).

    Args:
        self: Instance de la tâche Celery
        domain_id: ID du domaine à re-crawler

    Returns:
        Dict avec résultat du crawl
    """
    logger.info(f"🕷️  Re-crawling domain {domain_id}")

    crawler = None

    try:
        with get_sync_db_context() as db:
            service = DomainCrawlService(db)

            # Récupérer le domaine
            domain = db.query(Domain).filter(Domain.id == domain_id).first()

            if not domain:
                logger.error(f"Domain {domain_id} not found")
                return {"error": "Domain not found"}

            # Réinitialiser le statut
            service.reset_domain_fetch_status(domain_id)

            # Crawler le domaine
            crawler = DomainCrawler()
            fetch_result = crawler.fetch_domain(domain.name)

            # Sauvegarder en DB
            service.save_fetch_result(fetch_result)

            # Fermer le crawler
            crawler.close()

            result = {
                "domain_name": domain.name,
                "http_status": fetch_result.http_status,
                "source_method": fetch_result.source_method,
                "success": fetch_result.http_status == 200
            }

            logger.info(
                f"✅ Re-crawl completed for {domain.name}: "
                f"HTTP {fetch_result.http_status} via {fetch_result.source_method}"
            )

            return result

    except Exception as e:
        logger.error(f"❌ Re-crawl failed for domain {domain_id}: {e}", exc_info=True)

        if crawler:
            try:
                crawler.close()
            except:
                pass

        raise


@celery_app.task(name="domain_crawl_batch")
def domain_crawl_batch_task(
    domain_names: list,
    land_id: Optional[int] = None
):
    """
    Tâche Celery pour crawler une liste spécifique de domaines (SYNC).

    Utile pour crawler des domaines spécifiques sans passer par la sélection.

    Args:
        domain_names: Liste de noms de domaines (ex: ["example.com", "github.com"])
        land_id: ID du land pour associer les domaines (optionnel)

    Returns:
        Dict avec résultats du crawl
    """
    logger.info(f"🕷️  Batch crawling {len(domain_names)} domain(s)")

    crawler = None
    stats = {
        "total": len(domain_names),
        "processed": 0,
        "success": 0,
        "errors": 0
    }

    try:
        crawler = DomainCrawler()

        with get_sync_db_context() as db:
            service = DomainCrawlService(db)

            for domain_name in domain_names:
                try:
                    # Fetch le domaine
                    fetch_result = crawler.fetch_domain(domain_name)

                    # Sauvegarder en DB
                    service.save_fetch_result(fetch_result)

                    stats["processed"] += 1

                    if fetch_result.http_status == 200:
                        stats["success"] += 1
                    else:
                        stats["errors"] += 1

                    logger.info(
                        f"✅ {domain_name} - HTTP {fetch_result.http_status} "
                        f"({stats['processed']}/{stats['total']})"
                    )

                except Exception as e:
                    logger.error(f"❌ Error crawling {domain_name}: {e}")
                    stats["errors"] += 1
                    continue

        # Fermer le crawler
        if crawler:
            crawler.close()

        logger.info(
            f"✅ Batch crawl completed: {stats['success']}/{stats['total']} successful"
        )

        return stats

    except Exception as e:
        logger.error(f"❌ Batch crawl failed: {e}", exc_info=True)

        if crawler:
            try:
                crawler.close()
            except:
                pass

        raise
