"""
Domain Crawl API Endpoints V2 SYNC

⚠️ V2 = SYNC UNIQUEMENT (voir AGENTS.md)
- ✅ Endpoints SYNC (def, pas async def)
- ✅ Utilise Session sync (pas AsyncSession)
- ✅ Utilise get_sync_db et get_current_active_user_sync

Endpoints:
- POST /api/v2/domains/crawl - Lance un crawl de domaines
- GET /api/v2/domains/stats - Statistiques sur les domaines
- GET /api/v2/domains - Liste des domaines crawlés
- POST /api/v2/domains/{domain_id}/recrawl - Re-crawl un domaine spécifique
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from app.db.session import get_sync_db
from app.api.dependencies import get_current_active_user_sync
from app.schemas.user import User
from app.schemas.domain_crawl import (
    DomainCrawlRequest,
    DomainCrawlResponse,
    DomainStatsResponse
)
from app.services.domain_crawl_service import DomainCrawlService
from app.tasks.domain_crawl_task import domain_crawl_task, domain_recrawl_task
from app.db.models import Domain

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/crawl", response_model=DomainCrawlResponse)
def crawl_domains(
    request: DomainCrawlRequest,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync)
):
    """
    Lance un crawl de domaines en background (SYNC endpoint).

    Le crawl est exécuté par une tâche Celery en arrière-plan.

    Args:
        request: Paramètres du crawl (land_id, limit, only_unfetched)
        db: Session DB (SYNC)
        current_user: Utilisateur authentifié

    Returns:
        DomainCrawlResponse avec job_id, domain_count, message

    Raises:
        HTTPException 404: Land non trouvé
        HTTPException 400: Aucun domaine à crawler
    """
    logger.info(
        f"User {current_user.id} requesting domain crawl "
        f"(land_id={request.land_id}, limit={request.limit})"
    )

    service = DomainCrawlService(db)

    # Vérifier que le land existe (si spécifié)
    if request.land_id is not None:
        land = service.get_land_by_id(request.land_id)
        if not land:
            raise HTTPException(
                status_code=404,
                detail=f"Land {request.land_id} not found"
            )

    # Sélectionner les domaines à crawler
    domains = service.select_domains_to_crawl(
        land_id=request.land_id,
        limit=request.limit,
        only_unfetched=request.only_unfetched
    )

    if not domains:
        raise HTTPException(
            status_code=400,
            detail="No domains to crawl (all already fetched or land has no domains)"
        )

    # Créer le job
    job = service.create_crawl_job(
        land_id=request.land_id,
        domain_count=len(domains),
        user_id=current_user.id
    )

    # Lancer la tâche Celery en arrière-plan
    domain_crawl_task.apply_async(
        args=[job.id, request.land_id, request.limit, request.only_unfetched],
        task_id=f"domain_crawl_{job.id}"
    )

    logger.info(
        f"Domain crawl job {job.id} created and started "
        f"({len(domains)} domains to crawl)"
    )

    return DomainCrawlResponse(
        job_id=job.id,
        domain_count=len(domains),
        message=f"Domain crawl started for {len(domains)} domain(s)"
    )


@router.get("/stats", response_model=DomainStatsResponse)
def get_domain_stats(
    land_id: Optional[int] = Query(None, description="Filter by land ID"),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync)
):
    """
    Récupère les statistiques sur les domaines (SYNC endpoint).

    Args:
        land_id: ID du land (None = tous les lands)
        db: Session DB (SYNC)
        current_user: Utilisateur authentifié

    Returns:
        DomainStatsResponse avec total, fetched, unfetched, avg_http_status
    """
    logger.info(f"User {current_user.id} requesting domain stats (land_id={land_id})")

    service = DomainCrawlService(db)

    # Vérifier que le land existe (si spécifié)
    if land_id is not None:
        land = service.get_land_by_id(land_id)
        if not land:
            raise HTTPException(
                status_code=404,
                detail=f"Land {land_id} not found"
            )

    stats = service.get_domain_stats(land_id=land_id)

    logger.info(
        f"Domain stats (land_id={land_id}): "
        f"total={stats.total_domains}, fetched={stats.fetched_domains}"
    )

    return stats


@router.get("/", response_model=List[dict])
def list_crawled_domains(
    land_id: Optional[int] = Query(None, description="Filter by land ID"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync)
):
    """
    Liste les domaines récemment crawlés (SYNC endpoint).

    Args:
        land_id: ID du land (None = tous)
        limit: Nombre max de domaines
        db: Session DB (SYNC)
        current_user: Utilisateur authentifié

    Returns:
        Liste de domaines avec métadonnées
    """
    logger.info(
        f"User {current_user.id} listing crawled domains "
        f"(land_id={land_id}, limit={limit})"
    )

    service = DomainCrawlService(db)

    domains = service.get_recent_crawled_domains(land_id=land_id, limit=limit)

    # Formater la réponse
    result = []
    for domain in domains:
        result.append({
            "id": domain.id,
            "name": domain.name,
            "land_id": domain.land_id,
            "title": domain.title,
            "description": domain.description,
            "keywords": domain.keywords,
            "language": domain.language,
            "http_status": domain.http_status,
            "source_method": domain.source_method,
            "fetched_at": domain.fetched_at.isoformat() if domain.fetched_at else None,
            "last_crawled_at": domain.last_crawled_at.isoformat() if domain.last_crawled_at else None,
            "error_code": domain.error_code,
            "error_message": domain.error_message,
            "fetch_duration_ms": domain.fetch_duration_ms,
            "retry_count": domain.retry_count
        })

    logger.info(f"Retrieved {len(result)} crawled domain(s)")

    return result


@router.post("/{domain_id}/recrawl")
def recrawl_domain(
    domain_id: int,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync)
):
    """
    Re-crawl un domaine spécifique (SYNC endpoint).

    Lance une tâche Celery pour re-crawler le domaine.

    Args:
        domain_id: ID du domaine
        db: Session DB (SYNC)
        current_user: Utilisateur authentifié

    Returns:
        Message de confirmation

    Raises:
        HTTPException 404: Domaine non trouvé
    """
    logger.info(f"User {current_user.id} requesting recrawl for domain {domain_id}")

    service = DomainCrawlService(db)

    # Vérifier que le domaine existe
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(
            status_code=404,
            detail=f"Domain {domain_id} not found"
        )

    # Lancer la tâche Celery
    task = domain_recrawl_task.apply_async(
        args=[domain_id],
        task_id=f"domain_recrawl_{domain_id}"
    )

    logger.info(f"Recrawl task started for domain {domain_id} ({domain.name})")

    return {
        "message": f"Recrawl started for domain {domain.name}",
        "domain_id": domain_id,
        "domain_name": domain.name,
        "task_id": task.id
    }


@router.get("/sources", response_model=dict)
def get_domain_sources_stats(
    land_id: Optional[int] = Query(None, description="Filter by land ID"),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync)
):
    """
    Récupère les statistiques par source de crawl (SYNC endpoint).

    Args:
        land_id: ID du land (None = tous)
        db: Session DB (SYNC)
        current_user: Utilisateur authentifié

    Returns:
        Dict avec comptage par source (trafilatura, archive_org, http_direct, error)
    """
    logger.info(
        f"User {current_user.id} requesting source stats (land_id={land_id})"
    )

    service = DomainCrawlService(db)

    # Vérifier que le land existe (si spécifié)
    if land_id is not None:
        land = service.get_land_by_id(land_id)
        if not land:
            raise HTTPException(
                status_code=404,
                detail=f"Land {land_id} not found"
            )

    counts = service.count_domains_by_source(land_id=land_id)

    logger.info(f"Source stats (land_id={land_id}): {counts}")

    return {
        "land_id": land_id,
        "by_source": counts,
        "total": sum(counts.values())
    }
