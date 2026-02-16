# 📋 FINALISATION DE LA MIGRATION - LEGACY → API

**Date d'analyse**: 2025-11-20
**Analysé par**: Claude
**Statut global**: 🟡 Migration ~70% complète

---

## 📊 VUE D'ENSEMBLE

### Résumé Exécutif
- **Code Legacy**: ~9,256 lignes Python (_legacy/)
- **Fonctionnalités migrées**: ~70%
- **Fonctionnalités manquantes**: 30 items identifiés
- **État production**: ✅ Prêt pour use cases de base
- **État avancé**: 🟡 Fonctionnalités avancées en migration

### Répartition par Priorité
- 🔴 **Critique** (6 tâches): Fonctionnalités core manquantes
- 🟡 **Haute** (8 tâches): Fonctionnalités importantes avec workarounds
- 🟢 **Moyenne** (10 tâches): Améliorations et optimisations
- ⚪ **Basse** (6 tâches): Nice-to-have et qualité de vie

---

## 🔴 PRIORITÉ CRITIQUE

### 1. Pipeline Embeddings (DÉSACTIVÉ dans V2)
**Statut**: ⚠️ Code existe mais désactivé
**Legacy**: `_legacy/embedding_pipeline.py` (377 lignes)
**API Actuelle**: Code commenté dans V2 (moved to projetV3)

**Fonctionnalités manquantes**:
- ❌ Génération embeddings pour paragraphes
- ❌ Recherche par similarité cosinus
- ❌ Clustering sémantique
- ❌ Index ANN (FAISS, Annoy)
- ❌ Batch processing embeddings
- ❌ Support multi-providers (OpenAI, Cohere, Local)

**Fichiers concernés**:
- `app/services/embedding_service.py` (désactivé)
- `app/api/v2/endpoints/paragraphs.py:generate_embeddings()` (désactivé)

**Tâches**:
1. [ ] Réactiver `embedding_service.py`
2. [ ] Implémenter provider abstraction (OpenAI, Cohere, SentenceTransformers)
3. [ ] Créer endpoint `POST /api/v2/paragraphs/generate-embeddings`
4. [ ] Créer endpoint `POST /api/v2/paragraphs/search-similar`
5. [ ] Implémenter index FAISS pour ANN search
6. [ ] Ajouter batch processing avec Celery
7. [ ] Créer endpoints health check providers
8. [ ] Tests unitaires et d'intégration
9. [ ] Documentation API

**Estimation**: 5-8 jours
**Dépendances**: projetV3 integration strategy

---

### 2. Recherche Sémantique (Semantic Search)
**Statut**: ⚠️ Table `similarities` existe mais endpoints manquants
**Legacy**: `_legacy/semantic_pipeline.py` (518 lignes)
**API Actuelle**: Modèle `Similarity` existe, pas d'endpoints

**Fonctionnalités manquantes**:
- ❌ Calcul similarités entre paragraphes
- ❌ Recherche par requête texte
- ❌ Clustering automatique
- ❌ Détection doublons sémantiques
- ❌ Recommandations de contenu similaire

**Fichiers concernés**:
- `app/models/paragraph.py` (relation `similarities_as_source/target`)
- Besoin nouveau: `app/services/semantic_search_service.py`
- Besoin nouveau: `app/api/v2/endpoints/semantic_search.py`

**Tâches**:
1. [ ] Créer `SemanticSearchService`
2. [ ] Implémenter calcul similarités batch
3. [ ] Endpoint `POST /api/v2/paragraphs/compute-similarities`
4. [ ] Endpoint `GET /api/v2/paragraphs/{id}/similar`
5. [ ] Endpoint `POST /api/v2/search/semantic` (full-text semantic)
6. [ ] Clustering avec K-Means/DBSCAN
7. [ ] Détection doublons automatique
8. [ ] Background task Celery pour calculs
9. [ ] Cache Redis pour résultats fréquents
10. [ ] Tests et documentation

**Estimation**: 4-6 jours
**Dépendances**: Tâche #1 (Embeddings)

---

### 3. Extraction Médias Dynamiques (Playwright)
**Statut**: ❌ Non migré
**Legacy**: `_legacy/core.py:extract_dynamic_medias()` (100+ lignes)
**API Actuelle**: Extraction statique uniquement

