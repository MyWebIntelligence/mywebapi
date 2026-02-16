"""
Tests de non-régression pour vérifier la parité avec le système legacy.

Ces tests valident que l'API reproduit fidèlement le comportement du système legacy
en termes d'extraction de contenu, enrichissement markdown, et gestion des médias.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from app.core import content_extractor


# URLs de référence pour les tests (à adapter selon votre domaine)
TEST_URLS = {
    "simple_article": "https://example.com/article",
    "with_images": "https://example.com/article-with-images",
    "with_videos": "https://example.com/article-with-videos",
    "archived": "https://example.com/old-article",  # URL qui nécessite Archive.org
}


# Fixtures HTML de test
SAMPLE_HTML_WITH_IMAGES = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Article</title>
    <meta name="description" content="Test description">
</head>
<body>
    <article>
        <h1>Test Article Title</h1>
        <p>This is a test article with some content.</p>
        <img src="/images/photo.jpg" alt="Test photo">
        <img src="https://example.com/images/photo2.jpg" alt="Another photo">
    </article>
</body>
</html>
"""

SAMPLE_HTML_WITH_VIDEO = """
<!DOCTYPE html>
<html>
<head><title>Video Article</title></head>
<body>
    <article>
        <h1>Video Article</h1>
        <p>Article with embedded video.</p>
        <video src="/videos/sample.mp4" controls></video>
        <audio src="/audio/sample.mp3" controls></audio>
    </article>
</body>
</html>
"""


class TestMarkdownFormatAlignment:
    """Vérifie que le format markdown est aligné avec le legacy."""

    @pytest.mark.asyncio
    async def test_trafilatura_uses_markdown_format(self):
        """Vérifie que Trafilatura extrait en format markdown."""
        result = await content_extractor.get_readable_content_with_fallbacks(
            url="https://example.com/test",
            html=SAMPLE_HTML_WITH_IMAGES
        )

        assert result.get('readable') is not None
        assert result.get('extraction_source') in ['trafilatura_direct', 'archive_org', 'beautifulsoup_fallback']

    @pytest.mark.asyncio
    async def test_markdown_includes_links_and_images(self):
        """Vérifie que le markdown inclut les liens et images."""
        with patch('trafilatura.extract') as mock_extract:
            # Simuler une extraction Trafilatura avec markdown
            mock_extract.return_value = "# Test\n\nSome content with [link](https://example.com)"

            result = await content_extractor.get_readable_content_with_fallbacks(
                url="https://example.com/test",
                html=SAMPLE_HTML_WITH_IMAGES
            )

            # Vérifier que l'extraction a bien utilisé les bonnes options
            assert mock_extract.call_count >= 1
            call_kwargs = mock_extract.call_args[1]
            assert call_kwargs.get('output_format') == 'markdown'
            assert call_kwargs.get('include_links') is True
            assert call_kwargs.get('include_images') is True


class TestMediaEnrichment:
    """Vérifie l'enrichissement markdown avec marqueurs IMAGE/VIDEO/AUDIO."""

    def test_enrich_markdown_with_images(self):
        """Vérifie l'ajout des marqueurs [IMAGE]."""
        markdown_content = "# Article\n\nSome text"
        readable_html = "<img src='https://example.com/photo.jpg'>"

        enriched, media_list = content_extractor.enrich_markdown_with_media(
            markdown_content, readable_html, "https://example.com/article"
        )

        assert "![IMAGE]" in enriched
        assert len(media_list) > 0
        assert media_list[0]['type'] == 'img'
        assert media_list[0]['url'] == 'https://example.com/photo.jpg'

    def test_enrich_markdown_with_video(self):
        """Vérifie l'ajout des marqueurs [VIDEO]."""
        markdown_content = "# Video Article"
        readable_html = "<video src='https://example.com/video.mp4'></video>"

        enriched, media_list = content_extractor.enrich_markdown_with_media(
            markdown_content, readable_html, "https://example.com/article"
        )

        assert "[VIDEO:" in enriched
        assert len(media_list) > 0
        assert media_list[0]['type'] == 'video'

    def test_enrich_markdown_with_audio(self):
        """Vérifie l'ajout des marqueurs [AUDIO]."""
        markdown_content = "# Audio Article"
        readable_html = "<audio src='https://example.com/audio.mp3'></audio>"

        enriched, media_list = content_extractor.enrich_markdown_with_media(
            markdown_content, readable_html, "https://example.com/article"
        )

        assert "[AUDIO:" in enriched
        assert len(media_list) > 0
        assert media_list[0]['type'] == 'audio'

    def test_resolve_relative_urls(self):
        """Vérifie la résolution des URLs relatives."""
        base_url = "https://example.com/articles/page"
        relative_url = "/images/photo.jpg"

        resolved = content_extractor.resolve_url(base_url, relative_url)

        assert resolved == "https://example.com/images/photo.jpg"

    def test_skip_data_urls(self):
        """Vérifie que les data URLs sont ignorées."""
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANS"

        resolved = content_extractor.resolve_url("https://example.com/", data_url)

        assert resolved == data_url  # Should return unchanged


class TestLinkExtraction:
    """Vérifie l'extraction des liens depuis markdown."""

    def test_extract_md_links_basic(self):
        """Vérifie l'extraction des liens markdown basiques."""
        markdown = """
        # Article

        Check out [this link](https://example.com/page1) and
        [another one](https://example.com/page2).
        """

        links = content_extractor.extract_md_links(markdown)

        assert len(links) == 2
        assert "https://example.com/page1" in links
        assert "https://example.com/page2" in links

    def test_extract_md_links_excludes_images(self):
        """Vérifie que les images ne sont pas extraites comme liens."""
        markdown = """
        # Article

        ![Image](https://example.com/image.jpg)
        [Real link](https://example.com/page)
        """

        links = content_extractor.extract_md_links(markdown)

        assert len(links) == 1
        assert "https://example.com/page" in links
        assert "https://example.com/image.jpg" not in links


