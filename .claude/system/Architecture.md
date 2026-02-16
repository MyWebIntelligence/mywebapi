# MyWebIntelligence API v2 Architecture

This document donne une vision « pipeline » de l’API v2, résume le modèle de données et rappelle le rôle du serveur FastAPI dans `docker-compose.yml`.  
Les chemins entre parenthèses renvoient à l’implémentation dans `MyWebIntelligenceAPI/app`.

---

## 1. Vision pipeline de l’API v2

### 1.1 Couches principales
1. **Entrée HTTP** – FastAPI (`api/router.py`) expose les routeurs v1/v2 (`api/v1`, `api/v2`). Chaque endpoint valide la requête via Pydantic, contrôle les permissions, puis délègue à un service de domaine.
2. **Services d’orchestration** – Modules `app/services/*` encapsulent les règles métier (sélection d’expressions, déclenchement de tâches Celery, appels externes, mises à jour SQLAlchemy).
3. **Tâches Celery** – `app/tasks/*` exécutent les workloads lourds (crawl, readable, media, exports, embeddings). Les tâches mettent à jour `crawl_jobs`/`jobs` et publient la progression (WS + logs).
4. **Moteurs de traitement** – `app/core/*` fournit les moteurs spécialisés : crawler, extracteur Trafilatura, media processor, embedding providers, etc.
5. **Accès aux données** – `app/crud/*` et `app/db/*` pilotent PostgreSQL via les sessions synchrones définies dans `app/db/session.py`.
6. **Observabilité** – Logs structurés (`utils/logging.py`), WebSockets (`core/websocket.py`), tables `crawl_jobs`, exports physiques et métriques (Prometheus/Grafana côté ops).

### 1.2 Lifecycle générique d’une requête v2
1. **Client** appelle `POST /api/v2/lands/{id}/<pipeline>`.
2. **Endpoint** (ex. `api/v2/endpoints/lands_v2.py`) vérifie l’utilisateur, sérialise la payload, enregistre un `crawl_job` via `crud_job`.
3. **Service** (ex. `services/crawling_service.py`) prépare les paramètres, envoie une tâche Celery et renvoie `job_id`, `ws_channel`.
4. **Tâche Celery** (ex. `tasks/crawling_task.py`) ouvre une session DB (`db/session.SessionLocal`), récupère les expressions, lance le moteur (`core/crawler_engine.py`), met à jour la base, publie la progression.
5. **Client** suit le job (WebSocket `core/websocket.py` ou `GET /api/v2/jobs/{id}`) et récupère les résultats (`exports`, statistiques, champs enrichis).

### 1.3 Pipelines majeurs

| Pipeline | Endpoint principal | Service / Tâche | Core utilisé | Effets |
|----------|-------------------|-----------------|--------------|--------|
| **Crawl** | `POST /lands/{id}/crawl` (`v1`, `v2`) | `services/crawling_service.py` → `tasks/crawling_task.py` | `core/crawler_engine.py` | Crée/actualise `expressions`, `media`, `links`, calcule relevance/sentiment/quality, met `approved_at` |
| **Readable** | `POST /lands/{id}/readable` | `services/readable_service.py` ou `readable_simple_service.py` via `tasks/readable_task.py` | `core/content_extractor.py`, `core/readable_db.py` | Génère markdown lisible, met à jour metadata, peut valider LLM, recalculer relevance |
| **Media Analyse** | `POST /lands/{id}/medianalyse` | `tasks/media_analysis_task.py` | `core/media_processor.py` | Télécharge et enrichit chaque média (dimensions, EXIF, couleur, hash), marque `media.is_processed` |
| **Embeddings / Paragraphes** | `POST /lands/{id}/embeddings` (v1) | `services/embedding_service.py` → `tasks/embedding_tasks.py` | `core/embedding_providers/*` | Génère paragraphes et embeddings, remplit `Paragraph`, `ParagraphEmbedding`, `ParagraphSimilarity` |
| **Exports** | `POST /lands/{id}/export` (`v1`, `v2`) | `services/export_service.py` / `_sync.py` → `tasks/export_task.py` | `services/export_service*` (SQL + CSV/GEXF writer) | Produit les fichiers sous `exports/`, expose colonnes seorank/media/readable |
| **Dictionary / Text** | `POST /lands/{id}/dictionary` etc. | `services/dictionary_service.py`, `services/text_processor_service.py` | `core/text_processing.py` | Maintient les `LandDictionary`, mots/lemmes, scores relevance |
| **Validation LLM** | `enable_llm` dans crawl ou `POST /lands/{id}/llm-validate` | `services/llm_validation_service.py` | OpenRouter API | Marque `valid_llm`, `valid_model`, ajustement relevance. Voir `docs/LLM_VALIDATION_GUIDE.md` |
| **SEO Rank** | `POST /lands/{id}/seorank` | `tasks/seorank_task.py` | API SEO Rank (httpx) | Enrichit `Expression.seo_rank` avec JSON brut de l'API |
| **Consolidation** | `POST /lands/{id}/consolidate` | `tasks/consolidation_task.py` | `core/text_processing.py` | Recalcule relevance, rebuild links/media, ajoute expressions manquantes |
| **Heuristic Update** | `POST /lands/{id}/heuristic-update` | `tasks/heuristic_update_task.py` | `crud/crud_domain.py` | Recalcule les noms de domaine selon les regles heuristiques |
| **Domain Crawl** | `POST /domains/crawl` | `services/domain_crawl_service.py`, `tasks/domain_crawl_task.py` | `core/domain_crawler.py` | Enrichit table `domains`. Voir `docs/domain_crawl.md` |

