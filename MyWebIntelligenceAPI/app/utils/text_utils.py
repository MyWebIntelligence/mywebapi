"""
Utilitaires d'analyse de texte pour l'extraction de paragraphes et métadonnées
"""

import re
import string
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

try:
    from langdetect import detect as _langdetect_detect, LangDetectException as _LangDetectException
except ImportError:  # pragma: no cover - optional dependency
    _langdetect_detect = None
    _LangDetectException = None

def analyze_text_metrics(text: str) -> Dict[str, any]:
    """Analyse complète des métriques d'un texte."""
    
    # Nettoyage de base
    clean_text = text.strip()
    
    # Métriques de base
    char_count = len(clean_text)
    word_count = len(clean_text.split()) if clean_text else 0
    
    # Comptage des phrases (approximatif)
    sentence_endings = re.findall(r'[.!?]+', clean_text)
    sentence_count = len(sentence_endings) if sentence_endings else 1
    
    # Détection de langue
    language = detect_language(clean_text)
    
    # Score de lisibilité (approximation française du Flesch Reading Ease)
    reading_level = calculate_reading_level(clean_text, word_count, sentence_count)
    
    return {
        'word_count': word_count,
        'char_count': char_count,
        'sentence_count': sentence_count,
        'language': language,
        'reading_level': reading_level
    }

def detect_language(text: str) -> Optional[str]:
    """
    Détecte la langue d'un texte de manière robuste.

    Supporte 55+ langues via langdetect (basé sur le détecteur de Google):
    - Langues européennes: fr, en, es, de, it, pt, nl, pl, ru, etc.
    - Langues asiatiques: zh-cn, zh-tw, ja, ko, th, vi, etc.
    - Langues du Moyen-Orient: ar, he, fa, tr, etc.

    Returns:
        Code ISO 639-1 de la langue (ex: 'fr', 'en', 'es') ou None si échec
    """
    # Minimum 10 caractères pour une détection fiable (réduit de 20 à 10)
    if not text or len(text.strip()) < 10:
        logger.info(f"Text too short for language detection: {len(text.strip()) if text else 0} chars")
        return None

    # Nettoyer le texte (enlever URLs, emails, etc.)
    original_length = len(text)
    clean_text = re.sub(r'http[s]?://\S+', '', text)
    clean_text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', clean_text)
    clean_text = clean_text.strip()

    logger.info(f"Language detection: original={original_length} chars, cleaned={len(clean_text)} chars")

    if len(clean_text) < 10:
        logger.warning(f"Text too short after cleaning ({len(clean_text)} chars), using fallback")
        return _detect_language_fallback(text)

    if not _langdetect_detect:
        logger.warning("langdetect library not installed, using fallback method")
        return _detect_language_fallback(text)

    try:
        detected_lang = _langdetect_detect(clean_text)
    except _LangDetectException as e:  # type: ignore[misc]
        logger.warning(f"LangDetectException: {e}, using fallback method")
        return _detect_language_fallback(text)
    except Exception as e:
        logger.warning(f"Unexpected error in language detection: {e}, using fallback method")
        return _detect_language_fallback(text)

    # Normaliser certains codes (langdetect retourne parfois des codes non-standard)
    lang_mapping = {
        'zh-cn': 'zh',  # Chinois simplifié
        'zh-tw': 'zh',  # Chinois traditionnel
        'no': 'nb',     # Norvégien
    }

    detected_lang = lang_mapping.get(detected_lang, detected_lang)

    # Valider que c'est un code ISO 639-1 valide (2 lettres)
    if detected_lang and len(detected_lang) <= 3:
        logger.info(f"Language detected by langdetect: {detected_lang}")
        return detected_lang

    logger.warning(f"Invalid language code from langdetect: {detected_lang}")
    return _detect_language_fallback(text)

