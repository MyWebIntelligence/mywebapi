"""
Export endpoints for MyWebIntelligence API
Provides multiple export formats: CSV, GEXF, Corpus
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import os
import tempfile

from app.api.dependencies import get_db, get_current_active_user as get_current_user
from app.db.models import User
from app.services.export_service import ExportService
from app.crud.crud_land import land as land_crud
from app.schemas.export import ExportRequest, ExportResponse, ExportJob
from app.tasks.export_tasks import create_export_task


router = APIRouter()


@router.post("/csv", response_model=ExportResponse)
async def export_csv(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExportResponse:
    """
    Export land data to CSV format
    Supports pagecsv, fullpagecsv, nodecsv, mediacsv
    """
    # Validate land exists and user has access
    land = await land_crud.get(db, id=request.land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    
    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate CSV export type
    csv_types = ["pagecsv", "fullpagecsv", "nodecsv", "mediacsv",
                 "pseudolinks", "pseudolinkspage", "pseudolinksdomain",
                 "tagmatrix", "tagcontent"]
    if request.export_type not in csv_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid CSV export type. Must be one of: {', '.join(csv_types)}"
        )
    
    task_result = create_export_task.delay(
        export_type=request.export_type,
        land_id=request.land_id,
        minimum_relevance=request.minimum_relevance or 1,
        user_id=current_user.id,
    )

    return ExportResponse(
        job_id=task_result.id,
        export_type=request.export_type,
        land_id=request.land_id,
        status="pending",
        message="Export job created successfully"
    )


@router.post("/gexf", response_model=ExportResponse)
async def export_gexf(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExportResponse:
    """
    Export land data to GEXF format for network visualization
    Supports pagegexf, nodegexf
    """
    # Validate land exists and user has access
    land = await land_crud.get(db, id=request.land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")

    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate GEXF export type
    gexf_types = ["pagegexf", "nodegexf"]
    if request.export_type not in gexf_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid GEXF export type. Must be one of: {', '.join(gexf_types)}"
        )

    task_result = create_export_task.delay(
        export_type=request.export_type,
        land_id=request.land_id,
        minimum_relevance=request.minimum_relevance or 1,
        user_id=current_user.id,
    )

    return ExportResponse(
        job_id=task_result.id,
        export_type=request.export_type,
        land_id=request.land_id,
        status="pending",
        message="Export job created successfully"
    )


@router.post("/nodelinkcsv", response_model=ExportResponse)
async def export_nodelinkcsv(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExportResponse:
    """
    Export complete network data as a ZIP of 4 CSV files:
    pagesnodes, pageslinks, domainnodes, domainlinks
    """
    land = await land_crud.get(db, id=request.land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    task_result = create_export_task.delay(
        export_type="nodelinkcsv",
        land_id=request.land_id,
        minimum_relevance=request.minimum_relevance or 1,
        user_id=current_user.id,
    )

    return ExportResponse(
        job_id=task_result.id,
        export_type="nodelinkcsv",
        land_id=request.land_id,
        status="pending",
        message="NodeLinkCSV export job created successfully"
    )


@router.post("/corpus", response_model=ExportResponse)
async def export_corpus(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExportResponse:
    """
    Export land data to corpus ZIP format
    Creates a ZIP file with individual text files for each expression
    """
    # Validate land exists and user has access
    land = await land_crud.get(db, id=request.land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    
    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Force export type to corpus
    if request.export_type != "corpus":
        request.export_type = "corpus"
    
    task_result = create_export_task.delay(
        export_type="corpus",
        land_id=request.land_id,
        minimum_relevance=request.minimum_relevance or 1,
        user_id=current_user.id,
    )

    return ExportResponse(
        job_id=task_result.id,
        export_type="corpus",
        land_id=request.land_id,
        status="pending",
        message="Export job created successfully"
    )


@router.get("/jobs/{job_id}", response_model=ExportJob)
async def get_export_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
) -> ExportJob:
    """
    Get the status of an export job
    """
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app
    
    result = AsyncResult(job_id, app=celery_app)
    
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get job info
    job_info = result.info or {}
    
    status = result.status.lower() if result.status else "unknown"
    
    # Map Celery states to our states
    status_mapping = {
        "pending": "pending",
        "started": "running", 
        "retry": "running",
        "failure": "failed",
        "success": "completed"
    }
    
    mapped_status = status_mapping.get(status, "unknown")
    
    return ExportJob(
        job_id=job_id,
        status=mapped_status,
        progress=job_info.get("progress", 0),
        message=job_info.get("message", ""),
        file_path=job_info.get("file_path") if mapped_status == "completed" else None,
        record_count=job_info.get("record_count") if mapped_status == "completed" else None,
        error=str(result.result) if mapped_status == "failed" else None
    )


@router.get("/download/{job_id}")
async def download_export_file(
    job_id: str,
    current_user: User = Depends(get_current_user)
) -> FileResponse:
    """
    Download the exported file for a completed job
    """
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app
    
    result = AsyncResult(job_id, app=celery_app)
    
    if not result or result.status != "SUCCESS":
        raise HTTPException(
            status_code=404, 
            detail="Export job not found or not completed"
        )
    
    job_info = result.info or {}
    file_path = job_info.get("file_path")
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=404, 
            detail="Export file not found"
        )
    
    # Determine media type based on file extension
    filename = os.path.basename(file_path)
    if filename.endswith('.csv'):
        media_type = 'text/csv'
    elif filename.endswith('.gexf'):
        media_type = 'application/xml'
    elif filename.endswith('.zip'):
        media_type = 'application/zip'
    else:
        media_type = 'application/octet-stream'
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )


@router.post("/direct", response_model=dict)
async def export_direct(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Direct export - synchronous export for small datasets
    Use with caution for large datasets
    """
    # Validate land exists and user has access
    land = await land_crud.get(db, id=request.land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    
    if land.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate export type
    valid_types = ["pagecsv", "fullpagecsv", "nodecsv", "mediacsv",
                   "pagegexf", "nodegexf", "corpus", "nodelinkcsv",
                   "pseudolinks", "pseudolinkspage", "pseudolinksdomain",
                   "tagmatrix", "tagcontent"]
    if request.export_type not in valid_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid export type. Must be one of: {', '.join(valid_types)}"
        )
    
    try:
        # Create export service and perform export
        export_service = ExportService(db)
        file_path, record_count = await export_service.export_data(
            export_type=request.export_type,
            land_id=request.land_id,
            minimum_relevance=request.minimum_relevance
        )
        
        return {
            "file_path": file_path,
            "record_count": record_count,
            "export_type": request.export_type,
            "land_id": request.land_id,
            "status": "completed",
            "message": f"Export completed successfully. {record_count} records exported."
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}"
        )


@router.delete("/jobs/{job_id}")
async def cancel_export_job(
    job_id: str,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Cancel a running export job
    """
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app
    
    result = AsyncResult(job_id, app=celery_app)
    
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if result.status in ["SUCCESS", "FAILURE"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel job with status: {result.status}"
        )
    
    # Revoke the task
    celery_app.control.revoke(job_id, terminate=True)
    
    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": "Export job cancelled successfully"
    }
