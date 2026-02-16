"""
Tests unitaires pour les services d'export
Focus sur les composants individuels des services d'export
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch
from zipfile import ZipFile
from lxml import etree

from app.services.export_service_sync import SyncExportService


class TestExportServiceUnit:
    """Tests unitaires pour SyncExportService"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.mock_db = MagicMock()
        self.service = SyncExportService(self.mock_db)
    
    def test_gexf_namespace_constants(self):
        """Test des constantes de namespace GEXF"""
        assert self.service.GEXF_NS is not None
        assert None in self.service.GEXF_NS
        assert 'viz' in self.service.GEXF_NS
        assert 'http://www.gexf.net/1.2draft' in self.service.GEXF_NS[None]
        assert 'http://www.gexf.net/1.1draft/viz' in self.service.GEXF_NS['viz']
    
    def test_get_gexf_structure(self):
        """Test de création de la structure GEXF"""
        attributes = [
            ('title', 'string'),
            ('relevance', 'integer'),
            ('depth', 'float')
        ]
        
        gexf, nodes, edges = self.service.get_gexf_structure(attributes)
        
        # Verify root element
        assert gexf.tag == 'gexf'
        assert gexf.get('version') == '1.2'
        
        # Verify meta element
        meta = gexf.find('meta')
        assert meta is not None
        assert 'lastmodifieddate' in meta.attrib
        assert meta.get('creator') == 'MyWebIntelligence'
        
        # Verify graph structure
        graph = gexf.find('graph')
        assert graph is not None
        assert graph.get('mode') == 'static'
        assert graph.get('defaultedgetype') == 'directed'
        
        # Verify attributes
        attr_section = graph.find('attributes')
        assert attr_section is not None
        assert attr_section.get('class') == 'node'
        
        attributes_elements = attr_section.findall('attribute')
        assert len(attributes_elements) == 3
        
        # Check specific attributes
        for i, (name, attr_type) in enumerate(attributes):
            attr_elem = attributes_elements[i]
            assert attr_elem.get('id') == str(i)
            assert attr_elem.get('title') == name
            assert attr_elem.get('type') == attr_type
        
        # Verify nodes and edges containers
        assert nodes.tag == 'nodes'
        assert edges.tag == 'edges'
    
    def test_add_gexf_node(self):
        """Test d'ajout de nœud GEXF"""
        attributes = [('title', 'string'), ('relevance', 'integer')]
        gexf, nodes, edges = self.service.get_gexf_structure(attributes)
        
        row_data = {
            'id': 123,
            'url': 'https://example.com',
            'title': 'Test Article',
            'relevance': 5
        }
        
        # Add node
        self.service.add_gexf_node(row_data, nodes, attributes, ('url', 'relevance'))
        
        # Verify node was added
        node_elements = nodes.findall('node')
        assert len(node_elements) == 1
        
        node = node_elements[0]
        assert node.get('id') == '123'
        assert node.get('label') == 'https://example.com'
        
        # Check size element
        size_elem = node.find('.//{%s}size' % self.service.GEXF_NS['viz'])
        assert size_elem is not None
        assert size_elem.get('value') == '5'
        
        # Check attributes
        attvalues = node.find('attvalues')
        assert attvalues is not None
        
        attvalue_elements = attvalues.findall('attvalue')
        assert len(attvalue_elements) == 2
        
        # Check specific attribute values
        attr_dict = {elem.get('for'): elem.get('value') for elem in attvalue_elements}
        assert attr_dict['0'] == 'Test Article'  # title
        assert attr_dict['1'] == '5'  # relevance
    
    def test_add_gexf_edge(self):
        """Test d'ajout d'arête GEXF"""
        attributes = []
        gexf, nodes, edges = self.service.get_gexf_structure(attributes)
        
        # Add edge
        edge_values = [1, 2, 0.8]
        self.service.add_gexf_edge(edge_values, edges)
        
        # Verify edge was added
        edge_elements = edges.findall('edge')
        assert len(edge_elements) == 1
        
        edge = edge_elements[0]
        assert edge.get('id') == '1_2'
        assert edge.get('source') == '1'
        assert edge.get('target') == '2'
        assert edge.get('weight') == '0.8'
    
    def test_slugify_edge_cases(self):
        """Test de slugify avec cas limites"""
        test_cases = [
            # (input, expected_output)
            (None, 'untitled'),
            ('', 'untitled'),
            ('   ', 'untitled'),
            ('a', 'a'),
            ('A', 'a'),
            ('123', '123'),
            ('àéîôù', 'aeiou'),
            ('Hello World!', 'hello-world'),
            ('Ça marche très bien', 'ca-marche-tres-bien'),
            ('Test@#$%^&*()_+', 'test'),
            ('Multiple---Dashes', 'multiple-dashes'),
            ('---Leading', 'leading'),
            ('Trailing---', 'trailing'),
            ('A' * 100, 'a' * 50),  # Truncation test
        ]
        
        for input_text, expected in test_cases:
            result = self.service.slugify(input_text)
            assert result == expected, f"Failed for input: {input_text}"
    
    def test_create_metadata_all_fields(self):
        """Test de création de métadonnées avec tous les champs"""
        row_data = {
            'id': 456,
            'title': 'Complete Article Title',
            'description': 'Detailed description of the article',
            'domain': 'news.example.com',
            'url': 'https://news.example.com/article/456'
        }
        
        metadata = self.service.create_metadata(row_data)
        
        # Check structure
        assert metadata.startswith('---\n')
        assert metadata.count('---') == 2
        assert metadata.endswith('---\n\n')
        
        # Check specific fields
        lines = metadata.split('\n')
        field_dict = {}
        for line in lines:
            if ':' in line and not line.strip().startswith('---'):
                key, value = line.split(':', 1)
                field_dict[key.strip()] = value.strip()
        
        assert field_dict['Title'] == '"Complete Article Title"'
        assert field_dict['Description'] == '"Detailed description of the article"'
        assert field_dict['Identifier'] == '"456"'
        assert field_dict['Publisher'] == '"news.example.com"'
        assert field_dict['Source'] == '"https://news.example.com/article/456"'
        
        # Check empty fields exist
        assert 'Creator' in field_dict
        assert 'Language' in field_dict
        assert field_dict['Creator'] == '""'
    
    def test_create_metadata_missing_fields(self):
        """Test de création de métadonnées avec champs manquants"""
        row_data = {
            'id': 789
            # Missing title, description, domain, url
        }
        
        metadata = self.service.create_metadata(row_data)
        
        # Should handle missing fields gracefully
        assert 'Title: ""' in metadata
        assert 'Description: ""' in metadata
        assert 'Identifier: "789"' in metadata
        assert 'Publisher: ""' in metadata
        assert 'Source: ""' in metadata
    
    def test_write_csv_file_empty_data(self):
        """Test d'écriture CSV avec données vides"""
        headers = ['id', 'title', 'url']
        data = []
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            filename = tmp_file.name
        
        try:
            count = self.service.write_csv_file(filename, headers, data)
            
            assert count == 0
            assert os.path.exists(filename)
            
            # Check that only header is written
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.strip().split('\n')
                assert len(lines) == 1  # Only header
                assert '"id","title","url"' in lines[0]
        
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_write_csv_file_special_characters(self):
        """Test d'écriture CSV avec caractères spéciaux"""
        headers = ['id', 'title']
        data = [
            {'id': 1, 'title': 'Article with "quotes"'},
            {'id': 2, 'title': 'Article with\nnewlines'},
            {'id': 3, 'title': 'Article with, commas'},
            {'id': 4, 'title': 'Article with çéàô accents'}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            filename = tmp_file.name
        
        try:
            count = self.service.write_csv_file(filename, headers, data)
            
            assert count == 4
            
            # Read and verify CSV content
            import csv
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                assert len(rows) == 5  # Header + 4 data rows
                assert rows[0] == headers
                assert rows[1] == ['1', 'Article with "quotes"']
                assert rows[2] == ['2', 'Article with\nnewlines']
                assert rows[3] == ['3', 'Article with, commas']
                assert rows[4] == ['4', 'Article with çéàô accents']
        
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    @patch('app.services.export_service_sync.SyncExportService.get_sql_data')
    def test_export_data_method_routing(self, mock_get_sql):
        """Test du routage des méthodes d'export"""
        mock_get_sql.return_value = [
            {'id': 1, 'title': 'Test', 'url': 'https://example.com'}
        ]
        
        export_types = [
            'pagecsv',
            'fullpagecsv', 
            'nodecsv',
            'mediacsv',
            'corpus'
        ]
        
        for export_type in export_types:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.close()
                
                try:
                    file_path, count = self.service.export_data(
                        export_type=export_type,
                        land_id=1,
                        minimum_relevance=1,
                        filename="test_export"
                    )
                    
                    # Verify file was created with correct extension
                    assert os.path.exists(file_path)
                    if export_type.endswith('csv'):
                        assert file_path.endswith('.csv')
                    elif export_type.endswith('gexf'):
                        assert file_path.endswith('.gexf')
                    elif export_type == 'corpus':
                        assert file_path.endswith('.zip')
                    
                    assert count >= 0  # Should return a count
                
                finally:
                    if os.path.exists(file_path):
                        os.unlink(file_path)
    
    def test_export_data_filename_generation(self):
        """Test de génération automatique de nom de fichier"""
        with patch.object(self.service, 'write_pagecsv', return_value=5) as mock_write:
            file_path, count = self.service.export_data(
                export_type='pagecsv',
                land_id=123,
                minimum_relevance=1
            )
            
            # Verify filename pattern
            filename = os.path.basename(file_path)
            assert filename.startswith('export_pagecsv_123_')
            assert filename.endswith('.csv')
            assert count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])