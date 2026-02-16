from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
import enum

class CrawlStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CrawlRequest(BaseModel):
    limit: Optional[int] = Field(None, description="Max number of URLs to process")
    depth: Optional[int] = Field(None, description="Crawl depth")
    http_status: Optional[str] = Field(None, description="Filter by HTTP status for re-crawling")
    analyze_media: bool = Field(False, description="Enable detailed media analysis during crawl")
    enable_llm: bool = Field(False, description="Enable OpenRouter LLM validation during crawl")

# Schéma de base pour un Job
class CrawlJobBase(BaseModel):
    land_id: int
    job_type: str
    parameters: Optional[Dict[str, Any]] = None

# Schéma pour la création d'un Job
class CrawlJobCreate(CrawlJobBase):
    task_id: str

class CrawlJobResponse(BaseModel):
    job_id: int
    celery_task_id: str
    land_id: int
    status: CrawlStatus
    created_at: datetime
    parameters: Dict[str, Any]
    ws_channel: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# Schéma pour le statut d'un job Celery (utilisé par l'endpoint jobs)
class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    result: Optional[Any] = None
    error_message: Optional[str] = None
