"""
Routeur principal de l'API v1
"""

from fastapi import APIRouter
from .endpoints import auth, lands, websocket, export, tags, jobs, paragraphs

# Routeur principal v1
api_router = APIRouter()

# Inclusion des endpoints par domaine fonctionnel
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(lands.router, prefix="/lands", tags=["lands"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(paragraphs.router, prefix="/paragraphs", tags=["paragraphs"])

# Endpoint d'info pour la v1
@api_router.get("/")
async def v1_info():
    """Informations sur l'API v1"""
    return {
        "version": "1.0.0",
        "status": "stable",
        "endpoints": {
            "auth": "Authentification et gestion utilisateurs",
            "lands": "Gestion des projets de crawling",
            "expressions": "Gestion du contenu extrait",
            "crawl": "Opérations de crawling",
            "media": "Analyse et gestion des médias",
            "export": "Export de données",
            "jobs": "Suivi des tâches asynchrones"
        }
    }