**Fonctionnalités manquantes**:
- ❌ Lancement Chromium headless
- ❌ Attente network idle + lazy loading
- ❌ Extraction médias JavaScript-rendered
- ❌ Support data-src, data-lazy-src, data-original
- ❌ Screenshots de pages

**Fichiers concernés**:
- Besoin nouveau: `app/services/dynamic_media_service.py`
- Extension: `app/services/media_extraction.py`

**Tâches**:
1. [ ] Ajouter dépendance Playwright au projet
2. [ ] Créer `DynamicMediaService`
3. [ ] Implémenter extraction avec Chromium headless
4. [ ] Gérer timeout et network idle
5. [ ] Support lazy-loading patterns
6. [ ] Ajouter option dans `crawl_land()`: `dynamic_media=True`
7. [ ] Endpoint `POST /api/v2/expressions/{id}/extract-dynamic-media`
8. [ ] Tests avec sites réels (SPA React/Vue)
9. [ ] Documentation usage et configuration

**Estimation**: 3-5 jours
**Risques**: Performance (headless browser lourd), timeouts

---

### 4. Intégration SerpAPI (Endpoints manquants)
**Statut**: ⚠️ Service existe mais pas d'endpoints API
**Legacy**: `_legacy/core.py:fetch_serpapi_url_list()` (400+ lignes)
**API Actuelle**: `app/services/serpapi_service.py` existe

**Fonctionnalités manquantes**:
- ❌ Endpoints API pour recherche
- ❌ Pagination automatique
- ❌ Windows temporelles (day/week/month)
- ❌ Multi-engines (Google/Bing/DuckDuckGo)
- ❌ Filtrage par dates

**Fichiers concernés**:
- `app/services/serpapi_service.py` (service existe ✅)
- Besoin nouveau: `app/api/v2/endpoints/serpapi.py`
- Besoin nouveau: `app/schemas/serpapi.py`

**Tâches**:
1. [ ] Créer schémas Pydantic (request/response)
2. [ ] Endpoint `POST /api/v2/lands/{land_id}/serpapi-search`
3. [ ] Support paramètres: query, engine, lang, datestart, dateend, timestep
4. [ ] Ajouter résultats comme expressions automatiquement
5. [ ] Background task Celery pour recherches longues
6. [ ] Gestion rate limits API
7. [ ] Caching résultats (éviter requêtes dupliquées)
8. [ ] Tests avec mocks SerpAPI
9. [ ] Documentation exemples d'usage

**Estimation**: 2-3 jours

---

### 5. Gestion Expression Links (Endpoints manquants)
**Statut**: ⚠️ Table `expression_links` existe mais pas d'endpoints
**Legacy**: `_legacy/core.py:link_expression()` + graphe
**API Actuelle**: Modèle existe, CRUD basique existe

**Fonctionnalités manquantes**:
- ❌ Endpoints pour lister liens d'une expression
- ❌ Analyse de graphe (PageRank, centralité)
- ❌ Visualisation graphe
- ❌ Détection clusters/communautés
- ❌ Export graphe (GraphML, JSON)

**Fichiers concernés**:
- `app/models/expression.py` (relations `outgoing_links`, `incoming_links` ✅)
- `app/crud/crud_link.py` (CRUD basique ✅)
- Besoin nouveau: `app/api/v2/endpoints/graph.py`
- Besoin nouveau: `app/services/graph_analysis_service.py`

**Tâches**:
1. [ ] Endpoint `GET /api/v2/expressions/{id}/links` (outgoing/incoming)
2. [ ] Endpoint `GET /api/v2/lands/{land_id}/graph` (vue complète)
3. [ ] Créer `GraphAnalysisService` avec NetworkX
4. [ ] Calcul PageRank pour expressions
5. [ ] Détection communautés (Louvain, Girvan-Newman)
6. [ ] Métriques centralité (betweenness, closeness, degree)
7. [ ] Export formats (GraphML, D3.js JSON, Cytoscape JSON)
8. [ ] Endpoint `GET /api/v2/lands/{land_id}/graph/metrics`
9. [ ] Tests et documentation

**Estimation**: 4-5 jours

---