def _detect_language_fallback(text: str) -> Optional[str]:
    """
    Méthode de fallback simple pour détection fr/en uniquement.
    Utilisée si langdetect échoue.
    """
    try:
        if not text or len(text.strip()) < 10:
            logger.info(f"Fallback: text too short ({len(text.strip()) if text else 0} chars)")
            return None

        # Mots français courants
        french_words = {
            'le', 'de', 'et', 'à', 'un', 'il', 'être', 'en', 'avoir', 'que',
            'pour', 'dans', 'ce', 'son', 'une', 'sur', 'avec', 'ne', 'se', 'pas',
            'tout', 'plus', 'par', 'les', 'du', 'des', 'la', 'au', 'fait', 'été'
        }

        # Mots anglais courants
        english_words = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'it',
            'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this',
            'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she', 'or'
        }

        # Nettoyer et diviser le texte
        words = re.findall(r'\b[a-zA-ZàâäéèêëïîôùûüÿñçÀÂÄÉÈÊËÏÎÔÙÛÜŸÑÇ]+\b', text.lower())

        if len(words) < 3:
            logger.info(f"Fallback: not enough words ({len(words)})")
            # Pour du contenu substantiel sans mots reconnus, retourner 'en' par défaut
            if len(text.strip()) > 50:
                logger.info("Fallback: defaulting to 'en' for substantial text")
                return 'en'
            return None

        french_score = sum(1 for word in words if word in french_words)
        english_score = sum(1 for word in words if word in english_words)

        logger.info(f"Fallback scores: fr={french_score}, en={english_score}, total_words={len(words)}")

        # Si suffisamment de mots détectés (seuil réduit de 3 à 2)
        if french_score + english_score >= 2:
            if french_score > english_score:
                logger.info("Fallback: detected 'fr' by word matching")
                return 'fr'
            elif english_score > french_score:
                logger.info("Fallback: detected 'en' by word matching")
                return 'en'

        # Détection par caractères spéciaux français
        french_chars = re.findall(r'[àâäéèêëïîôùûüÿñç]', text.lower())
        if len(french_chars) > len(words) * 0.02:  # 2% de caractères français
            logger.info(f"Fallback: detected 'fr' by accent chars ({len(french_chars)} accents)")
            return 'fr'

        # Pour du contenu substantiel, retourner 'en' par défaut
        if len(text.strip()) > 50:
            logger.info("Fallback: defaulting to 'en' for unidentified text")
            return 'en'

        logger.info("Fallback: no language detected")
        return None

    except Exception as e:
        logger.warning(f"Error in fallback language detection: {e}")
        return None

def calculate_reading_level(text: str, word_count: int, sentence_count: int) -> Optional[float]:
    """Calcule un score de lisibilité approximatif."""
    try:
        if word_count < 5 or sentence_count < 1:
            return None
        
        # Calcul des syllabes approximatif
        syllable_count = estimate_syllables(text)
        
        if syllable_count == 0:
            return None
        
        # Formule adaptée du Flesch Reading Ease pour le français
        # Score = 207 - (1.015 × moyenne_mots_par_phrase) - (84.6 × moyenne_syllabes_par_mot)
        avg_words_per_sentence = word_count / sentence_count
        avg_syllables_per_word = syllable_count / word_count
        
        score = 207 - (1.015 * avg_words_per_sentence) - (84.6 * avg_syllables_per_word)
        
        # Normaliser entre 0 et 100
        return max(0.0, min(100.0, score))
        
    except Exception as e:
        logger.warning(f"Error calculating reading level: {e}")
        return None

def estimate_syllables(text: str) -> int:
    """Estimation approximative du nombre de syllabes."""
    # Simplification pour le français : compte les voyelles consécutives comme une syllabe
    vowels = "aeiouàâäéèêëïîôùûüÿAEIOUÀÂÄÉÈÊËÏÎÔÙÛÜŸ"
    syllable_count = 0
    previous_was_vowel = False
    
    for char in text:
        is_vowel = char in vowels
        if is_vowel and not previous_was_vowel:
            syllable_count += 1
        previous_was_vowel = is_vowel
    
    # Au minimum 1 syllabe par mot
    word_count = len(text.split())
    return max(syllable_count, word_count)

def extract_paragraphs_from_text(
    text: str, 
    min_length: int = 50,
    max_length: int = 5000
) -> List[str]:
    """Extrait les paragraphes d'un texte long."""
    
    if not text or not text.strip():
        return []
    
    # Séparation par double saut de ligne ou retour à la ligne HTML
    raw_paragraphs = re.split(r'\n\s*\n|<br\s*/?>|<p[^>]*>', text.strip(), flags=re.IGNORECASE)
    
    paragraphs = []
    for para in raw_paragraphs:
        # Nettoyage HTML basique
        clean_para = clean_html_basic(para)
        clean_para = re.sub(r'\s+', ' ', clean_para.strip())
        
        # Filtrage par longueur
        if min_length <= len(clean_para) <= max_length:
            paragraphs.append(clean_para)
        elif len(clean_para) > max_length:
            # Diviser les paragraphes trop longs
            chunks = split_long_paragraph(clean_para, max_length)
            paragraphs.extend(chunks)
    
    return paragraphs

def split_long_paragraph(text: str, max_length: int) -> List[str]:
    """Divise un paragraphe trop long en chunks plus petits."""
    
    if len(text) <= max_length:
        return [text]
    
    # Essayer de diviser par phrases
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # Si ajouter cette phrase dépasse la limite
        if len(current_chunk + " " + sentence) > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                # Phrase trop longue, la couper arbitrairement
                while len(sentence) > max_length:
                    chunks.append(sentence[:max_length].strip())
                    sentence = sentence[max_length:].strip()
                current_chunk = sentence
        else:
            current_chunk = (current_chunk + " " + sentence).strip()
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return [chunk for chunk in chunks if len(chunk) >= 20]  # Éliminer les chunks trop courts

