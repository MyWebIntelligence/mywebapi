"""
Expressions API Endpoints V2 SYNC

Endpoints d'exploration des expressions pour le client V2.
Remplace les requetes SQL legacy de DataQueries.js.

Endpoints:
- GET  /api/v2/lands/{land_id}/expressions   - Liste paginee/triee/filtree
- GET  /api/v2/expressions/{expr_id}         - Detail expression
- PUT  /api/v2/expressions/{expr_id}         - Mise a jour contenu
- DELETE /api/v2/expressions/{expr_id}       - Suppression
- GET  /api/v2/expressions/{expr_id}/neighbors - Prev/next navigation
"""

from typing import Optional, List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, text
import logging
import math

from app.db.session import get_sync_db
from app.api.dependencies import get_current_active_user_sync
from app.schemas.user import User
from app.db.models import Expression, Domain, Media, TaggedContent, Tag

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────────
# GET /api/v2/lands/{land_id}/expressions
# ──────────────────────────────────────────────────

ALLOWED_SORT_COLUMNS = {
    "id": Expression.id,
    "title": Expression.title,
    "relevance": Expression.relevance,
    "depth": Expression.depth,
    "domain": Domain.name,
    "quality_score": Expression.quality_score,
    "created_at": Expression.created_at,
}


@router.get("/lands/{land_id}/expressions")
def list_expressions(
    land_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort: str = Query("relevance"),
    order: str = Query("desc"),
    min_relevance: float = Query(0, ge=0),
    max_depth: int = Query(10, ge=0),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync),
):
    """Liste paginee des expressions d'un land avec filtres et tri."""

    sort_col = ALLOWED_SORT_COLUMNS.get(sort, Expression.relevance)
    order_dir = "desc" if order == "desc" else "asc"

    # Base query
    q = (
        db.query(
            Expression.id,
            Expression.title,
            Expression.url,
            Expression.http_status,
            Expression.relevance,
            Expression.depth,
            Expression.quality_score,
            Expression.lang,
            Domain.id.label("domain_id"),
            Domain.name.label("domain_name"),
            func.count(TaggedContent.id).label("tag_count"),
        )
        .join(Domain, Domain.id == Expression.domain_id)
        .outerjoin(TaggedContent, TaggedContent.expression_id == Expression.id)
        .filter(Expression.land_id == land_id)
        .filter(Expression.relevance >= min_relevance)
        .filter(Expression.depth <= max_depth)
    )

    if search:
        q = q.filter(Expression.title.ilike(f"%{search}%"))

    q = q.group_by(Expression.id, Domain.id, Domain.name)

    # Count total before pagination
    count_q = (
        db.query(func.count(Expression.id))
        .filter(Expression.land_id == land_id)
        .filter(Expression.relevance >= min_relevance)
        .filter(Expression.depth <= max_depth)
    )
    if search:
        count_q = count_q.filter(Expression.title.ilike(f"%{search}%"))
    total = count_q.scalar() or 0

    # Sort
    if order_dir == "desc":
        q = q.order_by(sort_col.desc(), Expression.id.desc())
    else:
        q = q.order_by(sort_col.asc(), Expression.id.asc())

    # Paginate
    offset = (page - 1) * page_size
    rows = q.offset(offset).limit(page_size).all()

    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "title": r.title,
            "url": r.url,
            "http_status": r.http_status,
            "relevance": r.relevance,
            "depth": r.depth,
            "quality_score": r.quality_score,
            "language": r.lang,
            "domain_id": r.domain_id,
            "domain_name": r.domain_name,
            "tags": r.tag_count,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


# ──────────────────────────────────────────────────
# GET /api/v2/expressions/{expr_id}
# ──────────────────────────────────────────────────