### 6. Archive.org Fallback (À vérifier)
**Statut**: 🤔 Incertain si migré pour expressions
**Legacy**: `_legacy/core.py:crawl_expression()` fallback Archive.org
**API Actuelle**: Migré pour domaines, pas sûr pour expressions

**Fonctionnalités manquantes**:
- ❓ Fallback Archive.org si expression HTTP 404/500
- ❓ Recherche snapshot le plus proche
- ❓ Extraction contenu archivé avec Trafilatura

**Fichiers concernés**:
- `app/core/domain_crawler.py` (Archive.org pour domaines ✅)
- `app/core/crawler_engine.py` (à vérifier pour expressions)

**Tâches**:
1. [ ] Vérifier si fallback Archive.org existe pour expressions
2. [ ] Si non: Implémenter dans `crawler_engine.py`
3. [ ] Ajouter colonne `source` dans `expressions` (direct/archive/trafilatura)
4. [ ] Tests avec URLs archivées
5. [ ] Documentation

**Estimation**: 1-2 jours
**Dépendance**: Investigation préalable

---

## 🟡 PRIORITÉ HAUTE

### 7. Tag Management Complet
**Statut**: ⚠️ Endpoints V1 incomplets
**Legacy**: Tags avec hiérarchie
**API Actuelle**: CRUD basique, pas de tagged_content endpoints

**Fonctionnalités manquantes**:
- ❌ Hiérarchie tags (parent/children)
- ❌ CRUD pour `tagged_content`
- ❌ Extraction automatique tags depuis contenu
- ❌ Export tags (matrix, content) comme legacy
- ❌ Statistiques usage tags

**Fichiers concernés**:
- `app/api/v1/endpoints/tags.py` (basique)
- Besoin: `app/api/v2/endpoints/tagged_content.py`
- Besoin: `app/services/tag_extraction_service.py`

**Tâches**:
1. [ ] Migrer endpoints tags vers V2 avec pagination
2. [ ] Endpoint `POST /api/v2/tags/{tag_id}/children` (hiérarchie)
3. [ ] CRUD complet tagged_content
4. [ ] Endpoint `POST /api/v2/expressions/{id}/tag` (ajout tag manuel)
5. [ ] Service extraction automatique tags (NER, keywords)
6. [ ] Endpoint `POST /api/v2/lands/{land_id}/auto-tag`
7. [ ] Export tags (matrix CSV, content CSV) comme legacy
8. [ ] Statistiques tags par land
9. [ ] Tests et documentation

**Estimation**: 3-4 jours

---

### 8. Dictionary Management Complet
**Statut**: ⚠️ Endpoints partiels (populate, stats)
**Legacy**: CRUD complet + stemming
**API Actuelle**: Populate + stats uniquement

**Fonctionnalités manquantes**:
- ❌ CRUD complet sur `Word` table
- ❌ Endpoint ajout/suppression mots individuels
- ❌ Endpoint liste dictionnaire
- ❌ Stemming français explicite
- ❌ Import/export dictionnaire

**Fichiers concernés**:
- `app/services/dictionary_service.py` (populate exists ✅)
- Besoin: `app/api/v2/endpoints/dictionary.py`
- Besoin: `app/crud/crud_word.py`

**Tâches**:
1. [ ] Créer `crud_word.py` avec CRUD complet
2. [ ] Endpoint `POST /api/v2/lands/{land_id}/dictionary/words`
3. [ ] Endpoint `GET /api/v2/lands/{land_id}/dictionary/words`
4. [ ] Endpoint `DELETE /api/v2/lands/{land_id}/dictionary/words/{word_id}`
5. [ ] Endpoint `POST /api/v2/lands/{land_id}/dictionary/import` (CSV/TXT)
6. [ ] Endpoint `GET /api/v2/lands/{land_id}/dictionary/export`
7. [ ] Stemming automatique avec NLTK Snowball
8. [ ] Tests stemming français
9. [ ] Documentation

**Estimation**: 2-3 jours

---

### 9. Quality Scoring Automatique
**Statut**: ⚠️ Service existe mais pas intégré au crawl
**Legacy**: Calcul intégré dans crawl
**API Actuelle**: `quality_scorer.py` existe mais pas utilisé