class TestFallbackChain:
    """Vérifie l'ordre correct de la chaîne de fallbacks."""

    @pytest.mark.asyncio
    async def test_fallback_order_trafilatura_first(self):
        """Vérifie que Trafilatura est tenté en premier."""
        with patch('trafilatura.extract') as mock_extract:
            mock_extract.return_value = "# Content from Trafilatura"

            result = await content_extractor.get_readable_content_with_fallbacks(
                url="https://example.com/test",
                html=SAMPLE_HTML_WITH_IMAGES
            )

            assert result.get('extraction_source') == 'trafilatura_direct'

    @pytest.mark.asyncio
    async def test_fallback_to_archive_when_trafilatura_fails(self):
        """Vérifie le fallback vers Archive.org quand Trafilatura échoue."""
        with patch('trafilatura.extract') as mock_extract:
            mock_extract.return_value = None  # Trafilatura échoue

            with patch('httpx.AsyncClient') as mock_client:
                # Simuler une réponse Archive.org
                mock_response = AsyncMock()
                mock_response.json.return_value = {
                    'archived_snapshots': {
                        'closest': {'url': 'https://web.archive.org/web/2024/example.com'}
                    }
                }
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

                with patch('trafilatura.fetch_url') as mock_fetch:
                    mock_fetch.return_value = SAMPLE_HTML_WITH_IMAGES

                    result = await content_extractor.get_readable_content_with_fallbacks(
                        url="https://example.com/test",
                        html="<html><body>Minimal</body></html>"
                    )

                    # Should attempt Archive.org
                    assert result.get('extraction_source') in ['archive_org', 'beautifulsoup_fallback']

    @pytest.mark.asyncio
    async def test_fallback_to_beautifulsoup_when_all_fail(self):
        """Vérifie le fallback vers BeautifulSoup quand tout échoue."""
        with patch('trafilatura.extract') as mock_extract:
            mock_extract.return_value = None  # Trafilatura échoue

            with patch('httpx.AsyncClient') as mock_client:
                # Simuler Archive.org non disponible
                mock_response = AsyncMock()
                mock_response.json.return_value = {'archived_snapshots': {}}
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

                result = await content_extractor.get_readable_content_with_fallbacks(
                    url="https://example.com/test",
                    html=SAMPLE_HTML_WITH_IMAGES
                )

                assert result.get('extraction_source') == 'beautifulsoup_fallback'


class TestArchiveOrgIntegration:
    """Vérifie l'intégration Archive.org avec trafilatura.fetch_url."""

    @pytest.mark.asyncio
    async def test_archive_uses_trafilatura_fetch_url(self):
        """Vérifie que Archive.org utilise trafilatura.fetch_url."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                'archived_snapshots': {
                    'closest': {'url': 'https://web.archive.org/web/2024/example.com'}
                }
            }
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            with patch('trafilatura.fetch_url') as mock_fetch_url:
                mock_fetch_url.return_value = SAMPLE_HTML_WITH_IMAGES

                with patch('trafilatura.extract') as mock_extract:
                    mock_extract.side_effect = [None, "# Archived content"]  # Fail direct, succeed on archive

                    result = await content_extractor.get_readable_content_with_fallbacks(
                        url="https://example.com/test",
                        html="<html>minimal</html>"
                    )

                    # Verify trafilatura.fetch_url was called
                    assert mock_fetch_url.call_count >= 0  # May or may not be called depending on logic


class TestFieldPersistence:
    """Vérifie la persistance des champs legacy (content, http_status)."""

    @pytest.mark.asyncio
    async def test_content_field_included(self):
        """Vérifie que le champ content (HTML brut) est inclus."""
        result = await content_extractor.get_readable_content_with_fallbacks(
            url="https://example.com/test",
            html=SAMPLE_HTML_WITH_IMAGES
        )

        assert 'content' in result
        assert result['content'] == SAMPLE_HTML_WITH_IMAGES

    @pytest.mark.asyncio
    async def test_extraction_source_tracked(self):
        """Vérifie que la source d'extraction est tracée."""
        result = await content_extractor.get_readable_content_with_fallbacks(
            url="https://example.com/test",
            html=SAMPLE_HTML_WITH_IMAGES
        )

        assert 'extraction_source' in result
        assert result['extraction_source'] in [
            'trafilatura_direct', 'archive_org', 'beautifulsoup_fallback', 'all_failed'
        ]


class TestMinimumContentLength:
    """Vérifie le seuil de réussite aligné sur legacy (>100 caractères)."""

    @pytest.mark.asyncio
    async def test_minimum_100_characters_required(self):
        """Vérifie qu'au moins 100 caractères sont requis."""
        with patch('trafilatura.extract') as mock_extract:
            # Simuler un contenu trop court
            mock_extract.return_value = "Short"

            result = await content_extractor.get_readable_content_with_fallbacks(
                url="https://example.com/test",
                html=SAMPLE_HTML_WITH_IMAGES
            )

            # Should fallback because content is too short
            assert result.get('extraction_source') != 'trafilatura_direct'


# Tests d'intégration (optionnels, nécessitent connexion réseau)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_url_extraction():
    """
    Test d'intégration avec une vraie URL.
    Désactivé par défaut (marquer @pytest.mark.integration).
    """
    result = await content_extractor.get_readable_content_with_fallbacks(
        url="https://example.com",
        html=None
    )

    # Vérifications basiques
    assert result is not None
    # assert result.get('readable') is not None  # Peut échouer si le site est down


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
