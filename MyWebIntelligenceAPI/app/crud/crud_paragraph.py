"""
CRUD operations pour les paragraphes
"""

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, text
from app.crud.base import CRUDBase
from app.db.models import Paragraph, Expression
from app.schemas.paragraph import ParagraphCreate, ParagraphUpdate
import hashlib
import logging

logger = logging.getLogger(__name__)

class CRUDParagraph(CRUDBase[Paragraph, ParagraphCreate, ParagraphUpdate]):
    
    def get(self, db: Session, id: int) -> Optional[Paragraph]:
        """Récupère un paragraphe par son identifiant."""
        return db.query(Paragraph).filter(Paragraph.id == id).first()
    
    def remove(self, db: Session, id: int) -> Optional[Paragraph]:
        """Supprime un paragraphe par son identifiant."""
        obj = self.get(db, id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
    
    def update(
        self,
        db: Session,
        *,
        db_obj: Paragraph,
        obj_in: Union[ParagraphUpdate, Dict[str, Any]]
    ) -> Paragraph:
        """Met à jour un paragraphe existant."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    
    def create_with_analysis(
        self, 
        db: Session, 
        obj_in: ParagraphCreate, 
        analyze_text: bool = True
    ) -> Paragraph:
        """Crée un paragraphe avec analyse textuelle automatique."""
        from app.utils.text_utils import analyze_text_metrics
        
        # Calculer le hash du texte pour déduplication
        text_hash = hashlib.sha256(obj_in.text.encode('utf-8')).hexdigest()
        
        # Vérifier si le paragraphe existe déjà
        existing = db.query(Paragraph).filter(
            and_(
                Paragraph.expression_id == obj_in.expression_id,
                Paragraph.text_hash == text_hash
            )
        ).first()
        
        if existing:
            logger.info(f"Paragraph with hash {text_hash[:8]} already exists for expression {obj_in.expression_id}")
            return existing
        
        # Analyser le texte
        metrics = analyze_text_metrics(obj_in.text) if analyze_text else {}
        
        db_obj = Paragraph(
            expression_id=obj_in.expression_id,
            text=obj_in.text,
            text_hash=text_hash,
            position=obj_in.position,
            language=obj_in.language,
            word_count=metrics.get('word_count'),
            char_count=metrics.get('char_count'),
            sentence_count=metrics.get('sentence_count'),
            reading_level=metrics.get('reading_level')
        )
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        logger.info(f"Created paragraph {db_obj.id} for expression {obj_in.expression_id}")
        return db_obj
    
    def get_by_expression(
        self, 
        db: Session, 
        expression_id: int,
        skip: int = 0,
        limit: int = 100,
        include_embeddings: bool = False
    ) -> List[Paragraph]:
        """Récupère les paragraphes d'une expression."""
        query = db.query(Paragraph).filter(
            Paragraph.expression_id == expression_id
        )
        
        if include_embeddings:
            query = query.filter(Paragraph.embedding.isnot(None))
        
        return query.order_by(Paragraph.position).offset(skip).limit(limit).all()
    
    def get_by_expression_with_stats(
        self, 
        db: Session, 
        expression_id: int
    ) -> Dict[str, Any]:
        """Récupère les paragraphes avec statistiques."""
        paragraphs = self.get_by_expression(db, expression_id)
        stats = self.get_stats_by_expression(db, expression_id)
        
        return {
            'paragraphs': paragraphs,
            'stats': stats
        }
    
    def get_with_embeddings(
        self, 
        db: Session, 
        expression_id: Optional[int] = None,
        land_id: Optional[int] = None,
        provider: Optional[str] = None,
        limit: int = 1000
    ) -> List[Paragraph]:
        """Récupère les paragraphes avec embeddings."""
        query = db.query(Paragraph).filter(
            Paragraph.embedding.isnot(None),
            func.array_length(Paragraph.embedding, 1) > 0
        )
        
        if expression_id:
            query = query.filter(Paragraph.expression_id == expression_id)
        
        if land_id:
            query = query.join(Expression).filter(Expression.land_id == land_id)
        
        if provider:
            query = query.filter(Paragraph.embedding_provider == provider)
        
        return query.limit(limit).all()
    
    def get_without_embeddings(
        self, 
        db: Session, 
        expression_id: Optional[int] = None,
        land_id: Optional[int] = None,
        limit: int = 1000
    ) -> List[Paragraph]:
        """Récupère les paragraphes sans embeddings."""
        query = db.query(Paragraph).filter(
            or_(
                Paragraph.embedding.is_(None),
                func.array_length(Paragraph.embedding, 1) == 0
            )
        )
        
        if expression_id:
            query = query.filter(Paragraph.expression_id == expression_id)
        
        if land_id:
            query = query.join(Expression).filter(Expression.land_id == land_id)
        
        return query.limit(limit).all()
    
    def get_by_land(
        self, 
        db: Session, 
        land_id: int,
        skip: int = 0,
        limit: int = 1000,
        with_embeddings_only: bool = False
    ) -> List[Paragraph]:
        """Récupère tous les paragraphes d'un land."""
        query = db.query(Paragraph).join(Expression).filter(
            Expression.land_id == land_id
        )
        
        if with_embeddings_only:
            query = query.filter(
                Paragraph.embedding.isnot(None),
                func.array_length(Paragraph.embedding, 1) > 0
            )
        
        return query.order_by(
            Expression.id, 
            Paragraph.position
        ).offset(skip).limit(limit).all()
    
    def update_embedding(
        self,
        db: Session,
        paragraph_id: int,
        embedding: List[float],
        provider: str,
        model: str
    ) -> Optional[Paragraph]:
        """Met à jour l'embedding d'un paragraphe."""
        from datetime import datetime, timezone
        
        paragraph = db.query(Paragraph).filter(Paragraph.id == paragraph_id).first()
        if not paragraph:
            logger.warning(f"Paragraph {paragraph_id} not found for embedding update")
            return None
        
        paragraph.embedding = embedding
        paragraph.embedding_provider = provider
        paragraph.embedding_model = model
        paragraph.embedding_dimensions = len(embedding)
        paragraph.embedding_computed_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(paragraph)
        logger.info(f"Updated embedding for paragraph {paragraph_id} with {provider}")
        return paragraph
    
    def bulk_update_embeddings(
        self,
        db: Session,
        updates: List[Dict[str, Any]]
    ) -> int:
        """Met à jour les embeddings en lot."""
        from datetime import datetime, timezone
        
        updated_count = 0
        for update in updates:
            paragraph_id = update.get('paragraph_id')
            embedding = update.get('embedding')
            provider = update.get('provider')
            model = update.get('model')
            
            if not all([paragraph_id, embedding, provider, model]):
                logger.warning(f"Incomplete update data: {update}")
                continue
            
            result = db.query(Paragraph).filter(
                Paragraph.id == paragraph_id
            ).update({
                Paragraph.embedding: embedding,
                Paragraph.embedding_provider: provider,
                Paragraph.embedding_model: model,
                Paragraph.embedding_dimensions: len(embedding),
                Paragraph.embedding_computed_at: datetime.now(timezone.utc)
            }, synchronize_session=False)
            
            updated_count += result
        
        db.commit()
        logger.info(f"Bulk updated {updated_count} paragraph embeddings")
        return updated_count
    
    def get_stats_by_expression(
        self, 
        db: Session, 
        expression_id: int
    ) -> Dict[str, Any]:
        """Statistiques des paragraphes pour une expression."""
        # Stats de base
        total_query = db.query(func.count(Paragraph.id)).filter(
            Paragraph.expression_id == expression_id
        )
        
        with_embeddings_query = db.query(func.count(Paragraph.id)).filter(
            and_(
                Paragraph.expression_id == expression_id,
                Paragraph.embedding.isnot(None),
                func.array_length(Paragraph.embedding, 1) > 0
            )
        )
        
        # Stats textuelles
        text_stats = db.query(
            func.avg(Paragraph.word_count).label('avg_word_count'),
            func.avg(Paragraph.reading_level).label('avg_reading_level'),
            func.sum(Paragraph.word_count).label('total_words'),
            func.max(Paragraph.word_count).label('max_word_count'),
            func.min(Paragraph.word_count).label('min_word_count')
        ).filter(Paragraph.expression_id == expression_id).first()
        
        # Distribution des langues
        language_dist = db.query(
            Paragraph.language,
            func.count(Paragraph.id).label('count')
        ).filter(
            and_(
                Paragraph.expression_id == expression_id,
                Paragraph.language.isnot(None)
            )
        ).group_by(Paragraph.language).all()
        
        # Distribution des providers d'embeddings
        provider_dist = db.query(
            Paragraph.embedding_provider,
            func.count(Paragraph.id).label('count')
        ).filter(
            and_(
                Paragraph.expression_id == expression_id,
                Paragraph.embedding_provider.isnot(None)
            )
        ).group_by(Paragraph.embedding_provider).all()
        
        total = total_query.scalar() or 0
        with_embeddings = with_embeddings_query.scalar() or 0
        
        return {
            'expression_id': expression_id,
            'total_paragraphs': total,
            'paragraphs_with_embeddings': with_embeddings,
            'embedding_coverage': (with_embeddings / total * 100) if total > 0 else 0,
            'avg_word_count': float(text_stats.avg_word_count or 0),
            'avg_reading_level': float(text_stats.avg_reading_level or 0),
            'total_words': int(text_stats.total_words or 0),
            'max_word_count': int(text_stats.max_word_count or 0),
            'min_word_count': int(text_stats.min_word_count or 0),
            'languages': {lang: count for lang, count in language_dist},
            'embedding_providers': {provider: count for provider, count in provider_dist}
        }
    
    def get_stats_by_land(
        self, 
        db: Session, 
        land_id: int
    ) -> Dict[str, Any]:
        """Statistiques des paragraphes pour un land."""
        # Utiliser une requête directe pour les performances
        query = text("""
            SELECT 
                COUNT(*) as total_paragraphs,
                COUNT(CASE WHEN embedding IS NOT NULL AND array_length(embedding, 1) > 0 THEN 1 END) as paragraphs_with_embeddings,
                AVG(word_count) as avg_word_count,
                AVG(reading_level) as avg_reading_level,
                SUM(word_count) as total_words,
                COUNT(DISTINCT expression_id) as total_expressions
            FROM paragraphs p
            JOIN expressions e ON p.expression_id = e.id
            WHERE e.land_id = :land_id
        """)
        
        result = db.execute(query, {'land_id': land_id}).fetchone()
        
        if not result:
            return {
                'land_id': land_id,
                'total_paragraphs': 0,
                'paragraphs_with_embeddings': 0,
                'embedding_coverage': 0,
                'total_expressions': 0
            }
        
        total_paragraphs = result.total_paragraphs
        paragraphs_with_embeddings = result.paragraphs_with_embeddings
        
        # Distribution des langues
        language_query = text("""
            SELECT p.language, COUNT(*) as count
            FROM paragraphs p
            JOIN expressions e ON p.expression_id = e.id
            WHERE e.land_id = :land_id AND p.language IS NOT NULL
            GROUP BY p.language
        """)
        
        language_results = db.execute(language_query, {'land_id': land_id}).fetchall()
        
        # Distribution des providers
        provider_query = text("""
            SELECT p.embedding_provider, COUNT(*) as count
            FROM paragraphs p
            JOIN expressions e ON p.expression_id = e.id
            WHERE e.land_id = :land_id AND p.embedding_provider IS NOT NULL
            GROUP BY p.embedding_provider
        """)
        
        provider_results = db.execute(provider_query, {'land_id': land_id}).fetchall()
        
        return {
            'land_id': land_id,
            'total_paragraphs': total_paragraphs,
            'paragraphs_with_embeddings': paragraphs_with_embeddings,
            'embedding_coverage': (paragraphs_with_embeddings / total_paragraphs * 100) if total_paragraphs > 0 else 0,
            'total_expressions': result.total_expressions,
            'avg_word_count': float(result.avg_word_count or 0),
            'avg_reading_level': float(result.avg_reading_level or 0),
            'total_words': int(result.total_words or 0),
            'avg_paragraphs_per_expression': (total_paragraphs / result.total_expressions) if result.total_expressions > 0 else 0,
            'languages': {row.language: row.count for row in language_results},
            'embedding_providers': {row.embedding_provider: row.count for row in provider_results}
        }
    
    def bulk_create(
        self, 
        db: Session, 
        paragraphs: List[ParagraphCreate],
        analyze_text: bool = True
    ) -> List[Paragraph]:
        """Création en lot optimisée."""
        from app.utils.text_utils import analyze_text_metrics
        
        db_objects = []
        for para in paragraphs:
            text_hash = hashlib.sha256(para.text.encode('utf-8')).hexdigest()
            
            # Vérifier la déduplication
            existing = db.query(Paragraph).filter(
                and_(
                    Paragraph.expression_id == para.expression_id,
                    Paragraph.text_hash == text_hash
                )
            ).first()
            
            if existing:
                continue  # Skip les doublons
            
            metrics = analyze_text_metrics(para.text) if analyze_text else {}
            
            db_obj = Paragraph(
                expression_id=para.expression_id,
                text=para.text,
                text_hash=text_hash,
                position=para.position,
                language=para.language,
                **metrics
            )
            db_objects.append(db_obj)
        
        if db_objects:
            db.add_all(db_objects)
            db.commit()
            
            for obj in db_objects:
                db.refresh(obj)
        
        logger.info(f"Bulk created {len(db_objects)} paragraphs (skipped {len(paragraphs) - len(db_objects)} duplicates)")
        return db_objects
    
    def delete_by_expression(
        self,
        db: Session,
        expression_id: int
    ) -> int:
        """Supprime tous les paragraphes d'une expression."""
        count = db.query(Paragraph).filter(
            Paragraph.expression_id == expression_id
        ).delete(synchronize_session=False)
        
        db.commit()
        logger.info(f"Deleted {count} paragraphs for expression {expression_id}")
        return count
    
    def search_by_text(
        self,
        db: Session,
        search_text: str,
        land_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Paragraph]:
        """Recherche de paragraphes par contenu textuel."""
        query = db.query(Paragraph)
        
        if land_id:
            query = query.join(Expression).filter(Expression.land_id == land_id)
        
        # Recherche textuelle simple (peut être améliorée avec PostgreSQL FTS)
        query = query.filter(
            Paragraph.text.ilike(f'%{search_text}%')
        )
        
        return query.order_by(
            Paragraph.word_count.desc()
        ).limit(limit).all()

# Instance globale
paragraph = CRUDParagraph(Paragraph)
