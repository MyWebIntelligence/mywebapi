"""
Provider OpenAI pour embeddings
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
import logging
import aiohttp
import json

from .base_provider import (
    BaseEmbeddingProvider, 
    EmbeddingResult, 
    ProviderConfig,
    ProviderStatus,
    ProviderError,
    RateLimitError,
    ConfigurationError
)

logger = logging.getLogger(__name__)

class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """Provider pour les embeddings OpenAI"""
    
    BASE_URL = "https://api.openai.com/v1"
    SUPPORTED_MODELS = {
        "text-embedding-3-small": {
            "dimensions": 1536,
            "max_tokens": 8191,
            "cost_per_1k": 0.00002
        },
        "text-embedding-3-large": {
            "dimensions": 3072,
            "max_tokens": 8191,
            "cost_per_1k": 0.00013
        },
        "text-embedding-ada-002": {
            "dimensions": 1536,
            "max_tokens": 8191,
            "cost_per_1k": 0.0001
        }
    }
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        
        if not config.api_key:
            raise ConfigurationError("OpenAI API key is required", self.name)
        
        if config.model not in self.SUPPORTED_MODELS:
            raise ConfigurationError(f"Model {config.model} not supported", self.name)
        
        self.api_key = config.api_key
        self.base_url = config.base_url or self.BASE_URL
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtient une session HTTP réutilisable"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def _make_request(self, texts: List[str]) -> Dict[str, Any]:
        """Fait une requête à l'API OpenAI"""
        session = await self._get_session()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": texts,
            "model": self.model,
            "encoding_format": "float"
        }
        
        url = f"{self.base_url}/embeddings"
        
        start_time = time.time()
        
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                response_time = time.time() - start_time
                
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise RateLimitError(
                        "Rate limit exceeded", 
                        self.name, 
                        retry_after
                    )
                
                if response.status == 401:
                    raise ConfigurationError("Invalid API key", self.name)
                
                if response.status != 200:
                    error_text = await response.text()
                    raise ProviderError(
                        f"API request failed: {response.status} - {error_text}",
                        self.name
                    )
                
                result = await response.json()
                self.update_status(True, response_time=response_time)
                return result
                
        except aiohttp.ClientError as e:
            self.update_status(False, str(e))
            raise ProviderError(f"Network error: {str(e)}", self.name)
    
    async def generate_embedding(self, text: str) -> EmbeddingResult:
        """Génère un embedding pour un texte unique"""
        if not self.validate_text(text):
            raise ProviderError("Invalid text", self.name)
        
        cleaned_text = self.clean_text(text)
        
        start_time = time.time()
        result = await self._make_request([cleaned_text])
        processing_time = time.time() - start_time
        
        if not result.get("data") or len(result["data"]) == 0:
            raise ProviderError("No embedding returned", self.name)
        
        embedding_data = result["data"][0]
        usage = result.get("usage", {})
        
        return EmbeddingResult(
            text=text,
            embedding=embedding_data["embedding"],
            model=self.model,
            provider=self.name,
            tokens_used=usage.get("total_tokens"),
            processing_time=processing_time,
            metadata={
                "openai_usage": usage,
                "request_id": result.get("id")
            }
        )
    
    async def generate_embeddings_batch(
        self, 
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[EmbeddingResult]:
        """Génère des embeddings pour une liste de textes"""
        if not texts:
            return []
        
        batch_size = batch_size or self.config.batch_size
        results = []
        
        # Valider et nettoyer les textes
        cleaned_texts = []
        valid_indices = []
        
        for i, text in enumerate(texts):
            if self.validate_text(text):
                cleaned_texts.append(self.clean_text(text))
                valid_indices.append(i)
            else:
                logger.warning(f"Skipping invalid text at index {i}")
        
        if not cleaned_texts:
            return []
        
        # Traiter par batches
        for i in range(0, len(cleaned_texts), batch_size):
            batch_texts = cleaned_texts[i:i + batch_size]
            batch_indices = valid_indices[i:i + batch_size]
            
            start_time = time.time()
            result = await self._make_request(batch_texts)
            processing_time = time.time() - start_time
            
            if not result.get("data"):
                logger.error(f"No data in batch response for batch {i//batch_size + 1}")
                continue
            
            usage = result.get("usage", {})
            tokens_per_text = usage.get("total_tokens", 0) // len(batch_texts) if batch_texts else 0
            
            for j, embedding_data in enumerate(result["data"]):
                original_index = batch_indices[j]
                original_text = texts[original_index]
                
                embedding_result = EmbeddingResult(
                    text=original_text,
                    embedding=embedding_data["embedding"],
                    model=self.model,
                    provider=self.name,
                    tokens_used=tokens_per_text,
                    processing_time=processing_time / len(batch_texts),
                    metadata={
                        "openai_usage": usage,
                        "batch_index": i // batch_size,
                        "request_id": result.get("id")
                    }
                )
                results.append(embedding_result)
            
            # Rate limiting respectueux
            if i + batch_size < len(cleaned_texts):
                await asyncio.sleep(1.0)  # Pause entre les batches
        
        return results
    
    async def check_health(self) -> ProviderStatus:
        """Vérifie la santé du provider"""
        try:
            # Test avec un texte simple
            test_text = "Test de santé du provider OpenAI"
            await self.generate_embedding(test_text)
            
            self.update_status(True)
            return self._status
            
        except Exception as e:
            error_msg = str(e)
            self.update_status(False, error_msg)
            return self._status
    
    def get_model_info(self) -> Dict[str, Any]:
        """Retourne les informations sur le modèle"""
        model_info = self.SUPPORTED_MODELS.get(self.model, {})
        
        return {
            "name": self.model,
            "provider": self.name,
            "dimensions": model_info.get("dimensions"),
            "max_tokens": model_info.get("max_tokens"),
            "cost_per_1k_tokens": model_info.get("cost_per_1k"),
            "batch_size": self.config.batch_size,
            "rate_limit": self.config.rate_limit,
            "base_url": self.base_url
        }
    
    async def close(self):
        """Ferme la session HTTP"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def __del__(self):
        """Nettoyage automatique"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            # Note: En Python, il vaut mieux fermer explicitement avec close()
            logger.warning("OpenAI provider session not properly closed")