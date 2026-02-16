"""
Tests unitaires pour le CrawlingService

Tests critiques pour la couche service de crawling :
- Validation des paramètres de crawl
- Création et dispatch des jobs Celery
- Gestion des erreurs de dispatch
- Setup des channels WebSocket
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi import HTTPException

from app.services.crawling_service import start_crawl_for_land
from app.schemas.job import CrawlStatus, CrawlRequest


@pytest.mark.asyncio
class TestCrawlingService:
    """Tests pour le service de crawling"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.mock_db = AsyncMock()
        self.land_id = 1
        self.crawl_request = CrawlRequest(limit=100, depth=3, http_status=None)
    
    async def test_start_crawl_for_land_success(self):
        """Test lancement de crawl réussi"""
        # Setup
        mock_land = MagicMock()
        mock_land.id = 1
        mock_land.name = "Test Land"
        
        mock_job = MagicMock()
        mock_job.id = 123
        mock_job.land_id = 1
        mock_job.job_type = 'crawl'
        mock_job.status = CrawlStatus.PENDING
        mock_job.created_at = datetime.now()
        
        mock_task = MagicMock()
        mock_task.id = "celery-task-456"
        
        with patch('app.crud.crud_land.land.get') as mock_get_land, \
             patch('app.crud.crud_job.job.create') as mock_create_job, \
             patch('app.core.celery_app.celery_app.send_task') as mock_send_task:
            
            mock_get_land.return_value = mock_land
            mock_create_job.return_value = mock_job
            mock_send_task.return_value = mock_task
            
            # Execute
            result = await start_crawl_for_land(
                db=self.mock_db,
                land_id=self.land_id,
                crawl_request=self.crawl_request
            )
            
            # Verify
            assert result["job_id"] == 123
            assert result["ws_channel"] == "crawl_progress_123"
            assert result["status"] == CrawlStatus.PENDING.value
            
            # Verify land lookup
            mock_get_land.assert_called_once_with(self.mock_db, id=1)
            
            # Verify job creation
            mock_create_job.assert_called_once()
            create_args = mock_create_job.call_args[1]
            assert create_args['obj_in'].land_id == 1
            assert create_args['obj_in'].job_type == "crawl"
            assert create_args['obj_in'].parameters['limit'] == 100
            assert create_args['obj_in'].parameters['depth'] == 3
            assert create_args['obj_in'].parameters['http_status'] is None
            
            # Verify task dispatch (V2 sync: no ws_channel kwarg)
            mock_send_task.assert_called_once_with(
                "tasks.crawl_land_task",
                args=[123]
            )
    
    async def test_start_crawl_for_land_with_all_parameters(self):
        """Test lancement de crawl avec tous les paramètres"""
        # Setup
        mock_land = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 123
        mock_task = MagicMock()
        mock_task.id = "celery-task-456"
        
        crawl_request = CrawlRequest(limit=500, depth=5, http_status="200")
        
        with patch('app.crud.crud_land.land.get') as mock_get_land, \
             patch('app.crud.crud_job.job.create') as mock_create_job, \
             patch('app.core.celery_app.celery_app.send_task') as mock_send_task:
            
            mock_get_land.return_value = mock_land
            mock_create_job.return_value = mock_job
            mock_send_task.return_value = mock_task
            
            # Execute avec tous les paramètres
            await start_crawl_for_land(
                db=self.mock_db,
                land_id=self.land_id,
                crawl_request=crawl_request
            )
            
            # Verify parameters
            create_args = mock_create_job.call_args[1]
            assert create_args['obj_in'].parameters['limit'] == 500
            assert create_args['obj_in'].parameters['depth'] == 5
            assert create_args['obj_in'].parameters['http_status'] == 200
    
    async def test_start_crawl_for_land_land_not_found(self):
        """Test land inexistant"""
        with patch('app.crud.crud_land.land.get') as mock_get_land:
            mock_get_land.return_value = None
            
            # Execute et vérifier que HTTPException est levée
            with pytest.raises(HTTPException) as exc_info:
                await start_crawl_for_land(
                    db=self.mock_db,
                    land_id=999,
                    crawl_request=self.crawl_request
                )
            
            assert exc_info.value.status_code == 404
            assert "Land not found" in str(exc_info.value.detail)
    
    async def test_start_crawl_for_land_invalid_depth(self):
        """Test validation profondeur négative"""
        mock_land = MagicMock()
        
        with patch('app.crud.crud_land.land.get') as mock_get_land:
            mock_get_land.return_value = mock_land
            
            # Execute avec profondeur négative
            invalid_request = CrawlRequest(limit=None, depth=-1, http_status=None)
            
            with pytest.raises(HTTPException) as exc_info:
                await start_crawl_for_land(
                    db=self.mock_db,
                    land_id=self.land_id,
                    crawl_request=invalid_request
                )
            
            assert exc_info.value.status_code == 422
            assert "Depth must be a positive integer" in str(exc_info.value.detail)
    
    async def test_start_crawl_for_land_invalid_limit(self):
        """Test validation limite zéro ou négative"""
        mock_land = MagicMock()
        
        with patch('app.crud.crud_land.land.get') as mock_get_land:
            mock_get_land.return_value = mock_land
            
            # Execute avec limite zéro
            invalid_request = CrawlRequest(limit=0, depth=None, http_status=None)
            
            with pytest.raises(HTTPException) as exc_info:
                await start_crawl_for_land(
                    db=self.mock_db,
                    land_id=self.land_id,
                    crawl_request=invalid_request
                )
            
            assert exc_info.value.status_code == 422
            assert "Limit must be a positive integer" in str(exc_info.value.detail)
    
    async def test_start_crawl_for_land_task_dispatch_failure(self):
        """Test échec de dispatch de la tâche Celery"""
        mock_land = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 123
        
        with patch('app.crud.crud_land.land.get') as mock_get_land, \
             patch('app.crud.crud_job.job.create') as mock_create_job, \
             patch('app.core.celery_app.celery_app.send_task') as mock_send_task, \
             patch('app.crud.crud_job.job.update_status') as mock_update_status:
            
            mock_get_land.return_value = mock_land
            mock_create_job.return_value = mock_job
            mock_send_task.side_effect = Exception("Celery broker error")
            
            # Execute et vérifier que HTTPException est levée
            with pytest.raises(HTTPException) as exc_info:
                await start_crawl_for_land(
                    db=self.mock_db,
                    land_id=self.land_id,
                    crawl_request=self.crawl_request
                )
            
            assert exc_info.value.status_code == 500
            assert "Crawl task dispatch failed" in str(exc_info.value.detail)
            
            # Verify que le job est marqué comme failed
            mock_update_status.assert_called_once()
    
    async def test_start_crawl_for_land_websocket_channel_format(self):
        """Test format du channel WebSocket"""
        mock_land = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 999
        mock_task = MagicMock()
        mock_task.id = "celery-task-999"
        
        with patch('app.crud.crud_land.land.get') as mock_get_land, \
             patch('app.crud.crud_job.job.create') as mock_create_job, \
             patch('app.core.celery_app.celery_app.send_task') as mock_send_task:
            
            mock_get_land.return_value = mock_land
            mock_create_job.return_value = mock_job
            mock_send_task.return_value = mock_task
            
            # Execute
            result = await start_crawl_for_land(
                db=self.mock_db,
                land_id=self.land_id,
                crawl_request=self.crawl_request
            )
            
            # Verify WebSocket channel format
            assert result["ws_channel"] == "crawl_progress_999"

            # Verify task dispatch (V2 sync: no ws_channel kwarg)
            mock_send_task.assert_called_once_with(
                "tasks.crawl_land_task",
                args=[999]
            )
    
    async def test_start_crawl_for_land_job_parameters_structure(self):
        """Test structure des paramètres du job"""
        mock_land = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 123
        mock_task = MagicMock()
        
        with patch('app.crud.crud_land.land.get') as mock_get_land, \
             patch('app.crud.crud_job.job.create') as mock_create_job, \
             patch('app.core.celery_app.celery_app.send_task') as mock_send_task:
            
            mock_get_land.return_value = mock_land
            mock_create_job.return_value = mock_job
            mock_send_task.return_value = mock_task
            
            crawl_request = CrawlRequest(limit=200, depth=4, http_status="404")
            
            # Execute
            await start_crawl_for_land(
                db=self.mock_db,
                land_id=self.land_id,
                crawl_request=crawl_request
            )
            
            # Verify job creation parameters
            create_args = mock_create_job.call_args[1]
            job_create = create_args['obj_in']
            assert job_create.land_id == 1
            assert job_create.job_type == "crawl"
            assert isinstance(job_create.parameters, dict)
            
            params = create_args['obj_in'].parameters
            assert params['limit'] == 200
            assert params['depth'] == 4
            assert params['http_status'] == 404
    
    async def test_start_crawl_for_land_default_parameters(self):
        """Test paramètres par défaut (None)"""
        mock_land = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 123
        mock_task = MagicMock()
        
        with patch('app.crud.crud_land.land.get') as mock_get_land, \
             patch('app.crud.crud_job.job.create') as mock_create_job, \
             patch('app.core.celery_app.celery_app.send_task') as mock_send_task:
            
            mock_get_land.return_value = mock_land
            mock_create_job.return_value = mock_job
            mock_send_task.return_value = mock_task
            
            # Execute sans paramètres optionnels
            default_request = CrawlRequest(limit=None, depth=None, http_status=None)
            await start_crawl_for_land(
                db=self.mock_db,
                land_id=self.land_id,
                crawl_request=default_request
            )
            
            # Verify default parameters
            create_args = mock_create_job.call_args[1]
            params = create_args['obj_in'].parameters
            assert params['limit'] is None
            assert params['depth'] is None
            assert params['http_status'] is None
    
    async def test_start_crawl_for_land_celery_id_update(self):
        """Test mise à jour de l'ID Celery et commit DB"""
        mock_land = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 123
        mock_task = MagicMock()
        mock_task.id = "celery-task-456"
        
        with patch('app.crud.crud_land.land.get') as mock_get_land, \
             patch('app.crud.crud_job.job.create') as mock_create_job, \
             patch('app.core.celery_app.celery_app.send_task') as mock_send_task:
            
            mock_get_land.return_value = mock_land
            mock_create_job.return_value = mock_job
            mock_send_task.return_value = mock_task
            
            # Execute
            await start_crawl_for_land(
                db=self.mock_db,
                land_id=self.land_id,
                crawl_request=self.crawl_request
            )
            
            # Verify que l'ID Celery est mis à jour
            assert mock_job.celery_task_id == "celery-task-456"

            # Verify commit et refresh (called twice: once after create, once after celery_task_id update)
            assert self.mock_db.commit.call_count == 2
            assert self.mock_db.refresh.call_count == 2