**Fonctionnalités manquantes**:
- ❌ Scoring automatique pendant crawl
- ❌ Endpoints scoring manuel
- ❌ Métriques quality détaillées
- ❌ Seuils quality configurables

**Fichiers concernés**:
- `app/services/quality_scorer.py` (service ✅)
- `app/core/crawler_engine.py` (intégrer scoring)
- Besoin: `app/api/v2/endpoints/quality.py`

**Tâches**:
1. [ ] Intégrer `quality_scorer` dans pipeline crawl
2. [ ] Endpoint `POST /api/v2/expressions/{id}/compute-quality`
3. [ ] Endpoint `POST /api/v2/lands/{land_id}/compute-quality` (batch)
4. [ ] Métriques détaillées: readability, structure, completeness
5. [ ] Configuration seuils dans settings
6. [ ] Filtrage expressions par quality_score
7. [ ] Background task Celery pour batch
8. [ ] Tests avec contenu réel
9. [ ] Documentation métriques

**Estimation**: 2-3 jours

---

### 10. Consolidation Complète
**Statut**: ⚠️ Placeholder dans `crawling_service.py`
**Legacy**: `_legacy/core.py:consolidate_land()` (200+ lignes)
**API Actuelle**: Fonction vide

**Fonctionnalités legacy manquantes**:
```python
def consolidate_land():
    # 1. Suppression anciens liens et médias
    # 2. Recalcul relevance sans OpenRouter
    # 3. Extraction liens sortants (Markdown + HTML)
    # 4. Ajout documents manquants
    # 5. Recréation liens avec gestion IntegrityError
    # 6. Extraction et recréation médias
```

**Tâches**:
1. [ ] Implémenter suppression anciens liens/médias
2. [ ] Recalcul relevance pour toutes expressions
3. [ ] Extraction liens sortants depuis readable
4. [ ] Création nouvelles expressions si URLs manquantes
5. [ ] Reconstruction graphe de liens
6. [ ] Re-extraction médias depuis HTML
7. [ ] Gestion erreurs IntegrityError (doublons)
8. [ ] Background task Celery
9. [ ] Tests avec land réel
10. [ ] Documentation

**Estimation**: 3-4 jours

---

### 11. SEO Rank Analysis
**Statut**: ❌ Placeholder uniquement
**Legacy**: `_legacy/core.py:fetch_seorank_for_url()` + update batch
**API Actuelle**: Colonne `seo_rank` existe, pas d'implémentation

**Fonctionnalités manquantes**:
- ❌ Intégration API SEOrank (Moz, SimilarWeb, Facebook)
- ❌ Métriques: domain authority, page authority, social shares
- ❌ Batch update avec filtres
- ❌ Rate limiting et retry

**Fichiers concernés**:
- Besoin nouveau: `app/services/seorank_service.py`
- `app/models/expression.py` (colonne `seo_rank` JSON ✅)

**Tâches**:
1. [ ] Créer `SeoRankService` avec API client
2. [ ] Support Moz API (domain authority, page authority)
3. [ ] Support SimilarWeb API (traffic metrics)
4. [ ] Support Facebook API (social shares)
5. [ ] Endpoint `POST /api/v2/expressions/{id}/fetch-seorank`
6. [ ] Endpoint `POST /api/v2/lands/{land_id}/update-seorank` (batch)
7. [ ] Paramètres: force_refresh, delay, filtres
8. [ ] Rate limiting avec backoff exponentiel
9. [ ] Background task Celery
10. [ ] Tests avec mocks API
11. [ ] Documentation

**Estimation**: 4-5 jours
**Dépendances**: Accès APIs (Moz, SimilarWeb, Facebook)

---

### 12. Canonical URL Management
**Statut**: ⚠️ Colonne existe mais pas utilisée
**Legacy**: Pas explicite dans legacy
**API Actuelle**: Colonne `canonical_url` existe

**Fonctionnalités manquantes**:
- ❌ Détection canonical URL depuis HTML `<link rel="canonical">`
- ❌ Déduplication expressions par canonical
- ❌ Fusion métadonnées doublons
- ❌ Redirection automatique vers canonical

**Fichiers concernés**:
- `app/models/expression.py` (colonne `canonical_url` ✅)
- `app/core/content_extractor.py` (ajouter détection)

