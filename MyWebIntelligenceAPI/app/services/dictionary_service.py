"""
Service de gestion des dictionnaires de mots-clés pour les lands.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Land, Word, LandDictionary
from app.crud.crud_land import land as crud_land
from app.core.text_processing import normalize_text, get_lemma, extract_keywords

logger = logging.getLogger(__name__)

class DictionaryService:
    """Service pour gérer les dictionnaires de mots-clés des lands."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def populate_land_dictionary(
        self,
        land_id: int,
        force_refresh: bool = False,
        seed_terms: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Peuple automatiquement le dictionnaire d'un land à partir de ses mots-clés.
        
        Args:
            land_id: ID du land
            force_refresh: Si True, recrée le dictionnaire même s'il existe
            
        Returns:
            Dict avec les statistiques de création
        """
        # Récupérer le land
        land = await crud_land.get(self.db, id=land_id)
        if not land:
            raise ValueError(f"Land {land_id} not found")
        
        # Vérifier si le dictionnaire existe déjà
        existing_dict = await self._get_land_dictionary_count(land_id)
        if existing_dict > 0 and not force_refresh:
            logger.info(f"Dictionary already exists for land {land_id} ({existing_dict} entries)")
            return {
                "action": "skipped",
                "reason": "Dictionary already exists",
                "existing_entries": existing_dict
            }
        
        # Supprimer l'ancien dictionnaire si force_refresh
        if force_refresh and existing_dict > 0:
            await self._clear_land_dictionary(land_id)
            logger.info(f"Cleared existing dictionary for land {land_id}")
        
        created_words = 0
        created_entries = 0
        
        # Source des termes (seed explicite ou relation ORM existante)
        if seed_terms is not None:
            raw_terms = seed_terms
        else:
            raw_terms = [
                {"word": getattr(word_obj, "word", ""), "lemma": getattr(word_obj, "lemma", "")}
                for word_obj in getattr(land, "words", []) or []
            ]

        # Traiter les mots du land
        if raw_terms:
            for word_data in raw_terms:
                if isinstance(word_data, str):
                    word = word_data.strip().lower()
                    lemma = word
                elif isinstance(word_data, dict):
                    word = (word_data.get('word') or '').strip().lower()
                    lemma = (word_data.get('lemma') or word).strip().lower()
                else:
                    continue
                
                if not word:
                    continue
                
                # Créer ou récupérer le mot
                word_obj, is_new_word = await self._create_or_get_word(word, lemma, land.lang)
                if word_obj:
                    # Ajouter au dictionnaire du land
                    dict_entry = await self._add_to_land_dictionary(land_id, word_obj.id)
                    if dict_entry:
                        created_entries += 1
                        if is_new_word:
                            created_words += 1
        
        # Générer des variations automatiques pour enrichir le dictionnaire
        variations_created = await self._generate_word_variations(land_id, land.lang or ['fr'])
        
        result = {
            "action": "created",
            "land_id": land_id,
            "created_words": created_words,
            "created_entries": created_entries,
            "variations_created": variations_created,
            "total_entries": created_entries + variations_created
        }
        
        logger.info(f"Dictionary populated for land {land_id}: {result}")
        return result
    
    async def _get_land_dictionary_count(self, land_id: int) -> int:
        """Compte les entrées du dictionnaire d'un land."""
        result = await self.db.execute(
            select(LandDictionary).where(LandDictionary.land_id == land_id)
        )
        return len(result.fetchall())
    
    async def _clear_land_dictionary(self, land_id: int):
        """Supprime toutes les entrées du dictionnaire d'un land."""
        from sqlalchemy import delete
        await self.db.execute(
            delete(LandDictionary).where(LandDictionary.land_id == land_id)
        )
        await self.db.commit()
    
    async def _create_or_get_word(self, word: str, lemma: str, languages: List[str]) -> tuple[Optional[Word], bool]:
        """Crée ou récupère un mot dans la base avec processing amélioré.

        Returns:
            Tuple[Word | None, bool]: l'objet Word et un booléen indiquant s'il vient d'être créé.
        """
        # Normaliser les textes
        normalized_word = normalize_text(word)

        # Utiliser le processing amélioré pour le lemme
        primary_lang = languages[0] if languages else 'fr'
        processed_lemma = get_lemma(normalized_word, primary_lang) if not lemma else get_lemma(lemma, primary_lang)

        if not normalized_word or not processed_lemma:
            return None, False

        # FIRST: Check by exact word value (which has unique constraint)
        result = await self.db.execute(
            select(Word).where(
                Word.word == normalized_word,
                Word.language == primary_lang
            )
        )
        word_obj = result.scalar_one_or_none()

        if word_obj:
            # Word already exists with exact match
            logger.debug(f"Word '{normalized_word}' already exists (id={word_obj.id})")
            return word_obj, False

        # SECOND: Check by lemma (for similar words)
        result = await self.db.execute(
            select(Word).where(
                Word.lemma == processed_lemma,
                Word.language == primary_lang
            )
        )
        word_obj = result.scalar_one_or_none()

        if word_obj:
            # Found by lemma but different word value
            logger.debug(f"Word found by lemma '{processed_lemma}' (existing word='{word_obj.word}', id={word_obj.id})")
            return word_obj, False

        # Create new word - no try/except needed since we checked above
        word_obj = Word(
            word=normalized_word,
            lemma=processed_lemma,
            language=primary_lang,
            frequency=1.0  # Fréquence par défaut
        )
        self.db.add(word_obj)
        await self.db.flush()  # Pour obtenir l'ID
        logger.debug(f"Created new word: '{normalized_word}' -> lemma: '{processed_lemma}' ({primary_lang}, id={word_obj.id})")
        return word_obj, True
    
    async def _add_to_land_dictionary(self, land_id: int, word_id: int) -> Optional[LandDictionary]:
        """Ajoute un mot au dictionnaire d'un land."""
        # Vérifier si l'entrée existe déjà
        result = await self.db.execute(
            select(LandDictionary).where(
                LandDictionary.land_id == land_id,
                LandDictionary.word_id == word_id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            return existing
        
        # Créer une nouvelle entrée
        dict_entry = LandDictionary(
            land_id=land_id,
            word_id=word_id,
            weight=1.0  # Poids par défaut
        )
        self.db.add(dict_entry)
        await self.db.flush()
        
        return dict_entry
    
    async def _generate_word_variations(self, land_id: int, languages: List[str]) -> int:
        """Génère automatiquement des variations de mots pour enrichir le dictionnaire."""
        variations_created = 0
        
        # Récupérer les mots existants du dictionnaire
        result = await self.db.execute(
            select(Word, LandDictionary).join(
                LandDictionary, Word.id == LandDictionary.word_id
            ).where(LandDictionary.land_id == land_id)
        )
        
        existing_words = result.fetchall()
        
        for word_obj, dict_entry in existing_words:
            base_word = word_obj.word
            
            # Générer des variations (pluriels, conjugaisons, etc.)
            variations = self._get_word_variations(base_word, languages)
            
            for variation in variations:
                if variation != base_word:  # Éviter les doublons
                    var_word, is_new = await self._create_or_get_word(variation, word_obj.lemma, languages)
                    if var_word and var_word.id != word_obj.id:
                        var_dict_entry = await self._add_to_land_dictionary(land_id, var_word.id)
                        if var_dict_entry:
                            variations_created += 1
        
        if variations_created > 0:
            await self.db.commit()
        
        return variations_created
    
    def _get_word_variations(self, word: str, languages: List[str]) -> List[str]:
        """
        Génère des variations d'un mot selon la langue avec stemming amélioré.
        
        Utilise le processing linguistique avancé pour générer des variations plus précises.
        """
        variations = set([word])  # Inclure le mot original
        primary_lang = languages[0] if languages else 'fr'
        
        # Utiliser le stemming/lemmatisation pour trouver la racine
        base_stem = get_lemma(word, primary_lang)
        if base_stem and base_stem != word:
            variations.add(base_stem)
        
        if primary_lang == 'fr':
            # Variations françaises améliorées
            
            # Variations de genre et nombre
            if word.endswith('e'):
                variations.add(word[:-1])  # féminin -> masculin
            if not word.endswith('s'):
                variations.add(word + 's')  # singulier -> pluriel
            if word.endswith('es'):
                variations.add(word[:-2])  # féminin pluriel -> masculin singulier
                variations.add(word[:-1])  # féminin pluriel -> masculin pluriel
            
            # Variations verbales françaises
            if word.endswith('er'):
                root = word[:-2]
                variations.update([
                    root + 'e',      # je/il presente
                    root + 'es',     # tu présentes  
                    root + 'ent',    # ils présentent
                    root + 'ons',    # nous présentons
                    root + 'ez',     # vous présentez
                    root + 'é',      # participe passé
                    root + 'ant',    # participe présent
                ])
            
            # Variations substantifs/adjectifs
            if word.endswith('tion'):
                root = word[:-4]
                variations.update([
                    root + 'ter',    # action -> actionner (approx)
                    root + 'teur',   # action -> acteur
                    root + 'trice',  # action -> actrice
                ])
            
            # Variations adjectivales
            if word.endswith('eux'):
                variations.add(word[:-3] + 'euse')  # heureux -> heureuse
            elif word.endswith('if'):
                variations.add(word[:-2] + 'ive')  # actif -> active
        
        elif primary_lang == 'en':
            # Variations anglaises améliorées
            
            # Pluriels
            if not word.endswith('s'):
                variations.add(word + 's')
            if word.endswith('y') and len(word) > 2:
                variations.add(word[:-1] + 'ies')  # city -> cities
            
            # Formes verbales
            if word.endswith('e'):
                root = word[:-1]
                variations.update([
                    word + 'd',      # past tense
                    root + 'ing',    # present continuous
                ])
            else:
                variations.update([
                    word + 'ed',     # past tense
                    word + 'ing',    # present continuous
                ])
            
            # Comparatifs/superlatifs
            if len(word) <= 6:  # Mots courts
                variations.update([
                    word + 'er',     # comparative
                    word + 'est',    # superlative
                ])
        
        # Nettoyer et retourner les variations valides
        clean_variations = []
        for variation in variations:
            normalized = normalize_text(variation)
            if normalized and len(normalized) >= 2:
                clean_variations.append(normalized)
        
        return list(set(clean_variations))
    
    async def get_land_dictionary_stats(self, land_id: int) -> Dict[str, Any]:
        """Récupère les statistiques du dictionnaire d'un land."""
        # Compter les entrées totales
        total_result = await self.db.execute(
            select(LandDictionary).where(LandDictionary.land_id == land_id)
        )
        total_entries = len(total_result.fetchall())
        
        # Récupérer quelques mots d'exemple
        sample_result = await self.db.execute(
            select(Word.word, Word.lemma, LandDictionary.weight).join(
                LandDictionary, Word.id == LandDictionary.word_id
            ).where(LandDictionary.land_id == land_id).limit(10)
        )
        sample_words = [
            {"word": row.word, "lemma": row.lemma, "weight": row.weight}
            for row in sample_result.fetchall()
        ]
        
        return {
            "land_id": land_id,
            "total_entries": total_entries,
            "sample_words": sample_words
        }
