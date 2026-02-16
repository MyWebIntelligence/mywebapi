"""
Tests unitaires pour l'endpoint Jobs

Tests critiques pour la gestion des statuts de tâches Celery :
- Validation des différents statuts (SUCCESS, FAILURE, PENDING, RUNNING)
- Gestion des jobs inexistants (404)
- Traceback d'erreurs
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from celery.result import AsyncResult
from app.api.v1.endpoints.jobs import get_job_status


@pytest.mark.asyncio
class TestJobsEndpoint:
    """Tests pour l'endpoint Jobs utilisant AsyncResult de Celery"""
    
    async def test_get_job_status_success(self):
        """Test récupération statut job avec succès"""
        job_id = "task-123"
        
        # Mock AsyncResult pour un job terminé avec succès
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.result = {"processed": 25, "errors": 0}
        mock_result.traceback = None
        
        with patch('app.api.v1.endpoints.jobs.AsyncResult', return_value=mock_result):
            result = await get_job_status(job_id)
            
            assert result.job_id == job_id
            assert result.status == "SUCCESS"
            assert result.progress == 100
            assert result.result == {"processed": 25, "errors": 0}
            assert result.error_message is None
    
    async def test_get_job_status_failure(self):
        """Test job en échec avec traceback"""
        job_id = "task-456"
        
        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.ready.return_value = True
        mock_result.result = Exception("Network timeout")
        mock_result.traceback = "Traceback (most recent call last):\n  File...\nException: Network timeout"
        
        with patch('app.api.v1.endpoints.jobs.AsyncResult', return_value=mock_result):
            result = await get_job_status(job_id)
            
            assert result.job_id == job_id
            assert result.status == "FAILURE"
            assert result.progress == 0
            assert "Network timeout" in result.result
            assert "Traceback" in result.error_message
    
    async def test_get_job_status_pending(self):
        """Test job en attente"""
        job_id = "task-789"
        
        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_result.ready.return_value = False
        mock_result.result = None
        
        with patch('app.api.v1.endpoints.jobs.AsyncResult', return_value=mock_result):
            result = await get_job_status(job_id)
            
            assert result.job_id == job_id
            assert result.status == "PENDING"
            assert result.progress == 0
            assert result.result is None
            assert result.error_message is None
    
    async def test_get_job_status_running_with_progress(self):
        """Test job en cours avec progression"""
        job_id = "task-running"
        
        mock_result = MagicMock()
        mock_result.status = "PROGRESS"
        mock_result.ready.return_value = False
        mock_result.result = {"progress": 45, "current_step": "Processing page 23/50"}
        
        with patch('app.api.v1.endpoints.jobs.AsyncResult', return_value=mock_result):
            result = await get_job_status(job_id)
            
            assert result.job_id == job_id
            assert result.status == "PROGRESS"
            assert result.progress == 45
            assert result.result["current_step"] == "Processing page 23/50"
    
    async def test_get_job_status_running_no_progress(self):
        """Test job en cours sans info de progression"""
        job_id = "task-no-progress"
        
        mock_result = MagicMock()
        mock_result.status = "RUNNING"
        mock_result.ready.return_value = False
        mock_result.result = {"some_data": "value"}
        
        with patch('app.api.v1.endpoints.jobs.AsyncResult', return_value=mock_result):
            result = await get_job_status(job_id)
            
            assert result.job_id == job_id
            assert result.status == "RUNNING"
            assert result.progress == 0  # Default quand pas de progress
            assert result.result["some_data"] == "value"
    
    async def test_get_job_status_not_found(self):
        """Test job inexistant"""
        job_id = "nonexistent-job"
        
        # Mock AsyncResult qui retourne None/False
        mock_result = MagicMock()
        mock_result.__bool__ = lambda self: False
        
        with patch('app.api.v1.endpoints.jobs.AsyncResult', return_value=mock_result):
            with pytest.raises(HTTPException) as exc_info:
                await get_job_status(job_id)
            
            assert exc_info.value.status_code == 404
            assert "Job not found" in str(exc_info.value.detail)
    
    async def test_job_status_model_creation(self):
        """Test création du modèle JobStatus avec différents paramètres"""
        from app.schemas.job import JobStatus
        
        # Test avec tous les champs
        job_status = JobStatus(
            job_id="test-123",
            status="SUCCESS",
            progress=100,
            result={"data": "test"},
            error_message=None
        )
        
        assert job_status.job_id == "test-123"
        assert job_status.status == "SUCCESS"
        assert job_status.progress == 100
        assert job_status.result == {"data": "test"}
        assert job_status.error_message is None
        
        # Test avec erreur
        job_error = JobStatus(
            job_id="error-123",
            status="FAILURE",
            progress=0,
            result="Error occurred",
            error_message="Full traceback here"
        )
        
        assert job_error.status == "FAILURE"
        assert job_error.error_message == "Full traceback here"
