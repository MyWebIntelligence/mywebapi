"""
LLM Validation Service for expression relevance validation using OpenRouter.
V2 SYNC-ONLY implementation - No async, based on legacy with modern adaptations.
"""
import json
import time
from typing import Dict, Any, Optional

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Expression, Land
from app.schemas.readable import ValidationResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LLMValidationService:
    """
    Service for validating expression relevance using LLM via OpenRouter API.

    V2 SYNC-ONLY: This service uses only synchronous methods (requests, not httpx).
    Designed for use in Celery workers with the synchronous crawler.
    """

    def __init__(self, db: Session = None):
        """
        Initialize LLM Validation Service.

        Args:
            db: Synchronous SQLAlchemy Session (optional, not used in current impl)
        """
        self.db = db
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.timeout = getattr(settings, 'OPENROUTER_TIMEOUT', 30)
        self.max_retries = getattr(settings, 'OPENROUTER_MAX_RETRIES', 3)

    def validate_expression_relevance(
        self,
        expression: Expression,
        land: Land,
        model: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate if an expression is relevant to the land's research topic.

        SYNCHRONOUS method - no async/await.

        Args:
            expression: Expression to validate
            land: Land context for validation
            model: Optional model override

        Returns:
            ValidationResult with relevance determination
        """
        if not self._is_validation_enabled():
            return ValidationResult(
                is_relevant=True,  # Default to relevant if disabled
                model_used="disabled",
                error_message="LLM validation is disabled"
            )

        try:
            # Build validation prompt
            prompt = self._build_relevance_prompt(expression, land)

            # Determine model to use
            validation_model = model or getattr(settings, 'OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet')

            # Call OpenRouter API (synchronous)
            response = self._call_openrouter_api(prompt, validation_model)

            # Parse response
            is_relevant = self._parse_yes_no_response(response.get('content', ''))

            return ValidationResult(
                is_relevant=is_relevant,
                model_used=validation_model,
                prompt_tokens=response.get('usage', {}).get('prompt_tokens'),
                completion_tokens=response.get('usage', {}).get('completion_tokens')
            )

        except Exception as e:
            logger.error(f"LLM validation failed for expression {expression.id}: {e}")
            return ValidationResult(
                is_relevant=True,  # Default to relevant on error
                model_used=model or "error",
                error_message=str(e)
            )

    def _is_validation_enabled(self) -> bool:
        """Check if LLM validation is enabled."""
        return (
            getattr(settings, 'OPENROUTER_ENABLED', False) and
            getattr(settings, 'OPENROUTER_API_KEY', None) is not None
        )

    def _build_relevance_prompt(self, expression: Expression, land: Land) -> str:
        """
        Build the relevance validation prompt in French (from legacy).
        """
        # Get land description and keywords
        land_desc = land.description or "Pas de description disponible"

        # Extract keywords from land words (simple array of strings in V2)
        terms = []
        if hasattr(land, 'words') and land.words:
            if isinstance(land.words, list):
                for word in land.words:
                    if isinstance(word, str):
                        terms.append(word)

        terms_str = ', '.join(terms) if terms else "Aucun mot-clé défini"

        # Get expression content
        title = expression.title or "Pas de titre"
        description = expression.description or "Pas de description"

        # Limit readable content to avoid token limits
        readable_text = ""
        if expression.readable:
            # Take first 1000 characters to stay within token limits
            readable_text = expression.readable[:1000]
            if len(expression.readable) > 1000:
                readable_text += "..."
        else:
            readable_text = "Pas de contenu lisible disponible"

        # Build the prompt (same structure as legacy)
        prompt = f"""Dans le cadre de la constitution d'un corpus de pages Web à des fins d'analyse de contenu,
nous voulons savoir si la page crawlée est pertinente pour le projet ou non.

Le projet a les caractéristiques suivantes :
- Nom du projet : {land.name}
- Description : {land_desc}
- Mots clés : {terms_str}

La page suivante :
- URL = {expression.url}
- Titre : {title}
- Description : {description}
- Readable (extrait) : {readable_text}

Tu répondras ABSOLUMENT et uniquement par "oui" ou "non" sans aucun commentaire."""

        return prompt

    def _call_openrouter_api(
        self,
        prompt: str,
        model: str
    ) -> Dict[str, Any]:
        """
        Call OpenRouter API with retry logic (SYNCHRONOUS).

        Args:
            prompt: The validation prompt
            model: Model to use for validation

        Returns:
            API response content
        """
        if not getattr(settings, 'OPENROUTER_API_KEY', None):
            raise ValueError("OpenRouter API key not configured")

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Tu es un assistant spécialisé dans l'évaluation de la pertinence de pages web pour des projets de recherche. Tu analyses le contenu des pages et détermines si elles correspondent aux objectifs du projet. Tu réponds uniquement et exclusivement par 'oui' ou 'non', sans aucun commentaire, explication ou texte additionnel."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0  # Deterministic responses
        }

        last_error = None

        # Retry logic
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    response_data = response.json()

                    if 'choices' in response_data and len(response_data['choices']) > 0:
                        choice = response_data['choices'][0]
                        message = choice.get('message', {})

                        return {
                            'content': message.get('content', ''),
                            'usage': response_data.get('usage', {})
                        }
                    else:
                        raise ValueError("No choices in API response")

                elif response.status_code == 429:
                    # Rate limit - wait and retry
                    wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                    logger.warning(f"Rate limit hit, waiting {wait_time}s before retry {attempt + 1}")
                    time.sleep(wait_time)
                    last_error = f"Rate limit (attempt {attempt + 1})"
                    continue

                else:
                    # Other HTTP error
                    error_text = response.text
                    raise ValueError(f"API error {response.status_code}: {error_text}")

            except requests.Timeout:
                last_error = f"Timeout (attempt {attempt + 1})"
                logger.warning(f"OpenRouter API timeout on attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                continue

            except Exception as e:
                last_error = str(e)
                logger.error(f"OpenRouter API error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                continue

        # All retries failed
        raise Exception(f"OpenRouter API failed after {self.max_retries} attempts. Last error: {last_error}")

    def _parse_yes_no_response(self, response_content: str) -> bool:
        """
        Parse the LLM response to extract yes/no decision.

        Args:
            response_content: Raw response from LLM

        Returns:
            True if relevant (response contains "oui"), False otherwise
        """
        if not response_content:
            return False

        content_lower = response_content.lower().strip()

        # Look for French "oui" or English "yes"
        if 'oui' in content_lower or 'yes' in content_lower:
            return True

        # Look for French "non" or English "no"
        if 'non' in content_lower or 'no' in content_lower:
            return False

        # Default to False if unclear
        logger.warning(f"Unclear LLM response: '{response_content}', defaulting to non-relevant")
        return False
