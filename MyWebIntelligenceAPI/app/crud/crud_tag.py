"""
CRUD pour les tags
"""

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.crud.base import CRUDBase
from app.db.models import Tag
from app.schemas.tag import TagCreate, TagUpdate


class CRUDTag(CRUDBase[Tag, TagCreate, TagUpdate]):
    async def create_with_land(
        self, db: AsyncSession, *, obj_in: TagCreate, land_id: int
    ) -> Tag:
        db_obj = Tag(**obj_in.dict(), land_id=land_id)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_multi_by_land(
        self, db: AsyncSession, *, land_id: int, skip: int = 0, limit: int = 100
    ) -> List[Tag]:
        result = await db.execute(
            select(self.model)
            .filter(Tag.land_id == land_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


tag = CRUDTag(Tag)
