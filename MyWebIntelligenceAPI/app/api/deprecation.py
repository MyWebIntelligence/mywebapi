"""
API Deprecation Management
Handles deprecation notices, sunset dates, and migration recommendations
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Response
from app.api.versioning import VersioningConfig, get_api_version_from_request, get_version_info

router = APIRouter()


def get_deprecation_notice(version: str) -> Optional[Dict[str, Any]]:
    """
    Génère un avis de dépréciation pour une version donnée
    """
    version_info = get_version_info(version)
    
    if not version_info or version_info.status != "deprecated":
        return None
    
    now = datetime.now()
    
    # Calculer les jours restants avant sunset
    days_until_sunset = None
    if version_info.sunset_date:
        days_until_sunset = (version_info.sunset_date - now).days
    
    # Déterminer la sévérité de l'avertissement
    if days_until_sunset is not None:
        if days_until_sunset <= 30:
            severity = "critical"
        elif days_until_sunset <= 90:
            severity = "high"
        else:
            severity = "medium"
    else:
        severity = "low"
    
    return {
        "version": version,
        "status": "deprecated",
        "severity": severity,
        "deprecation_date": version_info.deprecation_date.isoformat() if version_info.deprecation_date else None,
        "sunset_date": version_info.sunset_date.isoformat() if version_info.sunset_date else None,
        "days_until_sunset": days_until_sunset,
        "message": f"API version {version} is deprecated",
        "detailed_message": _generate_detailed_deprecation_message(version_info, days_until_sunset),
        "migration_guide": version_info.migration_guide_url,
        "recommended_version": _get_recommended_version(),
        "support_contact": "support@mywebintelligence.com"
    }


def _generate_detailed_deprecation_message(version_info, days_until_sunset: Optional[int]) -> str:
    """Génère un message de dépréciation détaillé"""
    message = f"API version {version_info.version} has been deprecated"
    
    if version_info.deprecation_date:
        message += f" since {version_info.deprecation_date.strftime('%B %d, %Y')}"
    
    if days_until_sunset is not None:
        if days_until_sunset <= 0:
            message += " and has reached its sunset date. This version is no longer supported."
        elif days_until_sunset <= 30:
            message += f" and will be sunset in {days_until_sunset} days. Please migrate immediately."
        elif days_until_sunset <= 90:
            message += f" and will be sunset in {days_until_sunset} days. Please plan your migration."
        else:
            message += f" and will be sunset in {days_until_sunset} days."
    
    message += f" Please migrate to {_get_recommended_version()} for continued support and new features."
    
    return message


def _get_recommended_version() -> str:
    """Retourne la version recommandée"""
    # Trouver la version stable la plus récente
    stable_versions = [
        v for v, info in VersioningConfig.SUPPORTED_VERSIONS.items() 
        if info.status == "stable"
    ]
    
    if stable_versions:
        # Trier par version (simple tri alphabétique pour v1, v2, etc.)
        return max(stable_versions)
    
    # Fallback vers la version par défaut
    return VersioningConfig.DEFAULT_VERSION


@router.get("/deprecation-notice")
async def get_current_deprecation_notice(request: Request) -> Dict[str, Any]:
    """
    Endpoint pour obtenir les avis de dépréciation actuels
    """
    current_version = get_api_version_from_request(request)
    
    notice = get_deprecation_notice(current_version)
    
    if not notice:
        return {
            "version": current_version,
            "status": "supported",
            "message": f"API version {current_version} is currently supported",
            "deprecation_notice": None
        }
    
    return {
        "version": current_version,
        "status": "deprecated",
        "deprecation_notice": notice,
        "migration_required": True
    }


@router.get("/all-deprecations")
async def get_all_deprecation_notices() -> Dict[str, Any]:
    """
    Retourne tous les avis de dépréciation actifs
    """
    all_notices = {}
    
    for version in VersioningConfig.SUPPORTED_VERSIONS.keys():
        notice = get_deprecation_notice(version)
        if notice:
            all_notices[version] = notice
    
    return {
        "active_deprecations": all_notices,
        "total_deprecated_versions": len(all_notices),
        "recommended_version": _get_recommended_version(),
        "support_info": {
            "migration_assistance": "migration-support@mywebintelligence.com",
            "documentation": "/docs/migration",
            "timeline": "/docs/deprecation-timeline"
        }
    }


@router.get("/migration-urgency")
async def get_migration_urgency(request: Request) -> Dict[str, Any]:
    """
    Évalue l'urgence de migration pour la version actuelle
    """
    current_version = get_api_version_from_request(request)
    notice = get_deprecation_notice(current_version)
    
    if not notice:
        return {
            "version": current_version,
            "urgency": "none",
            "message": "No migration required",
            "action": "continue"
        }
    
    days_until_sunset = notice.get("days_until_sunset")
    
    if days_until_sunset is None:
        urgency = "low"
        action = "plan_migration"
        message = "Version is deprecated but no sunset date set"
    elif days_until_sunset <= 0:
        urgency = "critical"
        action = "migrate_immediately"
        message = "Version has reached sunset date"
    elif days_until_sunset <= 7:
        urgency = "critical"
        action = "migrate_immediately"
        message = f"Version will sunset in {days_until_sunset} days"
    elif days_until_sunset <= 30:
        urgency = "high"
        action = "migrate_soon"
        message = f"Version will sunset in {days_until_sunset} days"
    elif days_until_sunset <= 90:
        urgency = "medium"
        action = "plan_migration"
        message = f"Version will sunset in {days_until_sunset} days"
    else:
        urgency = "low"
        action = "plan_migration"
        message = f"Version will sunset in {days_until_sunset} days"
    
    return {
        "version": current_version,
        "urgency": urgency,
        "action": action,
        "message": message,
        "days_until_sunset": days_until_sunset,
        "recommended_version": _get_recommended_version(),
        "migration_resources": {
            "guide": notice.get("migration_guide"),
            "examples": "/docs/examples/migration",
            "tools": "/tools/migration",
            "support": "migration-support@mywebintelligence.com"
        }
    }


@router.post("/acknowledge-deprecation")
async def acknowledge_deprecation(
    request: Request,
    acknowledgment_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Permet aux clients d'accuser réception des avis de dépréciation
    (pour les analytics et le suivi)
    """
    current_version = get_api_version_from_request(request)
    
    # En production, ceci enregistrerait l'accusé de réception en base
    # Pour l'instant, on retourne juste une confirmation
    
    return {
        "acknowledged": True,
        "version": current_version,
        "timestamp": datetime.now().isoformat(),
        "next_steps": [
            "Review migration guide",
            "Test v2 endpoints in staging",
            "Plan migration timeline",
            "Contact support if needed"
        ],
        "tracking_id": f"ack_{current_version}_{int(datetime.now().timestamp())}"
    }


