"""
Pydantic schemas for export functionality
Based on the old crawler export system with enhanced FastAPI integration
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from .base import TimeStampedSchema


class ExportRequest(BaseModel):
    """Request schema for export operations"""
    land_id: int = Field(..., description="ID of the land to export")
    export_type: str = Field(..., description="Type of export (pagecsv, fullpagecsv, nodecsv, mediacsv, pagegexf, nodegexf, corpus)")
    minimum_relevance: int = Field(default=1, ge=0, le=10, description="Minimum relevance score filter")
    filename: Optional[str] = Field(None, description="Optional custom filename (without extension)")


class ExportResponse(BaseModel):
    """Response schema for export operations"""
    job_id: str = Field(..., description="Unique job identifier")
    export_type: str = Field(..., description="Type of export")
    land_id: int = Field(..., description="ID of the land being exported")
    status: str = Field(..., description="Job status (pending, running, completed, failed)")
    message: str = Field(..., description="Status message")


class ExportJob(BaseModel):
    """Schema for export job status"""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status (pending, running, completed, failed)")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Job progress percentage")
    message: str = Field(default="", description="Current status message")
    file_path: Optional[str] = Field(None, description="Path to completed export file")
    record_count: Optional[int] = Field(None, description="Number of records exported")
    error: Optional[str] = Field(None, description="Error message if failed")


# Legacy schemas for backward compatibility
class ExportBase(BaseModel):
    land_id: int
    export_type: str
    parameters: Optional[dict] = None


class ExportCreate(ExportBase):
    minimum_relevance: int = 1


class ExportUpdate(BaseModel):
    status: Optional[str] = None
    error_message: Optional[str] = None


class Export(TimeStampedSchema):
    id: int
    land_id: int
    export_type: str
    filename: str
    file_size: Optional[int] = None
    status: str
