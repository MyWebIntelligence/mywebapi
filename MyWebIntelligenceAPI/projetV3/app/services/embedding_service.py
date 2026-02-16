"""
Service pour la gestion des embeddings
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.embedding_providers import get_provider_registry, BaseEmbeddingProvider
from app.core.settings import embeddings_settings
from app.crud.crud_paragraph import paragraph as paragraph_crud
from app.db.models import Paragraph, Expression
from app.schemas.embedding import (
    EmbeddingGenerateRequest,
    EmbeddingGenerateResponse,
    EmbeddingProgress,
    EmbeddingStats
)

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service principal pour la gestion des embeddings"""
    
    def __init__(self):
        self.provider_registry = get_provider_registry()
        self.embeddings_settings = embeddings_settings
        self.default_provider = embeddings_settings.default_provider
    
    async def _ensure_registry_initialized(self) -> None:
        """S'assure que le registre des providers est prêt."""
        if getattr(self.provider_registry, "_initialized", False):
            return
        await self.provider_registry.initialize(auto_configure=True)
    
    async def generate_embeddings_for_land(
        self,
        db: Session,
        land_id: int,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        force_regenerate: bool = False,
        batch_size: int = 100,
        extract_paragraphs: bool = True
    ) -> Dict[str, Any]:
        """
        Génère les embeddings pour tous les paragraphes d'un land
        
        Args:
            db: Session de base de données
            land_id: ID du land à traiter
            provider_name: Nom du provider à utiliser
            model: Modèle spécifique (optionnel)
            force_regenerate: Force la régénération des embeddings existants
            batch_size: Taille des batches pour le traitement
            extract_paragraphs: Extrait les paragraphes avant génération
            
        Returns:
            Statistiques du traitement
        """
        provider_name = provider_name or self.default_provider
        logger.info(f"Starting embedding generation for land {land_id} with provider {provider_name}")
        
        await self._ensure_registry_initialized()
        
        # Récupérer le provider
        provider = self.provider_registry.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not available")
        
        if not provider.status.is_available:
            raise ValueError(f"Provider {provider_name} is not healthy: {provider.status.error_message}")
        
        stats = {
            'land_id': land_id,
            'provider': provider_name,
            'model': provider.model,
            'started_at': datetime.now(),
            'total_expressions': 0,
            'total_paragraphs': 0,
            'new_paragraphs': 0,
            'updated_paragraphs': 0,
            'failed_paragraphs': 0,
            'total_tokens': 0,
            'processing_time': 0.0,
            'errors': []
        }
        
        try:
            # Étape 1: Extraire les paragraphes si nécessaire
            if extract_paragraphs:
                extraction_stats = await self._extract_paragraphs_for_land(db, land_id)
                stats['new_paragraphs'] = extraction_stats.get('created_paragraphs', 0)
                logger.info(f"Extracted {stats['new_paragraphs']} new paragraphs")
            
            # Étape 2: Récupérer les paragraphes à traiter
            paragraphs = self._get_paragraphs_for_embedding(
                db, land_id, provider_name, force_regenerate
            )
            
            stats['total_paragraphs'] = len(paragraphs)
            if not paragraphs:
                logger.info(f"No paragraphs to process for land {land_id}")
                return stats
            
            # Étape 3: Générer les embeddings par batches
            start_time = datetime.now()
            
            for i in range(0, len(paragraphs), batch_size):
                batch = paragraphs[i:i + batch_size]
                batch_stats = await self._process_paragraph_batch(
                    db, batch, provider, force_regenerate
                )
                
                stats['updated_paragraphs'] += batch_stats['successful']
                stats['failed_paragraphs'] += batch_stats['failed']
                stats['total_tokens'] += batch_stats['tokens_used']
                stats['errors'].extend(batch_stats['errors'])
                
                logger.info(f"Processed batch {i//batch_size + 1}/{(len(paragraphs) + batch_size - 1)//batch_size}")
                
                # Pause entre les batches pour respecter le rate limiting
                if i + batch_size < len(paragraphs):
                    await asyncio.sleep(1.0)
            
            stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            stats['completed_at'] = datetime.now()
            
            logger.info(f"Embedding generation completed for land {land_id}: "
                       f"{stats['updated_paragraphs']} updated, {stats['failed_paragraphs']} failed")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error generating embeddings for land {land_id}: {e}")
            stats['error'] = str(e)
            stats['completed_at'] = datetime.now()
            raise
    
    async def _extract_paragraphs_for_land(self, db: Session, land_id: int) -> Dict[str, Any]:
        """Extrait les paragraphes des expressions d'un land"""
        from .text_processor_service import TextProcessorService
        
        text_processor = TextProcessorService()
        return await text_processor.extract_paragraphs_for_land(db, land_id)
    
    def _get_paragraphs_for_embedding(
        self, 
        db: Session, 
        land_id: int, 
        provider_name: str,
        force_regenerate: bool
    ) -> List[Paragraph]:
        """Récupère les paragraphes qui ont besoin d'embeddings"""
        
        if force_regenerate:
            # Tous les paragraphes du land
            return paragraph_crud.get_by_land(db, land_id, limit=10000)
        else:
            # Seulement ceux sans embeddings ou avec un provider différent
            paragraphs_without = paragraph_crud.get_without_embeddings(db, land_id=land_id, limit=10000)
            
            # Ceux avec un provider différent
            all_paragraphs = paragraph_crud.get_by_land(db, land_id, limit=10000)
            different_provider = [
                p for p in all_paragraphs 
                if p.embedding_provider and p.embedding_provider != provider_name
            ]
            
            # Combiner et dédupliquer
            all_to_process = list({p.id: p for p in paragraphs_without + different_provider}.values())
            return all_to_process
    
    async def _process_paragraph_batch(
        self,
        db: Session,
        paragraphs: List[Paragraph],
        provider: BaseEmbeddingProvider,
        force_regenerate: bool
    ) -> Dict[str, Any]:
        """Traite un batch de paragraphes pour générer leurs embeddings"""
        
        batch_stats = {
            'successful': 0,
            'failed': 0,
            'tokens_used': 0,
            'errors': []
        }
        
        try:
            # Préparer les textes
            texts = [p.text for p in paragraphs]
            
            # Générer les embeddings
            results = await provider.generate_embeddings_batch(texts)
            
            # Mettre à jour en base
            updates = []
            for i, result in enumerate(results):
                if i < len(paragraphs):
                    paragraph = paragraphs[i]
                    updates.append({
                        'paragraph_id': paragraph.id,
                        'embedding': result.embedding,
                        'provider': result.provider,
                        'model': result.model
                    })
                    
                    if result.tokens_used:
                        batch_stats['tokens_used'] += result.tokens_used
            
            # Mise à jour en lot
            updated_count = paragraph_crud.bulk_update_embeddings(db, updates)
            batch_stats['successful'] = updated_count
            
        except Exception as e:
            error_msg = f"Batch processing error: {str(e)}"
            logger.error(error_msg)
            batch_stats['errors'].append(error_msg)
            batch_stats['failed'] = len(paragraphs)
        
        return batch_stats
    
    async def generate_embeddings_for_expressions(
        self,
        db: Session,
        expression_ids: List[int],
        provider_name: Optional[str] = None,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """Génère les embeddings pour des expressions spécifiques"""
        
        provider_name = provider_name or self.default_provider
        logger.info(f"Generating embeddings for {len(expression_ids)} expressions")
        
        await self._ensure_registry_initialized()
        
        provider = self.provider_registry.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not available")
        
        stats = {
            'expression_ids': expression_ids,
            'provider': provider_name,
            'processed_expressions': 0,
            'total_paragraphs': 0,
            'successful_paragraphs': 0,
            'failed_paragraphs': 0,
            'errors': []
        }
        
        for expr_id in expression_ids:
            try:
                # Récupérer les paragraphes de l'expression
                paragraphs = self._get_paragraphs_for_expression(
                    db, expr_id, provider_name, force_regenerate
                )
                
                if paragraphs:
                    batch_stats = await self._process_paragraph_batch(
                        db, paragraphs, provider, force_regenerate
                    )
                    
                    stats['total_paragraphs'] += len(paragraphs)
                    stats['successful_paragraphs'] += batch_stats['successful']
                    stats['failed_paragraphs'] += batch_stats['failed']
                    stats['errors'].extend(batch_stats['errors'])
                
                stats['processed_expressions'] += 1
                
            except Exception as e:
                error_msg = f"Error processing expression {expr_id}: {str(e)}"
                logger.error(error_msg)
                stats['errors'].append(error_msg)
        
        return stats
    
    def _get_paragraphs_for_expression(
        self,
        db: Session,
        expression_id: int,
        provider_name: str,
        force_regenerate: bool
    ) -> List[Paragraph]:
        """Récupère les paragraphes d'une expression qui ont besoin d'embeddings"""
        
        if force_regenerate:
            return paragraph_crud.get_by_expression(db, expression_id, limit=1000)
        else:
            all_paragraphs = paragraph_crud.get_by_expression(db, expression_id, limit=1000)
            return [
                p for p in all_paragraphs 
                if not p.embedding or p.embedding_provider != provider_name
            ]
    
    def get_embedding_stats(self, db: Session, land_id: int) -> EmbeddingStats:
        """Récupère les statistiques d'embeddings pour un land"""
        
        stats = paragraph_crud.get_stats_by_land(db, land_id)
        
        return EmbeddingStats(
            land_id=land_id,
            total_expressions=stats.get('total_expressions', 0),
            total_paragraphs=stats.get('total_paragraphs', 0),
            paragraphs_with_embeddings=stats.get('paragraphs_with_embeddings', 0),
            embedding_coverage=stats.get('embedding_coverage', 0.0),
            providers_used=stats.get('embedding_providers', {}),
            models_used={},  # TODO: Ajouter model tracking
            avg_embedding_dimensions=None,  # TODO: Calculer moyenne
            total_tokens_used=None,  # TODO: Ajouter token tracking
            last_updated=datetime.now()
        )
    
    async def health_check_providers(self) -> Dict[str, Any]:
        """Vérifie la santé de tous les providers"""
        
        await self._ensure_registry_initialized()
        return await self.provider_registry.health_check_all()
    
    async def get_available_providers(self) -> List[str]:
        """Retourne la liste des providers disponibles"""
        await self._ensure_registry_initialized()
        return self.provider_registry.list_available_providers()
    
    async def get_provider_info(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'un provider"""
        await self._ensure_registry_initialized()
        return self.provider_registry.get_provider_info(provider_name)