def clean_html_basic(text: str) -> str:
    """Nettoyage HTML basique."""
    if not text:
        return ""
    
    # Supprimer les balises HTML
    text = re.sub(r'<[^>]+>', '', text)
    
    # Décoder les entités HTML courantes
    html_entities = {
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&nbsp;': ' ',
        '&hellip;': '...',
        '&mdash;': '—',
        '&ndash;': '–'
    }
    
    for entity, replacement in html_entities.items():
        text = text.replace(entity, replacement)
    
    return text

def clean_text_for_embedding(text: str) -> str:
    """Nettoie le texte pour optimiser les embeddings."""
    
    if not text:
        return ""
    
    # Supprimer les caractères de contrôle
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Normaliser les espaces
    text = re.sub(r'\s+', ' ', text)
    
    # Supprimer les URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Supprimer les emails
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    
    # Supprimer les numéros de téléphone français
    text = re.sub(r'\b(?:0[1-9])(?:[-.\s]?\d{2}){4}\b', '', text)
    
    # Nettoyer les caractères spéciaux répétitifs
    text = re.sub(r'[.,;:!?]{2,}', '.', text)
    text = re.sub(r'[-_]{3,}', '', text)
    
    return text.strip()

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extrait les mots-clés d'un texte (version simplifiée)."""
    
    if not text:
        return []
    
    # Mots vides français
    stop_words = {
        'le', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir', 'que', 'pour',
        'dans', 'ce', 'son', 'une', 'sur', 'avec', 'ne', 'se', 'pas', 'tout', 'plus',
        'par', 'grand', 'cela', 'les', 'du', 'des', 'la', 'te', 'vous', 'leur', 'où',
        'très', 'nous', 'quand', 'qui', 'comme', 'si', 'ces', 'cette', 'peut', 'faire',
        'après', 'sans', 'autres', 'mais', 'elle', 'est', 'sont', 'était', 'ont', 'été'
    }
    
    # Nettoyer et extraire les mots
    words = re.findall(r'\b[a-zA-ZàâäéèêëïîôùûüÿñçÀÂÄÉÈÊËÏÎÔÙÛÜŸÑÇ]{3,}\b', text.lower())
    
    # Filtrer les mots vides et compter les occurrences
    word_count = {}
    for word in words:
        if word not in stop_words and len(word) > 2:
            word_count[word] = word_count.get(word, 0) + 1
    
    # Trier par fréquence et prendre les plus fréquents
    keywords = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in keywords[:max_keywords]]

def get_text_summary_stats(text: str) -> Dict[str, Any]:
    """Retourne un résumé statistique complet du texte."""
    
    if not text:
        return {
            'char_count': 0,
            'word_count': 0,
            'sentence_count': 0,
            'paragraph_count': 0,
            'avg_word_length': 0,
            'language': None,
            'reading_level': None,
            'keywords': []
        }
    
    metrics = analyze_text_metrics(text)
    paragraphs = extract_paragraphs_from_text(text)
    keywords = extract_keywords(text)
    
    words = text.split()
    avg_word_length = sum(len(word.strip(string.punctuation)) for word in words) / len(words) if words else 0
    
    return {
        'char_count': metrics['char_count'],
        'word_count': metrics['word_count'],
        'sentence_count': metrics['sentence_count'],
        'paragraph_count': len(paragraphs),
        'avg_word_length': round(avg_word_length, 2),
        'language': metrics['language'],
        'reading_level': metrics['reading_level'],
        'keywords': keywords
    }

def normalize_text(text: str) -> str:
    """Normalise un texte pour la comparaison."""
    if not text:
        return ""
    
    # Conversion en minuscules
    text = text.lower()
    
    # Suppression des accents (version simplifiée)
    accent_map = {
        'àâäá': 'a', 'éèêë': 'e', 'íìîï': 'i', 'óòôö': 'o', 'úùûü': 'u',
        'ý': 'y', 'ñ': 'n', 'ç': 'c'
    }
    
    for accented, normal in accent_map.items():
        for char in accented:
            text = text.replace(char, normal)
    
    # Suppression de la ponctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Normalisation des espaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def prepare_text_for_sentiment(content: str, max_length: int = 2000) -> str:
    """
    Prepare text for sentiment analysis.

    - Strip HTML tags (if any remain)
    - Remove excessive whitespace
    - Truncate to max_length
    - Preserve sentence structure

    Args:
        content: Raw or readable content
        max_length: Maximum characters to keep

    Returns:
        Cleaned text ready for sentiment analysis
    """
    from bs4 import BeautifulSoup

    if not content:
        return ""

    # Remove HTML tags if present
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Truncate intelligently (try to break at sentence)
    if len(text) > max_length:
        text = text[:max_length]
        last_period = text.rfind('.')
        if last_period > max_length * 0.8:  # If period found in last 20%
            text = text[:last_period + 1]

    return text
