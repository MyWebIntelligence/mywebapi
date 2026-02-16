"""
Service Domain Crawl V2 SYNC

⚠️ V2 = SYNC UNIQUEMENT (voir AGENTS.md)
- ✅ Utilise Session (pas AsyncSession)
- ✅ Pas d'async/await
- ✅ Requêtes DB synchrones

Service layer pour:
- Sélection des domaines à crawler
- Sauvegarde des résultats en DB
- Calcul des statistiques
"""

from typing import List, Optional
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Integer

from app.db.models import Domain, Land, CrawlJob
from app.schemas.domain_crawl import DomainFetchResult, DomainStatsResponse

logger = logging.getLogger(__name__)


class DomainCrawlService:
    """
    Service pour gestion du crawl de domaines (V2 SYNC).

    Gère:
    - Sélection des domaines à crawler
    - Sauvegarde des résultats en DB
    - Statistiques sur les domaines
    """

    def __init__(self, db: Session):
        """
        Initialise le service.

        Args:
            db: Session SQLAlchemy SYNC (pas AsyncSession)
        """
        self.db = db

    def select_domains_to_crawl(
        self,
        land_id: Optional[int] = None,
        limit: int = 100,
        only_unfetched: bool = True
    ) -> List[Domain]:
        """
        Sélectionne les domaines à crawler (SYNC).

        Args:
            land_id: ID du land (None = tous les lands)
            limit: Nombre max de domaines
            only_unfetched: Si True, seulement les domaines non fetchés

        Returns:
            Liste de domaines à crawler
        """
        query = self.db.query(Domain)

        # Filtrer par land si spécifié
        if land_id is not None:
            query = query.filter(Domain.land_id == land_id)

        # Filtrer par statut fetch
        if only_unfetched:
            query = query.filter(Domain.fetched_at.is_(None))

        # Limiter le nombre
        query = query.limit(limit)

        domains = query.all()

        logger.info(
            f"Selected {len(domains)} domain(s) to crawl "
            f"(land_id={land_id}, limit={limit}, only_unfetched={only_unfetched})"
        )

        return domains

    def save_fetch_result(self, result: DomainFetchResult) -> Domain:
        """
        Sauvegarde le résultat d'un fetch en DB (SYNC).

        Met à jour le domaine existant ou en crée un nouveau.

        Args:
            result: Résultat du fetch

        Returns:
            Domain mis à jour
        """
        # Chercher le domaine existant
        domain = self.db.query(Domain).filter(
            Domain.name == result.domain_name
        ).first()

        if not domain:
            # Créer un nouveau domaine si inexistant
            # (cas rare - normalement les domaines existent déjà)
            logger.warning(f"Domain {result.domain_name} not found in DB, creating new entry")
            domain = Domain(
                name=result.domain_name,
                created_at=datetime.now()
            )
            self.db.add(domain)

        # Mettre à jour avec les résultats (uniquement les champs existants dans la table)
        domain.title = result.title
        domain.description = result.description
        domain.keywords = result.keywords
        domain.language = result.language
        domain.http_status = str(result.http_status) if result.http_status else None  # Convert to string
        domain.fetched_at = result.fetched_at
        domain.last_crawled = result.fetched_at  # Map last_crawled_at to last_crawled

        # Les champs suivants n'existent pas dans la table actuelle
        # Ils nécessiteront une migration future
        # domain.content = result.content
        # domain.source_method = result.source_method
        # domain.error_code = result.error_code
        # domain.error_message = result.error_message
        # domain.fetch_duration_ms = result.fetch_duration_ms
        # domain.retry_count = result.retry_count

        self.db.commit()
        self.db.refresh(domain)

        logger.info(
            f"Saved fetch result for {result.domain_name} "
            f"(HTTP {result.http_status}, source={result.source_method})"
        )

        return domain

    def get_domain_stats(self, land_id: Optional[int] = None) -> DomainStatsResponse:
        """
        Calcule les statistiques sur les domaines (SYNC).

        Args:
            land_id: ID du land (None = tous les lands)

        Returns:
            Statistiques sur les domaines
        """
        query = self.db.query(Domain)

        if land_id is not None:
            query = query.filter(Domain.land_id == land_id)

        total_domains = query.count()
        fetched_domains = query.filter(Domain.fetched_at.isnot(None)).count()
        unfetched_domains = total_domains - fetched_domains

        # Calculer le statut HTTP moyen (seulement pour les domaines fetchés)
        # Cast http_status to Integer because it's stored as String
        avg_http_status = self.db.query(
            func.avg(cast(Domain.http_status, Integer))
        ).filter(
            Domain.http_status.isnot(None)
        )

        if land_id is not None:
            avg_http_status = avg_http_status.filter(Domain.land_id == land_id)

        avg_http_status = avg_http_status.scalar() or 0.0

        stats = DomainStatsResponse(
            total_domains=total_domains,
            fetched_domains=fetched_domains,
            unfetched_domains=unfetched_domains,
            avg_http_status=round(avg_http_status, 2)
        )

        logger.info(
            f"Domain stats (land_id={land_id}): "
            f"total={stats.total_domains}, fetched={stats.fetched_domains}, "
            f"avg_http={stats.avg_http_status}"
        )

        return stats

    def create_crawl_job(
        self,
        land_id: Optional[int],
        domain_count: int,
        user_id: int
    ) -> CrawlJob:
        """
        Crée un job de crawl dans la DB (SYNC).

        Args:
            land_id: ID du land (None = tous)
            domain_count: Nombre de domaines à crawler
            user_id: ID de l'utilisateur qui lance le job

        Returns:
            CrawlJob créé
        """
        job = CrawlJob(
            job_type="domain_crawl",
            status="pending",
            land_id=land_id or 1,  # CrawlJob requires land_id (not nullable)
            parameters={
                "user_id": user_id,
                "domain_count": domain_count,
                "only_unfetched": True,
                "original_land_id": land_id  # Store original (might be None)
            },
            result_data={}
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        logger.info(
            f"Created domain crawl job {job.id} "
            f"(land_id={land_id}, domains={domain_count}, user={user_id})"
        )

        return job

    def update_job_status(
        self,
        job_id: int,
        status: str,
        result: Optional[dict] = None,
        error_message: Optional[str] = None
    ):
        """
        Met à jour le statut d'un job (SYNC).

        Args:
            job_id: ID du job
            status: Nouveau statut (pending, running, completed, failed)
            result: Résultat du job (optionnel)
            error_message: Message d'erreur si échec
        """
        job = self.db.query(CrawlJob).filter(CrawlJob.id == job_id).first()

        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job.status = status

        if result:
            job.result_data = result

        if error_message:
            job.error_message = error_message

        if status == "completed":
            job.completed_at = datetime.now()
        elif status == "running" and not job.started_at:
            job.started_at = datetime.now()

        self.db.commit()
        self.db.refresh(job)

        logger.info(f"Updated job {job_id} status to '{status}'")

    def get_land_by_id(self, land_id: int) -> Optional[Land]:
        """
        Récupère un land par son ID (SYNC).

        Args:
            land_id: ID du land

        Returns:
            Land ou None si non trouvé
        """
        return self.db.query(Land).filter(Land.id == land_id).first()

    def count_domains_by_source(self, land_id: Optional[int] = None) -> dict:
        """
        Compte les domaines par source (SYNC).

        Args:
            land_id: ID du land (None = tous)

        Returns:
            Dict avec comptage par source
        """
        query = self.db.query(
            Domain.source_method,
            func.count(Domain.id).label('count')
        ).filter(
            Domain.source_method.isnot(None)
        ).group_by(Domain.source_method)

        if land_id is not None:
            query = query.filter(Domain.land_id == land_id)

        results = query.all()

        counts = {
            "trafilatura": 0,
            "archive_org": 0,
            "http_direct": 0,
            "error": 0
        }

        for source_method, count in results:
            counts[source_method] = count

        logger.info(f"Domain counts by source (land_id={land_id}): {counts}")

        return counts

    def get_recent_crawled_domains(
        self,
        land_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Domain]:
        """
        Récupère les domaines récemment crawlés (SYNC).

        Args:
            land_id: ID du land (None = tous)
            limit: Nombre max de domaines

        Returns:
            Liste de domaines récemment crawlés
        """
        query = self.db.query(Domain).filter(
            Domain.fetched_at.isnot(None)
        ).order_by(Domain.fetched_at.desc())

        if land_id is not None:
            query = query.filter(Domain.land_id == land_id)

        domains = query.limit(limit).all()

        logger.info(
            f"Retrieved {len(domains)} recently crawled domain(s) "
            f"(land_id={land_id}, limit={limit})"
        )

        return domains

    def reset_domain_fetch_status(
        self,
        domain_id: int
    ):
        """
        Réinitialise le statut de fetch d'un domaine (pour re-crawl).

        Args:
            domain_id: ID du domaine
        """
        domain = self.db.query(Domain).filter(Domain.id == domain_id).first()

        if not domain:
            logger.error(f"Domain {domain_id} not found")
            return

        domain.fetched_at = None
        domain.http_status = None
        domain.title = None
        domain.description = None
        domain.keywords = None
        domain.language = None
        domain.content = None
        domain.source_method = None
        domain.error_code = None
        domain.error_message = None

        self.db.commit()

        logger.info(f"Reset fetch status for domain {domain_id} ({domain.name})")
