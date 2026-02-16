"""
Tests simples pour les fonctionnalités d'export
Validation des services d'export et endpoints
"""

import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.services.export_service_sync import SyncExportService
from app.schemas.export import ExportRequest


class TestExportServices:
    """Tests pour les services d'export"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.mock_db = MagicMock(spec=Session)
        self.export_service = SyncExportService(self.mock_db)
    
    def test_export_service_initialization(self):
        """Test d'initialisation du service d'export"""
        assert self.export_service.db == self.mock_db
        assert hasattr(self.export_service, 'GEXF_NS')
        assert 'http://www.gexf.net/1.2draft' in self.export_service.GEXF_NS.values()
    
    def test_available_export_methods(self):
        """Test que tous les formats d'export sont disponibles"""
        expected_methods = [
            'write_pagecsv',
            'write_fullpagecsv', 
            'write_nodecsv',
            'write_mediacsv',
            'write_pagegexf',
            'write_nodegexf',
            'write_corpus'
        ]
        
        for method_name in expected_methods:
            assert hasattr(self.export_service, method_name)
            method = getattr(self.export_service, method_name)
            assert callable(method)
    
    def test_slugify_method(self):
        """Test de la méthode slugify"""
        test_cases = [
            ("Test Title", "test-title"),
            ("Café français", "cafe-francais"),
            ("Special@#$%Characters!", "special-characters"),
            ("", "untitled"),
            ("Multiple   Spaces", "multiple-spaces"),
            ("Very Long Title That Should Be Truncated Because It Is Too Long For Normal Use", "very-long-title-that-should-be-truncated-because-i")
        ]
        
        for input_text, expected in test_cases:
            result = self.export_service.slugify(input_text)
            assert result == expected
    
    def test_create_metadata(self):
        """Test de création des métadonnées pour corpus"""
        test_row = {
            'id': 123,
            'title': 'Test Article',
            'description': 'Test description',
            'domain': 'example.com',
            'url': 'https://example.com/test'
        }
        
        metadata = self.export_service.create_metadata(test_row)
        
        assert 'Title: "Test Article"' in metadata
        assert 'Description: "Test description"' in metadata
        assert 'Identifier: "123"' in metadata
        assert 'Publisher: "example.com"' in metadata
        assert 'Source: "https://example.com/test"' in metadata
        assert metadata.startswith('---')
        assert metadata.count('---') == 2
    
    @patch('app.services.export_service_sync.SyncExportService.get_sql_data')
    @patch('app.services.export_service_sync.SyncExportService.write_csv_file')
    def test_write_pagecsv(self, mock_write_csv, mock_get_sql):
        """Test d'export CSV basique"""
        # Mock data
        mock_data = [
            {'id': 1, 'url': 'https://example.com', 'title': 'Test', 'relevance': 5},
            {'id': 2, 'url': 'https://example2.com', 'title': 'Test 2', 'relevance': 7}
        ]
        mock_get_sql.return_value = mock_data
        mock_write_csv.return_value = 2
        
        # Execute
        filename = "/tmp/test_export.csv"
        count = self.export_service.write_pagecsv(filename, land_id=1, minimum_relevance=1)
        
        # Verify
        mock_get_sql.assert_called_once()
        mock_write_csv.assert_called_once()
        assert count == 2
    
    @patch('app.services.export_service_sync.SyncExportService.get_sql_data')
    def test_write_corpus(self, mock_get_sql):
        """Test d'export corpus ZIP"""
        # Mock data
        mock_data = [
            {
                'id': 1,
                'title': 'Test Article',
                'description': 'Test description',
                'readable': 'This is the readable content of the article.',
                'domain': 'example.com',
                'url': 'https://example.com/test'
            }
        ]
        mock_get_sql.return_value = mock_data
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            filename = tmp_file.name
        
        try:
            # Execute
            count = self.export_service.write_corpus(filename, land_id=1, minimum_relevance=1)
            
            # Verify
            assert count == 1
            assert os.path.exists(filename)
            
            # Check ZIP content
            from zipfile import ZipFile
            with ZipFile(filename, 'r') as archive:
                files = archive.namelist()
                assert len(files) == 1
                assert files[0].startswith('1-test-article')
                assert files[0].endswith('.txt')
                
                # Check file content
                content = archive.read(files[0]).decode('utf-8')
                assert 'Title: "Test Article"' in content
                assert 'This is the readable content' in content
        
        finally:
            # Cleanup
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_csv_file_writing(self):
        """Test d'écriture de fichier CSV"""
        headers = ['id', 'title', 'url']
        data = [
            {'id': 1, 'title': 'Article 1', 'url': 'https://example.com/1'},
            {'id': 2, 'title': 'Article 2', 'url': 'https://example.com/2'}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            filename = tmp_file.name
        
        try:
            # Execute
            count = self.export_service.write_csv_file(filename, headers, data)
            
            # Verify
            assert count == 2
            assert os.path.exists(filename)
            
            # Check CSV content
            import csv
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                assert len(rows) == 3  # Header + 2 data rows
                assert rows[0] == headers
                assert rows[1] == ['1', 'Article 1', 'https://example.com/1']
                assert rows[2] == ['2', 'Article 2', 'https://example.com/2']
        
        finally:
            # Cleanup
            if os.path.exists(filename):
                os.unlink(filename)


class TestExportEndpoints:
    """Tests pour les endpoints d'export"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.client = TestClient(app)
    
    @patch('app.api.v1.endpoints.export.get_current_user')
    @patch('app.api.v1.endpoints.export.land_crud.get')
    @patch('uuid.uuid4')
    def test_export_csv_endpoint(self, mock_uuid, mock_get_land, mock_get_user):
        """Test de l'endpoint d'export CSV"""
        # Mock user and land
        mock_user = MagicMock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user
        
        mock_land = MagicMock()
        mock_land.user_id = 1
        mock_get_land.return_value = mock_land
        
        # Mock UUID
        mock_uuid.return_value = MagicMock()
        mock_uuid.return_value.__str__ = MagicMock(return_value="test-job-id")
        
        # Test request
        request_data = {
            "land_id": 1,
            "export_type": "pagecsv",
            "minimum_relevance": 1
        }
        
        # Execute
        response = self.client.post("/api/v1/export/csv", json=request_data)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-id"
        assert data["export_type"] == "pagecsv"
        assert data["land_id"] == 1
        assert data["status"] == "pending"
    
    @patch('app.api.v1.endpoints.export.get_current_user')
    @patch('app.api.v1.endpoints.export.land_crud.get')
    def test_export_csv_invalid_type(self, mock_get_land, mock_get_user):
        """Test d'export CSV avec type invalide"""
        # Mock user and land
        mock_user = MagicMock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user
        
        mock_land = MagicMock()
        mock_land.user_id = 1
        mock_get_land.return_value = mock_land
        
        # Test request with invalid type
        request_data = {
            "land_id": 1,
            "export_type": "invalid_type",
            "minimum_relevance": 1
        }
        
        # Execute
        response = self.client.post("/api/v1/export/csv", json=request_data)
        
        # Verify
        assert response.status_code == 400
        assert "Invalid CSV export type" in response.json()["detail"]
    
    @patch('app.api.v1.endpoints.export.get_current_user')
    @patch('app.api.v1.endpoints.export.land_crud.get')
    def test_export_land_not_found(self, mock_get_land, mock_get_user):
        """Test d'export avec land inexistant"""
        # Mock user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user
        
        # Mock land not found
        mock_get_land.return_value = None
        
        # Test request
        request_data = {
            "land_id": 999,
            "export_type": "pagecsv",
            "minimum_relevance": 1
        }
        
        # Execute
        response = self.client.post("/api/v1/export/csv", json=request_data)
        
        # Verify
        assert response.status_code == 404
        assert "Land not found" in response.json()["detail"]
    
    @patch('app.api.v1.endpoints.export.get_current_user')
    @patch('app.api.v1.endpoints.export.land_crud.get')
    def test_export_access_denied(self, mock_get_land, mock_get_user):
        """Test d'export avec accès refusé"""
        # Mock user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user
        
        # Mock land belonging to different user
        mock_land = MagicMock()
        mock_land.user_id = 2  # Different user
        mock_get_land.return_value = mock_land
        
        # Test request
        request_data = {
            "land_id": 1,
            "export_type": "pagecsv",
            "minimum_relevance": 1
        }
        
        # Execute
        response = self.client.post("/api/v1/export/csv", json=request_data)
        
        # Verify
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]


