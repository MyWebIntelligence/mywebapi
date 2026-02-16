"""
Sentiment Analysis Provider for MyWebIntelligence API

Hybrid approach:
- TextBlob (default): Lightweight, fast, free
- OpenRouter (optional): High quality, LLM-based

Supports FR/EN with automatic fallback.
"""

import logging
from typing import Optional, Dict, Any, Literal

logger = logging.getLogger(__name__)

SentimentLabel = Literal["positive", "neutral", "negative"]


class SentimentModelProvider:
    """
    Hybrid sentiment analysis provider.

    Methods:
    - TextBlob: Fast, lightweight (default)
    - OpenRouter: High quality (optional, requires API key)
    """

    # Configuration
    SUPPORTED_LANGUAGES = ["fr", "en"]  # TextBlob supports these well
    TEXTBLOB_AVAILABLE = False
    OPENROUTER_AVAILABLE = False

    def __init__(self):
        """Initialize provider and check available methods."""
        # Check TextBlob availability
        try:
            from textblob import TextBlob
            self.TEXTBLOB_AVAILABLE = True
            logger.info("✅ TextBlob sentiment provider available")
        except ImportError:
            logger.warning("❌ TextBlob not installed (pip install textblob textblob-fr)")

        # Check OpenRouter availability (lazy check, will verify in method)
        self.OPENROUTER_AVAILABLE = True  # Will check settings when needed

        if not self.TEXTBLOB_AVAILABLE and not self.OPENROUTER_AVAILABLE:
            logger.error("❌ No sentiment provider available!")

    def is_language_supported(self, lang: str) -> bool:
        """Check if language is supported."""
        return lang.lower() in self.SUPPORTED_LANGUAGES

    def _analyze_textblob(self, text: str, language: str) -> Dict[str, Any]:
        """
        Analyze sentiment using TextBlob.

        Fast, lightweight, rule-based approach.
        """
        try:
            from textblob import TextBlob

            # Use French-specific TextBlob if needed
            if language == "fr":
                try:
                    from textblob_fr import PatternTagger, PatternAnalyzer
                    blob = TextBlob(text, pos_tagger=PatternTagger(), analyzer=PatternAnalyzer())
                except ImportError:
                    logger.warning("textblob-fr not available, using English analyzer")
                    blob = TextBlob(text)
            else:
                blob = TextBlob(text)

            # Get polarity (-1.0 to +1.0)
            # TextBlob-FR returns a tuple (polarity, subjectivity) instead of an object
            sentiment = blob.sentiment
            if isinstance(sentiment, tuple):
                # TextBlob-FR returns (polarity, subjectivity)
                polarity = sentiment[0]
            else:
                # Standard TextBlob returns an object with .polarity attribute
                polarity = sentiment.polarity

            # Determine label with thresholds
            if polarity > 0.1:
                label = "positive"
            elif polarity < -0.1:
                label = "negative"
            else:
                label = "neutral"

            return {
                "score": round(polarity, 3),
                "label": label,
                "confidence": round(abs(polarity), 3),  # Use absolute polarity as confidence
                "status": "computed",
                "model": "textblob"
            }

        except Exception as e:
            logger.error(f"TextBlob analysis failed: {e}")
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "failed",
                "model": None
            }

    async def _analyze_openrouter(self, text: str, language: str) -> Dict[str, Any]:
        """
        Analyze sentiment using OpenRouter LLM.

        High quality, but slower and costs money.
        """
        try:
            from app.services.llm_validation_service import LLMValidationService
            from app.config import settings
            import json

            # Prepare prompt
            prompt = f"""Analyze the sentiment of the following text in {language.upper()}.

Text: {text[:1000]}

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{"sentiment": "positive" or "neutral" or "negative", "score": -1.0 to 1.0, "confidence": 0.0 to 1.0}}

Example response:
{{"sentiment": "positive", "score": 0.75, "confidence": 0.9}}"""

            # Call LLM service
            llm_service = LLMValidationService()
            response_text = await llm_service._call_openrouter(
                prompt=prompt,
                temperature=0.0  # Deterministic for sentiment
            )

            # Parse JSON response
            # Remove markdown code blocks if present
            response_clean = response_text.strip()
            if response_clean.startswith("```"):
                # Extract JSON from markdown
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1])

            result = json.loads(response_clean)

            return {
                "score": round(float(result["score"]), 3),
                "label": result["sentiment"],
                "confidence": round(float(result["confidence"]), 3),
                "status": "computed",
                "model": f"llm/{settings.OPENROUTER_MODEL}"
            }

        except Exception as e:
            logger.error(f"OpenRouter analysis failed: {e}", exc_info=True)
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "failed",
                "model": None
            }

    async def analyze_sentiment(
        self,
        text: str,
        language: str = "en",
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze (cleaned, readable content preferred)
            language: ISO 639-1 language code
            use_llm: Use OpenRouter LLM instead of TextBlob

        Returns:
            Dict with:
                - score: float (-1.0 to +1.0)
                - label: str ("positive", "neutral", "negative")
                - confidence: float (0.0 to 1.0)
                - status: str ("computed", "unsupported_lang", "no_content", "failed")
                - model: str (model name used)

        Example:
            >>> provider = SentimentModelProvider()
            >>> result = await provider.analyze_sentiment("This is great!", "en")
            >>> print(result)
            {
                'score': 0.95,
                'label': 'positive',
                'confidence': 0.95,
                'status': 'computed',
                'model': 'textblob'
            }
        """
        # Validation
        if not text or len(text.strip()) < 10:
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "no_content",
                "model": None
            }

        if not self.is_language_supported(language):
            logger.warning(f"Unsupported language: {language}")
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "unsupported_lang",
                "model": None
            }

        try:
            # Choose method based on use_llm flag
            if use_llm:
                # Check if OpenRouter is available
                from app.config import settings
                if settings.OPENROUTER_ENABLED and settings.OPENROUTER_API_KEY:
                    logger.debug(f"Using LLM for sentiment analysis (lang={language})")
                    return await self._analyze_openrouter(text, language)
                else:
                    logger.warning("LLM requested but OpenRouter not configured, falling back to TextBlob")
                    return self._analyze_textblob(text, language)
            else:
                # Use TextBlob (default)
                logger.debug(f"Using TextBlob for sentiment analysis (lang={language})")
                return self._analyze_textblob(text, language)

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}", exc_info=True)
            return {
                "score": None,
                "label": None,
                "confidence": None,
                "status": "failed",
                "model": None
            }
