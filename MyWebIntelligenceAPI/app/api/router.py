"""
Routeur principal de l'API
"""

from fastapi import APIRouter
from .v1.router import api_router as v1_router

# Routeur principal de l'API
api_router = APIRouter()

# Inclusion des versions d'API
api_router.include_router(v1_router)

# Endpoint de base pour info API
@api_router.get("/")
async def api_info():
    """Informations générales sur l'API"""
    return {
        "name": "MyWebIntelligence API",
        "version": "1.0.0",
        "description": "API complète pour l'intelligence web et l'analyse de contenu",
        "docs": "/docs",
        "redoc": "/redoc",
        "versions": {
            "v1": {
                "status": "stable",
                "path": "/api/v1",
                "description": "Version stable de l'API"
            }
        }
    }
