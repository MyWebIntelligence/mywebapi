"""
Test de vérification des métadonnées extraites.
"""
import pytest
from bs4 import BeautifulSoup
from app.core import content_extractor


def test_published_date_extraction():
    """Test l'extraction de la date de publication depuis les meta tags."""
    html = """
    <html>
    <head>
        <meta property="article:published_time" content="2025-10-11T09:05:23+02:00">
        <title>Test Article</title>
    </head>
    <body>Test content</body>
    </html>
    """
    
    soup = BeautifulSoup(html, 'html.parser')
    published_date = content_extractor.get_published_date(soup)
    
    assert published_date is not None
    assert published_date == "2025-10-11T09:05:23+02:00"


def test_canonical_url_extraction():
    """Test l'extraction de l'URL canonique."""
    html = """
    <html>
    <head>
        <link rel="canonical" href="https://example.com/article">
        <title>Test Article</title>
    </head>
    <body>Test content</body>
    </html>
    """
    
    soup = BeautifulSoup(html, 'html.parser')
    canonical_url = content_extractor.get_canonical_url(soup)
    
    assert canonical_url is not None
    assert canonical_url == "https://example.com/article"


def test_metadata_extraction():
    """Test l'extraction complète des métadonnées."""
    html = """
    <html lang="fr">
    <head>
        <title>Test Article</title>
        <meta property="article:published_time" content="2025-10-11T09:05:23+02:00">
        <link rel="canonical" href="https://example.com/article">
        <meta name="description" content="Test description">
        <meta name="keywords" content="test, article">
    </head>
    <body>Test content</body>
    </html>
    """
    
    soup = BeautifulSoup(html, 'html.parser')
    metadata = content_extractor.get_metadata(soup, "https://example.com/article")
    
    assert metadata['title'] == "Test Article"
    assert metadata['description'] == "Test description"
    assert metadata['keywords'] == "test, article"
    assert metadata['lang'] == "fr"
    assert metadata['canonical_url'] == "https://example.com/article"
    assert metadata['published_at'] == "2025-10-11T09:05:23+02:00"


def test_language_detection():
    """Test la détection de langue."""
    from app.utils.text_utils import detect_language
    
    french_text = "Bonjour, ceci est un texte en français avec plusieurs mots."
    english_text = "Hello, this is a text in English with several words."
    
    assert detect_language(french_text) == "fr"
    assert detect_language(english_text) == "en"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
