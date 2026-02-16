"""
Readable pipeline schemas for request/response validation.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class MergeStrategy(str, Enum):
    """Strategies for merging content with existing data."""
    SMART_MERGE = "smart_merge"
    MERCURY_PRIORITY = "mercury_priority"
    PRESERVE_EXISTING = "preserve_existing"


class ReadableRequest(BaseModel):
    """Request schema for readable processing."""
    limit: Optional[int] = Field(None, ge=1, description="Maximum number of expressions to process")
    depth: Optional[int] = Field(None, ge=0, description="Maximum crawl depth to process")
    merge_strategy: MergeStrategy = Field(MergeStrategy.SMART_MERGE, description="Merge strategy for content fusion")
    enable_llm: bool = Field(False, description="Enable OpenRouter relevance check")


class ReadableRequestV2(ReadableRequest):
    """Extended request schema for v2 API."""
    batch_size: Optional[int] = Field(10, ge=1, le=50, description="Number of expressions to process per batch")
    max_concurrent: Optional[int] = Field(5, ge=1, le=20, description="Maximum concurrent batches")


class ReadableProcessingResult(BaseModel):
    """Result of readable processing operation."""
    processed: int = Field(description="Total number of expressions processed")
    updated: int = Field(description="Number of expressions updated")
    errors: int = Field(description="Number of processing errors")
    skipped: int = Field(description="Number of expressions skipped")
    media_created: int = Field(description="Number of media records created")
    links_created: int = Field(description="Number of expression links created")
    duration_seconds: float = Field(description="Processing duration in seconds")
    merge_strategy_used: MergeStrategy = Field(description="Merge strategy that was used")
    llm_validation_used: bool = Field(description="Whether LLM validation was enabled")
    wayback_fallbacks: int = Field(0, description="Number of wayback machine fallbacks used")


class ExtractionResult(BaseModel):
    """Result of content extraction for a single expression."""
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    readable: Optional[str] = None
    language: Optional[str] = None
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    media_urls: List[str] = Field(default_factory=list)
    link_urls: List[str] = Field(default_factory=list)
    extraction_source: str = Field(description="Source of extraction: trafilatura, archive, etc.")
    success: bool = Field(description="Whether extraction was successful")
    error_message: Optional[str] = None


class MediaInfo(BaseModel):
    """Information about media extracted from markdown."""
    url: str
    alt_text: Optional[str] = None
    title: Optional[str] = None
    media_type: str = Field(description="Type: image, video, audio")


class LinkInfo(BaseModel):
    """Information about links extracted from markdown."""
    url: str
    anchor_text: Optional[str] = None
    title: Optional[str] = None
    link_type: str = Field(default="internal", description="Type: internal, external")


class ValidationResult(BaseModel):
    """Result of LLM validation."""
    is_relevant: bool
    confidence: Optional[float] = None
    model_used: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    error_message: Optional[str] = None

    model_config = {
        "protected_namespaces": (),
    }


class ReadableStats(BaseModel):
    """Statistics for readable processing."""
    total_expressions: int
    expressions_with_readable: int
    expressions_without_readable: int
    expressions_eligible: int = Field(description="Expressions eligible for readable processing")
    last_processed_at: Optional[datetime] = None
    processing_coverage: float = Field(description="Percentage of expressions with readable content")