"""
Quality Scoring Service for MyWebIntelligence API

Computes quality_score based on heuristics and existing metadata.
Pure function service (no external dependencies, deterministic).

Architecture:
    5 scoring blocks with weighted contribution:
    - Access (30%): HTTP status, content-type, crawlability
    - Structure (15%): Title, description, keywords, canonical
    - Richness (25%): Word count, text/HTML ratio, reading time
    - Coherence (20%): Language match, relevance, freshness
    - Integrity (10%): LLM validation, readable extraction, pipeline completion

Score range: 0.0 (very poor) to 1.0 (excellent)
"""

import logging
import math
from datetime import datetime, timezone
from typing import TypedDict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Configuration des poids (modifiable via settings)
WEIGHTS = {
    "access": 0.30,
    "structure": 0.15,
    "richness": 0.25,
    "coherence": 0.20,
    "integrity": 0.10
}


class QualityResult(TypedDict):
    """Résultat du calcul de qualité."""
    score: float                    # 0.0 à 1.0
    category: str                   # "Excellent", "Bon", "Moyen", "Faible", "Très faible"
    flags: list[str]                # ["short_content", "wrong_language"]
    reason: str                     # Explication textuelle
    details: dict[str, float]       # Scores par bloc pour debug


class QualityScorer:
    """
    Service de calcul du quality_score.

    100% déterministe, basé sur métadonnées existantes.
    Pas de dépendances externes.
    """

    def __init__(self, custom_weights: Optional[dict] = None):
        """
        Initialize scorer avec pondérations optionnelles.

        Args:
            custom_weights: Remplace WEIGHTS par défaut (pour tests/tuning)
        """
        if custom_weights:
            self.weights = custom_weights
        else:
            # Load from settings
            self.weights = {
                "access": getattr(settings, 'QUALITY_WEIGHT_ACCESS', 0.30),
                "structure": getattr(settings, 'QUALITY_WEIGHT_STRUCTURE', 0.15),
                "richness": getattr(settings, 'QUALITY_WEIGHT_RICHNESS', 0.25),
                "coherence": getattr(settings, 'QUALITY_WEIGHT_COHERENCE', 0.20),
                "integrity": getattr(settings, 'QUALITY_WEIGHT_INTEGRITY', 0.10)
            }
        logger.debug(f"QualityScorer initialized with weights: {self.weights}")

    def compute_quality_score(
        self,
        expression: 'models.Expression',
        land: 'models.Land'
    ) -> QualityResult:
        """
        Calcule quality_score complet pour une expression.

        Args:
            expression: Expression ORM object (can be a mock with dict attributes)
            land: Land parent ORM object (can be a mock with dict attributes)

        Returns:
            QualityResult avec score 0-1, catégorie, flags, raison
        """
        all_flags = []
        details = {}

        # Bloc 1: Accès (30%) - BLOQUANT si erreur
        access_score, access_flags = self._score_access(expression)
        all_flags.extend(access_flags)
        details["access"] = access_score

        # Si accès échoue (HTTP erreur), score = 0
        if access_score == 0.0:
            return {
                "score": 0.0,
                "category": "Très faible",
                "flags": all_flags,
                "reason": f"Accès impossible: {', '.join(all_flags)}",
                "details": details
            }

        # Bloc 2: Structure (15%)
        struct_score, struct_flags = self._score_structure(expression)
        all_flags.extend(struct_flags)
        details["structure"] = struct_score

        # Bloc 3: Richesse (25%)
        rich_score, rich_flags = self._score_richness(expression)
        all_flags.extend(rich_flags)
        details["richness"] = rich_score

        # Bloc 4: Cohérence (20%)
        coher_score, coher_flags = self._score_coherence(expression, land)
        all_flags.extend(coher_flags)
        details["coherence"] = coher_score

        # Bloc 5: Intégrité (10%)
        integ_score, integ_flags = self._score_integrity(expression)
        all_flags.extend(integ_flags)
        details["integrity"] = integ_score

        # Agrégation pondérée
        final_score = (
            access_score * self.weights["access"] +
            struct_score * self.weights["structure"] +
            rich_score * self.weights["richness"] +
            coher_score * self.weights["coherence"] +
            integ_score * self.weights["integrity"]
        )

        # Clamp 0-1 (sécurité)
        final_score = max(0.0, min(1.0, final_score))

        # Déterminer catégorie
        if final_score >= 0.8:
            category = "Excellent"
        elif final_score >= 0.6:
            category = "Bon"
        elif final_score >= 0.4:
            category = "Moyen"
        elif final_score >= 0.2:
            category = "Faible"
        else:
            category = "Très faible"

        # Générer raison textuelle
        if final_score >= 0.8:
            reason = f"Haute qualité ({final_score:.2f}): contenu riche et complet"
        elif final_score >= 0.6:
            reason = f"Qualité acceptable ({final_score:.2f}): contenu standard"
        else:
            # Identifier principale pénalité
            main_issues = []
            if "http_error" in all_flags:
                main_issues.append("erreur HTTP")
            if "short_content" in all_flags or "very_short_content" in all_flags:
                main_issues.append("contenu trop court")
            if "wrong_language" in all_flags:
                main_issues.append("langue incorrecte")
            if "low_relevance" in all_flags:
                main_issues.append("faible pertinence")
            if "no_readable" in all_flags:
                main_issues.append("extraction échouée")

            reason = f"Qualité {category.lower()} ({final_score:.2f}): {', '.join(main_issues or all_flags[:2])}"

        return {
            "score": round(final_score, 3),
            "category": category,
            "flags": all_flags,
            "reason": reason,
            "details": details
        }

    def _score_access(self, expression) -> tuple[float, list[str]]:
        """
        Score d'accessibilité (0.0 à 1.0) - Bloc 1 (30%).

        Critères:
        - HTTP status (2xx = OK, 3xx = redirect, 4xx/5xx = error)
        - Content-Type (text/html OK, PDF bloquant, autre pénalité)
        - Crawled_at présent

        Returns:
            (score, flags)
        """
        score = 0.0
        flags = []

        # HTTP Status (critère bloquant)
        http_status = getattr(expression, 'http_status', None)

        if http_status is None:
            flags.append("no_http_status")
            return 0.0, flags

        # Convert to int if string
        if isinstance(http_status, str):
            try:
                http_status = int(http_status)
            except ValueError:
                flags.append("invalid_http_status")
                return 0.0, flags

        if 200 <= http_status < 300:
            score += 1.0  # Full score si 2xx
        elif 300 <= http_status < 400:
            score += 0.5  # Moitié si redirect
            flags.append("redirect")
        else:
            score = 0.0  # Zero si erreur
            flags.append("http_error")
            return score, flags  # Bloquant

        # Content-Type (critère bloquant pour PDF)
        content_type = getattr(expression, 'content_type', None)
        if content_type:
            content_type_lower = content_type.lower()
            if "text/html" in content_type_lower:
                pass  # OK, pas de pénalité
            elif "application/pdf" in content_type_lower:
                flags.append("non_html_pdf")
                return 0.0, flags  # Bloquant
            else:
                flags.append("non_html")
                score *= 0.3  # Grosse pénalité mais pas bloquant

        # Contenu crawlé (vérifie que crawled_at existe)
        crawled_at = getattr(expression, 'crawled_at', None)
        if crawled_at is None:
            flags.append("not_crawled")
            return 0.0, flags

        return score, flags

    def _score_structure(self, expression) -> tuple[float, list[str]]:
        """
        Score de structure HTML/métadonnées (0.0 à 1.0) - Bloc 2 (15%).

        Critères:
        - Title (40% du score structure)
        - Description (30%)
        - Keywords (15%)
        - Canonical URL (15%)

        Returns:
            (score, flags)
        """
        score = 0.0
        flags = []

        # Title présent et non vide
        title = getattr(expression, 'title', None)
        if title and len(title.strip()) > 0:
            score += 0.4  # 40% du score structure
        else:
            flags.append("no_title")

        # Description présente et suffisamment longue
        description = getattr(expression, 'description', None)
        if description and len(description.strip()) > 20:
            score += 0.3  # 30%
        else:
            flags.append("no_description")

        # Keywords présents
        keywords = getattr(expression, 'keywords', None)
        if keywords and len(keywords.strip()) > 0:
            score += 0.15  # 15%
        else:
            flags.append("no_keywords")

        # Canonical URL (bonne pratique SEO)
        canonical_url = getattr(expression, 'canonical_url', None)
        if canonical_url:
            score += 0.15  # 15%
        else:
            flags.append("no_canonical")

        return score, flags

    def _score_richness(self, expression) -> tuple[float, list[str]]:
        """
        Score de richesse textuelle (0.0 à 1.0) - Bloc 3 (25%).

        Critères:
        - Word count optimal (courbe gaussienne centrée sur 1500 mots) - 50%
        - Ratio word_count / content_length (optimal 0.1-0.3) - 30%
        - Reading time cohérent (0.5-15 min optimal) - 20%

        Returns:
            (score, flags)
        """
        score = 0.0
        flags = []

        # Word count (50% du score richesse)
        word_count = getattr(expression, 'word_count', None)

        if word_count is None or word_count == 0:
            flags.append("no_content")
            return 0.0, flags

        wc = word_count

        if wc < 80:
            # Trop court, quasi-null
            score_wc = 0.1
            flags.append("very_short_content")
        elif wc < 150:
            # Court mais acceptable
            score_wc = 0.3
            flags.append("short_content")
        elif 150 <= wc <= 5000:
            # Zone optimale : courbe gaussienne centrée sur 1500
            optimal = 1500
            sigma = 1500  # Écart-type large pour tolérance
            score_wc = math.exp(-((wc - optimal) ** 2) / (2 * sigma ** 2))
        else:
            # Très long : décroissance douce
            score_wc = 0.8 - (wc - 5000) / 50000  # Décroit doucement
            score_wc = max(0.5, score_wc)  # Plancher à 0.5
            if wc > 10000:
                flags.append("very_long_content")

        score += score_wc * 0.5

        # Ratio word_count / content_length (30% du score richesse)
        content_length = getattr(expression, 'content_length', None)
        if content_length and content_length > 0:
            ratio = word_count / content_length

            if ratio < 0.05:
                # HTML très lourd, peu de texte (boilerplate, scripts)
                score_ratio = 0.2
                flags.append("poor_text_ratio")
            elif ratio < 0.1:
                score_ratio = 0.5
                flags.append("low_text_ratio")
            elif 0.1 <= ratio <= 0.3:
                # Zone optimale
                score_ratio = 1.0
            else:
                # Trop de texte vs HTML (inhabituel mais OK)
                score_ratio = 0.9

            score += score_ratio * 0.3
        else:
            # Pas de content_length → neutre
            score += 0.3 * 0.5  # Score moyen

        # Reading time cohérent (20% du score richesse)
        reading_time = getattr(expression, 'reading_time', None)
        if reading_time:
            rt = reading_time  # En minutes

            if rt < 0.25:  # <15 secondes
                score_rt = 0.2
                flags.append("very_short_reading")
            elif rt < 0.5:  # 15-30 secondes
                score_rt = 0.5
                flags.append("short_reading")
            elif 0.5 <= rt <= 15:  # 30s à 15min (zone normale)
                score_rt = 1.0
            elif 15 < rt <= 25:  # 15-25min (long mais OK)
                score_rt = 0.8
            else:  # >25min (suspicieux)
                score_rt = 0.3
                flags.append("very_long_reading")

            score += score_rt * 0.2
        else:
            # Pas de reading_time → neutre
            score += 0.2 * 0.5

        return score, flags

    def _score_coherence(
        self,
        expression,
        land
    ) -> tuple[float, list[str]]:
        """
        Score de cohérence avec le land et logique métier (0.0 à 1.0) - Bloc 4 (20%).

        Critères:
        - Langue alignée avec land (40% du score cohérence)
        - Relevance (pertinence mot-clés) (40%)
        - Fraîcheur contenu (published_at) (20%)

        Returns:
            (score, flags)
        """
        score = 0.0
        flags = []

        # Langue alignée avec land (40% du score cohérence)
        expr_lang = getattr(expression, 'language', None)  # Note: column name is 'language', not 'lang'
        land_lang = getattr(land, 'lang', None)

        if expr_lang and land_lang:
            land_languages = land_lang if isinstance(land_lang, list) else [land_lang]

            if expr_lang in land_languages:
                score_lang = 1.0
            else:
                score_lang = 0.0
                flags.append("wrong_language")

            score += score_lang * 0.4
        else:
            # Pas de langue détectée → neutre
            score += 0.4 * 0.5
            if not expr_lang:
                flags.append("no_language")

        # Relevance (pertinence mot-clés) (40% du score cohérence)
        relevance = getattr(expression, 'relevance', None)
        if relevance is not None:
            # Normaliser relevance (supposé 0-10 ou plus)
            # Mapper vers 0-1 avec saturation à 5.0
            norm_relevance = min(relevance / 5.0, 1.0)
            score += norm_relevance * 0.4

            if relevance < 0.5:
                flags.append("low_relevance")
        else:
            # Pas de relevance → neutre
            score += 0.4 * 0.5

        # Fraîcheur contenu (20% du score cohérence)
        published_at = getattr(expression, 'published_at', None)
        if published_at:
            now = datetime.now(timezone.utc)

            # Ensure published_at is timezone-aware
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)

            age_days = (now - published_at).days

            if age_days < 0:
                # Publié dans le futur (erreur)
                score_fresh = 0.0
                flags.append("future_date")
            elif age_days < 365:  # <1 an
                score_fresh = 1.0
            elif age_days < 730:  # 1-2 ans
                score_fresh = 0.9
            elif age_days < 1825:  # 2-5 ans
                score_fresh = 0.7
            else:  # >5 ans
                score_fresh = 0.5
                flags.append("old_content")

            score += score_fresh * 0.2
        else:
            # Pas de date de publication → neutre
            score += 0.2 * 0.5

        return score, flags

    def _score_integrity(self, expression) -> tuple[float, list[str]]:
        """
        Score d'intégrité du pipeline (0.0 à 1.0) - Bloc 5 (10%).

        Critères:
        - Validation LLM réussie (40% du score intégrité)
        - Extraction readable réussie (40%)
        - Pipeline complet (approved_at présent) (20%)

        Returns:
            (score, flags)
        """
        score = 0.0
        flags = []

        # Validation LLM réussie (40% du score intégrité)
        validllm = getattr(expression, 'validllm', None)
        if validllm == "oui":
            score += 0.4
        elif validllm == "non":
            score += 0.0
            flags.append("llm_rejected")
        else:
            # Pas de validation LLM → neutre
            score += 0.4 * 0.5

        # Extraction readable réussie (40% du score intégrité)
        readable_at = getattr(expression, 'readable_at', None)
        readable = getattr(expression, 'readable', None)

        if readable_at and readable:
            if len(readable.strip()) > 100:
                score += 0.4
            else:
                score += 0.2
                flags.append("short_readable")
        else:
            score += 0.0
            flags.append("no_readable")

        # Pipeline complet (approved_at présent) (20%)
        approved_at = getattr(expression, 'approved_at', None)
        if approved_at:
            score += 0.2
        else:
            score += 0.0
            flags.append("not_approved")

        return score, flags