@router.get("/expressions/{expr_id}")
def get_expression(
    expr_id: int,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync),
):
    """Detail complet d'une expression avec domain, media et tags."""

    expr = (
        db.query(Expression)
        .filter(Expression.id == expr_id)
        .first()
    )
    if not expr:
        raise HTTPException(status_code=404, detail=f"Expression {expr_id} not found")

    domain = db.query(Domain).filter(Domain.id == expr.domain_id).first()

    media_rows = (
        db.query(Media)
        .filter(Media.expression_id == expr_id)
        .all()
    )

    tagged = (
        db.query(TaggedContent, Tag.name, Tag.color)
        .join(Tag, Tag.id == TaggedContent.tag_id)
        .filter(TaggedContent.expression_id == expr_id)
        .all()
    )

    return {
        "id": expr.id,
        "land_id": expr.land_id,
        "domain_id": expr.domain_id,
        "domain_name": domain.name if domain else None,
        "url": expr.url,
        "title": expr.title,
        "description": expr.description,
        "content": expr.content,
        "readable": expr.readable,
        "summary": expr.summary,
        "http_status": expr.http_status,
        "depth": expr.depth,
        "relevance": expr.relevance,
        "language": expr.lang,
        "word_count": expr.word_count,
        "quality_score": expr.quality_score,
        "sentiment_score": expr.sentiment_score,
        "sentiment_label": expr.sentiment_label,
        "valid_llm": expr.valid_llm,
        "valid_model": expr.valid_model,
        "seo_rank": expr.seo_rank,
        "crawled_at": expr.crawled_at.isoformat() if expr.crawled_at else None,
        "created_at": expr.created_at.isoformat() if expr.created_at else None,
        "media": [
            {
                "id": m.id,
                "url": m.url,
                "type": m.type.value if m.type else None,
                "alt_text": m.alt_text,
                "width": m.width,
                "height": m.height,
                "file_size": m.file_size,
            }
            for m in media_rows
        ],
        "tags": [
            {
                "id": tc.id,
                "tag_id": tc.tag_id,
                "tag_name": tag_name,
                "tag_color": tag_color,
                "text": tc.text,
                "from_char": tc.from_char,
                "to_char": tc.to_char,
            }
            for tc, tag_name, tag_color in tagged
        ],
    }


# ──────────────────────────────────────────────────
# PUT /api/v2/expressions/{expr_id}
# ──────────────────────────────────────────────────

@router.put("/expressions/{expr_id}")
def update_expression(
    expr_id: int,
    data: dict,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync),
):
    """Mise a jour du contenu d'une expression."""

    expr = db.query(Expression).filter(Expression.id == expr_id).first()
    if not expr:
        raise HTTPException(status_code=404, detail=f"Expression {expr_id} not found")

    if "content" in data:
        expr.content = data["content"]
    if "title" in data:
        expr.title = data["title"]
    if "readable" in data:
        expr.readable = data["readable"]

    db.commit()
    db.refresh(expr)

    return {"id": expr.id, "message": "Expression updated"}


# ──────────────────────────────────────────────────
# DELETE /api/v2/expressions/{expr_id}
# ──────────────────────────────────────────────────

@router.delete("/expressions/{expr_id}", status_code=204)
def delete_expression(
    expr_id: int,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync),
):
    """Suppression d'une expression et de ses donnees associees."""

    expr = db.query(Expression).filter(Expression.id == expr_id).first()
    if not expr:
        raise HTTPException(status_code=404, detail=f"Expression {expr_id} not found")

    db.delete(expr)
    db.commit()
    return None


# ──────────────────────────────────────────────────
# GET /api/v2/expressions/{expr_id}/neighbors
# ──────────────────────────────────────────────────

@router.get("/expressions/{expr_id}/neighbors")
def get_expression_neighbors(
    expr_id: int,
    land_id: int = Query(...),
    sort: str = Query("relevance"),
    order: str = Query("desc"),
    min_relevance: float = Query(0, ge=0),
    max_depth: int = Query(10, ge=0),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_active_user_sync),
):
    """
    Retourne les IDs prev/next dans l'ordre de tri courant.
    Utilise ROW_NUMBER() comme le legacy DataQueries.js.
    """

    sort_col_map = {
        "id": "e.id",
        "title": "e.title",
        "relevance": "e.relevance",
        "depth": "e.depth",
        "domain": "d.name",
    }
    col = sort_col_map.get(sort, "e.relevance")
    dir_ = "DESC" if order == "desc" else "ASC"
    tie = "DESC" if order == "desc" else "ASC"

    sql = text(f"""
        WITH ordered AS (
            SELECT e.id,
                   ROW_NUMBER() OVER (ORDER BY {col} {dir_}, e.id {tie}) AS pos
            FROM expressions e
            JOIN domains d ON d.id = e.domain_id
            WHERE e.land_id = :land_id
              AND e.relevance >= :min_rel
              AND e.depth <= :max_depth
        ),
        current_pos AS (
            SELECT pos FROM ordered WHERE id = :expr_id
        )
        SELECT
            (SELECT id FROM ordered WHERE pos = (SELECT pos - 1 FROM current_pos)) AS prev_id,
            (SELECT id FROM ordered WHERE pos = (SELECT pos + 1 FROM current_pos)) AS next_id
    """)

    row = db.execute(
        sql,
        {"land_id": land_id, "min_rel": min_relevance, "max_depth": max_depth, "expr_id": expr_id},
    ).first()

    return {
        "prev_id": row.prev_id if row else None,
        "next_id": row.next_id if row else None,
    }