**Tâches**:
1. [ ] Extraction canonical URL depuis HTML
2. [ ] Sauvegarde dans colonne `canonical_url`
3. [ ] Détection doublons (même canonical)
4. [ ] Endpoint `POST /api/v2/lands/{land_id}/deduplicate-expressions`
5. [ ] Stratégie fusion: conserver plus complet
6. [ ] Tests avec sites ayant canonical URLs
7. [ ] Documentation

**Estimation**: 2-3 jours

---

### 13. Heuristics pour Domaines
**Statut**: ❌ Non migré
**Legacy**: Mapping domaines logiques (ex: twitter.com/user → domaine)
**API Actuelle**: Pas d'équivalent

**Fonctionnalités manquantes**:
- ❌ Configuration heuristics (patterns regex)
- ❌ Extraction domaine logique vs technique
- ❌ Mapping configurables
- ❌ Update batch domaines selon nouvelles heuristics

**Fichiers concernés**:
- Besoin nouveau: `app/core/heuristics.py`
- `app/core/crawler_engine.py` (intégrer)

**Tâches**:
1. [ ] Créer module `heuristics.py`
2. [ ] Configuration patterns dans settings (JSON/YAML)
3. [ ] Fonction `extract_logical_domain(url, heuristics)`
4. [ ] Endpoint `POST /api/v2/domains/update-heuristics`
5. [ ] Tests avec URLs complexes (subdomains, paths)
6. [ ] Documentation exemples patterns

**Estimation**: 2 jours

---

### 14. Export Tags (Legacy)
**Statut**: ❌ Non migré
**Legacy**: `_legacy/export.py:export_tags()` (matrix, content)
**API Actuelle**: Pas d'export tags

**Fonctionnalités manquantes**:
- ❌ Export tags matrix CSV
- ❌ Export tags content CSV

**Fichiers concernés**:
- Besoin: Extension `app/services/export_service_sync.py`

**Tâches**:
1. [ ] Implémenter `export_tags_matrix()`
2. [ ] Implémenter `export_tags_content()`
3. [ ] Endpoint `POST /api/v2/export/tags` (paramètre type)
4. [ ] Tests export
5. [ ] Documentation formats

**Estimation**: 1-2 jours
**Dépendance**: Tâche #7 (Tag Management)

---

## 🟢 PRIORITÉ MOYENNE

### 15. Semantic Pipeline (TF-IDF, LDA, NMF)
**Statut**: ❌ Non migré
**Legacy**: `_legacy/semantic_pipeline.py` (518 lignes)
**API Actuelle**: Aucun équivalent

**Fonctionnalités manquantes**:
- ❌ TF-IDF vectorization
- ❌ Topic modeling (LDA, NMF)
- ❌ Extraction keywords automatique
- ❌ Named Entity Recognition (NER)

**Tâches**:
1. [ ] Créer `SemanticPipelineService`
2. [ ] Implémenter TF-IDF avec scikit-learn
3. [ ] Topic modeling LDA/NMF
4. [ ] Extraction keywords top-N
5. [ ] NER avec spaCy (multilangue)
6. [ ] Endpoint `POST /api/v2/lands/{land_id}/analyze-topics`
7. [ ] Endpoint `GET /api/v2/lands/{land_id}/keywords`
8. [ ] Tests et documentation

**Estimation**: 4-5 jours

---

### 16. Sentiment Analysis Batch
**Statut**: ⚠️ Service existe mais endpoints limités
**Legacy**: Intégré dans crawl
**API Actuelle**: `sentiment_service.py` existe

**Fonctionnalités manquantes**:
- ❌ Batch processing toutes expressions d'un land
- ❌ Statistiques sentiment par land
- ❌ Évolution sentiment temporelle

**Tâches**:
1. [ ] Endpoint `POST /api/v2/lands/{land_id}/analyze-sentiment` (batch)
2. [ ] Endpoint `GET /api/v2/lands/{land_id}/sentiment-stats`
3. [ ] Graphique évolution temporelle (par date published)
4. [ ] Background task Celery
5. [ ] Tests et documentation

**Estimation**: 1-2 jours

---

### 17. Media Analysis Complète
**Statut**: ⚠️ Endpoint existe mais features limitées
**Legacy**: `_legacy/media_analyzer.py` (296 lignes)
**API Actuelle**: `media_processor.py` basique

