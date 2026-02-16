"""
Tests d'intégration pour les fonctionnalités d'export
Tests avec vraie base de données et données réelles
"""

import pytest
import asyncio
import tempfile
import os
from zipfile import ZipFile
from lxml import etree

from app.db.base import AsyncSessionLocal
from app.services.export_service import ExportService
from app.services.export_service_sync import SyncExportService
from app.crud.crud_land import land as land_crud
from app.crud.crud_user import user as user_crud
from app.crud.crud_expression import expression as expression_crud
from app.crud.crud_domain import domain as domain_crud
from app.schemas.land import LandCreate
from app.schemas.user import UserCreate
from app.schemas.expression import ExpressionCreate
from app.schemas.domain import DomainCreate


@pytest.mark.asyncio
class TestExportIntegration:
    """Tests d'intégration avec vraie base de données"""
    
    async def setup_method(self):
        """Setup avec données de test"""
        self.db = AsyncSessionLocal()
        
        # Create test user
        user_data = UserCreate(
            email="test_export@example.com",
            password="testpassword123",
            full_name="Export Test User"
        )
        self.test_user = await user_crud.create(self.db, obj_in=user_data)
        
        # Create test land
        land_data = LandCreate(
            name="Test Export Land",
            description="Land for export testing",
            lang=["fr"],
            user_id=self.test_user.id
        )
        self.test_land = await land_crud.create(self.db, obj_in=land_data)
        
        # Create test domain
        domain_data = DomainCreate(
            name="example.com",
            title="Example Domain",
            description="Test domain for exports",
            keywords="test,export,domain"
        )
        self.test_domain = await domain_crud.create(self.db, obj_in=domain_data)
        
        # Create test expressions
        self.test_expressions = []
        expression_data_list = [
            {
                "url": "https://example.com/article1",
                "title": "Premier Article de Test",
                "description": "Description du premier article",
                "keywords": "test,premier,article",
                "readable": "Ceci est le contenu lisible du premier article de test.",
                "relevance": 8,
                "depth": 1,
                "http_status": 200,
                "land_id": self.test_land.id,
                "domain_id": self.test_domain.id
            },
            {
                "url": "https://example.com/article2", 
                "title": "Deuxième Article de Test",
                "description": "Description du deuxième article",
                "keywords": "test,deuxième,article",
                "readable": "Ceci est le contenu lisible du deuxième article de test.",
                "relevance": 6,
                "depth": 1,
                "http_status": 200,
                "land_id": self.test_land.id,
                "domain_id": self.test_domain.id
            },
            {
                "url": "https://example.com/article3",
                "title": "Troisième Article de Test", 
                "description": "Description du troisième article",
                "keywords": "test,troisième,article",
                "readable": "Ceci est le contenu lisible du troisième article de test.",
                "relevance": 4,
                "depth": 2,
                "http_status": 200,
                "land_id": self.test_land.id,
                "domain_id": self.test_domain.id
            }
        ]
        
        for expr_data in expression_data_list:
            expression = await expression_crud.create(self.db, obj_in=ExpressionCreate(**expr_data))
            self.test_expressions.append(expression)
    
    async def teardown_method(self):
        """Cleanup après tests"""
        # Clean up test data
        for expression in self.test_expressions:
            await expression_crud.remove(self.db, id=expression.id)
        
        await domain_crud.remove(self.db, id=self.test_domain.id)
        await land_crud.remove(self.db, id=self.test_land.id)
        await user_crud.remove(self.db, id=self.test_user.id)
        
        await self.db.close()
    
    async def test_pagecsv_export_integration(self):
        """Test d'export CSV basique avec vraies données"""
        export_service = ExportService(self.db)
        
        file_path, count = await export_service.export_data(
            export_type="pagecsv",
            land_id=self.test_land.id,
            minimum_relevance=1
        )
        
        try:
            # Verify file was created
            assert os.path.exists(file_path)
            assert file_path.endswith('.csv')
            assert count == 3  # All 3 expressions
            
            # Verify CSV content
            import csv
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                # Check header
                assert len(rows) == 4  # Header + 3 data rows
                header = rows[0]
                expected_headers = [
                    'id', 'url', 'title', 'description', 'keywords',
                    'relevance', 'depth', 'domain_id', 'domain_name',
                    'domain_description', 'domain_keywords'
                ]
                assert header == expected_headers
                
                # Check data content
                data_rows = rows[1:]
                assert len(data_rows) == 3
                
                # Check first row
                first_row = data_rows[0]
                assert "https://example.com/article1" in first_row
                assert "Premier Article de Test" in first_row
                assert "8" in first_row  # relevance
                assert "example.com" in first_row  # domain name
        
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    async def test_fullpagecsv_export_integration(self):
        """Test d'export CSV complet avec contenu readable"""
        export_service = ExportService(self.db)
        
        file_path, count = await export_service.export_data(
            export_type="fullpagecsv",
            land_id=self.test_land.id,
            minimum_relevance=1
        )
        
        try:
            assert os.path.exists(file_path)
            assert count == 3
            
            # Verify readable content is included
            import csv
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                header = rows[0]
                assert 'readable' in header
                
                # Check that readable content is present
                readable_index = header.index('readable')
                for data_row in rows[1:]:
                    readable_content = data_row[readable_index]
                    assert len(readable_content) > 0
                    assert "contenu lisible" in readable_content
        
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    async def test_nodecsv_export_integration(self):
        """Test d'export CSV des domaines avec statistiques"""
        export_service = ExportService(self.db)
        
        file_path, count = await export_service.export_data(
            export_type="nodecsv",
            land_id=self.test_land.id,
            minimum_relevance=1
        )
        
        try:
            assert os.path.exists(file_path)
            assert count == 1  # One domain (example.com)
            
            # Verify domain aggregation
            import csv
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                header = rows[0]
                expected_headers = [
                    'id', 'name', 'title', 'description', 'keywords',
                    'expressions', 'average_relevance'
                ]
                assert header == expected_headers
                
                # Check aggregated data
                data_row = rows[1]
                assert "example.com" in data_row
                assert "3" in data_row  # 3 expressions
                # Average relevance should be (8+6+4)/3 = 6
                assert "6.0" in data_row or "6" in data_row
        
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    async def test_corpus_export_integration(self):
        """Test d'export corpus ZIP avec vraies données"""
        export_service = ExportService(self.db)
        
        file_path, count = await export_service.export_data(
            export_type="corpus",
            land_id=self.test_land.id,
            minimum_relevance=1
        )
        
        try:
            assert os.path.exists(file_path)
            assert file_path.endswith('.zip')
            assert count == 3
            
            # Verify ZIP content
            with ZipFile(file_path, 'r') as archive:
                files = archive.namelist()
                assert len(files) == 3
                
                # Check file naming pattern
                for filename in files:
                    assert filename.endswith('.txt')
                    assert '-' in filename  # ID-slugified-title.txt
                
                # Check content of first file
                first_file = files[0]
                content = archive.read(first_file).decode('utf-8')
                
                # Should contain metadata header
                assert content.startswith('---')
                assert 'Title:' in content
                assert 'Source:' in content
                assert 'Identifier:' in content
                
                # Should contain readable content
                assert 'contenu lisible' in content
        
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    async def test_gexf_export_integration(self):
        """Test d'export GEXF avec vraies données"""
        export_service = ExportService(self.db)
        
        file_path, count = await export_service.export_data(
            export_type="pagegexf",
            land_id=self.test_land.id,
            minimum_relevance=1
        )
        
        try:
            assert os.path.exists(file_path)
            assert file_path.endswith('.gexf')
            assert count == 3
            
            # Parse GEXF XML
            tree = etree.parse(file_path)
            root = tree.getroot()
            
            # Check GEXF structure
            assert root.tag == 'gexf'
            assert root.get('version') == '1.2'
            
            # Check meta
            meta = root.find('meta')
            assert meta is not None
            assert meta.get('creator') == 'MyWebIntelligence'
            
            # Check graph
            graph = root.find('graph')
            assert graph is not None
            
            # Check nodes
            nodes = graph.find('nodes')
            assert nodes is not None
            
            node_elements = nodes.findall('node')
            assert len(node_elements) == 3
            
            # Check node attributes
            for node in node_elements:
                assert 'id' in node.attrib
                assert 'label' in node.attrib
                assert node.get('label').startswith('https://example.com/')
                
                # Check attributes
                attvalues = node.find('attvalues')
                assert attvalues is not None
                
                attvalue_elements = attvalues.findall('attvalue')
                assert len(attvalue_elements) > 0
        
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    async def test_export_with_relevance_filter(self):
        """Test d'export avec filtre de pertinence"""
        export_service = ExportService(self.db)
        
        # Export with high relevance filter (should get only 2 articles: 8 and 6)
        file_path, count = await export_service.export_data(
            export_type="pagecsv",
            land_id=self.test_land.id,
            minimum_relevance=6
        )
        
        try:
            assert count == 2  # Only articles with relevance >= 6
            
            # Verify filtered content
            import csv
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                assert len(rows) == 3  # Header + 2 data rows
                
                # Check relevance values
                header = rows[0]
                relevance_index = header.index('relevance')
                
                for data_row in rows[1:]:
                    relevance = int(data_row[relevance_index])
                    assert relevance >= 6
        
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    async def test_export_empty_land(self):
        """Test d'export avec land vide"""
        # Create empty land
        empty_land_data = LandCreate(
            name="Empty Test Land",
            description="Empty land for testing",
            lang=["fr"],
            user_id=self.test_user.id
        )
        empty_land = await land_crud.create(self.db, obj_in=empty_land_data)
        
        try:
            export_service = ExportService(self.db)
            
            file_path, count = await export_service.export_data(
                export_type="pagecsv",
                land_id=empty_land.id,
                minimum_relevance=1
            )
            
            try:
                assert os.path.exists(file_path)
                assert count == 0
                
                # Check that only header is present
                import csv
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    
                    assert len(rows) == 1  # Only header
            
            finally:
                if os.path.exists(file_path):
                    os.unlink(file_path)
        
        finally:
            await land_crud.remove(self.db, id=empty_land.id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])