"""
Opérations CRUD pour les liens entre expressions.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, exc
from typing import Optional

from app.db import models

class CRUDExpressionLink:
    async def create_link(self, db: AsyncSession, source_id: int, target_id: int, 
                         anchor_text: Optional[str] = None, link_type: Optional[str] = None,
                         rel_attribute: Optional[str] = None, position: Optional[int] = None) -> Optional[models.ExpressionLink]:
        """
        Crée un lien entre deux expressions avec métadonnées.
        """
        link = models.ExpressionLink(
            source_id=source_id, 
            target_id=target_id,
            anchor_text=anchor_text,
            link_type=link_type,
            rel_attribute=rel_attribute,
            position=position
        )
        try:
            db.add(link)
            await db.commit()
            await db.refresh(link)
            return link
        except exc.IntegrityError:
            # Le lien existe déjà, ce n'est pas une erreur.
            await db.rollback()
            return None
        except Exception:
            await db.rollback()
            raise

    async def delete_links_for_expression(self, db: AsyncSession, source_id: int):
        """
        Supprime tous les liens sortants d'une expression.
        """
        stmt = delete(models.ExpressionLink).where(models.ExpressionLink.source_id == source_id)
        await db.execute(stmt)
        await db.commit()

expression_link = CRUDExpressionLink()
