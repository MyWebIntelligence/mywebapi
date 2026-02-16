"""
Tâche Celery pour l'exportation
"""
import asyncio
from app.core.celery_app import celery_app
from app.services.export_service import ExportService
from app.db.base import AsyncSessionLocal
from app.crud import crud_land

@celery_app.task(bind=True)
def export_land_task(self, land_id: int, export_type: str, minimum_relevance: int):
    """
    Tâche Celery pour exporter un land.
    """
    async def async_export():
        db = AsyncSessionLocal()
        service = ExportService(db)
        try:
            land = await crud_land.get(db, id=land_id)
            if not land:
                raise ValueError(f"Land with id {land_id} not found.")

            result = await service.export_land(land, export_type, minimum_relevance)
            return {"file_path": result}
        except Exception as e:
            print(f"Error during export task for land {land_id}: {e}")
            raise
        finally:
            await db.close()

    return asyncio.run(async_export())
