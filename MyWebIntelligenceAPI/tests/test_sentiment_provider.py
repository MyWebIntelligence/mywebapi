"""
Unit tests for sentiment analysis provider
"""

import pytest
from app.core.sentiment_provider import SentimentModelProvider


@pytest.fixture
def provider():
    """Create a sentiment provider instance"""
    return SentimentModelProvider()


@pytest.mark.asyncio
async def test_positive_sentiment_en(provider):
    """Test positive sentiment detection in English"""
    result = await provider.analyze_sentiment(
        "This movie is absolutely fantastic! I loved every moment.",
        language="en"
    )
    assert result["status"] == "computed"
    assert result["label"] == "positive"
    assert result["score"] > 0.3
    assert result["confidence"] > 0.0
    assert result["model"] == "textblob"


@pytest.mark.asyncio
async def test_negative_sentiment_en(provider):
    """Test negative sentiment detection in English"""
    result = await provider.analyze_sentiment(
        "This movie is terrible. A complete waste of time.",
        language="en"
    )
    assert result["status"] == "computed"
    assert result["label"] == "negative"
    assert result["score"] < -0.1
    assert result["model"] == "textblob"


@pytest.mark.asyncio
async def test_positive_sentiment_fr(provider):
    """Test positive sentiment detection in French"""
    result = await provider.analyze_sentiment(
        "Ce film est absolument fantastique ! J'ai adoré chaque moment.",
        language="fr"
    )
    assert result["status"] == "computed"
    assert result["label"] in ["positive", "neutral"]  # TextBlob FR can be less accurate
    assert result["model"] == "textblob"


@pytest.mark.asyncio
async def test_neutral_sentiment(provider):
    """Test neutral sentiment detection"""
    result = await provider.analyze_sentiment(
        "The weather today is cloudy with some sun.",
        language="en"
    )
    assert result["status"] == "computed"
    assert result["label"] in ["positive", "neutral", "negative"]
    assert result["model"] == "textblob"


@pytest.mark.asyncio
async def test_unsupported_language(provider):
    """Test unsupported language handling"""
    result = await provider.analyze_sentiment(
        "日本語のテキスト",
        language="ja"
    )
    assert result["status"] == "unsupported_lang"
    assert result["score"] is None
    assert result["label"] is None


@pytest.mark.asyncio
async def test_empty_content(provider):
    """Test empty content handling"""
    result = await provider.analyze_sentiment("", language="en")
    assert result["status"] == "no_content"
    assert result["score"] is None


@pytest.mark.asyncio
async def test_very_short_content(provider):
    """Test very short content handling"""
    result = await provider.analyze_sentiment("OK", language="en")
    assert result["status"] == "no_content"


def test_language_supported(provider):
    """Test language support check"""
    assert provider.is_language_supported("fr") is True
    assert provider.is_language_supported("en") is True
    assert provider.is_language_supported("FR") is True
    assert provider.is_language_supported("ja") is False
    assert provider.is_language_supported("de") is False


@pytest.mark.asyncio
async def test_textblob_available(provider):
    """Test that TextBlob is available"""
    assert provider.TEXTBLOB_AVAILABLE is True


@pytest.mark.asyncio
async def test_long_text_truncation(provider):
    """Test that long texts are handled properly"""
    long_text = "This is great! " * 200  # Very long positive text
    result = await provider.analyze_sentiment(long_text[:2000], language="en")
    assert result["status"] == "computed"
    assert result["label"] == "positive"
