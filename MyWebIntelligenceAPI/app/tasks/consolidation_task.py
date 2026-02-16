"""
Tache Celery pour la consolidation d'un land (V2 sync).
Reproduit la logique legacy : recalcul relevance, rebuild links/media, ajout docs manquants.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.core.celery_app import celery_app
from app.core import text_processing
from app.core.content_extractor import extract_md_links
from app.db import models
from app.db.models import CrawlStatus
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _get_land_dictionary(db, land: models.Land) -> Dict[str, float]:
    """Construit le dictionnaire de mots-cles du land pour le calcul de relevance."""
    dictionary: Dict[str, float] = {}
    words = land.words or []
    for word in words:
        if isinstance(word, str) and word.strip():
            dictionary[word.strip().lower()] = 1.0
    return dictionary


def _compute_relevance_sync(dictionary: Dict[str, float], expr, lang: str = "fr") -> float:
    """Wrapper sync pour expression_relevance (async)."""
    try:
        return asyncio.run(text_processing.expression_relevance(dictionary, expr, lang))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(text_processing.expression_relevance(dictionary, expr, lang))
        finally:
            loop.close()


def _is_crawlable(url: Optional[str]) -> bool:
    """Verifie si une URL est crawlable."""
    if not url:
        return False
    url = url.strip()
    if url.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
        return False
    if not url.startswith(("http://", "https://")):
        return False
    return True


@celery_app.task(bind=True)
def consolidate_land_task(self, land_id: int, limit: int = 0, depth: Optional[int] = None) -> Dict[str, Any]:
    """
    Consolide un land en recalculant relevance, liens, medias.

    Logique legacy portee :
    1. Selectionne les expressions deja crawlees
    2. Recalcule la relevance avec le dictionnaire du land
    3. Supprime et recree les liens sortants depuis le contenu readable
    4. Ajoute les expressions manquantes decouvertes dans les liens
    5. Recree les medias depuis le contenu readable
    """
    db = SessionLocal()
    start_time = datetime.now(timezone.utc)

    logger.info("=" * 60)
    logger.info("[CONSOLIDATE] START - land=%s limit=%s depth=%s", land_id, limit, depth)
    logger.info("=" * 60)

    stats = {
        "processed": 0,
        "errors": 0,
        "links_rebuilt": 0,
        "media_rebuilt": 0,
        "expressions_added": 0,
        "relevance_updated": 0,
    }

    try:
        land = db.query(models.Land).filter(models.Land.id == land_id).first()
        if not land:
            logger.error("[CONSOLIDATE] Land %s not found", land_id)
            db.close()
            return {"status": "failed", "error": f"Land {land_id} not found"}

        dictionary = _get_land_dictionary(db, land)

        # Selectionner les expressions deja crawlees
        query = (
            db.query(models.Expression)
            .filter(
                models.Expression.land_id == land_id,
                (models.Expression.approved_at.isnot(None))
                | (models.Expression.readable_at.isnot(None)),
            )
        )
        if depth is not None:
            query = query.filter(models.Expression.depth == depth)
        if limit > 0:
            query = query.limit(limit)

        expressions = query.all()

        if not expressions:
            logger.info("[CONSOLIDATE] Aucune expression a consolider")
            result = {**stats, "status": "completed", "message": "Aucune expression a consolider"}
            db.close()
            return result

        total = len(expressions)
        logger.info("[CONSOLIDATE] %d expressions a traiter", total)

        for i, expr in enumerate(expressions):
            try:
                # 1. Supprimer anciens liens sortants
                db.query(models.ExpressionLink).filter(
                    models.ExpressionLink.source_id == expr.id
                ).delete(synchronize_session=False)

                # 2. Supprimer anciens medias
                db.query(models.Media).filter(
                    models.Media.expression_id == expr.id
                ).delete(synchronize_session=False)
                db.flush()

                # 3. Recalculer la relevance
                class TempExpr:
                    def __init__(self, title, readable, eid):
                        self.title = title
                        self.readable = readable
                        self.id = eid

                temp = TempExpr(expr.title, expr.readable, expr.id)
                lang = expr.lang or "fr"
                new_relevance = _compute_relevance_sync(dictionary, temp, lang)
                if new_relevance != expr.relevance:
                    expr.relevance = new_relevance
                    stats["relevance_updated"] += 1

                # 4. Extraire liens du contenu readable
                links: List[str] = []
                if expr.readable:
                    links = extract_md_links(expr.readable)
                    # Aussi extraire les liens HTML si le contenu en contient
                    html_links = re.findall(r'href=["\']([^"\']+)["\']', expr.readable)
                    for lnk in html_links:
                        if lnk not in links:
                            links.append(lnk)

                # 5. Ajouter expressions manquantes et creer les liens
                for link_url in set(links):
                    if not _is_crawlable(link_url):
                        continue

                    # Chercher l'expression cible existante
                    target = (
                        db.query(models.Expression)
                        .filter(
                            models.Expression.land_id == land_id,
                            models.Expression.url == link_url,
                        )
                        .first()
                    )

                    if not target:
                        # Ajouter l'expression manquante
                        import hashlib
                        url_hash = hashlib.md5(link_url.encode()).hexdigest()
                        # Trouver ou creer le domaine
                        from urllib.parse import urlparse
                        parsed = urlparse(link_url)
                        domain_name = parsed.netloc
                        domain = (
                            db.query(models.Domain)
                            .filter(
                                models.Domain.land_id == land_id,
                                models.Domain.name == domain_name,
                            )
                            .first()
                        )
                        if not domain:
                            domain = models.Domain(
                                land_id=land_id,
                                name=domain_name,
                            )
                            db.add(domain)
                            db.flush()

                        target = models.Expression(
                            land_id=land_id,
                            domain_id=domain.id,
                            url=link_url,
                            url_hash=url_hash,
                            depth=(expr.depth or 0) + 1,
                        )
                        db.add(target)
                        db.flush()
                        stats["expressions_added"] += 1

                    # Creer le lien
                    if target.id != expr.id:
                        existing_link = (
                            db.query(models.ExpressionLink)
                            .filter(
                                models.ExpressionLink.source_id == expr.id,
                                models.ExpressionLink.target_id == target.id,
                            )
                            .first()
                        )
                        if not existing_link:
                            db.add(models.ExpressionLink(
                                source_id=expr.id,
                                target_id=target.id,
                                link_type="internal",
                            ))
                            stats["links_rebuilt"] += 1

                # 6. Extraire medias du contenu readable
                if expr.readable:
                    # Images markdown
                    img_matches = re.findall(r'!\[.*?\]\((.*?)\)', expr.readable)
                    for img_url in img_matches:
                        if img_url and not img_url.startswith("data:"):
                            db.add(models.Media(
                                expression_id=expr.id,
                                url=img_url,
                                type="img",
                            ))
                            stats["media_rebuilt"] += 1

                    # Videos
                    video_matches = re.findall(r'\[VIDEO:\s*(.*?)\]', expr.readable)
                    for vid_url in video_matches:
                        if vid_url:
                            db.add(models.Media(
                                expression_id=expr.id,
                                url=vid_url.strip(),
                                type="video",
                            ))
                            stats["media_rebuilt"] += 1

                db.commit()
                stats["processed"] += 1

                if (i + 1) % 50 == 0:
                    logger.info("[CONSOLIDATE] [%d/%d] %d traites, %d liens, %d medias",
                                i + 1, total, stats["processed"], stats["links_rebuilt"], stats["media_rebuilt"])

            except Exception as e:
                db.rollback()
                stats["errors"] += 1
                logger.error("[CONSOLIDATE] ERROR expr=%s: %s", expr.id, e)

        # Reparer les approved_at
        now = datetime.now(timezone.utc)
        db.execute(
            models.Expression.__table__.update()
            .where(
                models.Expression.land_id == land_id,
                models.Expression.relevance > 0,
                models.Expression.crawled_at.isnot(None),
                models.Expression.approved_at.is_(None),
            )
            .values(approved_at=now)
        )
        db.execute(
            models.Expression.__table__.update()
            .where(
                models.Expression.land_id == land_id,
                models.Expression.relevance == 0,
                models.Expression.approved_at.isnot(None),
            )
            .values(approved_at=None)
        )
        db.commit()

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("[CONSOLIDATE] DONE - land=%s processed=%d errors=%d links=%d media=%d exprs_added=%d duration=%.1fs",
                    land_id, stats["processed"], stats["errors"], stats["links_rebuilt"],
                    stats["media_rebuilt"], stats["expressions_added"], duration)
        logger.info("=" * 60)

        return {
            **stats,
            "status": "completed",
            "duration_seconds": duration,
        }

    except Exception as exc:
        logger.exception("[CONSOLIDATE] FAILED land=%s: %s", land_id, exc)
        db.rollback()
        return {**stats, "status": "failed", "error": str(exc)}
    finally:
        db.close()
