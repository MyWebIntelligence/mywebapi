"""
Fonctions CRUD pour les Expressions
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import models
from app.schemas.expression import ExpressionCreate, ExpressionUpdate
from app.crud import crud_domain


class CRUDExpression:
    async def get_expressions_to_crawl(
        self, db: AsyncSession, land_id: int, limit: int = 0, http_status: Optional[str] = None, depth: Optional[int] = None
    ) -> List[models.Expression]:
        """
        Récupère une liste d'expressions à crawler pour un land donné.

        LOGIQUE DES TIMESTAMPS:
        - created_at: Quand l'expression est ajoutée en base (découverte URL)
        - crawled_at: Quand le contenu HTTP a été récupéré (fetch réussi)
        - approved_at: Quand le crawler a traité la réponse (même si 404/erreur)
        - readable_at: Quand le contenu readable a été extrait
        - updated_at: Quand le contenu readable a été modifié

        CRITÈRE: approved_at IS NULL = expressions jamais traitées par le crawler
        """
        query = (
            select(models.Expression)
            .where(models.Expression.land_id == land_id)
            .where(models.Expression.approved_at.is_(None))
            .order_by(models.Expression.depth.asc(), models.Expression.created_at.asc())
        )

        if http_status is not None:
            try:
                http_value = int(http_status)
            except (TypeError, ValueError):
                http_value = None
            if http_value is not None:
                query = query.where(models.Expression.http_status == http_value)
        
        if depth is not None:
            query = query.where(models.Expression.depth == depth)

        if limit > 0:
            query = query.limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_or_create_expression(
        self, db: AsyncSession, land_id: int, url: str, depth: int
    ) -> Optional[models.Expression]:
        """
        Récupère une expression par URL ou la crée si elle n'existe pas.
        Ne commit pas la transaction.
        """
        url_hash = models.Expression.compute_url_hash(url)
        # 1. Vérifier si l'expression existe déjà
        query = select(models.Expression).where(
            models.Expression.land_id == land_id,
            models.Expression.url_hash == url_hash,
            models.Expression.url == url,
        )
        result = await db.execute(query)
        db_expression = result.scalar_one_or_none()

        if db_expression:
            return db_expression

        # 2. Si elle n'existe pas, la créer
        domain_name = crud_domain.domain.get_domain_name(url)
        domain = await crud_domain.domain.get_or_create(db, name=domain_name, land_id=land_id)
        
        expression_in = ExpressionCreate(
            url=url,
            depth=depth,
            land_id=land_id,
            domain_id=domain.id
        )

        new_data = expression_in.model_dump()
        new_data["url_hash"] = url_hash
        new_expression = models.Expression(**new_data)
        db.add(new_expression)
        await db.flush()
        await db.refresh(new_expression)
        return new_expression

    async def update_expression(
        self, db: AsyncSession, *, db_obj: models.Expression, obj_in: ExpressionUpdate
    ) -> models.Expression:
        """
        Met à jour une expression. Ne commit pas la transaction.
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def get_distinct_depths(self, db: AsyncSession, land_id: int, http_status: Optional[str] = None) -> List[int]:
        """
        Récupère les profondeurs distinctes des expressions à crawler.
        Utilise approved_at IS NULL comme critère (pas crawled_at).
        """
        query = (
            select(models.Expression.depth)
            .where(models.Expression.land_id == land_id)
            .where(models.Expression.approved_at.is_(None))
            .distinct()
            .order_by(models.Expression.depth)
        )
        if http_status is not None:
            try:
                http_value = int(http_status)
            except (TypeError, ValueError):
                http_value = None
            if http_value is not None:
                query = query.where(models.Expression.http_status == http_value)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_url_and_land(self, db: AsyncSession, url: str, land_id: int) -> Optional[models.Expression]:
        """
        Récupère une expression par URL et ID de land.
        """
        url_hash = models.Expression.compute_url_hash(url)
        query = select(models.Expression).where(
            models.Expression.land_id == land_id,
            models.Expression.url_hash == url_hash,
            models.Expression.url == url,
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_ids(self, db: AsyncSession, expression_ids: List[int]) -> List[models.Expression]:
        """Récupère une liste d'expressions à partir de leurs identifiants."""
        if not expression_ids:
            return []
        query = (
            select(models.Expression)
            .options(selectinload(models.Expression.land))
            .where(models.Expression.id.in_(expression_ids))
        )
        result = await db.execute(query)
        expressions = list(result.scalars().all())
        expr_by_id = {expr.id: expr for expr in expressions}
        return [expr_by_id[eid] for eid in expression_ids if eid in expr_by_id]

    async def create_expression(self, db: AsyncSession, land_id: int, domain_id: int, url: str, depth: int) -> models.Expression:
        """
        Crée une nouvelle expression. Ne commit pas la transaction.
        """
        expression_in = ExpressionCreate(
            url=url,
            depth=depth,
            land_id=land_id,
            domain_id=domain_id
        )

        new_data = expression_in.model_dump()
        new_data["url_hash"] = models.Expression.compute_url_hash(url)
        new_expression = models.Expression(**new_data)
        db.add(new_expression)
        await db.flush()
        await db.refresh(new_expression)
        return new_expression

    async def get_expressions_to_consolidate(
        self, db: AsyncSession, land_id: int, limit: int = 0, depth: Optional[int] = None
    ) -> List[models.Expression]:
        """
        Récupère les expressions qui ont déjà été crawlées et qui ont besoin d'être consolidées.
        """
        query = (
            select(models.Expression)
            .where(models.Expression.land_id == land_id)
            .where(models.Expression.crawled_at.isnot(None))
            .order_by(models.Expression.crawled_at.asc())
        )

        if depth is not None:
            query = query.where(models.Expression.depth <= depth)

        if limit > 0:
            query = query.limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())


expression = CRUDExpression()
