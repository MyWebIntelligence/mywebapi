"""
Service pour le traitement et l'extraction de texte
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_paragraph import paragraph as paragraph_crud
from app.crud.crud_expression import expression as expression_crud
from app.db.models import Expression, Paragraph
from app.schemas.paragraph import ParagraphCreate
from app.utils.text_utils import (
    extract_paragraphs_from_text,
    analyze_text_metrics,
    get_text_summary_stats
)
from app.core.text_processing import expression_relevance, get_land_dictionary

logger = logging.getLogger(__name__)

class TextProcessorService:
    """Service pour le traitement et l'analyse de texte"""
    
    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
    
    async def extract_paragraphs_for_land(
        self, 
        db: AsyncSession, 
        land_id: int,
        force_reextract: bool = False,
        min_paragraph_length: int = 50,
        max_paragraph_length: int = 5000
    ) -> Dict[str, Any]:
        """
        Extrait les paragraphes de toutes les expressions d'un land
        
        Args:
            db: Session de base de données
            land_id: ID du land à traiter
            force_reextract: Force la réextraction même si des paragraphes existent
            min_paragraph_length: Longueur minimale d'un paragraphe
            max_paragraph_length: Longueur maximale d'un paragraphe
            
        Returns:
            Statistiques de l'extraction
        """
        logger.info(f"Starting paragraph extraction for land {land_id}")
        
        stats = {
            'land_id': land_id,
            'total_expressions': 0,
            'processed_expressions': 0,
            'created_paragraphs': 0,
            'skipped_expressions': 0,
            'errors': []
        }
        
        try:
            # Récupérer toutes les expressions du land
            expressions = expression_crud.get_by_land(db, land_id, limit=10000)
            stats['total_expressions'] = len(expressions)
            
            if not expressions:
                logger.info(f"No expressions found for land {land_id}")
                return stats
            
            for expression in expressions:
                try:
                    extraction_result = await self.extract_paragraphs_for_expression(
                        db, 
                        expression,
                        force_reextract=force_reextract,
                        min_length=min_paragraph_length,
                        max_length=max_paragraph_length
                    )
                    
                    stats['created_paragraphs'] += extraction_result['created_paragraphs']
                    if extraction_result['created_paragraphs'] == 0:
                        stats['skipped_expressions'] += 1
                    
                    stats['processed_expressions'] += 1
                    
                except Exception as e:
                    error_msg = f"Error processing expression {expression.id}: {str(e)}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)
            
            logger.info(f"Paragraph extraction completed for land {land_id}: "
                       f"{stats['created_paragraphs']} paragraphs created from "
                       f"{stats['processed_expressions']} expressions")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error extracting paragraphs for land {land_id}: {e}")
            stats['error'] = str(e)
            raise
    
    async def extract_paragraphs_for_expression(
        self,
        db: AsyncSession,
        expression: Expression,
        force_reextract: bool = False,
        min_length: int = 50,
        max_length: int = 5000
    ) -> Dict[str, Any]:
        """
        Extrait les paragraphes d'une expression
        
        Args:
            db: Session de base de données
            expression: Expression à traiter
            force_reextract: Force la réextraction
            min_length: Longueur minimale d'un paragraphe
            max_length: Longueur maximale d'un paragraphe
            
        Returns:
            Statistiques de l'extraction
        """
        
        result = {
            'expression_id': expression.id,
            'created_paragraphs': 0,
            'skipped': False,
            'error': None
        }
        
        try:
            # Vérifier si des paragraphes existent déjà
            if not force_reextract:
                existing_paragraphs = paragraph_crud.get_by_expression(db, expression.id, limit=1)
                if existing_paragraphs:
                    logger.debug(f"Paragraphs already exist for expression {expression.id}, skipping")
                    result['skipped'] = True
                    return result
            
            source_text = self._get_expression_text(expression)
            
            # Analyser le texte pour voir s'il vaut la peine d'être traité
            if not source_text or len(source_text.strip()) < min_length:
                logger.debug(f"Expression {expression.id} text too short, skipping")
                result['skipped'] = True
                return result
            
            # Extraire les paragraphes
            paragraphs = extract_paragraphs_from_text(
                source_text,
                min_length=min_length,
                max_length=max_length
            )
            
            if not paragraphs:
                logger.debug(f"No valid paragraphs extracted from expression {expression.id}")
                result['skipped'] = True
                return result
            
            # Détecter la langue principale du texte
            text_stats = get_text_summary_stats(source_text)
            detected_language = text_stats.get('language')
            
            # Créer les objets paragraphe
            paragraph_objects = []
            for i, paragraph_text in enumerate(paragraphs):
                paragraph_create = ParagraphCreate(
                    expression_id=expression.id,
                    text=paragraph_text,
                    position=i,
                    language=detected_language
                )
                paragraph_objects.append(paragraph_create)
            
            # Supprimer les anciens paragraphes si force_reextract
            if force_reextract:
                deleted_count = paragraph_crud.delete_by_expression(db, expression.id)
                logger.debug(f"Deleted {deleted_count} existing paragraphs for expression {expression.id}")
            
            # Créer en lot
            created_paragraphs = paragraph_crud.bulk_create(
                db, 
                paragraph_objects, 
                analyze_text=True
            )
            
            result['created_paragraphs'] = len(created_paragraphs)
            
            logger.debug(f"Created {len(created_paragraphs)} paragraphs for expression {expression.id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting paragraphs for expression {expression.id}: {e}")
            result['error'] = str(e)
            return result
    
    def _get_expression_text(self, expression: Expression) -> str:
        """Combine les champs texte disponibles pour une expression."""
        candidates = [
            getattr(expression, "readable", None),
            getattr(expression, "content", None),
            getattr(expression, "description", None),
            getattr(expression, "summary", None),
            getattr(expression, "title", None),
        ]
        filtered = [text.strip() for text in candidates if isinstance(text, str) and text.strip()]
        return "\n\n".join(filtered)
    
    @staticmethod
    def analyze_text_content(text: str) -> Dict[str, Any]:
        """
        Analyse complète d'un contenu textuel
        
        Args:
            text: Texte à analyser
            
        Returns:
            Analyse complète du texte
        """
        try:
            # Statistiques générales
            summary_stats = get_text_summary_stats(text)
            
            # Métriques détaillées
            detailed_metrics = analyze_text_metrics(text)
            
            # Extraction de paragraphes pour évaluation
            sample_paragraphs = extract_paragraphs_from_text(text, min_length=20, max_length=1000)
            
            analysis = {
                'content_stats': summary_stats,
                'detailed_metrics': detailed_metrics,
                'paragraph_analysis': {
                    'extractable_paragraphs': len(sample_paragraphs),
                    'avg_paragraph_length': sum(len(p) for p in sample_paragraphs) / len(sample_paragraphs) if sample_paragraphs else 0,
                    'sample_paragraphs': sample_paragraphs[:3] if sample_paragraphs else []
                },
                'quality_score': TextProcessorService._calculate_text_quality_score(summary_stats, detailed_metrics),
                'recommendations': TextProcessorService._generate_text_recommendations(summary_stats, detailed_metrics)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing text content: {e}")
            return {
                'error': str(e),
                'content_stats': {},
                'quality_score': 0
            }
    
    @staticmethod
    def _calculate_text_quality_score(
        summary_stats: Dict[str, Any], 
        detailed_metrics: Dict[str, Any]
    ) -> float:
        """Calcule un score de qualité du texte (0-100)"""
        
        score = 0.0
        
        # Longueur appropriée (20% du score)
        word_count = summary_stats.get('word_count', 0)
        if 50 <= word_count <= 2000:
            score += 20
        elif 20 <= word_count < 50 or 2000 < word_count <= 5000:
            score += 15
        elif word_count > 10:
            score += 10
        
        # Lisibilité (25% du score)
        reading_level = detailed_metrics.get('reading_level')
        if reading_level:
            if 40 <= reading_level <= 80:  # Lisibilité optimale
                score += 25
            elif 20 <= reading_level < 40 or 80 < reading_level <= 90:
                score += 20
            elif reading_level > 10:
                score += 15
        
        # Structure (20% du score)
        paragraph_count = summary_stats.get('paragraph_count', 0)
        sentence_count = detailed_metrics.get('sentence_count', 0)
        
        if paragraph_count > 1 and sentence_count > 3:
            score += 20
        elif paragraph_count >= 1 and sentence_count > 1:
            score += 15
        elif sentence_count > 0:
            score += 10
        
        # Diversité lexicale (15% du score)
        keywords = summary_stats.get('keywords', [])
        avg_word_length = summary_stats.get('avg_word_length', 0)
        
        if len(keywords) >= 5 and 4 <= avg_word_length <= 7:
            score += 15
        elif len(keywords) >= 3:
            score += 10
        elif len(keywords) >= 1:
            score += 5
        
        # Langue détectée (10% du score)
        language = detailed_metrics.get('language')
        if language in ['fr', 'en']:
            score += 10
        elif language:
            score += 5
        
        # Cohérence (10% du score)
        char_count = detailed_metrics.get('char_count', 0)
        if word_count > 0 and char_count > 0:
            avg_chars_per_word = char_count / word_count
            if 4 <= avg_chars_per_word <= 8:  # Longueur de mot normale
                score += 10
            elif 2 <= avg_chars_per_word <= 12:
                score += 5
        
        return min(100.0, max(0.0, score))
    
    @staticmethod
    def _generate_text_recommendations(
        summary_stats: Dict[str, Any],
        detailed_metrics: Dict[str, Any]
    ) -> List[str]:
        """Génère des recommandations pour améliorer le texte"""
        
        recommendations = []
        
        word_count = summary_stats.get('word_count', 0)
        reading_level = detailed_metrics.get('reading_level')
        paragraph_count = summary_stats.get('paragraph_count', 0)
        
        # Recommandations de longueur
        if word_count < 20:
            recommendations.append("Le texte est très court. Considérez l'enrichir pour un meilleur contexte.")
        elif word_count > 5000:
            recommendations.append("Le texte est très long. Une division en sections pourrait améliorer la lisibilité.")
        
        # Recommandations de lisibilité
        if reading_level and reading_level < 20:
            recommendations.append("Le texte semble difficile à lire. Simplifiez les phrases et le vocabulaire.")
        elif reading_level and reading_level > 90:
            recommendations.append("Le texte pourrait être plus riche. Variez le vocabulaire et la structure.")
        
        # Recommandations de structure
        if paragraph_count == 0:
            recommendations.append("Structurez le texte en paragraphes pour une meilleure organisation.")
        elif paragraph_count == 1 and word_count > 200:
            recommendations.append("Divisez le contenu en plusieurs paragraphes pour améliorer la lisibilité.")
        
        # Recommandations de langue
        language = detailed_metrics.get('language')
        if not language:
            recommendations.append("La langue du texte n'a pas pu être détectée. Vérifiez le contenu.")
        
        if not recommendations:
            recommendations.append("Le texte est de bonne qualité pour l'analyse et l'extraction d'embeddings.")
        
        return recommendations
    
    def get_processing_stats(self, db: AsyncSession, land_id: int) -> Dict[str, Any]:
        """Récupère les statistiques de traitement pour un land"""
        
        # Statistiques des paragraphes
        paragraph_stats = paragraph_crud.get_stats_by_land(db, land_id)
        
        # Statistiques des expressions
        expressions = expression_crud.get_by_land(db, land_id, limit=10000)
        
        expressions_with_paragraphs = 0
        total_expression_length = 0
        
        for expression in expressions:
            if expression.text:
                total_expression_length += len(expression.text)
            
            # Vérifier si l'expression a des paragraphes
            paragraphs = paragraph_crud.get_by_expression(db, expression.id, limit=1)
            if paragraphs:
                expressions_with_paragraphs += 1
        
        return {
            'land_id': land_id,
            'total_expressions': len(expressions),
            'expressions_with_paragraphs': expressions_with_paragraphs,
            'expression_processing_coverage': (expressions_with_paragraphs / len(expressions) * 100) if expressions else 0,
            'total_paragraphs': paragraph_stats.get('total_paragraphs', 0),
            'avg_paragraphs_per_expression': paragraph_stats.get('avg_paragraphs_per_expression', 0),
            'total_words': paragraph_stats.get('total_words', 0),
            'avg_word_count': paragraph_stats.get('avg_word_count', 0),
            'avg_reading_level': paragraph_stats.get('avg_reading_level', 0),
            'language_distribution': paragraph_stats.get('languages', {}),
            'total_expression_chars': total_expression_length,
            'avg_expression_length': total_expression_length / len(expressions) if expressions else 0
        }
    
    async def calculate_relevance(
        self,
        text: str,
        title: str = None,
        land_id: int = None,
        language: str = "fr"
    ) -> float:
        """
        Calcule le score de pertinence d'un texte par rapport au dictionnaire d'un land.
        
        Args:
            text: Contenu textuel à analyser
            title: Titre optionnel (pondéré plus fortement)
            land_id: ID du land pour récupérer le dictionnaire
            language: Langue du texte (défaut: français)
            
        Returns:
            Score de pertinence (0.0 = non pertinent, >15 = très pertinent)
        """
        try:
            if not land_id:
                logger.warning("No land_id provided for relevance calculation")
                return 0.0
            
            # Récupérer le dictionnaire du land
            dictionary = await get_land_dictionary(self.db, land_id)
            
            if not dictionary:
                logger.warning(f"No dictionary found for land {land_id}")
                return 0.0
            
            # Créer un objet mock avec les propriétés attendues par expression_relevance
            class MockExpression:
                def __init__(self, title, readable):
                    self.title = title
                    self.readable = readable
            
            mock_expr = MockExpression(title, text)
            
            # Calculer la pertinence
            relevance_score = await expression_relevance(dictionary, mock_expr, language)
            
            logger.debug(
                f"Relevance calculated: {relevance_score} "
                f"(dictionary size: {len(dictionary)}, text length: {len(text) if text else 0})"
            )
            
            return float(relevance_score)
            
        except Exception as e:
            logger.error(f"Error calculating relevance: {e}")
            return 0.0
    
    async def update_expression_relevance(
        self,
        expression_id: int,
        force_recalculate: bool = False
    ) -> Dict[str, Any]:
        """
        Met à jour le score de pertinence d'une expression.
        
        Args:
            expression_id: ID de l'expression
            force_recalculate: Force le recalcul même si un score existe
            
        Returns:
            Résultats de la mise à jour
        """
        try:
            from sqlalchemy import select, update
            from app.db.models import Expression
            
            # Récupérer l'expression
            result = await self.db.execute(
                select(Expression).where(Expression.id == expression_id)
            )
            expression = result.scalar_one_or_none()
            
            if not expression:
                return {
                    'success': False,
                    'error': f'Expression {expression_id} not found'
                }
            
            # Vérifier si le recalcul est nécessaire
            if not force_recalculate and expression.relevance is not None:
                return {
                    'success': True,
                    'expression_id': expression_id,
                    'relevance': expression.relevance,
                    'action': 'skipped',
                    'message': 'Relevance already calculated'
                }
            
            # Calculer la nouvelle pertinence
            new_relevance = await self.calculate_relevance(
                text=expression.readable or '',
                title=expression.title,
                land_id=expression.land_id,
                language=expression.lang or 'fr'
            )
            
            # Mettre à jour en base
            await self.db.execute(
                update(Expression)
                .where(Expression.id == expression_id)
                .values(relevance=new_relevance)
            )
            
            await self.db.commit()
            
            return {
                'success': True,
                'expression_id': expression_id,
                'old_relevance': expression.relevance,
                'new_relevance': new_relevance,
                'action': 'updated',
                'message': f'Relevance updated from {expression.relevance} to {new_relevance}'
            }
            
        except Exception as e:
            logger.error(f"Error updating expression relevance {expression_id}: {e}")
            await self.db.rollback()
            return {
                'success': False,
                'error': str(e)
            }
