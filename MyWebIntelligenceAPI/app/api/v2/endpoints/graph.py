"""
Graph data endpoint for network visualization.
Returns nodes (expressions or domains) and edges (links + similarities).
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api.dependencies import get_db, get_current_active_user
from app.crud.crud_land import land as crud_land
from app.schemas.user import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{land_id}/graph", response_model=Dict[str, Any])
async def get_land_graph(
    land_id: int,
    type: str = Query("page", description="Graph type: 'page' or 'domain'"),
    min_relevance: int = Query(0, ge=0, description="Minimum relevance filter"),
    max_depth: int = Query(10, ge=0, description="Maximum depth filter"),
    include_similarities: bool = Query(True, description="Include similarity edges"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get graph data for a land suitable for network visualization.

    Returns nodes and edges for rendering with Sigma.js / Graphology.
    - type=page: expressions as nodes, expression_links as edges
    - type=domain: domains as nodes, aggregated links between domains as edges
    """
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if type == "domain":
        return await _build_domain_graph(db, land_id, min_relevance, max_depth)
    else:
        return await _build_page_graph(
            db, land_id, min_relevance, max_depth, include_similarities
        )


async def _build_page_graph(
    db: AsyncSession,
    land_id: int,
    min_relevance: int,
    max_depth: int,
    include_similarities: bool,
) -> Dict[str, Any]:
    """Build a page-level graph: expressions as nodes, links as edges."""

    # Fetch expression nodes
    rows = await db.execute(
        text("""
            SELECT e.id, e.title, e.url, e.relevance, e.depth,
                   d.name AS domain_name, e.sentiment_score
            FROM expressions e
            LEFT JOIN domains d ON d.id = e.domain_id
            WHERE e.land_id = :land_id
              AND e.relevance >= :min_rel
              AND e.depth <= :max_depth
            ORDER BY e.relevance DESC
            LIMIT 2000
        """),
        {"land_id": land_id, "min_rel": min_relevance, "max_depth": max_depth},
    )
    expressions = rows.fetchall()
    node_ids = {r.id for r in expressions}

    nodes: List[Dict[str, Any]] = []
    for r in expressions:
        nodes.append({
            "id": str(r.id),
            "label": (r.title or "")[:60] or f"#{r.id}",
            "url": r.url or "",
            "relevance": r.relevance or 0,
            "depth": r.depth or 0,
            "domain": r.domain_name or "",
            "sentiment": float(r.sentiment_score) if r.sentiment_score is not None else None,
            "type": "page",
        })

    # Fetch link edges
    edges: List[Dict[str, Any]] = []
    if node_ids:
        link_rows = await db.execute(
            text("""
                SELECT source_id, target_id
                FROM expression_links
                WHERE source_id IN (SELECT id FROM expressions WHERE land_id = :land_id
                                    AND relevance >= :min_rel AND depth <= :max_depth)
                  AND target_id IN (SELECT id FROM expressions WHERE land_id = :land_id
                                    AND relevance >= :min_rel AND depth <= :max_depth)
            """),
            {"land_id": land_id, "min_rel": min_relevance, "max_depth": max_depth},
        )
        for lr in link_rows.fetchall():
            edges.append({
                "source": str(lr.source_id),
                "target": str(lr.target_id),
                "weight": 1,
                "type": "link",
            })

    # Fetch similarity edges (optional)
    if include_similarities and node_ids:
        sim_rows = await db.execute(
            text("""
                SELECT DISTINCT ON (e1.id, e2.id)
                       e1.id AS source_expr, e2.id AS target_expr,
                       s.similarity_score
                FROM similarities s
                JOIN paragraphs p1 ON p1.id = s.paragraph1_id
                JOIN paragraphs p2 ON p2.id = s.paragraph2_id
                JOIN expressions e1 ON e1.id = p1.expression_id
                JOIN expressions e2 ON e2.id = p2.expression_id
                WHERE e1.land_id = :land_id
                  AND e2.land_id = :land_id
                  AND e1.id != e2.id
                  AND s.similarity_score >= 0.5
                LIMIT 500
            """),
            {"land_id": land_id},
        )
        for sr in sim_rows.fetchall():
            src, tgt = str(sr.source_expr), str(sr.target_expr)
            if src in {n["id"] for n in nodes} and tgt in {n["id"] for n in nodes}:
                edges.append({
                    "source": src,
                    "target": tgt,
                    "weight": float(sr.similarity_score),
                    "type": "similarity",
                })

    return {"nodes": nodes, "edges": edges, "type": "page", "land_id": land_id}


async def _build_domain_graph(
    db: AsyncSession,
    land_id: int,
    min_relevance: int,
    max_depth: int,
) -> Dict[str, Any]:
    """Build a domain-level graph: domains as nodes, aggregated links as edges."""

    # Fetch domain nodes with expression counts
    rows = await db.execute(
        text("""
            SELECT d.id, d.name, d.title,
                   COUNT(e.id) AS expr_count,
                   AVG(e.relevance) AS avg_relevance
            FROM domains d
            JOIN expressions e ON e.domain_id = d.id
            WHERE e.land_id = :land_id
              AND e.relevance >= :min_rel
              AND e.depth <= :max_depth
            GROUP BY d.id, d.name, d.title
            ORDER BY expr_count DESC
            LIMIT 500
        """),
        {"land_id": land_id, "min_rel": min_relevance, "max_depth": max_depth},
    )
    domains = rows.fetchall()

    nodes: List[Dict[str, Any]] = []
    for r in domains:
        nodes.append({
            "id": str(r.id),
            "label": r.name or r.title or f"Domain #{r.id}",
            "url": f"https://{r.name}" if r.name else "",
            "relevance": round(float(r.avg_relevance or 0), 2),
            "depth": 0,
            "domain": r.name or "",
            "sentiment": None,
            "type": "domain",
            "expr_count": r.expr_count,
        })

    # Fetch aggregated cross-domain links
    edges: List[Dict[str, Any]] = []
    if domains:
        edge_rows = await db.execute(
            text("""
                SELECT e1.domain_id AS source_domain, e2.domain_id AS target_domain,
                       COUNT(*) AS link_count
                FROM expression_links el
                JOIN expressions e1 ON e1.id = el.source_id
                JOIN expressions e2 ON e2.id = el.target_id
                WHERE e1.land_id = :land_id
                  AND e2.land_id = :land_id
                  AND e1.domain_id IS NOT NULL
                  AND e2.domain_id IS NOT NULL
                  AND e1.domain_id != e2.domain_id
                GROUP BY e1.domain_id, e2.domain_id
                ORDER BY link_count DESC
                LIMIT 1000
            """),
            {"land_id": land_id},
        )
        domain_ids = {n["id"] for n in nodes}
        for er in edge_rows.fetchall():
            src, tgt = str(er.source_domain), str(er.target_domain)
            if src in domain_ids and tgt in domain_ids:
                edges.append({
                    "source": src,
                    "target": tgt,
                    "weight": er.link_count,
                    "type": "link",
                })

    return {"nodes": nodes, "edges": edges, "type": "domain", "land_id": land_id}
