"""
Point d'entrée principal de l'application FastAPI
"""

import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from .api.router import api_router
from .api.v2.router import api_router as api_v2_router
from .api.versioning import VersioningMiddleware
from app.config import settings
from app.db.base import Base, engine

logger = logging.getLogger(__name__)

# Test au chargement du module
logger.info(f"📦 Chargement de main.py - Tables déclarées: {list(Base.metadata.tables.keys())[:5]}")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# Configuration des middlewares
# 1. Versioning middleware (en premier pour traiter les headers de version)
app.add_middleware(VersioningMiddleware)

# 2. Configuration CORS
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(api_v2_router, prefix="/api/v2")


@app.on_event("startup")
async def startup_event():
    """Créer les tables au démarrage de l'application"""
    print("🔧 Début de l'initialisation de la base de données...", flush=True)
    print(f"📊 Création de {len(Base.metadata.tables)} tables...", flush=True)

    # Créer un engine avec isolation_level AUTOCOMMIT pour éviter les rollbacks
    from sqlalchemy.ext.asyncio import create_async_engine
    autocommit_engine = create_async_engine(
        settings.DATABASE_URL,
        isolation_level="AUTOCOMMIT"
    )

    try:
        async with autocommit_engine.connect() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables de base de données créées avec succès!", flush=True)
    except Exception as e:
        # Ignorer les erreurs si les tables existent déjà
        if "already exists" in str(e):
            print("✅ Tables de base de données déjà existantes", flush=True)
        else:
            print(f"❌ Erreur: {e}", flush=True)
            raise
    finally:
        await autocommit_engine.dispose()


@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.APP_NAME}"}
