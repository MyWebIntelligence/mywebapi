"""
API Versioning System for MyWebIntelligence
Gestion avancée des versions d'API avec support de dépréciation
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastapi import Request, Response, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import re


class APIVersion(BaseModel):
    """Modèle représentant une version d'API"""
    version: str
    status: str  # "stable", "deprecated", "beta", "alpha"
    release_date: datetime
    deprecation_date: Optional[datetime] = None
    sunset_date: Optional[datetime] = None
    description: str
    breaking_changes: List[str] = []
    migration_guide_url: Optional[str] = None


class VersioningConfig:
    """Configuration du système de versioning"""
    
    # Versions supportées
    SUPPORTED_VERSIONS = {
        "v1": APIVersion(
            version="1.0.0",
            status="deprecated",
            release_date=datetime(2025, 6, 1),
            deprecation_date=datetime(2025, 12, 1),
            sunset_date=datetime(2026, 1, 4),
            description="Version stable initiale de l'API (dépréciée)",
            breaking_changes=[],
            migration_guide_url="/docs/migration/v1-to-v2"
        ),
        "v2": APIVersion(
            version="2.0.0", 
            status="stable",
            release_date=datetime(2025, 7, 4),
            description="Version stable avec améliorations de performance et nouveaux formats",
            breaking_changes=[
                "Export endpoints retournent maintenant des job_id au lieu de liens directs",
                "Pagination obligatoire pour les endpoints de listing",
                "Nouveaux codes d'erreur standardisés",
                "Champs de réponse renommés pour plus de cohérence"
            ],
            migration_guide_url="/docs/migration/v1-to-v2"
        )
    }
    
    # Version par défaut
    DEFAULT_VERSION = "v1"
    
    # Headers de versioning supportés
    VERSION_HEADERS = [
        "API-Version",
        "Accept-Version", 
        "X-API-Version"
    ]
    
    # Pattern pour extraire version de l'URL
    URL_VERSION_PATTERN = re.compile(r"/api/(v\d+)/")


def extract_version_from_request(request: Request) -> str:
    """
    Extrait la version demandée depuis la requête
    
    Ordre de priorité:
    1. Header API-Version
    2. Header Accept-Version  
    3. Header X-API-Version
    4. URL path (/api/v1/, /api/v2/)
    5. Query parameter ?version=v1
    6. Version par défaut
    """
    # 1. Vérifier les headers
    for header_name in VersioningConfig.VERSION_HEADERS:
        version = request.headers.get(header_name)
        if version:
            return normalize_version(version)
    
    # 2. Extraire de l'URL
    path = str(request.url.path)
    match = VersioningConfig.URL_VERSION_PATTERN.search(path)
    if match:
        return match.group(1)
    
    # 3. Query parameter
    version_param = request.query_params.get("version")
    if version_param:
        return normalize_version(version_param)
    
    # 4. Version par défaut
    return VersioningConfig.DEFAULT_VERSION


def normalize_version(version: str) -> str:
    """Normalise une version (v1, 1.0, 1 -> v1)"""
    version = version.strip().lower()
    
    # Si déjà au bon format
    if version.startswith('v') and len(version) >= 2:
        return version
    
    # Convertir formats numériques
    if version.isdigit():
        return f"v{version}"
    
    # Convertir format x.y
    if '.' in version:
        major = version.split('.')[0]
        if major.isdigit():
            return f"v{major}"
    
    # Fallback
    return VersioningConfig.DEFAULT_VERSION


def validate_version(version: str) -> bool:
    """Vérifie si une version est supportée"""
    return version in VersioningConfig.SUPPORTED_VERSIONS


def get_version_info(version: str) -> Optional[APIVersion]:
    """Récupère les informations d'une version"""
    return VersioningConfig.SUPPORTED_VERSIONS.get(version)


def is_version_deprecated(version: str) -> bool:
    """Vérifie si une version est dépréciée"""
    version_info = get_version_info(version)
    if not version_info:
        return False
    
    return version_info.status == "deprecated"


def get_deprecation_warning(version: str) -> Optional[str]:
    """Génère un avertissement de dépréciation"""
    version_info = get_version_info(version)
    if not version_info or version_info.status != "deprecated":
        return None
    
    warning = f"API version {version} is deprecated"
    
    if version_info.sunset_date:
        days_until_sunset = (version_info.sunset_date - datetime.now()).days
        warning += f" and will be discontinued in {days_until_sunset} days"
    
    if version_info.migration_guide_url:
        warning += f". Migration guide: {version_info.migration_guide_url}"
    
    return warning


