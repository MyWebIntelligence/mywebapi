"""
Tests unitaires pour LLMValidationService.
V2 SYNC-ONLY: toutes les méthodes sont synchrones (requests, pas httpx).
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.llm_validation_service import LLMValidationService
from app.schemas.readable import ValidationResult
from app.db.models import Expression, Land


@pytest.fixture
def mock_db():
    """Mock de session de base de données (sync)."""
    return MagicMock()


@pytest.fixture
def llm_service(mock_db):
    """Instance de LLMValidationService avec mock DB."""
    return LLMValidationService(mock_db)


@pytest.fixture
def sample_expression():
    """Expression d'exemple pour les tests."""
    expr = MagicMock(spec=Expression)
    expr.id = 1
    expr.url = "https://example.com/test-article"
    expr.title = "Test Article Title"
    expr.description = "This is a test article description"
    expr.readable = "# Test Article\n\nThis is the readable content of the test article."
    expr.lang = "fr"
    expr.land_id = 1
    return expr


@pytest.fixture
def sample_land():
    """Land d'exemple pour les tests."""
    land = MagicMock(spec=Land)
    land.id = 1
    land.name = "Test Research Project"
    land.description = "Research project about testing and validation"
    land.words = ["test", "validation", "research"]
    return land


class TestLLMValidationService:
    """Tests pour LLMValidationService."""

    @patch('app.services.llm_validation_service.settings')
    def test_is_validation_enabled_true(self, mock_settings, llm_service):
        """Test de vérification de l'activation de la validation LLM."""
        mock_settings.OPENROUTER_ENABLED = True
        mock_settings.OPENROUTER_API_KEY = "test-api-key"

        result = llm_service._is_validation_enabled()
        assert result is True

    @patch('app.services.llm_validation_service.settings')
    def test_is_validation_enabled_false_disabled(self, mock_settings, llm_service):
        """Test quand la validation LLM est désactivée."""
        mock_settings.OPENROUTER_ENABLED = False
        mock_settings.OPENROUTER_API_KEY = "test-api-key"

        result = llm_service._is_validation_enabled()
        assert result is False

    @patch('app.services.llm_validation_service.settings')
    def test_is_validation_enabled_false_no_key(self, mock_settings, llm_service):
        """Test quand la clé API est manquante."""
        mock_settings.OPENROUTER_ENABLED = True
        mock_settings.OPENROUTER_API_KEY = None

        result = llm_service._is_validation_enabled()
        assert result is False

    def test_build_relevance_prompt(self, llm_service, sample_expression, sample_land):
        """Test de construction du prompt de validation."""
        prompt = llm_service._build_relevance_prompt(sample_expression, sample_land)

        # Vérifications
        assert "Test Research Project" in prompt
        assert "Research project about testing and validation" in prompt
        assert "test, validation, research" in prompt
        assert "https://example.com/test-article" in prompt
        assert "Test Article Title" in prompt
        assert "This is a test article description" in prompt
        assert "Test Article" in prompt  # Début du contenu readable
        assert "oui" in prompt
        assert "non" in prompt

    def test_build_relevance_prompt_long_content(self, llm_service, sample_expression, sample_land):
        """Test de construction du prompt avec contenu long."""
        # Contenu très long (> 1000 caractères)
        long_content = "Long content " * 100  # > 1000 caractères
        sample_expression.readable = long_content

        prompt = llm_service._build_relevance_prompt(sample_expression, sample_land)

        # Vérifications - contenu tronqué
        readable_section = prompt.split("Readable (extrait) : ")[1].split("\n")[0]
        assert len(readable_section) <= 1003  # 1000 + "..."
        assert readable_section.endswith("...")

    def test_parse_yes_no_response_oui(self, llm_service):
        """Test de parsing de réponse 'oui'."""
        test_cases = [
            "oui",
            "OUI",
            "Oui",
            "  oui  ",
            "La réponse est oui.",
            "yes"
        ]

        for response in test_cases:
            result = llm_service._parse_yes_no_response(response)
            assert result is True, f"Failed for: {response}"

    def test_parse_yes_no_response_non(self, llm_service):
        """Test de parsing de réponse 'non'."""
        test_cases = [
            "non",
            "NON",
            "Non",
            "  non  ",
            "La réponse est non.",
            "no"
        ]

        for response in test_cases:
            result = llm_service._parse_yes_no_response(response)
            assert result is False, f"Failed for: {response}"

    def test_parse_yes_no_response_unclear(self, llm_service):
        """Test de parsing de réponse peu claire."""
        test_cases = [
            "",
            "peut-être",
            "je ne sais pas",
            "unclear response",
            "123",
            None
        ]

        for response in test_cases:
            result = llm_service._parse_yes_no_response(response or "")
            assert result is False, f"Failed for: {response}"

    @patch('app.services.llm_validation_service.requests.post')
    @patch('app.services.llm_validation_service.settings')
    def test_call_openrouter_api_success(self, mock_settings, mock_post, llm_service):
        """Test d'appel API OpenRouter réussi (sync requests.post)."""
        mock_settings.OPENROUTER_API_KEY = "test-api-key"

        # Mock de la réponse
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "oui"
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 1
            }
        }
        mock_post.return_value = mock_response

        # Test (sync)
        result = llm_service._call_openrouter_api(
            "Test prompt",
            "anthropic/claude-3.5-sonnet"
        )

        # Vérifications
        assert result['content'] == "oui"
        assert result['usage']['prompt_tokens'] == 100
        assert result['usage']['completion_tokens'] == 1
        mock_post.assert_called_once()

    @patch('app.services.llm_validation_service.time.sleep')
    @patch('app.services.llm_validation_service.requests.post')
    @patch('app.services.llm_validation_service.settings')
    def test_call_openrouter_api_rate_limit(self, mock_settings, mock_post, mock_sleep, llm_service):
        """Test de gestion de la limite de taux (sync)."""
        mock_settings.OPENROUTER_API_KEY = "test-api-key"

        # Mock de la réponse rate limit puis succès
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "oui"}}],
            "usage": {}
        }

        mock_post.side_effect = [rate_limit_response, success_response]

        # Test (sync)
        result = llm_service._call_openrouter_api(
            "Test prompt",
            "anthropic/claude-3.5-sonnet"
        )

        # Vérifications
        assert result['content'] == "oui"
        assert mock_post.call_count == 2  # Retry après rate limit

    @patch('app.services.llm_validation_service.time.sleep')
    @patch('app.services.llm_validation_service.requests.post')
    @patch('app.services.llm_validation_service.settings')
    def test_call_openrouter_api_failure(self, mock_settings, mock_post, mock_sleep, llm_service):
        """Test d'échec d'appel API OpenRouter (sync)."""
        mock_settings.OPENROUTER_API_KEY = "test-api-key"

        # Mock de réponse d'erreur
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        mock_post.return_value = error_response

        # Test (sync) - la ValueError est catchée puis re-raised via Exception
        with pytest.raises(Exception) as exc_info:
            llm_service._call_openrouter_api(
                "Test prompt",
                "anthropic/claude-3.5-sonnet"
            )

        # Vérifications
        assert "500" in str(exc_info.value)

    @patch.object(LLMValidationService, '_is_validation_enabled')
    def test_validate_expression_relevance_disabled(self, mock_enabled, llm_service, sample_expression, sample_land):
        """Test de validation quand le service est désactivé (sync)."""
        mock_enabled.return_value = False

        result = llm_service.validate_expression_relevance(sample_expression, sample_land)

        assert result.is_relevant is True  # Défaut à True si désactivé
        assert result.model_used == "disabled"
        assert result.error_message == "LLM validation is disabled"

    @patch('app.services.llm_validation_service.settings')
    @patch.object(LLMValidationService, '_is_validation_enabled')
    @patch.object(LLMValidationService, '_call_openrouter_api')
    def test_validate_expression_relevance_success(self, mock_api, mock_enabled, mock_settings, llm_service, sample_expression, sample_land):
        """Test de validation réussie (sync)."""
        mock_enabled.return_value = True
        mock_settings.OPENROUTER_MODEL = "anthropic/claude-3.5-sonnet"
        mock_api.return_value = {
            'content': 'oui',
            'usage': {'prompt_tokens': 100, 'completion_tokens': 1}
        }

        result = llm_service.validate_expression_relevance(sample_expression, sample_land)

        assert result.is_relevant is True
        assert result.model_used == "anthropic/claude-3.5-sonnet"
        assert result.prompt_tokens == 100
        assert result.completion_tokens == 1
        assert result.error_message is None

    @patch('app.services.llm_validation_service.settings')
    @patch.object(LLMValidationService, '_is_validation_enabled')
    @patch.object(LLMValidationService, '_call_openrouter_api')
    def test_validate_expression_relevance_not_relevant(self, mock_api, mock_enabled, mock_settings, llm_service, sample_expression, sample_land):
        """Test de validation avec résultat non pertinent (sync)."""
        mock_enabled.return_value = True
        mock_settings.OPENROUTER_MODEL = "anthropic/claude-3.5-sonnet"
        mock_api.return_value = {
            'content': 'non',
            'usage': {'prompt_tokens': 100, 'completion_tokens': 1}
        }

        result = llm_service.validate_expression_relevance(sample_expression, sample_land)

        assert result.is_relevant is False
        assert result.model_used == "anthropic/claude-3.5-sonnet"


@pytest.mark.asyncio
class TestLLMValidationServiceIntegration:
    """Tests d'intégration pour LLMValidationService."""

    async def test_real_openrouter_api_call(self):
        """Test avec un vrai appel API OpenRouter."""
        pytest.skip("Requires real OpenRouter API key")

    async def test_validation_with_database(self):
        """Test de validation avec vraie base de données."""
        pytest.skip("Requires real database setup")