def create_deprecation_headers(version: str) -> Dict[str, str]:
    """
    Crée les headers de dépréciation pour les réponses HTTP
    """
    headers = {}
    notice = get_deprecation_notice(version)
    
    if notice:
        headers["Deprecation"] = "true"
        headers["API-Deprecation"] = notice["message"]
        
        if notice.get("sunset_date"):
            headers["Sunset"] = notice["sunset_date"]
        
        if notice.get("migration_guide"):
            headers["API-Migration-Guide"] = notice["migration_guide"]
        
        if notice.get("recommended_version"):
            headers["API-Recommended-Version"] = notice["recommended_version"]
        
        # Header personnalisé pour l'urgence
        if notice.get("severity"):
            headers["API-Deprecation-Severity"] = notice["severity"]
    
    return headers


class DeprecationMetrics:
    """
    Classe pour suivre les métriques d'utilisation des versions dépréciées
    """
    
    @staticmethod
    def track_deprecated_version_usage(version: str, endpoint: str, user_agent: str = None):
        """
        Enregistre l'utilisation d'une version dépréciée
        En production, ceci enverrait des métriques à un système de monitoring
        """
        # Mock implementation - en production, utiliser Prometheus, DataDog, etc.
        print(f"DEPRECATION_USAGE: version={version}, endpoint={endpoint}, user_agent={user_agent}")
    
    @staticmethod
    def get_deprecation_stats() -> Dict[str, Any]:
        """
        Retourne les statistiques d'utilisation des versions dépréciées
        """
        # Mock data - en production, récupérer depuis le système de métriques
        return {
            "deprecated_version_usage": {
                "v1": {
                    "total_requests": 15420,
                    "unique_clients": 45,
                    "most_used_endpoints": [
                        "/api/v1/lands",
                        "/api/v1/export/csv"
                    ],
                    "daily_requests": 850
                }
            },
            "migration_progress": {
                "total_clients": 120,
                "migrated_clients": 75,
                "migration_rate": "62.5%"
            },
            "recommendations": [
                "Focus migration efforts on /api/v1/export endpoints",
                "Contact high-usage clients directly",
                "Provide automated migration tools"
            ]
        }