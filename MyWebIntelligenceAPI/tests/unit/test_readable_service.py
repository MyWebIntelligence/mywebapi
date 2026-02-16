"""
Tests unitaires pour ReadableService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.readable_service import ReadableService
from app.schemas.readable import MergeStrategy, ExtractionResult
from app.db.models import Expression, Land


@pytest.fixture
def mock_db():
    """Mock de session de base de données."""
    return AsyncMock()


@pytest.fixture
def readable_service(mock_db):
    """Instance de ReadableService avec mock DB."""
    return ReadableService(mock_db)


@pytest.fixture
def sample_expression():
    """Expression d'exemple pour les tests."""
    expr = Expression()
    expr.id = 1
    expr.url = "https://example.com/test"
    expr.title = "Test Title"
    expr.description = "Test description"
    expr.readable = None
    expr.lang = "fr"
    expr.land_id = 1
    expr.published_at = None
    expr.readable_at = None
    return expr


@pytest.fixture
def sample_land():
    """Land d'exemple pour les tests."""
    land = Land()
    land.id = 1
    land.name = "Test Land"
    land.description = "Test land description"
    land.words = [{"word": "test"}, {"word": "example"}]
    return land


class TestReadableService:
    """Tests pour ReadableService."""
    
    async def test_get_expressions_to_process(self, readable_service, mock_db):
        """Test de récupération des expressions à traiter."""
        # Mock du résultat de la requête
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [
            sample_expression()
        ]
        mock_db.execute.return_value = mock_result
        
        # Test
        expressions = await readable_service.get_expressions_to_process(land_id=1, limit=10)
        
        # Vérifications
        assert len(expressions) == 1
        mock_db.execute.assert_called_once()
    
    @patch('app.services.readable_service.ContentExtractor')
    async def test_extract_content_success(self, mock_extractor_class, readable_service):
        """Test d'extraction de contenu réussie."""
        # Mock de ContentExtractor
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        
        # Mock du résultat d'extraction
        mock_extractor.get_readable_content_with_fallbacks.return_value = {
            'readable': '# Test Content\n\nThis is test content.',
            'title': 'Test Title',
            'description': 'Test description',
            'language': 'fr',
            'source': 'trafilatura'
        }
        
        mock_extractor.get_metadata.return_value = {
            'title': 'Metadata Title',
            'description': 'Metadata description',
            'language': 'fr'
        }
        
        # Test
        result = await readable_service._extract_content("https://example.com/test")
        
        # Vérifications
        assert result.success is True
        assert result.readable == '# Test Content\n\nThis is test content.'
        assert result.title == 'Test Title'
        assert result.extraction_source == 'trafilatura'
    
    @patch('app.services.readable_service.ContentExtractor')
    async def test_extract_content_failure(self, mock_extractor_class, readable_service):
        """Test d'extraction de contenu échouée."""
        # Mock de ContentExtractor
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        
        # Mock d'échec d'extraction
        mock_extractor.get_readable_content_with_fallbacks.return_value = None
        
        # Test
        result = await readable_service._extract_content("https://example.com/test")
        
        # Vérifications
        assert result.success is False
        assert result.error_message == "No readable content extracted"
    
    def test_apply_merge_strategy_smart_merge(self, readable_service, sample_expression):
        """Test de la stratégie smart_merge."""
        # Préparation
        extraction = ExtractionResult(
            url="https://example.com/test",
            title="New Longer Test Title",
            description="New longer test description",
            readable="# New Content\n\nNew readable content.",
            language="en",
            published_at=datetime(2023, 1, 1),
            author="Test Author",
            media_urls=[],
            link_urls=[],
            extraction_source="trafilatura",
            success=True
        )
        
        # Test
        updated = readable_service._apply_merge_strategy(
            sample_expression, extraction, MergeStrategy.SMART_MERGE
        )
        
        # Vérifications
        assert updated is True
        assert sample_expression.title == "New Longer Test Title"  # Plus long
        assert sample_expression.readable == "# New Content\n\nNew readable content."  # Nouveau contenu
        assert sample_expression.lang == "en"  # Nouveau car ancien était None
    
    def test_apply_merge_strategy_mercury_priority(self, readable_service, sample_expression):
        """Test de la stratégie mercury_priority."""
        # Préparation
        sample_expression.title = "Old Title"
        sample_expression.readable = "Old content"
        
        extraction = ExtractionResult(
            url="https://example.com/test",
            title="New Title",
            description="New description", 
            readable="New content",
            language="en",
            published_at=None,
            author=None,
            media_urls=[],
            link_urls=[],
            extraction_source="trafilatura",
            success=True
        )
        
        # Test
        updated = readable_service._apply_merge_strategy(
            sample_expression, extraction, MergeStrategy.MERCURY_PRIORITY
        )
        
        # Vérifications
        assert updated is True
        assert sample_expression.title == "New Title"  # Écrasé
        assert sample_expression.readable == "New content"  # Écrasé
    
    def test_apply_merge_strategy_preserve_existing(self, readable_service, sample_expression):
        """Test de la stratégie preserve_existing."""
        # Préparation
        sample_expression.title = "Existing Title"
        sample_expression.readable = "Existing content"
        
        extraction = ExtractionResult(
            url="https://example.com/test",
            title="New Title",
            description="New description",
            readable="New content", 
            language="en",
            published_at=None,
            author=None,
            media_urls=[],
            link_urls=[],
            extraction_source="trafilatura",
            success=True
        )
        
        # Test
        updated = readable_service._apply_merge_strategy(
            sample_expression, extraction, MergeStrategy.PRESERVE_EXISTING
        )
        
        # Vérifications
        assert updated is False  # Rien n'a changé
        assert sample_expression.title == "Existing Title"  # Préservé
        assert sample_expression.readable == "Existing content"  # Préservé
    
    @patch('app.services.readable_service.MediaLinkExtractor')
    async def test_process_single_expression_success(self, mock_extractor_class, readable_service, sample_expression, mock_db):
        """Test de traitement d'une expression réussie."""
        # Mock de MediaLinkExtractor
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.process_expression_media_and_links.return_value = (2, 3)  # 2 médias, 3 liens
        
        # Mock de l'extraction de contenu
        with patch.object(readable_service, '_extract_content') as mock_extract:
            mock_extract.return_value = ExtractionResult(
                url="https://example.com/test",
                title="Test Title",
                description="Test description",
                readable="# Test Content",
                language="fr",
                published_at=None,
                author=None,
                media_urls=[],
                link_urls=[],
                extraction_source="trafilatura",
                success=True
            )
            
            # Mock du calcul de pertinence
            with patch.object(readable_service, '_recalculate_relevance') as mock_relevance:
                mock_relevance.return_value = None
                
                # Test
                result = await readable_service._process_single_expression(
                    sample_expression, MergeStrategy.SMART_MERGE, False
                )
                
                # Vérifications
                assert result['expression_id'] == 1
                assert result['updated'] is True
                assert result['media_created'] == 2
                assert result['links_created'] == 3
                assert 'error' not in result
    
    async def test_get_readable_stats(self, readable_service, mock_db):
        """Test de récupération des statistiques readable."""
        # Mock des résultats de requête
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(
            total=100,
            with_readable=75,
            last_processed=datetime(2023, 1, 1)
        )
        mock_db.execute.return_value = mock_result
        
        # Mock pour la requête eligible
        mock_eligible_result = MagicMock()
        mock_eligible_result.scalar.return_value = 25
        mock_db.execute.side_effect = [mock_result, mock_eligible_result]
        
        # Test
        stats = await readable_service.get_readable_stats(land_id=1)
        
        # Vérifications
        assert stats.total_expressions == 100
        assert stats.expressions_with_readable == 75
        assert stats.expressions_without_readable == 25
        assert stats.expressions_eligible == 25
        assert stats.processing_coverage == 75.0
    
    @patch('app.services.readable_service.MediaLinkExtractor')
    async def test_process_land_readable_complete_workflow(self, mock_extractor_class, readable_service, mock_db):
        """Test du workflow complet de traitement readable."""
        # Mock des expressions à traiter
        expressions = [sample_expression() for _ in range(3)]
        
        with patch.object(readable_service, 'get_expressions_to_process') as mock_get_expr:
            mock_get_expr.return_value = expressions
            
            # Mock du traitement par batch
            with patch.object(readable_service, '_process_batch') as mock_batch:
                mock_batch.return_value = [
                    {'expression_id': 1, 'updated': True, 'media_created': 1, 'links_created': 2},
                    {'expression_id': 2, 'updated': True, 'media_created': 0, 'links_created': 1},
                    {'expression_id': 3, 'error': True}
                ]
                
                # Test
                result = await readable_service.process_land_readable(
                    land_id=1,
                    limit=10,
                    depth=2,
                    merge_strategy=MergeStrategy.SMART_MERGE,
                    enable_llm=False,
                    batch_size=3
                )
                
                # Vérifications
                assert result.processed == 3
                assert result.updated == 2
                assert result.errors == 1
                assert result.media_created == 1
                assert result.links_created == 3
                assert result.merge_strategy_used == MergeStrategy.SMART_MERGE
                assert result.llm_validation_used is False


@pytest.mark.asyncio
class TestReadableServiceIntegration:
    """Tests d'intégration pour ReadableService."""
    
    async def test_extraction_with_real_content_extractor(self):
        """Test d'intégration avec le vrai ContentExtractor."""
        # Ce test nécessiterait une vraie base de données et des URLs de test
        # Pour l'instant, on le marque comme skip
        pytest.skip("Requires real database and test URLs")
    
    async def test_full_pipeline_with_database(self):
        """Test du pipeline complet avec une vraie base de données."""
        # Ce test nécessiterait une vraie base de données de test
        # Pour l'instant, on le marque comme skip
        pytest.skip("Requires real database setup")