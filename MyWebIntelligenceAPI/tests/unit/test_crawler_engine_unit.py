"""
Tests unitaires pour le CrawlerEngine

Tests critiques pour le moteur de crawl :
- Extraction de contenu HTML valide
- Gestion des timeouts et erreurs HTTP
- Traitement des URLs malformées
- Mise à jour en base de données
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import httpx
from datetime import datetime

from app.core.crawler_engine import CrawlerEngine
from app.db import models


@pytest.mark.asyncio
class TestCrawlerEngine:
    """Tests pour le CrawlerEngine"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.mock_db = AsyncMock()
        self.crawler = CrawlerEngine(self.mock_db)
        # Mock le client HTTP pour éviter de vrais appels
        self.crawler.http_client = AsyncMock()
    
    async def test_crawl_expression_success(self):
        """Test crawl réussi d'une expression"""
        # Setup
        mock_expr = MagicMock()
        mock_expr.id = 1
        mock_expr.url = "https://example.com"
        mock_expr.land_id = 1
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.text = "<html><head><title>Test Page</title></head><body><p>Content</p></body></html>"
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        
        self.crawler.http_client.get = AsyncMock(return_value=mock_response)
        
        # Mock content extractor
        with patch('app.core.content_extractor.get_readable_content') as mock_get_readable, \
             patch('app.core.content_extractor.get_metadata') as mock_get_metadata, \
             patch('app.crud.crud_expression.expression.update_expression') as mock_update:
            
            mock_get_readable.return_value = ("Extracted content", MagicMock())
            mock_get_metadata.return_value = {
                'title': 'Test Page',
                'description': 'Test description',
                'keywords': 'test, keywords',
                'lang': 'en'
            }
            
            # Execute
            await self.crawler.crawl_expression(mock_expr)
            
            # Verify
            self.crawler.http_client.get.assert_called_once_with("https://example.com")
            mock_response.raise_for_status.assert_called_once()
            mock_get_readable.assert_called_once()
            mock_get_metadata.assert_called_once()
            mock_update.assert_called_once()
            
            # Verify update data
            call_args = mock_update.call_args
            assert call_args[1]['db_obj'] == mock_expr
            update_data = call_args[1]['obj_in']
            assert update_data.http_status == 200
            assert update_data.title == 'Test Page'
            assert update_data.description == 'Test description'
            assert update_data.readable == 'Extracted content'
    
    async def test_crawl_expression_http_error(self):
        """Test gestion des erreurs HTTP"""
        # Setup
        mock_expr = MagicMock()
        mock_expr.id = 1
        mock_expr.url = "https://example.com/404"
        
        # Mock HTTP error
        mock_response = Mock()
        mock_response.status_code = 404
        http_error = httpx.HTTPStatusError("Not Found", request=Mock(), response=mock_response)
        
        self.crawler.http_client.get = AsyncMock(return_value=mock_response)
        mock_response.raise_for_status = Mock(side_effect=http_error)
        
        with patch('app.crud.crud_expression.expression.update_expression') as mock_update:
            # Execute
            await self.crawler.crawl_expression(mock_expr)
            
            # Verify
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            update_data = call_args[1]['obj_in']
            assert update_data.http_status == 404
            assert hasattr(update_data, 'crawled_at')
    
    async def test_crawl_expression_request_error(self):
        """Test gestion des erreurs de requête (timeout, DNS, etc.)"""
        # Setup
        mock_expr = MagicMock()
        mock_expr.id = 1
        mock_expr.url = "https://nonexistent.example.com"
        
        # Mock request error
        request_error = httpx.RequestError("Connection timeout")
        self.crawler.http_client.get = AsyncMock(side_effect=request_error)
        
        with patch('app.crud.crud_expression.expression.update_expression') as mock_update:
            # Execute
            await self.crawler.crawl_expression(mock_expr)
            
            # Verify
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            update_data = call_args[1]['obj_in']
            assert update_data.http_status == 0  # Custom code for request errors
            assert hasattr(update_data, 'crawled_at')
    
    async def test_crawl_expression_empty_content(self):
        """Test traitement d'une page avec contenu vide"""
        # Setup
        mock_expr = MagicMock()
        mock_expr.id = 1
        mock_expr.url = "https://example.com/empty"
        
        # Mock HTTP response with empty content
        mock_response = Mock()
        mock_response.text = ""
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        
        self.crawler.http_client.get = AsyncMock(return_value=mock_response)
        
        with patch('app.crud.crud_expression.expression.update_expression') as mock_update:
            # Execute
            await self.crawler.crawl_expression(mock_expr)

            # Verify
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            update_data = call_args[1]['obj_in']
            assert update_data.http_status == 200
            # Ne devrait pas avoir de titre, description, etc. car pas de contenu
            assert update_data.title is None
            assert update_data.description is None
            assert update_data.readable is None
    
    async def test_crawl_expression_malformed_html(self):
        """Test traitement d'HTML malformé"""
        # Setup
        mock_expr = MagicMock()
        mock_expr.id = 1
        mock_expr.url = "https://example.com/malformed"
        
        # Mock HTTP response with malformed HTML
        mock_response = Mock()
        mock_response.text = "<html><head><title>Test</title><body><p>Unclosed paragraph"
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        
        self.crawler.http_client.get = AsyncMock(return_value=mock_response)
        
        with patch('app.core.content_extractor.get_readable_content') as mock_get_readable, \
             patch('app.core.content_extractor.get_metadata') as mock_get_metadata, \
             patch('app.crud.crud_expression.expression.update_expression') as mock_update:
            
            # Les extractors devraient gérer le HTML malformé
            mock_get_readable.return_value = ("Extracted content", MagicMock())
            mock_get_metadata.return_value = {
                'title': 'Test',
                'description': '',
                'keywords': '',
                'lang': 'en'
            }
            
            # Execute
            await self.crawler.crawl_expression(mock_expr)
            
            # Verify - ne devrait pas lever d'exception
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            update_data = call_args[1]['obj_in']
            assert update_data.http_status == 200
            assert update_data.title == 'Test'
    
    async def test_crawl_land_success(self):
        """Test crawl réussi d'un land avec plusieurs expressions"""
        # Setup
        mock_expr1 = MagicMock()
        mock_expr1.id = 1
        mock_expr1.url = "https://example.com/page1"
        
        mock_expr2 = MagicMock()
        mock_expr2.id = 2
        mock_expr2.url = "https://example.com/page2"
        
        expressions = [mock_expr1, mock_expr2]
        
        mock_land = MagicMock()
        mock_land.start_urls = []

        with patch('app.crud.crud_land.land.get', AsyncMock(return_value=mock_land)), \
             patch('app.crud.crud_expression.expression.get_expressions_to_crawl') as mock_get_expressions, \
             patch.object(self.crawler, 'crawl_expression') as mock_crawl_expr:
            
            mock_get_expressions.return_value = expressions
            self.mock_db.get = AsyncMock(side_effect=[mock_expr1, mock_expr2])
            mock_crawl_expr.return_value = None  # Crawl réussi
            self.crawler.http_client.aclose = AsyncMock()
            
            # Execute
            processed, errors, http_stats = await self.crawler.crawl_land(land_id=1, limit=10)
            
            # Verify
            mock_get_expressions.assert_called_once_with(
                self.mock_db, land_id=1, limit=10, depth=None, http_status=None
            )
            assert mock_crawl_expr.call_count == 2
            assert processed == 2
            assert errors == 0
            assert http_stats == {}
            self.crawler.http_client.aclose.assert_called_once()
    
    async def test_crawl_land_with_errors(self):
        """Test crawl d'un land avec des erreurs sur certaines expressions"""
        # Setup
        mock_expr1 = MagicMock()
        mock_expr1.id = 1
        mock_expr1.url = "https://example.com/page1"
        
        mock_expr2 = MagicMock()
        mock_expr2.id = 2
        mock_expr2.url = "https://example.com/page2"
        
        expressions = [mock_expr1, mock_expr2]
        
        mock_land = MagicMock()
        mock_land.start_urls = []

        with patch('app.crud.crud_land.land.get', AsyncMock(return_value=mock_land)), \
             patch('app.crud.crud_expression.expression.get_expressions_to_crawl') as mock_get_expressions, \
             patch.object(self.crawler, 'crawl_expression') as mock_crawl_expr:
            
            mock_get_expressions.return_value = expressions
            self.mock_db.get = AsyncMock(side_effect=[mock_expr1, mock_expr2])
            # Premier crawl réussit, deuxième échoue
            mock_crawl_expr.side_effect = [None, Exception("Network error")]
            self.crawler.http_client.aclose = AsyncMock()
            
            # Execute
            processed, errors, http_stats = await self.crawler.crawl_land(land_id=1)
            
            # Verify
            assert mock_crawl_expr.call_count == 2
            assert processed == 1
            assert errors == 1
            assert http_stats.get('error') == 1
    
    async def test_crawl_land_with_parameters(self):
        """Test crawl d'un land avec paramètres spécifiques"""
        mock_land = MagicMock()
        mock_land.start_urls = []

        with patch('app.crud.crud_land.land.get', AsyncMock(return_value=mock_land)), \
             patch('app.crud.crud_expression.expression.get_expressions_to_crawl') as mock_get_expressions, \
             patch.object(self.crawler, 'crawl_expression'):
            
            mock_get_expressions.return_value = []
            self.mock_db.get = AsyncMock(return_value=None)
            
            # Execute avec paramètres
            processed, errors, http_stats = await self.crawler.crawl_land(
                land_id=1, 
                limit=50, 
                depth=3, 
                http_status="404"
            )
            
            # Verify que les paramètres sont passés correctement
            mock_get_expressions.assert_called_once_with(
                self.mock_db, 
                land_id=1, 
                limit=50, 
                depth=3, 
                http_status="404"
            )
            assert processed == 0
            assert errors == 0
            assert http_stats == {}
    
    async def test_crawl_expression_with_special_characters(self):
        """Test crawl d'une URL avec caractères spéciaux"""
        # Setup
        mock_expr = MagicMock()
        mock_expr.id = 1
        mock_expr.url = "https://example.com/café-français"
        
        mock_response = Mock()
        mock_response.text = "<html><head><title>Café Français</title></head><body>Contenu français</body></html>"
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        
        self.crawler.http_client.get = AsyncMock(return_value=mock_response)
        
        with patch('app.core.content_extractor.get_readable_content') as mock_get_readable, \
             patch('app.core.content_extractor.get_metadata') as mock_get_metadata, \
             patch('app.crud.crud_expression.expression.update_expression') as mock_update:
            
            mock_get_readable.return_value = ("Contenu français", MagicMock())
            mock_get_metadata.return_value = {
                'title': 'Café Français',
                'description': '',
                'keywords': '',
                'lang': 'fr'
            }
            
            # Execute
            await self.crawler.crawl_expression(mock_expr)
            
            # Verify
            self.crawler.http_client.get.assert_called_once_with("https://example.com/café-français")
            mock_update.assert_called_once()
    
    async def test_crawl_expression_timeout_handling(self):
        """Test gestion des timeouts"""
        # Setup
        mock_expr = MagicMock()
        mock_expr.id = 1
        mock_expr.url = "https://slow.example.com"
        
        # Mock timeout error
        timeout_error = httpx.TimeoutException("Request timeout")
        self.crawler.http_client.get = AsyncMock(side_effect=timeout_error)
        
        with patch('app.crud.crud_expression.expression.update_expression') as mock_update:
            # Execute
            await self.crawler.crawl_expression(mock_expr)
            
            # Verify que l'erreur est gérée comme une RequestError
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            update_data = call_args[1]['obj_in']
            assert update_data.http_status == 0
    
    async def test_crawler_engine_initialization(self):
        """Test initialisation du CrawlerEngine"""
        # Test que l'engine est correctement initialisé
        assert self.crawler.db == self.mock_db
        assert hasattr(self.crawler, 'http_client')
    
    async def test_crawler_engine_http_client_config(self):
        """Test configuration du client HTTP"""
        # Créer un nouveau crawler pour tester la config par défaut
        new_crawler = CrawlerEngine(self.mock_db)
        
        # Vérifier que le client HTTP est configuré avec timeout et redirects
        assert isinstance(new_crawler.http_client, httpx.AsyncClient)
        assert isinstance(new_crawler.http_client.timeout, httpx.Timeout)
        assert new_crawler.http_client.follow_redirects == True
        
        # Nettoyer
        await new_crawler.http_client.aclose()
