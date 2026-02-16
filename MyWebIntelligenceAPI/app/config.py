"""
Configuration de l'application avec Pydantic BaseSettings
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Configuration principale de l'application"""
    
    # Configuration de base
    APP_NAME: str = "MyWebIntelligence API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Configuration serveur
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Configuration base de données
    DATABASE_URL: str = "postgresql+asyncpg://mwi_user:mwi_password@localhost:5432/mwi_db"
    DATABASE_ECHO: bool = False
    
    # Configuration Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Configuration Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_AUTOSCALE: Optional[str] = None
    
    # Configuration JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Configuration CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    
    # Configuration de sécurité
    API_V1_PREFIX: str = "/api/v1"
    API_KEY_HEADER: str = "X-API-Key"
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Configuration embeddings
    EMBEDDINGS_ENABLED: bool = True
    EMBEDDINGS_DEFAULT_PROVIDER: str = "openai"
    EMBEDDINGS_ALLOW_EXTERNAL_PROVIDERS: bool = True
    EMBEDDINGS_REQUIRE_USER_CONFIRMATION: bool = True
    EMBEDDINGS_PROVIDER_CONFIG: Optional[str] = None
    EMBEDDINGS_PROVIDER_CONFIG_FILE: Optional[str] = None
    
    # Configuration crawling
    DEFAULT_CRAWL_DEPTH: int = 3
    MAX_CRAWL_DEPTH: int = 10
    DEFAULT_CRAWL_LIMIT: int = 1000
    MAX_CRAWL_LIMIT: int = 10000
    CRAWL_BATCH_SIZE: int = 10
    
    # Configuration des médias
    MEDIA_STORAGE_PATH: str = "./media"
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_IMAGE_TYPES: List[str] = ["jpeg", "jpg", "png", "gif", "webp", "svg"]
    ALLOWED_VIDEO_TYPES: List[str] = ["mp4", "webm", "avi", "mov"]
    ANALYZE_MEDIA: bool = True
    N_DOMINANT_COLORS: int = 5
    PLAYWRIGHT_TIMEOUT_MS: int = 7000
    PLAYWRIGHT_MAX_RETRIES: int = 1
    
    # Configuration export
    EXPORT_STORAGE_PATH: str = "./exports"
    EXPORT_RETENTION_DAYS: int = 7

    # Configuration external APIs (SerpAPI, SEO Rank, etc.)
    SERPAPI_API_KEY: str = ""
    SERPAPI_BASE_URL: str = "https://serpapi.com/search"
    SERPAPI_TIMEOUT: int = 15
    SEORANK_API_KEY: str = ""
    SEORANK_API_BASE_URL: str = "https://seo-rank.my-addr.com/api2/moz+sr+fb"
    SEORANK_TIMEOUT: int = 15
    SEORANK_REQUEST_DELAY: float = 1.0
    
    # Configuration heuristics (domain name extraction patterns)
    # JSON string: {"twitter.com": "twitter\\.com/([a-zA-Z0-9_]+)", ...}
    HEURISTICS: str = "{}"

    # Configuration logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    
    # Configuration monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8001
    
    # Configuration email (pour notifications)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: Optional[str] = None
    
    # Configuration OpenRouter (pour validation LLM et sentiment)
    OPENROUTER_ENABLED: bool = False
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "anthropic/claude-3.5-sonnet"
    OPENROUTER_TIMEOUT: int = 30
    OPENROUTER_MAX_RETRIES: int = 3

    # Configuration Sentiment Analysis
    ENABLE_SENTIMENT_ANALYSIS: bool = True  # Master switch pour activer/désactiver le sentiment
    SENTIMENT_MIN_CONFIDENCE: float = 0.5  # Seuil de confiance minimal (0.0 à 1.0)
    SENTIMENT_SUPPORTED_LANGUAGES: str = "fr,en"  # Langues supportées (séparées par des virgules)

    # Configuration Quality Scoring
    ENABLE_QUALITY_SCORING: bool = True  # Master switch pour activer/désactiver le quality score
    QUALITY_WEIGHT_ACCESS: float = 0.30  # Poids bloc Access (HTTP status, content-type)
    QUALITY_WEIGHT_STRUCTURE: float = 0.15  # Poids bloc Structure (title, description, etc.)
    QUALITY_WEIGHT_RICHNESS: float = 0.25  # Poids bloc Richness (word count, ratio, etc.)
    QUALITY_WEIGHT_COHERENCE: float = 0.20  # Poids bloc Coherence (language, relevance, etc.)
    QUALITY_WEIGHT_INTEGRITY: float = 0.10  # Poids bloc Integrity (LLM, pipeline, etc.)
    
    def create_directories(self):
        """Créer les répertoires nécessaires s'ils n'existent pas"""
        Path(self.MEDIA_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.EXPORT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


# Instance globale des settings
settings = Settings()

# Créer les répertoires au démarrage
settings.create_directories()
