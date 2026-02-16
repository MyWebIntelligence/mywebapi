"""
Tests unitaires pour MediaLinkExtractor.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.media_link_extractor import MediaLinkExtractor
from app.schemas.readable import MediaInfo, LinkInfo
from app.db.models import Expression, Media, ExpressionLink


@pytest.fixture
def mock_db():
    """Mock de session de base de données."""
    return AsyncMock()


@pytest.fixture
def extractor(mock_db):
    """Instance de MediaLinkExtractor avec mock DB."""
    return MediaLinkExtractor(mock_db)


@pytest.fixture
def sample_markdown():
    """Contenu markdown d'exemple pour les tests."""
    return """
# Test Article

This is a test article with various media and links.

![Alt text](https://example.com/image.jpg "Image title")
![](https://example.com/image2.png)

Here's a [test link](https://example.com/page "Link title") and another [link](https://external.com/page).

<img src="https://example.com/html-image.gif" alt="HTML image" title="HTML title">

Video: ![Video](https://example.com/video.mp4)

[Internal link](https://example.com/internal)
[External link](https://external.org/page)

Some text with <a href="https://example.com/html-link" title="HTML link title">HTML link</a>.
"""


class TestMediaLinkExtractor:
    """Tests pour MediaLinkExtractor."""
    
    def test_extract_media_from_markdown(self, extractor):
        """Test d'extraction de médias depuis markdown."""
        markdown = """
![Alt text](https://example.com/image.jpg "Image title")
![](https://example.com/image2.png)
<img src="https://example.com/html-image.gif" alt="HTML alt" title="HTML title">
![Video](https://example.com/video.mp4)
        """
        
        base_url = "https://example.com/"
        media_list = extractor.extract_media_from_markdown(markdown, base_url)
        
        # Vérifications
        assert len(media_list) == 4
        
        # Premier media (markdown avec tous les attributs)
        media1 = media_list[0]
        assert media1.url == "https://example.com/image.jpg"
        assert media1.alt_text == "Alt text"
        assert media1.title == "Image title"
        assert media1.media_type == "image"
        
        # Deuxième media (markdown sans attributs)
        media2 = media_list[1]
        assert media2.url == "https://example.com/image2.png"
        assert media2.alt_text is None
        assert media2.title is None
        assert media2.media_type == "image"

        # Troisième media (vidéo - markdown images are extracted first)
        media3 = media_list[2]
        assert media3.url == "https://example.com/video.mp4"
        assert media3.media_type == "video"

        # Quatrième media (HTML - extracted after all markdown images)
        media4 = media_list[3]
        assert media4.url == "https://example.com/html-image.gif"
        assert media4.alt_text == "HTML alt"
        assert media4.title == "HTML title"
        assert media4.media_type == "image"
    
    def test_extract_links_from_markdown(self, extractor):
        """Test d'extraction de liens depuis markdown."""
        markdown = """
[Internal link](https://example.com/internal "Internal title")
[External link](https://external.org/page)
<a href="https://example.com/html-link" title="HTML title">HTML link</a>
[Anchor link](#section)
        """
        
        base_url = "https://example.com/"
        link_list = extractor.extract_links_from_markdown(markdown, base_url)
        
        # Vérifications
        assert len(link_list) == 3  # Anchor link exclu

        # Premier lien (markdown interne)
        link1 = link_list[0]
        assert link1.url == "https://example.com/internal"
        assert link1.anchor_text == "Internal link"
        assert link1.title == "Internal title"
        assert link1.link_type == "internal"

        # Deuxième lien (markdown externe)
        link2 = link_list[1]
        assert link2.url == "https://external.org/page"
        assert link2.anchor_text == "External link"
        assert link2.link_type == "external"

        # Troisième lien (HTML - extracted after markdown links)
        link3 = link_list[2]
        assert link3.url == "https://example.com/html-link"
        assert link3.anchor_text == "HTML link"
        assert link3.link_type == "internal"
    
    def test_relative_url_resolution(self, extractor):
        """Test de résolution des URLs relatives."""
        markdown = """
![Relative image](./images/test.jpg)
[Relative link](./pages/test.html)
[Absolute link](/about)
        """
        
        base_url = "https://example.com/articles/page.html"
        
        media_list = extractor.extract_media_from_markdown(markdown, base_url)
        link_list = extractor.extract_links_from_markdown(markdown, base_url)
        
        # Vérifications URLs relatives
        assert media_list[0].url == "https://example.com/articles/images/test.jpg"
        assert link_list[0].url == "https://example.com/articles/pages/test.html"
        assert link_list[1].url == "https://example.com/about"
    
    def test_url_deduplication(self, extractor):
        """Test de déduplication des URLs."""
        markdown = """
![Image 1](https://example.com/image.jpg)
![Image 2](https://example.com/image.jpg)
[Link 1](https://example.com/page)
[Link 2](https://example.com/page)
        """
        
        base_url = "https://example.com/"
        
        media_list = extractor.extract_media_from_markdown(markdown, base_url)
        link_list = extractor.extract_links_from_markdown(markdown, base_url)
        
        # Vérifications - pas de doublons
        assert len(media_list) == 1
        assert len(link_list) == 1
    
    def test_determine_media_type(self, extractor):
        """Test de détermination du type de média."""
        test_cases = [
            ("image.jpg", "image"),
            ("image.JPEG", "image"),
            ("image.png", "image"),
            ("image.gif", "image"),
            ("image.webp", "image"),
            ("image.svg", "image"),
            ("video.mp4", "video"),
            ("video.AVI", "video"),
            ("video.webm", "video"),
            ("audio.mp3", "audio"),
            ("audio.WAV", "audio"),
            ("audio.ogg", "audio"),
            ("unknown.txt", "image"),  # Défaut
        ]
        
        for url, expected_type in test_cases:
            result = extractor._determine_media_type(f"https://example.com/{url}")
            assert result == expected_type, f"Failed for {url}"
    
    def test_link_type_determination(self, extractor):
        """Test de détermination du type de lien."""
        base_domain = "example.com"
        
        test_cases = [
            ("https://example.com/page", "internal"),
            ("https://subdomain.example.com/page", "external"),
            ("https://external.org/page", "external"),
            ("http://example.com/page", "internal"),
            ("ftp://example.com/file", "internal"),  # Same netloc = internal
        ]
        
        for url, expected_type in test_cases:
            result = extractor._determine_link_type(url, base_domain)
            assert result == expected_type, f"Failed for {url}"
    
    def test_url_validation(self, extractor):
        """Test de validation des URLs."""
        # URLs valides pour les médias
        valid_media_urls = [
            "https://example.com/image.jpg",
            "http://example.com/image.png",
            "/images/local.gif",
            "./relative/image.jpg"
        ]
        
        for url in valid_media_urls:
            assert extractor._is_valid_media_url(url) is True
        
        # URLs invalides pour les médias
        invalid_media_urls = [
            "",
            "#anchor",
            "javascript:alert('test')",
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            "mailto:test@example.com",
            "tel:+1234567890"
        ]
        
        for url in invalid_media_urls:
            assert extractor._is_valid_media_url(url) is False
        
        # URLs valides pour les liens
        valid_link_urls = [
            "https://example.com/page",
            "http://example.com/page",
            "/page",
            "./page"
        ]
        
        for url in valid_link_urls:
            assert extractor._is_valid_link_url(url) is True
        
        # URLs invalides pour les liens
        invalid_link_urls = [
            "",
            "#anchor",
            "javascript:alert('test')",
            "data:text/html,<h1>Test</h1>"
        ]
        
        for url in invalid_link_urls:
            assert extractor._is_valid_link_url(url) is False
    
    def test_clean_media_url(self, extractor):
        """Test de nettoyage des URLs de médias."""
        test_cases = [
            # Suppression des paramètres de tracking
            (
                "https://example.com/image.jpg?utm_source=google&utm_medium=cpc&ref=tracking",
                "https://example.com/image.jpg"
            ),
            # URLs WordPress proxy
            (
                "https://i0.wp.com/example.com/image.jpg?url=https%3A//original.com/image.jpg",
                "https://original.com/image.jpg"
            ),
            # URL normale sans changement
            (
                "https://example.com/image.jpg",
                "https://example.com/image.jpg"
            ),
            # Suppression du fragment
            (
                "https://example.com/image.jpg#section",
                "https://example.com/image.jpg"
            )
        ]
        
        for original_url, expected_url in test_cases:
            result = extractor._clean_media_url(original_url)
            assert result == expected_url, f"Failed for {original_url}"
    
    async def test_create_media_records(self, extractor, mock_db):
        """Test de création des enregistrements Media."""
        # Mock de the existing media query: await db.execute() returns sync result
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_delete_result = MagicMock()  # sync result (scalars/all are sync)
        mock_delete_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_delete_result)
        
        # Données de test
        media_list = [
            MediaInfo(
                url="https://example.com/image1.jpg",
                alt_text="Alt 1",
                title="Title 1",
                media_type="image"
            ),
            MediaInfo(
                url="https://example.com/image2.png",
                alt_text=None,
                title=None,
                media_type="image"
            )
        ]
        
        # Test
        created_count = await extractor.create_media_records(expression_id=1, media_list=media_list)
        
        # Vérifications
        assert created_count == 2
        assert mock_db.add.call_count == 2
        mock_db.flush.assert_called_once()
    
    async def test_create_expression_links(self, extractor, mock_db):
        """Test de création des liens d'expressions."""
        # Mock pour la recherche d'expressions cibles (scalar_one_or_none)
        mock_target_result = MagicMock()
        mock_target_expression = MagicMock()
        mock_target_expression.id = 2
        mock_target_result.scalar_one_or_none.return_value = mock_target_expression

        # Mock pour la recherche de liens existants (scalar_one_or_none)
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None  # Pas de lien existant

        # Configuration des appels mock (await db.execute returns these sequentially)
        mock_db.execute = AsyncMock(side_effect=[mock_target_result, mock_existing_result])

        # Données de test
        link_list = [
            LinkInfo(
                url="https://example.com/target-page",
                anchor_text="Target Page",
                title="Target Title",
                link_type="internal"
            )
        ]

        # Test
        created_count = await extractor.create_expression_links(source_expression_id=1, link_list=link_list)

        # Vérifications
        assert created_count == 1
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
    
    async def test_process_expression_media_and_links(self, extractor, sample_markdown):
        """Test du traitement complet média et liens."""
        # Mock de l'expression
        expression = MagicMock()
        expression.id = 1
        expression.url = "https://example.com/article"
        
        # Mock des méthodes de création
        with patch.object(extractor, 'create_media_records') as mock_create_media:
            mock_create_media.return_value = 3
            
            with patch.object(extractor, 'create_expression_links') as mock_create_links:
                mock_create_links.return_value = 2
                
                # Test
                media_created, links_created = await extractor.process_expression_media_and_links(
                    expression, sample_markdown
                )
                
                # Vérifications
                assert media_created == 3
                assert links_created == 2
                mock_create_media.assert_called_once()
                mock_create_links.assert_called_once()


@pytest.mark.asyncio
class TestMediaLinkExtractorIntegration:
    """Tests d'intégration pour MediaLinkExtractor."""
    
    async def test_full_extraction_workflow(self):
        """Test complet d'extraction avec vraies données."""
        # Ce test nécessiterait une vraie base de données
        pytest.skip("Requires real database setup")
    
    async def test_performance_with_large_markdown(self):
        """Test de performance avec un gros document markdown."""
        # Test de performance à implémenter si nécessaire
        pytest.skip("Performance test not implemented yet")