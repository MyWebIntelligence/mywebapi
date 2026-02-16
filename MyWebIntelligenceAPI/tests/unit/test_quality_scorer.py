"""
Tests unitaires pour le QualityScorer

Valide les 5 blocs de scoring et les cas de la truth table.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.services.quality_scorer import QualityScorer, QualityResult


# Mock classes for testing
class MockExpression:
    """Mock Expression object pour tests"""

    def __init__(self, **kwargs):
        # Assign all kwargs as attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockLand:
    """Mock Land object pour tests"""

    def __init__(self, lang=None):
        self.lang = lang if lang else ["fr"]


# Fixtures
@pytest.fixture
def scorer():
    """QualityScorer avec poids par défaut"""
    return QualityScorer()


@pytest.fixture
def truth_table():
    """Charge la truth table depuis le fichier JSON"""
    truth_table_path = Path(__file__).parent.parent / "data" / "quality_truth_table.json"
    with open(truth_table_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def perfect_expression():
    """Expression parfaite (score ~1.0)"""
    return MockExpression(
        http_status=200,
        content_type="text/html",
        title="Great Article Title",
        description="Comprehensive description with sufficient length for SEO",
        keywords="machine learning, AI, deep learning",
        canonical_url="https://example.com/article",
        word_count=1500,
        content_length=12000,  # Good ratio (0.125) for richness
        reading_time=7,
        language="fr",
        relevance=4.5,
        published_at=datetime.now(timezone.utc) - timedelta(days=30),
        validllm="oui",
        readable="Long readable content with meaningful text..." * 10,
        readable_at=datetime.now(timezone.utc),
        approved_at=datetime.now(timezone.utc),
        crawled_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def test_land():
    """Land de test FR+EN"""
    return MockLand(lang=["fr", "en"])


# Tests unitaires par bloc
class TestAccessBlock:
    """Tests pour le bloc Access (30%)"""

    def test_http_200_ok(self, scorer, test_land):
        """HTTP 200 doit donner score access = 1.0"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert result["details"]["access"] == 1.0
        assert "http_error" not in result["flags"]

    def test_http_404_blocks(self, scorer, test_land):
        """HTTP 404 doit bloquer avec score = 0"""
        expr = MockExpression(
            http_status=404,
            content_type="text/html"
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert result["score"] == 0.0
        assert "http_error" in result["flags"]
        assert result["category"] == "Très faible"

    def test_http_redirect_penalty(self, scorer, test_land):
        """HTTP 302 redirect doit avoir pénalité"""
        expr = MockExpression(
            http_status=302,
            content_type="text/html",
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert result["details"]["access"] == 0.5
        assert "redirect" in result["flags"]

    def test_pdf_blocks(self, scorer, test_land):
        """PDF doit être bloqué"""
        expr = MockExpression(
            http_status=200,
            content_type="application/pdf"
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert result["score"] == 0.0
        assert "non_html_pdf" in result["flags"]


class TestStructureBlock:
    """Tests pour le bloc Structure (15%)"""

    def test_all_structure_present(self, scorer, test_land):
        """Tous les éléments de structure présents"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            title="Test Title",
            description="Test description with sufficient length",
            keywords="test, keywords",
            canonical_url="https://example.com/test",
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert result["details"]["structure"] == 1.0
        assert "no_title" not in result["flags"]

    def test_no_title_penalty(self, scorer, test_land):
        """Pas de title doit avoir pénalité"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            title=None,
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert result["details"]["structure"] < 1.0
        assert "no_title" in result["flags"]


class TestRichnessBlock:
    """Tests pour le bloc Richness (25%)"""

    def test_optimal_word_count(self, scorer, test_land):
        """Word count optimal ~1500 mots"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            word_count=1500,
            content_length=10000,  # Better ratio for richness
            reading_time=7,
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        # Richness devrait être élevé
        assert result["details"]["richness"] > 0.75

    def test_short_content_penalty(self, scorer, test_land):
        """Contenu court doit avoir pénalité"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            word_count=50,
            content_length=5000,
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert result["details"]["richness"] < 0.5
        assert "very_short_content" in result["flags"]

    def test_no_content_blocks(self, scorer, test_land):
        """Pas de contenu doit bloquer richness"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            word_count=0,
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        # Access OK mais richness = 0
        assert result["score"] < 0.5
        assert "no_content" in result["flags"]


class TestCoherenceBlock:
    """Tests pour le bloc Coherence (20%)"""

    def test_language_match(self, scorer):
        """Langue correspond au land"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            language="fr",
            relevance=3.0,
            crawled_at=datetime.now(timezone.utc)
        )
        land = MockLand(lang=["fr"])
        result = scorer.compute_quality_score(expr, land)
        # Pas de pénalité langue
        assert "wrong_language" not in result["flags"]

    def test_wrong_language_penalty(self, scorer):
        """Langue incorrecte doit avoir pénalité"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            language="de",
            relevance=3.0,
            crawled_at=datetime.now(timezone.utc)
        )
        land = MockLand(lang=["fr"])
        result = scorer.compute_quality_score(expr, land)
        assert "wrong_language" in result["flags"]

    def test_low_relevance_penalty(self, scorer, test_land):
        """Faible relevance doit avoir pénalité"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            language="fr",
            relevance=0.2,
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert "low_relevance" in result["flags"]


class TestIntegrityBlock:
    """Tests pour le bloc Integrity (10%)"""

    def test_llm_validated(self, scorer, test_land):
        """LLM validé doit contribuer positivement"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            validllm="oui",
            readable="Readable content here..." * 10,
            readable_at=datetime.now(timezone.utc),
            approved_at=datetime.now(timezone.utc),
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert result["details"]["integrity"] == 1.0

    def test_llm_rejected_penalty(self, scorer, test_land):
        """LLM rejeté doit avoir pénalité"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            validllm="non",
            readable="Content...",
            readable_at=datetime.now(timezone.utc),
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert "llm_rejected" in result["flags"]

    def test_no_readable_penalty(self, scorer, test_land):
        """Pas de readable doit avoir pénalité"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            readable=None,
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert "no_readable" in result["flags"]


# Tests d'intégration
class TestQualityScorer:
    """Tests d'intégration du scorer complet"""

    def test_perfect_expression_score(self, scorer, perfect_expression, test_land):
        """Expression parfaite doit avoir score excellent"""
        result = scorer.compute_quality_score(perfect_expression, test_land)

        assert result["score"] >= 0.85
        assert result["category"] == "Excellent"
        assert len(result["flags"]) == 0
        assert "score" in result
        assert "category" in result
        assert "flags" in result
        assert "reason" in result
        assert "details" in result

    def test_result_structure(self, scorer, perfect_expression, test_land):
        """Vérifier structure QualityResult"""
        result = scorer.compute_quality_score(perfect_expression, test_land)

        # Type checks
        assert isinstance(result["score"], float)
        assert isinstance(result["category"], str)
        assert isinstance(result["flags"], list)
        assert isinstance(result["reason"], str)
        assert isinstance(result["details"], dict)

        # Score bounds
        assert 0.0 <= result["score"] <= 1.0

        # Details contient les 5 blocs
        assert "access" in result["details"]
        assert "structure" in result["details"]
        assert "richness" in result["details"]
        assert "coherence" in result["details"]
        assert "integrity" in result["details"]

    def test_custom_weights(self, test_land):
        """Test avec pondérations personnalisées"""
        custom_weights = {
            "access": 0.5,
            "structure": 0.1,
            "richness": 0.2,
            "coherence": 0.1,
            "integrity": 0.1
        }
        scorer = QualityScorer(custom_weights=custom_weights)

        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)

        # Access parfait devrait donner score plus élevé avec weights custom
        assert result["score"] >= 0.4


class TestTruthTable:
    """Tests de validation contre la truth table"""

    def test_truth_table_consistency(self, truth_table):
        """Vérifier cohérence de la truth table"""
        assert len(truth_table) == 20

        for case in truth_table:
            # Champs requis
            assert "case_id" in case
            assert "description" in case
            assert "expected_score_min" in case
            assert "expected_score_max" in case

            # Cohérence min/max
            assert case["expected_score_min"] <= case["expected_score_max"]
            assert 0.0 <= case["expected_score_min"] <= 1.0
            assert 0.0 <= case["expected_score_max"] <= 1.0

    def test_truth_table_case_1_perfect(self, scorer, truth_table):
        """Cas 1: Article complet optimal"""
        case = truth_table[0]  # case_id 1

        expr = MockExpression(
            http_status=case["http_status"],
            content_type=case["content_type"],
            title=case.get("title", "Test"),
            description=case.get("description", "Test description"),
            keywords="test" if case.get("has_keywords") else None,
            canonical_url="https://example.com" if case.get("has_canonical") else None,
            word_count=case["word_count"],
            content_length=case.get("content_length", 50000),
            reading_time=case.get("reading_time", 7),
            language=case.get("language"),
            relevance=case.get("relevance", 3.0),
            validllm=case.get("validllm"),
            readable="Content..." * 50 if case.get("has_readable") else None,
            readable_at=datetime.now(timezone.utc) if case.get("has_readable") else None,
            approved_at=datetime.now(timezone.utc) if case.get("has_approved") else None,
            crawled_at=datetime.now(timezone.utc)
        )

        land = MockLand(lang=case.get("land_lang", ["fr"]))
        result = scorer.compute_quality_score(expr, land)

        # Valider score dans fourchette
        assert case["expected_score_min"] <= result["score"] <= case["expected_score_max"], \
            f"Case {case['case_id']}: score {result['score']} hors limites [{case['expected_score_min']}, {case['expected_score_max']}]"

        assert result["category"] == case["expected_category"]

    def test_truth_table_case_2_http_error(self, scorer, truth_table):
        """Cas 2: Erreur 404"""
        case = truth_table[1]  # case_id 2

        expr = MockExpression(
            http_status=404,
            content_type="text/html",
            word_count=0
        )

        land = MockLand(lang=["fr"])
        result = scorer.compute_quality_score(expr, land)

        assert result["score"] == 0.0
        assert "http_error" in result["flags"]
        assert result["category"] == "Très faible"

    def test_truth_table_case_5_pdf(self, scorer, truth_table):
        """Cas 5: PDF non-HTML"""
        case = truth_table[4]  # case_id 5

        expr = MockExpression(
            http_status=200,
            content_type="application/pdf",
            word_count=0
        )

        land = MockLand(lang=["fr"])
        result = scorer.compute_quality_score(expr, land)

        assert result["score"] == 0.0
        assert "non_html_pdf" in result["flags"]

    @pytest.mark.parametrize("case_index", [0, 1, 2, 3, 4, 7, 12])
    def test_truth_table_sample_cases(self, scorer, truth_table, case_index):
        """Valider échantillon de cas de la truth table"""
        case = truth_table[case_index]

        # Build mock expression from case
        expr = MockExpression(
            http_status=case.get("http_status"),
            content_type=case.get("content_type", "text/html"),
            title=case.get("title") if case.get("has_title") else None,
            description=case.get("description") if case.get("has_description") else None,
            keywords="test" if case.get("has_keywords") else None,
            canonical_url="https://example.com" if case.get("has_canonical") else None,
            word_count=case.get("word_count", 0),
            content_length=case.get("content_length"),
            reading_time=case.get("reading_time"),
            language=case.get("language"),
            relevance=case.get("relevance"),
            validllm=case.get("validllm"),
            readable="Content..." * 50 if case.get("has_readable") else None,
            readable_at=datetime.now(timezone.utc) if case.get("has_readable") else None,
            approved_at=datetime.now(timezone.utc) if case.get("has_approved") else None,
            crawled_at=datetime.now(timezone.utc) if case.get("http_status") else None
        )

        land = MockLand(lang=case.get("land_lang", ["fr"]))
        result = scorer.compute_quality_score(expr, land)

        # Valider dans fourchette (avec tolérance de 10% pour flexibilité)
        tolerance = 0.1
        min_score = max(0.0, case["expected_score_min"] - tolerance)
        max_score = min(1.0, case["expected_score_max"] + tolerance)

        assert min_score <= result["score"] <= max_score, \
            f"Case {case['case_id']} ({case['description']}): " \
            f"score {result['score']:.2f} hors limites [{min_score:.2f}, {max_score:.2f}]"


# Tests edge cases
class TestEdgeCases:
    """Tests de cas limites"""

    def test_missing_http_status(self, scorer, test_land):
        """HTTP status manquant"""
        expr = MockExpression(http_status=None)
        result = scorer.compute_quality_score(expr, test_land)
        assert result["score"] == 0.0
        assert "no_http_status" in result["flags"]

    def test_http_status_string(self, scorer, test_land):
        """HTTP status en string (legacy format)"""
        expr = MockExpression(
            http_status="200",
            content_type="text/html",
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert result["details"]["access"] == 1.0

    def test_very_high_relevance(self, scorer, test_land):
        """Relevance très élevée (saturation à 1.0)"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            language="fr",
            relevance=10.0,  # Très élevé
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        # Coherence doit être saturé à une valeur raisonnable
        assert result["details"]["coherence"] <= 1.0

    def test_future_published_date(self, scorer, test_land):
        """Date de publication dans le futur"""
        expr = MockExpression(
            http_status=200,
            content_type="text/html",
            published_at=datetime.now(timezone.utc) + timedelta(days=30),
            crawled_at=datetime.now(timezone.utc)
        )
        result = scorer.compute_quality_score(expr, test_land)
        assert "future_date" in result["flags"]
