"""
Tests d'intégration pour les endpoints readable.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.schemas.readable import MergeStrategy


class TestReadableEndpoints:
    """Tests d'intégration pour les endpoints readable."""
    
    @pytest.fixture
    def client(self):
        """Client de test FastAPI."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Headers d'authentification pour les tests."""
        # En production, ceci serait un vrai token JWT
        return {"Authorization": "Bearer test-token"}
    
    @pytest.fixture
    def mock_land(self):
        """Mock de land pour les tests."""
        from app.db.models import Land
        land = Land()
        land.id = 1
        land.name = "Test Land"
        land.description = "Test land description"
        land.owner_id = 1
        land.words = [{"word": "test"}, {"word": "example"}]
        return land
    
    @pytest.fixture
    def mock_user(self):
        """Mock d'utilisateur pour les tests."""
        from app.db.models import User
        user = User()
        user.id = 1
        user.email = "test@example.com"
        return user
    
    @patch('app.api.dependencies.get_current_active_user')
    @patch('app.api.dependencies.get_db')
    @patch('app.crud.crud_land.land.get')
    @patch('app.crud.crud_job.job.create')
    @patch('app.crud.crud_job.job.update')
    @patch('app.tasks.readable_task.process_readable_task.delay')
    def test_v1_readable_endpoint_success(
        self,
        mock_task_delay,
        mock_job_update,
        mock_job_create,
        mock_land_get,
        mock_get_db,
        mock_get_user,
        client,
        mock_land,
        mock_user
    ):
        """Test de l'endpoint v1 readable avec succès."""
        # Configuration des mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = AsyncMock()
        mock_land_get.return_value = mock_land
        
        # Mock de la création de job
        mock_job = AsyncMock()
        mock_job.id = 123
        mock_job_create.return_value = mock_job
        
        # Mock de la tâche Celery
        mock_task_result = AsyncMock()
        mock_task_result.id = "celery-task-id"
        mock_task_delay.return_value = mock_task_result
        
        # Test
        response = client.post(
            "/api/v1/lands/1/readable",
            json={
                "limit": 10,
                "depth": 2,
                "merge_strategy": "smart_merge",
                "enable_llm": False
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == 123
        assert data["task_id"] == "celery-task-id"
        assert data["parameters"]["limit"] == 10
        assert data["parameters"]["merge_strategy"] == "smart_merge"
        assert "Readable processing started" in data["message"]
        
        # Vérifier que la tâche a été lancée
        mock_task_delay.assert_called_once()
        mock_job_create.assert_called_once()
    
    @patch('app.api.dependencies.get_current_active_user')
    @patch('app.api.dependencies.get_db')
    @patch('app.crud.crud_land.land.get')
    def test_v1_readable_endpoint_land_not_found(
        self,
        mock_land_get,
        mock_get_db,
        mock_get_user,
        client,
        mock_user
    ):
        """Test de l'endpoint v1 avec land non trouvé."""
        # Configuration des mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = AsyncMock()
        mock_land_get.return_value = None  # Land non trouvé
        
        # Test
        response = client.post(
            "/api/v1/lands/999/readable",
            json={},
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Vérifications
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    @patch('app.api.dependencies.get_current_active_user')
    @patch('app.api.dependencies.get_db')
    @patch('app.crud.crud_land.land.get')
    def test_v1_readable_endpoint_permission_denied(
        self,
        mock_land_get,
        mock_get_db,
        mock_get_user,
        client,
        mock_land,
        mock_user
    ):
        """Test de l'endpoint v1 avec permission refusée."""
        # Configuration des mocks
        mock_user.id = 2  # Utilisateur différent
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = AsyncMock()
        mock_land.owner_id = 1  # Land appartient à un autre utilisateur
        mock_land_get.return_value = mock_land
        
        # Test
        response = client.post(
            "/api/v1/lands/1/readable",
            json={},
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Vérifications
        assert response.status_code == 404  # Retourne 404 pour cacher l'existence
        data = response.json()
        assert "not found" in data["detail"].lower() or "permission" in data["detail"].lower()
    
    @patch('app.api.dependencies.get_current_active_user')
    @patch('app.api.dependencies.get_db')
    @patch('app.crud.crud_land.land.get')
    @patch('app.crud.crud_job.job.create')
    @patch('app.crud.crud_job.job.update')
    @patch('app.tasks.readable_task.process_readable_task.delay')
    @patch('app.services.readable_service.ReadableService.get_readable_stats')
    def test_v2_readable_endpoint_success(
        self,
        mock_get_stats,
        mock_task_delay,
        mock_job_update,
        mock_job_create,
        mock_land_get,
        mock_get_db,
        mock_get_user,
        client,
        mock_land,
        mock_user
    ):
        """Test de l'endpoint v2 readable avec succès."""
        # Configuration des mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = AsyncMock()
        mock_land_get.return_value = mock_land
        
        # Mock de la création de job
        mock_job = AsyncMock()
        mock_job.id = 123
        mock_job_create.return_value = mock_job
        
        # Mock de la tâche Celery
        mock_task_result = AsyncMock()
        mock_task_result.id = "celery-task-id"
        mock_task_delay.return_value = mock_task_result
        
        # Mock des statistiques
        from app.schemas.readable import ReadableStats
        mock_stats = ReadableStats(
            total_expressions=100,
            expressions_with_readable=75,
            expressions_without_readable=25,
            expressions_eligible=20,
            processing_coverage=75.0
        )
        mock_get_stats.return_value = mock_stats
        
        # Test
        response = client.post(
            "/api/v2/lands/1/readable",
            json={
                "limit": 20,
                "depth": 3,
                "merge_strategy": "mercury_priority",
                "enable_llm": True,
                "batch_size": 15,
                "max_concurrent": 8
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Vérifications
        assert response.status_code == 200
        data = response.json()
        
        # Structure de réponse v2
        assert data["success"] is True
        assert data["job_id"] == 123
        assert data["task_id"] == "celery-task-id"
        assert data["celery_task_id"] == "celery-task-id"
        assert data["ws_channel"] == "job_123"
        
        # Paramètres
        params = data["parameters"]
        assert params["limit"] == 20
        assert params["depth"] == 3
        assert params["merge_strategy"] == "mercury_priority"
        assert params["enable_llm"] is True
        assert params["batch_size"] == 15
        assert params["max_concurrent"] == 8
        
        # Informations de traitement
        info = data["processing_info"]
        assert info["total_expressions"] == 100
        assert info["expressions_eligible"] == 20
        assert info["expressions_with_readable"] == 75
        assert info["processing_coverage"] == "75.0%"
        
        # Informations de suivi
        tracking = data["tracking"]
        assert tracking["job_status_endpoint"] == "/api/v2/jobs/123"
        assert tracking["websocket_channel"] == "job_123"
        assert tracking["land_channel"] == "land_1"
        
        # Estimation de temps
        assert "estimated_time" in data
    
    @patch('app.api.dependencies.get_current_active_user')
    @patch('app.api.dependencies.get_db')
    @patch('app.crud.crud_land.land.get')
    def test_v2_readable_endpoint_error_handling(
        self,
        mock_land_get,
        mock_get_db,
        mock_get_user,
        client,
        mock_user
    ):
        """Test de gestion d'erreur de l'endpoint v2."""
        # Configuration des mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = AsyncMock()
        mock_land_get.return_value = None  # Land non trouvé
        
        # Test
        response = client.post(
            "/api/v2/lands/999/readable",
            json={},
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Vérifications format d'erreur v2
        assert response.status_code == 404
        data = response.json()
        detail = data["detail"]
        assert detail["error_code"] == "LAND_NOT_FOUND"
        assert "not found" in detail["message"]
        assert detail["details"]["land_id"] == 999
        assert "suggestion" in detail
    
    def test_v1_readable_endpoint_parameter_validation(self, client):
        """Test de validation des paramètres v1."""
        # Test avec paramètres invalides
        response = client.post(
            "/api/v1/lands/1/readable",
            json={
                "limit": -1,  # Limite négative
                "depth": -1,  # Profondeur négative
                "merge_strategy": "invalid_strategy",  # Stratégie invalide
                "enable_llm": "not_boolean"  # Type incorrect
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Vérifications
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    def test_v2_readable_endpoint_parameter_validation(self, client):
        """Test de validation des paramètres v2."""
        # Test avec paramètres invalides
        response = client.post(
            "/api/v2/lands/1/readable",
            json={
                "limit": 0,  # Limite trop petite
                "batch_size": 100,  # Batch trop gros (max 50)
                "max_concurrent": 25  # Concurrence trop élevée (max 20)
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Vérifications
        assert response.status_code == 422  # Validation error
    
    def test_readable_endpoints_require_authentication(self, client):
        """Test que les endpoints requièrent une authentification."""
        # Test endpoint v1 sans authentification
        response_v1 = client.post("/api/v1/lands/1/readable", json={})
        assert response_v1.status_code == 401  # Unauthorized
        
        # Test endpoint v2 sans authentification
        response_v2 = client.post("/api/v2/lands/1/readable", json={})
        assert response_v2.status_code == 401  # Unauthorized
    
    @patch('app.api.dependencies.get_current_active_user')
    @patch('app.api.dependencies.get_db')
    @patch('app.crud.crud_land.land.get')
    @patch('app.crud.crud_job.job.create')
    def test_readable_endpoint_defaults(
        self,
        mock_job_create,
        mock_land_get,
        mock_get_db,
        mock_get_user,
        client,
        mock_land,
        mock_user
    ):
        """Test des valeurs par défaut des endpoints."""
        # Configuration des mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = AsyncMock()
        mock_land_get.return_value = mock_land
        
        # Mock de la création de job
        mock_job = AsyncMock()
        mock_job.id = 123
        mock_job_create.return_value = mock_job
        
        with patch('app.tasks.readable_task.process_readable_task.delay') as mock_task:
            mock_task.return_value.id = "task-id"
            
            # Test v1 avec paramètres par défaut
            response_v1 = client.post(
                "/api/v1/lands/1/readable",
                json={},  # Pas de paramètres
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response_v1.status_code == 200
            data_v1 = response_v1.json()
            params_v1 = data_v1["parameters"]
            assert params_v1["merge_strategy"] == "smart_merge"
            assert params_v1["enable_llm"] is False
            
            # Test v2 avec paramètres par défaut
            with patch('app.services.readable_service.ReadableService.get_readable_stats') as mock_stats:
                from app.schemas.readable import ReadableStats
                mock_stats.return_value = ReadableStats(
                    total_expressions=0,
                    expressions_with_readable=0,
                    expressions_without_readable=0,
                    expressions_eligible=0,
                    processing_coverage=0.0
                )
                
                response_v2 = client.post(
                    "/api/v2/lands/1/readable",
                    json={},  # Pas de paramètres
                    headers={"Authorization": "Bearer test-token"}
                )
                
                assert response_v2.status_code == 200
                data_v2 = response_v2.json()
                params_v2 = data_v2["parameters"]
                assert params_v2["merge_strategy"] == "smart_merge"
                assert params_v2["enable_llm"] is False
                assert params_v2["batch_size"] == 10
                assert params_v2["max_concurrent"] == 5


@pytest.mark.asyncio
class TestReadableEndpointsIntegration:
    """Tests d'intégration complets pour les endpoints readable."""
    
    async def test_full_readable_workflow_with_database(self):
        """Test complet du workflow readable avec base de données."""
        # Ce test nécessiterait une vraie base de données de test
        pytest.skip("Requires real database setup")
    
    async def test_readable_with_real_celery_worker(self):
        """Test avec un vrai worker Celery."""
        # Ce test nécessiterait un worker Celery en fonctionnement
        pytest.skip("Requires real Celery worker")
    
    async def test_websocket_progress_updates(self):
        """Test des mises à jour de progression via WebSocket."""
        # Ce test nécessiterait une configuration WebSocket
        pytest.skip("Requires WebSocket test setup")