**Fonctionnalités manquantes**:
- ❌ Perceptual hashing (dHash, pHash)
- ❌ Détection doublons par hash
- ❌ Object detection (YOLO, ResNet)
- ❌ OCR texte dans images
- ❌ NSFW detection

**Tâches**:
1. [ ] Implémenter perceptual hashing (imagehash)
2. [ ] Détection doublons par similarité hash
3. [ ] Object detection avec TensorFlow/PyTorch
4. [ ] OCR avec Tesseract/EasyOCR
5. [ ] NSFW detection (NudeNet ou API)
6. [ ] Colonnes: `detected_objects`, `text_content` (existent ✅)
7. [ ] Endpoint `POST /api/v2/media/{id}/analyze-advanced`
8. [ ] Tests avec images réelles
9. [ ] Documentation

**Estimation**: 5-7 jours

---

### 18. Crawl Statistics Enrichies
**Statut**: ⚠️ Stats basiques existent
**Legacy**: Statistiques détaillées
**API Actuelle**: Stats limitées

**Fonctionnalités manquantes**:
- ❌ Distribution HTTP status codes
- ❌ Distribution par depth
- ❌ Timeline crawl (expressions/jour)
- ❌ Performance metrics (temps moyen/expression)

**Tâches**:
1. [ ] Endpoint `GET /api/v2/lands/{land_id}/crawl-stats`
2. [ ] Métriques: distributions, timeline, performance
3. [ ] Graphiques prêts pour dashboard
4. [ ] Cache Redis pour stats lourdes
5. [ ] Documentation

**Estimation**: 2-3 jours

---

### 19. User Management Complet
**Statut**: ⚠️ Authentification existe, gestion limitée
**API Actuelle**: JWT auth ✅, endpoints utilisateurs limités

**Fonctionnalités manquantes**:
- ❌ Gestion utilisateurs admin (CRUD)
- ❌ Rôles et permissions
- ❌ Réinitialisation mot de passe
- ❌ Gestion sessions actives
- ❌ Audit logs complets

**Tâches**:
1. [ ] Endpoint `GET /api/v2/users` (admin only)
2. [ ] Endpoint `POST /api/v2/users` (création admin)
3. [ ] Endpoint `PUT /api/v2/users/{user_id}` (update)
4. [ ] Endpoint `DELETE /api/v2/users/{user_id}`
5. [ ] Système rôles/permissions (RBAC)
6. [ ] Reset password flow (email + token)
7. [ ] Endpoint `GET /api/v2/users/me/sessions`
8. [ ] Endpoint `POST /api/v2/users/me/logout-all`
9. [ ] Audit logs détaillés
10. [ ] Tests et documentation

**Estimation**: 4-5 jours

---

### 20. Pagination Standardisée
**Statut**: ⚠️ V2 a pagination mais pas V1
**API Actuelle**: Incohérence V1/V2

**Tâches**:
1. [ ] Standardiser pagination V1 (cursor-based)
2. [ ] Helper pagination dans dependencies
3. [ ] Documentation standards pagination
4. [ ] Tests tous endpoints paginés

**Estimation**: 1-2 jours

---

### 21. Error Handling Standardisé
**Statut**: ⚠️ V2 a format standard, V1 non
**API Actuelle**: Incohérence

**Tâches**:
1. [ ] Migrer V1 vers format erreur V2
2. [ ] Catalogue error codes complet
3. [ ] Handler exceptions global
4. [ ] Documentation error codes
5. [ ] Tests error handling

**Estimation**: 1-2 jours

---

### 22. Validation LLM Avancée
**Statut**: ⚠️ Basique existe
**API Actuelle**: `llm_validation_service.py` basique

**Fonctionnalités manquantes**:
- ❌ Multi-providers (OpenAI, Anthropic, Local)
- ❌ Prompts configurables
- ❌ Extraction métadonnées via LLM (résumé, entités)
- ❌ Classification automatique

