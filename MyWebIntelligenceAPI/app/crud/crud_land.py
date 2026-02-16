from typing import List, Optional, Dict, Any, Union

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.models import Land, Word, LandDictionary, CrawlStatus
from app.schemas.land import LandCreate, LandUpdate
from app.core.text_processing import get_lemma

class CRUDLand:
    async def get(self, db: AsyncSession, id: int):
        result = await db.execute(
            select(Land).options(selectinload(Land.words)).filter(Land.id == id)
        )
        return result.scalars().first()

    async def get_by_name(self, db: AsyncSession, name: str):
        result = await db.execute(
            select(Land).options(selectinload(Land.words)).filter(Land.name == name)
        )
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100):
        result = await db.execute(
            select(Land)
            .options(selectinload(Land.words))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def create(
        self,
        db: AsyncSession,
        obj_in: Union[LandCreate, Dict[str, Any]],
        owner_id: Optional[int] = None,
    ):
        if isinstance(obj_in, LandCreate):
            data = obj_in.model_dump()
        else:
            data = dict(obj_in)

        owner = owner_id or data.pop("owner_id", None)
        if owner is None:
            raise ValueError("owner_id must be provided to create a land")

        start_urls = data.get("start_urls") or []
        lang = data.get("lang") or ["fr"]

        db_obj = Land(
            name=data.get("name"),
            description=data.get("description"),
            owner_id=owner,
            start_urls=start_urls,
            lang=lang,
            crawl_depth=data.get("crawl_depth", 3),
            crawl_limit=data.get("crawl_limit", 1000),
            settings=data.get("settings"),
        )
        
        # Traiter les mots-clés si fournis
        words_data = data.get("words", [])
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj, attribute_names=["words"])
        
        # Auto-peupler le dictionnaire si des mots sont fournis
        if words_data:
            try:
                # Use the simpler add_terms_to_land method which handles duplicates properly
                await self.add_terms_to_land(db, db_obj.id, words_data)
            except Exception as e:
                # Log l'erreur mais ne fail pas la création du land
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to add terms to land {db_obj.id}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        return db_obj

    async def update(self, db: AsyncSession, db_obj: Land, obj_in: LandUpdate):
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, id: int):
        obj = await self.get(db, id=id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    async def get_by_name_and_user(
        self, db: AsyncSession, name: str, user_id: int
    ) -> Optional[Land]:
        result = await db.execute(
            select(Land)
                .options(selectinload(Land.words))
                .filter(Land.name == name, Land.owner_id == user_id)
        )
        return result.scalars().first()

    async def count_user_lands(self, db: AsyncSession, user_id: int) -> int:
        result = await db.execute(
            select(func.count(Land.id)).filter(Land.owner_id == user_id)
        )
        count = result.scalar()
        return int(count or 0)

    async def get_user_lands_paginated(
        self,
        db: AsyncSession,
        user_id: int,
        offset: int,
        limit: int,
        name_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[Land]:
        query = select(Land).options(selectinload(Land.words)).filter(Land.owner_id == user_id)

        if name_filter:
            like_pattern = f"%{name_filter}%"
            query = query.filter(Land.name.ilike(like_pattern))

        if status_filter:
            try:
                status = CrawlStatus(status_filter.upper())
                query = query.filter(Land.crawl_status == status)
            except ValueError:
                pass

        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def add_terms_to_land(self, db: AsyncSession, land_id: int, terms: list[str]):
        land = await self.get(db, id=land_id)
        if not land:
            return None

        if isinstance(land.lang, list) and land.lang:
            lang_code = land.lang[0]
        else:
            lang_code = land.lang or "fr"

        for term in terms:
            lemma = get_lemma(term, lang_code)

            # Check by exact word first (unique constraint)
            # Note: Some existing words may have language stored as '["fr"]' instead of 'fr'
            result = await db.execute(select(Word).filter(Word.word == term))
            word = result.scalars().first()

            # If not found by exact word, check by lemma
            if not word:
                result = await db.execute(select(Word).filter(Word.lemma == lemma))
                word = result.scalars().first()

            # Create word if it doesn't exist
            if not word:
                word = Word(word=term, lemma=lemma, language=lang_code, frequency=1.0)
                db.add(word)
                await db.commit()
                await db.refresh(word)

            result = await db.execute(
                select(LandDictionary).filter_by(land_id=land.id, word_id=word.id)
            )
            association = result.scalars().first()
            if not association:
                new_association = LandDictionary(land_id=land.id, word_id=word.id, weight=1.0)
                db.add(new_association)
        
        await db.commit()
        await db.refresh(land, attribute_names=["words"])
        return land

    async def add_urls_to_land(
        self, db: AsyncSession, land_id: int, urls: List[str]
    ) -> Optional[Land]:
        land = await self.get(db, id=land_id)
        if not land:
            return None

        existing = land.start_urls or []
        # Preserve order while removing duplicates
        merged = []
        for url in existing + urls:
            if url and url not in merged:
                merged.append(url)

        land.start_urls = merged
        db.add(land)
        await db.commit()
        return await self.get(db, id=land_id)

land = CRUDLand()