def create_version_response_headers(version: str, request_version: str) -> Dict[str, str]:
    """Crée les headers de réponse pour le versioning"""
    headers = {
        "API-Version": version,
        "API-Supported-Versions": ",".join(VersioningConfig.SUPPORTED_VERSIONS.keys())
    }
    
    # Avertissement de dépréciation
    warning = get_deprecation_warning(version)
    if warning:
        headers["API-Deprecation-Warning"] = warning
    
    # Headers de dépréciation standardisés
    version_info = get_version_info(version)
    if version_info and version_info.status == "deprecated":
        headers["Deprecation"] = "true"
        
        if version_info.sunset_date:
            headers["Sunset"] = version_info.sunset_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        if version_info.migration_guide_url:
            headers["API-Migration-Guide"] = version_info.migration_guide_url
        
        # Calculer l'urgence
        if version_info.sunset_date:
            days_until_sunset = (version_info.sunset_date - datetime.now()).days
            if days_until_sunset <= 30:
                headers["API-Deprecation-Severity"] = "critical"
            elif days_until_sunset <= 90:
                headers["API-Deprecation-Severity"] = "high"
            else:
                headers["API-Deprecation-Severity"] = "medium"
    
    # Si version demandée différente de version utilisée
    if request_version != version:
        headers["API-Version-Fallback"] = f"Requested {request_version}, using {version}"
    
    return headers


class VersioningMiddleware:
    """Middleware pour la gestion automatique du versioning"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Extraire version demandée
            requested_version = extract_version_from_request(request)
            
            # Déterminer version à utiliser
            if validate_version(requested_version):
                used_version = requested_version
            else:
                used_version = VersioningConfig.DEFAULT_VERSION
            
            # Ajouter version au scope pour usage dans les endpoints
            scope["api_version"] = used_version
            scope["requested_api_version"] = requested_version
            
            # Wrapper pour modifier la réponse
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    # Ajouter headers de versioning
                    headers = create_version_response_headers(used_version, requested_version)
                    
                    # Convertir headers en format ASGI
                    for key, value in headers.items():
                        message["headers"].append([key.encode(), value.encode()])
                
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


def get_api_version_from_request(request: Request) -> str:
    """Récupère la version API depuis le scope de la requête"""
    return getattr(request.scope, "api_version", VersioningConfig.DEFAULT_VERSION)


def version_endpoint(min_version: str = "v1", max_version: Optional[str] = None):
    """
    Décorateur pour marquer un endpoint avec des contraintes de version
    
    Args:
        min_version: Version minimum supportée
        max_version: Version maximum supportée (optionnel)
    """
    def decorator(func):
        func._api_min_version = min_version
        func._api_max_version = max_version
        return func
    return decorator


def check_version_compatibility(request: Request, min_version: str, max_version: Optional[str] = None) -> bool:
    """
    Vérifie la compatibilité de version pour un endpoint
    
    Args:
        request: Requête FastAPI
        min_version: Version minimum requise
        max_version: Version maximum supportée
        
    Returns:
        True si compatible, False sinon
    """
    current_version = get_api_version_from_request(request)
    
    # Extraire numéro de version pour comparaison
    def version_number(v: str) -> int:
        return int(v.replace('v', ''))
    
    current_num = version_number(current_version)
    min_num = version_number(min_version)
    
    if current_num < min_num:
        return False
    
    if max_version:
        max_num = version_number(max_version)
        if current_num > max_num:
            return False
    
    return True


def create_version_error_response(
    requested_version: str, 
    supported_versions: List[str],
    message: str = "Unsupported API version"
) -> JSONResponse:
    """Crée une réponse d'erreur pour version non supportée"""
    return JSONResponse(
        status_code=400,
        content={
            "error": "unsupported_api_version",
            "message": message,
            "requested_version": requested_version,
            "supported_versions": supported_versions,
            "migration_info": {
                "latest_stable": "v1",
                "latest_beta": "v2",
                "migration_guide": "/docs/api-versioning"
            }
        },
        headers={
            "API-Error": "Unsupported version",
            "API-Supported-Versions": ",".join(supported_versions)
        }
    )


# Utility functions pour usage dans les endpoints
def require_version(request: Request, min_version: str, max_version: Optional[str] = None):
    """
    Vérifie et applique les contraintes de version
    Lève une exception si version incompatible
    """
    if not check_version_compatibility(request, min_version, max_version):
        current_version = get_api_version_from_request(request)
        supported = list(VersioningConfig.SUPPORTED_VERSIONS.keys())
        
        raise create_version_error_response(
            current_version,
            supported,
            f"Endpoint requires API version {min_version} or higher"
        )


def get_versioned_response_model(request: Request, models: Dict[str, type]):
    """
    Retourne le modèle de réponse approprié selon la version
    
    Args:
        request: Requête FastAPI
        models: Dict mapping version -> model class
        
    Returns:
        Classe du modèle approprié
    """
    version = get_api_version_from_request(request)
    return models.get(version, models.get(VersioningConfig.DEFAULT_VERSION))


# Configuration des changements breaking par version
BREAKING_CHANGES = {
    "v2": {
        "export_endpoints": {
            "description": "Export endpoints now return job_id instead of direct links",
            "migration": "Update client to handle async job pattern",
            "affected_endpoints": ["/api/v2/export/csv", "/api/v2/export/gexf", "/api/v2/export/corpus"]
        },
        "pagination": {
            "description": "Pagination is now mandatory for listing endpoints",
            "migration": "Add page and page_size parameters to all listing requests",
            "affected_endpoints": ["/api/v2/lands", "/api/v2/expressions", "/api/v2/jobs"]
        },
        "error_codes": {
            "description": "Standardized error codes and response format",
            "migration": "Update error handling to use new error code structure",
            "affected_endpoints": ["All endpoints"]
        }
    }
}