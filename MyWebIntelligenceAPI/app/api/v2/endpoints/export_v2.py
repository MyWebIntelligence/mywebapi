"""
Export endpoints v2
Real Celery task integration for all export formats.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import os

from app.api.dependencies import get_db, get_current_active_user
from app.db.models import User
from app.crud.crud_land import land as land_crud
from app.tasks.export_tasks import create_export_task
from pydantic import BaseModel

router = APIRouter()

# ── All supported export types ────────────────────────────
SUPPORTED_TYPES = {
    "csv": [
        "pagecsv", "fullpagecsv", "nodecsv", "mediacsv",
        "pseudolinks", "pseudolinkspage", "pseudolinksdomain",
        "tagmatrix", "tagcontent",
    ],
    "gexf": ["pagegexf", "nodegexf"],
    "zip": ["corpus", "nodelinkcsv"],
}
ALL_TYPES = [t for group in SUPPORTED_TYPES.values() for t in group]


class V2ExportRequest(BaseModel):
    """Export request for v2"""
    land_id: int
    export_type: str
    minimum_relevance: Optional[float] = 1


class V2ExportJobResponse(BaseModel):
    """Async job response for v2 exports"""
    job_id: str
    export_type: str
    land_id: int
    status: str
    created_at: datetime
    message: str
    tracking_url: str


class V2JobStatus(BaseModel):
    """Job status for v2"""
    job_id: str
    status: str  # pending, running, completed, failed, cancelled
    progress: int  # 0-100
    message: str
    file_path: Optional[str] = None
    record_count: Optional[int] = None
    error: Optional[str] = None


async def _validate_land_access(db, land_id: int, current_user: User):
    """Validate land exists and user owns it."""
    land = await land_crud.get(db, id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail=f"Land {land_id} not found")
    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return land


def _create_export_job(export_type: str, land_id: int, minimum_relevance: float, user_id: int) -> V2ExportJobResponse:
    """Launch a Celery export task and return the job response."""
    task_result = create_export_task.delay(
        export_type=export_type,
        land_id=land_id,
        minimum_relevance=int(minimum_relevance),
        user_id=user_id,
    )
    return V2ExportJobResponse(
        job_id=task_result.id,
        export_type=export_type,
        land_id=land_id,
        status="pending",
        created_at=datetime.now(),
        message=f"{export_type} export job created",
        tracking_url=f"/api/v2/export/jobs/{task_result.id}",
    )


@router.post("/", response_model=V2ExportJobResponse)
async def export_any(
    request_data: V2ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> V2ExportJobResponse:
    """
    Universal export endpoint — accepts any supported export_type.
    Launches a Celery task and returns a job ID for tracking.
    """
    if request_data.export_type not in ALL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid export type '{request_data.export_type}'. "
                   f"Supported: {', '.join(ALL_TYPES)}",
        )
    await _validate_land_access(db, request_data.land_id, current_user)
    return _create_export_job(
        request_data.export_type,
        request_data.land_id,
        request_data.minimum_relevance,
        current_user.id,
    )


@router.post("/csv", response_model=V2ExportJobResponse)
async def export_csv_v2(
    request_data: V2ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> V2ExportJobResponse:
    """Export land data to CSV format (async Celery task)."""
    csv_types = SUPPORTED_TYPES["csv"]
    if request_data.export_type not in csv_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CSV type. Must be one of: {', '.join(csv_types)}",
        )
    await _validate_land_access(db, request_data.land_id, current_user)
    return _create_export_job(
        request_data.export_type,
        request_data.land_id,
        request_data.minimum_relevance,
        current_user.id,
    )


@router.post("/gexf", response_model=V2ExportJobResponse)
async def export_gexf_v2(
    request_data: V2ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> V2ExportJobResponse:
    """Export land data to GEXF format (async Celery task)."""
    gexf_types = SUPPORTED_TYPES["gexf"]
    if request_data.export_type not in gexf_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid GEXF type. Must be one of: {', '.join(gexf_types)}",
        )
    await _validate_land_access(db, request_data.land_id, current_user)
    return _create_export_job(
        request_data.export_type,
        request_data.land_id,
        request_data.minimum_relevance,
        current_user.id,
    )


@router.post("/corpus", response_model=V2ExportJobResponse)
async def export_corpus_v2(
    request_data: V2ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> V2ExportJobResponse:
    """Export land data to corpus ZIP format (async Celery task)."""
    await _validate_land_access(db, request_data.land_id, current_user)
    return _create_export_job(
        "corpus",
        request_data.land_id,
        request_data.minimum_relevance,
        current_user.id,
    )


@router.post("/nodelinkcsv", response_model=V2ExportJobResponse)
async def export_nodelinkcsv_v2(
    request_data: V2ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> V2ExportJobResponse:
    """Export complete network as ZIP of 4 CSVs (async Celery task)."""
    await _validate_land_access(db, request_data.land_id, current_user)
    return _create_export_job(
        "nodelinkcsv",
        request_data.land_id,
        request_data.minimum_relevance,
        current_user.id,
    )


@router.get("/jobs/{job_id}", response_model=V2JobStatus)
async def get_export_job_status_v2(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
) -> V2JobStatus:
    """Get the status of an export Celery task."""
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app

    result = AsyncResult(job_id, app=celery_app)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    info = result.info or {}
    status_map = {
        "PENDING": "pending",
        "STARTED": "running",
        "PROGRESS": "running",
        "RETRY": "running",
        "FAILURE": "failed",
        "SUCCESS": "completed",
    }
    mapped = status_map.get(result.status, "unknown")

    return V2JobStatus(
        job_id=job_id,
        status=mapped,
        progress=info.get("progress", 0) if isinstance(info, dict) else (100 if mapped == "completed" else 0),
        message=info.get("message", "") if isinstance(info, dict) else "",
        file_path=info.get("file_path") if mapped == "completed" and isinstance(info, dict) else None,
        record_count=info.get("record_count") if mapped == "completed" and isinstance(info, dict) else None,
        error=str(result.result) if mapped == "failed" else None,
    )


@router.get("/download/{job_id}")
async def download_export_file_v2(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
) -> FileResponse:
    """Download the exported file for a completed job."""
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app

    result = AsyncResult(job_id, app=celery_app)
    if not result or result.status != "SUCCESS":
        raise HTTPException(status_code=404, detail="Export not found or not completed")

    info = result.info or {}
    file_path = info.get("file_path") if isinstance(info, dict) else None
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Export file not found")

    filename = os.path.basename(file_path)
    if filename.endswith(".csv"):
        media_type = "text/csv"
    elif filename.endswith(".gexf"):
        media_type = "application/xml"
    elif filename.endswith(".zip"):
        media_type = "application/zip"
    else:
        media_type = "application/octet-stream"

    return FileResponse(path=file_path, filename=filename, media_type=media_type)


@router.delete("/jobs/{job_id}")
async def cancel_export_job_v2(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Cancel a running export job."""
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app

    result = AsyncResult(job_id, app=celery_app)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    if result.status in ("SUCCESS", "FAILURE"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status {result.status}")

    celery_app.control.revoke(job_id, terminate=True)
    return {"job_id": job_id, "status": "cancelled", "message": "Export job cancelled"}


@router.get("/formats")
async def list_export_formats_v2() -> dict:
    """List all supported export formats."""
    return {
        "formats": {
            "csv": {
                "types": SUPPORTED_TYPES["csv"],
                "description": "Comma-separated values",
            },
            "gexf": {
                "types": SUPPORTED_TYPES["gexf"],
                "description": "Graph Exchange XML Format for network visualization",
            },
            "zip": {
                "types": SUPPORTED_TYPES["zip"],
                "description": "ZIP archives (corpus text files, nodelinkcsv network bundle)",
            },
        },
        "all_types": ALL_TYPES,
    }