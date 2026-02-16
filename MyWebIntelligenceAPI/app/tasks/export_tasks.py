"""
Celery tasks for export operations
Based on the old crawler export functionality
"""

import os
import uuid
from typing import Dict, Any
from celery import current_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.export_service_sync import SyncExportService
from app.crud.crud_land import land as land_crud


@celery_app.task(bind=True)
def create_export_task(
    self,
    export_type: str,
    land_id: int,
    minimum_relevance: int = 1,
    user_id: int = None,
    filename: str = None
) -> Dict[str, Any]:
    """
    Celery task for creating exports
    
    Args:
        export_type: Type of export (pagecsv, fullpagecsv, nodecsv, mediacsv, pagegexf, nodegexf, corpus)
        land_id: ID of the land to export
        minimum_relevance: Minimum relevance filter
        user_id: ID of the user requesting the export
        filename: Optional custom filename
        
    Returns:
        Dictionary with export results
    """
    task_id = self.request.id
    
    try:
        # Update task status
        self.update_state(
            state='STARTED',
            meta={
                'progress': 0,
                'message': f'Starting {export_type} export for land {land_id}',
                'export_type': export_type,
                'land_id': land_id
            }
        )
        
        # Create sync session for Celery (Celery workers run in sync context)
        from app.db.base import engine
        from sqlalchemy.orm import sessionmaker, Session
        
        # Create sync sessionmaker
        SyncSessionLocal = sessionmaker(bind=engine.sync_engine)
        
        db: Session = SyncSessionLocal()
        
        try:
            # Validate land exists
            land = db.query(land_crud.model).filter(land_crud.model.id == land_id).first()
            if not land:
                raise ValueError(f"Land with ID {land_id} not found")
            
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': 25,
                    'message': f'Land validated, creating {export_type} export',
                    'export_type': export_type,
                    'land_id': land_id
                }
            )
            
            # Create export service (we'll need a sync version or async wrapper)
            # For now, let's create a synchronous version of the export
            from app.services.export_service_sync import SyncExportService
            
            export_service = SyncExportService(db)
            
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': 50,
                    'message': f'Processing {export_type} export',
                    'export_type': export_type,
                    'land_id': land_id
                }
            )
            
            # Perform export
            file_path, record_count = export_service.export_data(
                export_type=export_type,
                land_id=land_id,
                minimum_relevance=minimum_relevance,
                filename=filename
            )
            
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': 90,
                    'message': f'Export completed, {record_count} records exported',
                    'export_type': export_type,
                    'land_id': land_id,
                    'record_count': record_count
                }
            )
            
            # Final success state
            result = {
                'progress': 100,
                'message': f'Export completed successfully',
                'export_type': export_type,
                'land_id': land_id,
                'file_path': file_path,
                'record_count': record_count,
                'task_id': task_id
            }
            
            return result
            
        finally:
            db.close()
            
    except Exception as exc:
        # Update task state with error
        self.update_state(
            state='FAILURE',
            meta={
                'progress': 0,
                'message': f'Export failed: {str(exc)}',
                'export_type': export_type,
                'land_id': land_id,
                'error': str(exc)
            }
        )
        raise exc


@celery_app.task(bind=True)
def batch_export_task(
    self,
    export_requests: list,
    user_id: int = None
) -> Dict[str, Any]:
    """
    Celery task for batch exports
    
    Args:
        export_requests: List of export request dictionaries
        user_id: ID of the user requesting the exports
        
    Returns:
        Dictionary with batch export results
    """
    task_id = self.request.id
    total_requests = len(export_requests)
    results = []
    
    try:
        self.update_state(
            state='STARTED',
            meta={
                'progress': 0,
                'message': f'Starting batch export of {total_requests} requests',
                'total_requests': total_requests
            }
        )
        
        for i, request in enumerate(export_requests):
            try:
                # Update progress
                progress = int((i / total_requests) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'progress': progress,
                        'message': f'Processing request {i+1} of {total_requests}',
                        'current_request': i + 1,
                        'total_requests': total_requests
                    }
                )
                
                # Execute individual export
                result = create_export_task.apply_async(
                    args=[
                        request['export_type'],
                        request['land_id'],
                        request.get('minimum_relevance', 1),
                        user_id,
                        request.get('filename')
                    ]
                ).get()
                
                results.append({
                    'request_index': i,
                    'success': True,
                    'result': result
                })
                
            except Exception as e:
                results.append({
                    'request_index': i,
                    'success': False,
                    'error': str(e)
                })
        
        # Final result
        successful_exports = sum(1 for r in results if r['success'])
        failed_exports = total_requests - successful_exports
        
        return {
            'progress': 100,
            'message': f'Batch export completed: {successful_exports} successful, {failed_exports} failed',
            'total_requests': total_requests,
            'successful_exports': successful_exports,
            'failed_exports': failed_exports,
            'results': results,
            'task_id': task_id
        }
        
    except Exception as exc:
        self.update_state(
            state='FAILURE',
            meta={
                'progress': 0,
                'message': f'Batch export failed: {str(exc)}',
                'error': str(exc)
            }
        )
        raise exc


@celery_app.task(bind=True)
def cleanup_export_files_task(self, max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Celery task to clean up old export files
    
    Args:
        max_age_hours: Maximum age of files to keep in hours
        
    Returns:
        Dictionary with cleanup results
    """
    import tempfile
    import time
    from pathlib import Path
    
    task_id = self.request.id
    
    try:
        self.update_state(
            state='STARTED',
            meta={
                'progress': 0,
                'message': f'Starting cleanup of export files older than {max_age_hours} hours'
            }
        )
        
        temp_dir = Path(tempfile.gettempdir())
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        deleted_files = []
        total_size_freed = 0
        
        # Find export files
        export_patterns = [
            'export_*_*.csv',
            'export_*_*.gexf', 
            'export_*_*.zip'
        ]
        
        files_to_check = []
        for pattern in export_patterns:
            files_to_check.extend(temp_dir.glob(pattern))
        
        total_files = len(files_to_check)
        
        for i, file_path in enumerate(files_to_check):
            try:
                # Update progress
                progress = int((i / max(total_files, 1)) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'progress': progress,
                        'message': f'Checking file {i+1} of {total_files}',
                        'current_file': str(file_path.name)
                    }
                )
                
                # Check file age
                file_age = current_time - file_path.stat().st_mtime
                
                if file_age > max_age_seconds:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    
                    deleted_files.append({
                        'filename': str(file_path.name),
                        'size': file_size,
                        'age_hours': round(file_age / 3600, 1)
                    })
                    total_size_freed += file_size
                    
            except Exception as e:
                # Log error but continue with other files
                continue
        
        return {
            'progress': 100,
            'message': f'Cleanup completed: {len(deleted_files)} files deleted, {total_size_freed} bytes freed',
            'deleted_files_count': len(deleted_files),
            'total_size_freed': total_size_freed,
            'deleted_files': deleted_files,
            'task_id': task_id
        }
        
    except Exception as exc:
        self.update_state(
            state='FAILURE',
            meta={
                'progress': 0,
                'message': f'Cleanup failed: {str(exc)}',
                'error': str(exc)
            }
        )
        raise exc


# Convenience functions for backward compatibility
def export_land_task(land_id: int, export_type: str, minimum_relevance: int = 1):
    """Legacy function for backward compatibility"""
    return create_export_task.delay(
        export_type=export_type,
        land_id=land_id,
        minimum_relevance=minimum_relevance
    )