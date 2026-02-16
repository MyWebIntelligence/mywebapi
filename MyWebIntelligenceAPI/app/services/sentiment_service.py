"""
Sentiment Enrichment Service for MyWebIntelligence API

Orchestrates language detection + sentiment analysis for expressions.
Integrates with existing text_processing module.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.core.sentiment_provider import SentimentModelProvider

logger = logging.getLogger(__name__)

# Configuration thresholds
MIN_CONFIDENCE_THRESHOLD = 0.5  # Below this, set status = "low_confidence"


class SentimentService:
    """
    Service for enriching expressions with sentiment scores.

    Workflow:
    1. Detect language (reuse existing module or use provided)
    2. Prepare text (clean, truncate)
    3. Call sentiment model
    4. Apply confidence threshold
    5. Return structured result
    """

    def __init__(self):
        """Initialize service with model provider."""
        self.provider = SentimentModelProvider()
        logger.info("SentimentService initialized")

    def _detect_language(self, text: str) -> str:
        """
        Detect language of text.

        Reuses existing language detection from text_processing if available,
        otherwise uses langdetect.
        """
        try:
            # Try to use existing text_processing module
            from app.core.text_processing import detect_language
            return detect_language(text)
        except (ImportError, AttributeError):
            # Fallback to langdetect
            try:
                import langdetect
                langdetect.DetectorFactory.seed = 0  # Consistent results
                detected = langdetect.detect(text)
                logger.debug(f"Detected language: {detected}")
                return detected
            except Exception as e:
                logger.warning(f"Language detection failed: {e}, defaulting to 'en'")
                return "en"

    def _prepare_text(self, content: Optional[str], readable: Optional[str]) -> Optional[str]:
        """
        Choose best text source and prepare for sentiment analysis.

        Prioritizes readable content over raw HTML content.
        """
        # Choose best source
        text = readable if readable else content

        if not text:
            return None

        # Basic cleaning
        text = text.strip()

        # Truncate very long texts (keep first 2000 chars)
        if len(text) > 2000:
            text = text[:2000]

        return text

    async def enrich_expression_sentiment(
        self,
        content: Optional[str],
        readable: Optional[str] = None,
        language: Optional[str] = None,
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Enrich an expression with sentiment analysis.

        Args:
            content: Raw HTML content (fallback)
            readable: Readable markdown content (preferred)
            language: Detected language (ISO 639-1), auto-detect if None
            use_llm: Use OpenRouter LLM instead of TextBlob

        Returns:
            Dict ready for Expression update:
                - sentiment_score: float or None
                - sentiment_label: str or None
                - sentiment_confidence: float or None
                - sentiment_status: str
                - sentiment_model: str or None
                - sentiment_computed_at: datetime or None

        Example:
            >>> service = SentimentService()
            >>> result = await service.enrich_expression_sentiment(
            ...     readable="This article is very positive!",
            ...     language="en"
            ... )
            >>> print(result["sentiment_score"])
            0.87
        """
        # Prepare text
        text = self._prepare_text(content, readable)

        if not text or len(text.strip()) < 10:
            logger.debug("No usable content for sentiment analysis")
            return {
                "sentiment_score": None,
                "sentiment_label": None,
                "sentiment_confidence": None,
                "sentiment_status": "no_content",
                "sentiment_model": None,
                "sentiment_computed_at": None
            }

        # Detect language if not provided
        if not language:
            try:
                language = self._detect_language(text)
                logger.debug(f"Detected language: {language}")
            except Exception as e:
                logger.warning(f"Language detection failed: {e}")
                language = "en"  # Fallback to English

        # Analyze sentiment
        result = await self.provider.analyze_sentiment(text, language, use_llm=use_llm)

        # Apply confidence threshold
        if result["status"] == "computed" and result["confidence"] is not None:
            if result["confidence"] < MIN_CONFIDENCE_THRESHOLD:
                logger.info(
                    f"Low confidence sentiment: {result['confidence']:.2f} < {MIN_CONFIDENCE_THRESHOLD}"
                )
                result["status"] = "low_confidence"
                # Keep score but flag as uncertain

        # Add timestamp if computed
        timestamp = None
        if result["status"] in ["computed", "low_confidence"]:
            timestamp = datetime.now(timezone.utc)

        return {
            "sentiment_score": result["score"],
            "sentiment_label": result["label"],
            "sentiment_confidence": result["confidence"],
            "sentiment_status": result["status"],
            "sentiment_model": result["model"],
            "sentiment_computed_at": timestamp
        }

    def should_compute_sentiment(
        self,
        existing_score: Optional[float],
        force_recompute: bool = False
    ) -> bool:
        """
        Determine if sentiment should be computed.

        Args:
            existing_score: Current sentiment_score in DB
            force_recompute: Override check

        Returns:
            True if should compute/recompute
        """
        if force_recompute:
            return True

        # Compute if never computed
        if existing_score is None:
            return True

        # Already computed and not forcing
        return False
