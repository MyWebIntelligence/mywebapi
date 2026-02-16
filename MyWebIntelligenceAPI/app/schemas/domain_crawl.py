"""
Schémas Pydantic pour Domain Crawl (V2 SYNC)

⚠️ V2 = SYNC UNIQUEMENT (voir AGENTS.md)
"""

from typing import Optional, Literal
from pydantic import BaseModel
from datetime import datetime


class DomainFetchResult(BaseModel):
    """Résultat d'un fetch de domaine avec toutes les métadonnées"""

    domain_name: str
    http_status: int  # 200, 404, 500, 0 (erreur non-HTTP)
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    language: Optional[str] = None
    content: Optional[str] = None  # HTML brut

    # Métadonnées de fetch
    source_method: Literal["trafilatura", "archive_org", "http_direct", "error"]
    fetched_at: datetime
    error_code: Optional[str] = None  # ERR_TRAFI, ERR_ARCHIVE_404, etc.
    error_message: Optional[str] = None

    # Stats
    fetch_duration_ms: int
    retry_count: int = 0

    class Config:
        from_attributes = True


class DomainCrawlRequest(BaseModel):
    """Requête de crawl de domaines"""

    land_id: Optional[int] = None  # Si None, crawl tous les domaines
    limit: int = 100
    only_unfetched: bool = True


class DomainCrawlResponse(BaseModel):
    """Réponse de lancement de crawl"""

    job_id: int
    domain_count: int
    message: str


class DomainStatsResponse(BaseModel):
    """Statistiques sur les domaines"""

    total_domains: int
    fetched_domains: int
    unfetched_domains: int
    avg_http_status: float