class TestExportSchemas:
    """Tests pour les schémas d'export"""
    
    def test_export_request_schema(self):
        """Test du schéma ExportRequest"""
        # Valid request
        valid_data = {
            "land_id": 1,
            "export_type": "pagecsv",
            "minimum_relevance": 5
        }
        
        request = ExportRequest(**valid_data)
        assert request.land_id == 1
        assert request.export_type == "pagecsv"
        assert request.minimum_relevance == 5
        assert request.filename is None
    
    def test_export_request_defaults(self):
        """Test des valeurs par défaut du schéma ExportRequest"""
        minimal_data = {
            "land_id": 1,
            "export_type": "pagecsv"
        }
        
        request = ExportRequest(**minimal_data)
        assert request.minimum_relevance == 1  # Default value
    
    def test_export_request_validation(self):
        """Test de validation du schéma ExportRequest"""
        # Test relevance bounds
        with pytest.raises(ValueError):
            ExportRequest(land_id=1, export_type="pagecsv", minimum_relevance=-1)
        
        with pytest.raises(ValueError):
            ExportRequest(land_id=1, export_type="pagecsv", minimum_relevance=11)
        
        # Valid edge cases
        request_min = ExportRequest(land_id=1, export_type="pagecsv", minimum_relevance=0)
        assert request_min.minimum_relevance == 0
        
        request_max = ExportRequest(land_id=1, export_type="pagecsv", minimum_relevance=10)
        assert request_max.minimum_relevance == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])