**Tâches**:
1. [ ] Provider abstraction (OpenRouter, OpenAI, Anthropic)
2. [ ] Templates prompts configurables
3. [ ] Endpoint `POST /api/v2/expressions/{id}/llm-extract-metadata`
4. [ ] Endpoint `POST /api/v2/expressions/{id}/llm-classify`
5. [ ] Caching réponses LLM (eviter coûts)
6. [ ] Tests avec mocks LLM
7. [ ] Documentation

**Estimation**: 3-4 jours

---

### 23. Content Deduplication
**Statut**: ❌ Non migré
**Legacy**: Pas explicite
**API Actuelle**: Aucune déduplication

**Fonctionnalités manquantes**:
- ❌ Détection doublons par contenu (hash)
- ❌ Détection doublons sémantiques (embeddings)
- ❌ Fusion doublons automatique

**Tâches**:
1. [ ] Hash contenu (SHA256 de `readable`)
2. [ ] Colonne `content_hash` dans `expressions`
3. [ ] Détection doublons exacts
4. [ ] Détection doublons sémantiques (cosine similarity)
5. [ ] Endpoint `POST /api/v2/lands/{land_id}/find-duplicates`
6. [ ] Endpoint `POST /api/v2/lands/{land_id}/merge-duplicates`
7. [ ] Tests et documentation

**Estimation**: 3-4 jours

---

### 24. Webhooks et Notifications
**Statut**: ❌ Non existant
**Legacy**: Pas dans legacy
**API Actuelle**: Pas de webhooks

**Fonctionnalités manquantes**:
- ❌ Webhooks fin de crawl
- ❌ Notifications email
- ❌ WebSocket notifications temps-réel

**Tâches**:
1. [ ] Modèle `Webhook` (url, events, secret)
2. [ ] Service `WebhookService` (delivery, retry)
3. [ ] Événements: crawl_completed, crawl_failed, job_completed
4. [ ] Endpoint `POST /api/v2/webhooks`
5. [ ] CRUD webhooks
6. [ ] Signature HMAC pour sécurité
7. [ ] Retry avec backoff
8. [ ] Tests avec mock server
9. [ ] Documentation

**Estimation**: 3-4 jours

---

## ⚪ PRIORITÉ BASSE

### 25. CLI Interface Moderne
**Statut**: ❌ Legacy CLI non migré
**Legacy**: `_legacy/cli.py` (24 commandes)
**API Actuelle**: API uniquement

**Tâches**:
1. [ ] Client CLI moderne (Typer ou Click)
2. [ ] Commandes principales: crawl, export, stats
3. [ ] Configuration fichier ~/.mywebapi/config.yaml
4. [ ] Authentification JWT depuis CLI
5. [ ] Progress bars pour opérations longues
6. [ ] Tests CLI
7. [ ] Documentation

**Estimation**: 5-7 jours

---

### 26. Web Dashboard (UI)
**Statut**: ❌ Non existant
**API Actuelle**: API seulement

**Tâches**:
1. [ ] Architecture frontend (React, Vue, Svelte)
2. [ ] Authentification JWT
3. [ ] Pages: lands, expressions, domaines, médias
4. [ ] Visualisation graphe (D3.js, Cytoscape)
5. [ ] Dashboard statistiques
6. [ ] Lancement crawls
7. [ ] Exports
8. [ ] Tests E2E (Playwright)
9. [ ] Documentation

**Estimation**: 15-20 jours

---

### 27. Tests Coverage
**Statut**: ⚠️ Tests partiels
**API Actuelle**: 6 modules tests

**Tâches**:
1. [ ] Tests unitaires services (80%+ coverage)
2. [ ] Tests intégration endpoints (90%+ coverage)
3. [ ] Tests E2E workflows complets
4. [ ] Tests performance (load testing)
5. [ ] CI/CD avec coverage reports
6. [ ] Documentation tests

**Estimation**: 8-10 jours

---

### 28. Documentation Complète
**Statut**: ⚠️ OpenAPI auto-généré uniquement
**API Actuelle**: Pas de guides utilisateur

**Tâches**:
1. [ ] Guides utilisateur (Markdown/Sphinx)
2. [ ] Tutoriels pas-à-pas
3. [ ] Exemples code (Python, curl, JavaScript)
4. [ ] Architecture documentation
5. [ ] API reference complète
6. [ ] Deployment guides
7. [ ] Troubleshooting

**Estimation**: 5-7 jours

---