### 1.4 Composants transverses
- **Authentification & sécurité** – `core/security.py`, endpoints `api/v1/auth.py`, dépendances `api/dependencies.py`.
- **Versioning** – `api/versioning.py` choisit entre `v1` et `v2` via header `Accept`.
- **Sérialisation** – `schemas/*` joyent ds Pydantic (ex. `schemas/land.py`, `schemas/job.py`, `schemas/readable.py`).
- **Config & settings** – `config.py` expose objets `Settings` (OpenRouter, Trafilatura, Media, Seorank, Celery). Les variables sont chargées via `.env`.
- **Tests** – `tests/unit` (moteurs/services), `tests/integration` (API), `tests/manual` (scripts de scénario), `tests/legacy` (parité).

---

## 2. Modèle de données (référence rapide)
Modèles SQLAlchemy définis dans `app/db/models.py` (lien : `MyWebIntelligenceAPI/app/db/models.py`). Principales entités :

| Table | Description | Relations clés |
|-------|-------------|----------------|
| **users** | Comptes applicatifs avec rôle (`role`) et champs OAuth facultatifs | `users` 1→N `lands` |
| **lands** | Projet de crawl (nom, description, config, statut, owner) | 1→N `domains`, `expressions`, `crawl_jobs`, `tags`, `land_dictionaries` |
| **domains** | Domaine web associé à un land (name, title, description, http_status, stats) | 1→N `expressions` |
| **expressions** | URLs crawlées (titre, contenu, metadata, statut HTTP, readability, relevance, sentiment, quality, seo_rank, valid_llm) | N→1 `land`, `domain`; 1→N `media`, `paragraphs`, `links` |
| **media** | Ressources média extraites (url, type, metadata, analyses: dimensions, dominant_colors, phash, is_processed, analyzed_at) | N→1 `expression` |
| **expression_links** | Liens découverts entre expressions (source_id, target_id, type, rel) | Graphe d’hyperliens |
| **land_dictionaries / words** | Dictionnaire de mots/lemmes par land utilisé pour relevance | `land_dictionaries` joint table `lands` ↔ `words` |
| **paragraphs / paragraph_embeddings / paragraph_similarities** | Stockage du contenu segmenté, vecteurs et similarités pour embeddings | 1→1/1→N sur `expression` |
| **tags / tagged_content** | Système de tagging des expressions/media |  |
| **crawl_jobs** | Table de suivi des jobs (type, status, progress, result_data) | Pilotée par services/tâches |
| **media_jobs / readable_jobs** (selon migrations) | Tables historiques pour pipelines spécifiques |  |

La structure complète (colonnes, index, contraintes) est disponible dans `app/db/models.py` et pilotée par Alembic (`alembic/`).

---

## 3. Serveur API dans `docker-compose.yml`

### 3.1 Services principaux
- **db** (`postgres:15`) – Base PostgreSQL `mwi_db` avec utilisateur `mwi_user`. Volume persistant `postgres_data`. Healthcheck `pg_isready`.
- **redis** (`redis:7-alpine`) – Broker / backend Celery (DB 1 & 2). Config minimaliste sans persistance.
- **mywebintelligenceapi** – Conteneur FastAPI :
  - Build `./MyWebIntelligenceAPI/Dockerfile`.
  - Monte le code (`./MyWebIntelligenceAPI:/app`) pour hot-reload en dev.
  - Charge `.env` du projet (`MyWebIntelligenceAPI/.env`).
  - Dépend de `db` (healthy) et `redis`.
  - Variables d’environnement : `DATABASE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_AUTOSCALE`.
  - Commande : `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
  - Port mappé `8000:8000`.
- **celery_worker** – Worker identique (même image, code monté, env identique) exécutant `celery -A app.core.celery_app worker`.

### 3.2 Cycle de vie
1. `mywebintelligenceapi` démarre FastAPI (`app/main.py`). L’instance prépare les sessions synchrones, charge les routes v1/v2 et enregistre les tasks Celery (via `core/celery_app.py`).
2. `celery_worker` lance un worker qui importe `app.tasks` (enregistrement auto des pipelines).
3. Jobs : l’API crée un enregistrement `crawl_jobs`, envoie une tâche vers Redis. Le worker consomme la tâche, utilise PostgreSQL pour lire/écrire les entités, puis met à jour `crawl_jobs`.
4. Les clients peuvent accéder à l’API via `http://localhost:8000` (Swagger sur `/docs`). WebSocket (`core/websocket.py`) fonctionne via le même conteneur.

### 3.3 Points d’attention OPS
- Ajuster `CELERY_AUTOSCALE` selon la charge (env optionnelle).
- Les dépendances (Trafilatura, PIL, sklearn…) sont installées via `Dockerfile`.
- Pour production, prévoir un reverse proxy (Traefik, Nginx) et persistance Redis si nécessaire.

---

## 4. Ressources complémentaires
- Playbook principal : `.claude/AGENTS.md`.
- Guides dédiés : `.claude/docs/QUALITY_SCORE_GUIDE.md`, `.claude/docs/SENTIMENT_ANALYSIS_FEATURE.md`, `.claude/docs/CHAÎNE_FALLBACKS.md`, `.claude/docs/LLM_VALIDATION_GUIDE.md`, `.claude/docs/domain_crawl.md`.
- Taches terminees : `.claude/tasks/transfert_mediaanalyse_dev.md`, `.claude/tasks/transfert_seorank_dev.md`, `.claude/tasks/Transfert_readable.md`.
- Audit complet du transfert legacy : `.claude/docs/TRANSFERT_AUDIT.md` (30/30 fonctions implementees).

Ce document doit servir de point d’entrée rapide pour comprendre comment l’API v2 orchestre ses pipelines, comment les données sont structurées et comment l’infrastructure Docker assemble le tout.
