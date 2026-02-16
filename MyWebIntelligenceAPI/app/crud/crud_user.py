from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

from ..db.models import User
from ..schemas.user import UserCreate, UserUpdate
from ..core.security import get_password_hash

class CRUDUser:
    async def get_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
        return await db.get(User, user_id)

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(select(User).filter(User.username == username))
        return result.scalars().first()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).filter(User.email == email))
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        hashed_password = get_password_hash(obj_in.password)
        db_user = User(
            username=obj_in.username,
            email=obj_in.email,
            hashed_password=hashed_password,
            is_admin=getattr(obj_in, 'is_superuser', False)
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user

    async def update(self, db: AsyncSession, *, db_obj: User, obj_in: UserUpdate) -> User:
        update_data = obj_in.model_dump(exclude_unset=True)
        if "password" in update_data and update_data["password"]:
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            db_obj.hashed_password = hashed_password
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, user_id: int) -> Optional[User]:
        user_obj = await self.get_by_id(db, user_id)
        if user_obj:
            await db.delete(user_obj)
            await db.commit()
        return user_obj

user = CRUDUser()


# Backward compatibility helpers
async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Compat helper used by legacy dependencies."""
    return await user.get_by_username(db, username)


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    return await user.get_by_email(db, email)