### 29. Database Migrations (Alembic)
**Statut**: ❌ Répertoire `migrations/` vide
**API Actuelle**: Pas de migrations

**Tâches**:
1. [ ] Setup Alembic
2. [ ] Migrations initiales depuis modèles
3. [ ] Script migration legacy → API
4. [ ] CI/CD auto-migrations
5. [ ] Documentation

**Estimation**: 2-3 jours

---

### 30. Performance Optimization
**Statut**: ⚪ Pas de profiling
**API Actuelle**: Performance non mesurée

**Tâches**:
1. [ ] Profiling endpoints lents
2. [ ] Optimisation requêtes SQL (N+1, indexes)
3. [ ] Caching Redis stratégique
4. [ ] Rate limiting par user
5. [ ] Compression responses (gzip)
6. [ ] CDN pour médias
7. [ ] Load balancing
8. [ ] Monitoring (Prometheus, Grafana)
9. [ ] Documentation performance

**Estimation**: 5-7 jours

---

## 📊 ESTIMATION GLOBALE

### Par Priorité
| Priorité | Tâches | Jours Min | Jours Max |
|----------|--------|-----------|-----------|
| 🔴 Critique | 6 | 17 | 29 |
| 🟡 Haute | 8 | 24 | 35 |
| 🟢 Moyenne | 10 | 30 | 44 |
| ⚪ Basse | 6 | 40 | 54 |
| **TOTAL** | **30** | **111** | **162** |

### Roadmap Recommandée

**Phase 1 - Critique (1-2 mois)**
- Tâches #1-6
- Focus: Embeddings, Semantic Search, Dynamic Media, SerpAPI, Links, Archive.org

**Phase 2 - Haute (1.5 mois)**
- Tâches #7-14
- Focus: Tags, Dictionary, Quality, Consolidation, SEO, Canonical, Heuristics, Export Tags

**Phase 3 - Moyenne (2 mois)**
- Tâches #15-24
- Focus: Semantic Pipeline, Sentiment, Media avancé, Stats, Users, Validation LLM

**Phase 4 - Basse (2-3 mois)**
- Tâches #25-30
- Focus: CLI, Dashboard, Tests, Docs, Migrations, Performance

**TOTAL ESTIMÉ**: 6-8 mois avec 1 développeur full-time

---

## 🎯 RECOMMANDATIONS STRATÉGIQUES

### Court Terme (Semaine 1-2)
1. ✅ Valider ce document avec l'équipe
2. ✅ Prioriser tâches critiques selon business needs
3. ✅ Setup environnement développement
4. 🚀 Commencer par Tâche #4 (SerpAPI) - Quick win, faible risque

### Moyen Terme (Mois 1-3)
1. 🔴 Implémenter toutes tâches critiques
2. 🟡 50% tâches haute priorité
3. 📊 Metrics et monitoring
4. 🧪 Tests coverage 60%+

### Long Terme (Mois 4-8)
1. 🟢 Compléter tâches moyenne/basse
2. 🎨 Dashboard web
3. 📚 Documentation complète
4. 🚀 Production-ready à 100%

---

## 📝 NOTES

### Risques Identifiés
- **Embeddings**: Dépendance projetV3, architecture à clarifier
- **Playwright**: Performance (headless browser lourd)
- **SEO APIs**: Coûts et rate limits externes
- **LLM**: Coûts OpenRouter/OpenAI, besoin caching agressif

### Décisions Techniques Nécessaires
- [ ] Stratégie embeddings: Local (SentenceTransformers) vs Cloud (OpenAI)
- [ ] Provider LLM principal: OpenRouter vs OpenAI vs Anthropic direct
- [ ] Frontend framework: React vs Vue vs Svelte
- [ ] Caching strategy: Redis vs Memcached
- [ ] Message queue: Celery/Redis vs RabbitMQ vs AWS SQS

### Points de Synchronisation
- [ ] Alignment avec projetV3 (embeddings, async features)
- [ ] Migration strategy legacy users
- [ ] Backward compatibility V1 vs deprecation
- [ ] API versioning strategy long-term (V3, V4...)

---

**Document généré par**: Claude (Anthropic)
**Date**: 2025-11-20
**Version**: 1.0
**Statut**: 📋 Prêt pour review
