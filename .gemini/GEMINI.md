# MyWebIntelligence API - Guide Complet pour Agents

MyWebIntelligence est une API FastAPI encapsulant les fonctionnalités du crawler MyWebIntelligencePython. Elle permet l'intégration avec MyWebClient et ouvre la voie à un déploiement SaaS scalable.

---

## 🔴 ⚠️ ERREUR FRÉQUENTE À NE PLUS FAIRE ⚠️ 🔴

### **DOUBLE CRAWLER : SYNC vs ASYNC - NE PAS OUBLIER !**

Le système utilise **DEUX crawlers différents** :

```
┌─────────────────────────────────────────────────────────────────┐
│  ❌ ERREUR FRÉQUENTE : Modifier seulement crawler_engine.py     │
│                                                                  │
│  ✅ SOLUTION : TOUJOURS modifier les DEUX crawlers !            │
│                                                                  │
│  1️⃣  crawler_engine.py        (AsyncCrawlerEngine)            │
│      └─ Utilisé par : API directe, tests unitaires             │
│                                                                  │
│  2️⃣  crawler_engine_sync.py   (SyncCrawlerEngine)             │
│      └─ Utilisé par : Tasks Celery (crawl en production)       │
└─────────────────────────────────────────────────────────────────┘
```

### **Checklist OBLIGATOIRE avant tout commit :**

Quand vous modifiez la logique de crawl :

- [ ] ✅ Modifier `crawler_engine.py` (async)
- [ ] ✅ Modifier `crawler_engine_sync.py` (sync)
- [ ] ✅ Vérifier que les deux ont la même logique
- [ ] ✅ Tester avec Celery (pas seulement l'API directe)

### **Exemples de Bugs Causés par Cette Erreur :**

1. **Bug du 14 octobre 2025** :
   - Champ `content` (HTML) ajouté dans `crawler_engine.py`
   - Oublié dans `crawler_engine_sync.py`
   - **Résultat** : HTML NULL en base de données car Celery utilise la version sync

2. **Autres cas similaires** :
   - Extraction de métadonnées (title, description, keywords)
   - Nouvelle logique de calcul de relevance
   - Modifications des champs sauvegardés en DB

### **Pourquoi Deux Crawlers ?**

- **Async** : Utilisé par FastAPI (native async)
- **Sync** : Utilisé par Celery (workers ne supportent pas async proprement)

### **Comment Vérifier ?**

```bash
# 1. Après modification, chercher la logique dans les DEUX fichiers
grep -n "votre_modification" app/core/crawler_engine.py
grep -n "votre_modification" app/core/crawler_engine_sync.py

# 2. Tester avec Celery (pas seulement l'API)
docker logs mywebclient-celery_worker-1 --tail 50

# 3. Vérifier en DB que les données sont bien sauvegardées
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT * FROM expressions ORDER BY created_at DESC LIMIT 1;"
```

---

## 🔴 ⚠️ ERREUR CATASTROPHIQUE - DATABASE INITIALIZATION ⚠️ 🔴

### **INCIDENT DU 17 OCTOBRE 2025 : 2 HEURES PERDUES SUR ALEMBIC**

**❌ CE QUI A ÉTÉ FAIT (MAUVAIS) :**
- Suppression d'Alembic (correct - pas de prod donc pas de migrations)
- Création d'un script `init_db.py` externe pour créer les tables
- 2 HEURES de debug sur des problèmes de race conditions, transactions, rollbacks...
- Complexification avec try/catch, checkfirst, isolation levels, etc.

**✅ LA SOLUTION SIMPLE QUI AURAIT DÛ ÊTRE FAITE DÈS LE DÉBUT :**
```python
# Dans app/main.py
@app.on_event("startup")
async def startup_event():
    """Créer les tables au démarrage"""
    from sqlalchemy.ext.asyncio import create_async_engine
    autocommit_engine = create_async_engine(
        settings.DATABASE_URL,
        isolation_level="AUTOCOMMIT"  # ← CLÉ : évite rollback sur erreur
    )
    try:
        async with autocommit_engine.connect() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables créées", flush=True)  # ← flush=True OBLIGATOIRE
    except Exception as e:
        if "already exists" in str(e):
            print("✅ Tables déjà existantes", flush=True)
        else:
            raise
    finally:
        await autocommit_engine.dispose()
```

### **LEÇONS APPRISES :**

1. **TOUJOURS choisir la solution la PLUS SIMPLE**
   - ❌ Script externe → race conditions, gestion d'erreurs complexe
   - ✅ Startup event FastAPI → natif, simple, fonctionne

2. **AUTOCOMMIT est OBLIGATOIRE pour les DDL**
   - Sans AUTOCOMMIT : une erreur sur un index rollback TOUTES les tables
   - Avec AUTOCOMMIT : chaque CREATE TABLE est commité immédiatement
   - **Résultat observé** : "Tables déjà existantes" alors qu'aucune table n'existe !

3. **Logging FastAPI : utiliser `print(flush=True)`**
   - `logger.info()` ne s'affiche PAS si le niveau de logging n'est pas configuré
   - `print()` sans flush peut être bufferisé
   - **Solution** : `print("message", flush=True)`

4. **Ne PAS utiliser de transactions pour CREATE TABLE**
   - `engine.begin()` → transaction → rollback sur erreur
   - `engine.connect()` avec AUTOCOMMIT → chaque DDL commitée

5. **Pas de production = Pas de migrations Alembic**
   - Supprimer Alembic complètement
   - Créer tables automatiquement au startup
   - Plus simple, plus maintenable

### **Checklist pour Initialisation DB :**

- [ ] ✅ Créer tables dans `@app.on_event("startup")` de main.py
- [ ] ✅ Utiliser `isolation_level="AUTOCOMMIT"`
- [ ] ✅ Utiliser `print(flush=True)` pour débugger
- [ ] ✅ Wrapper les erreurs "already exists" sans faire crasher
- [ ] ✅ Tester avec `docker compose down -v && docker compose up -d`
- [ ] ✅ Vérifier les tables : `docker exec db psql -U user -d db -c "\dt"`

### **Erreur de Diagnostic :**

**Symptôme** : "Tables déjà existantes" dans les logs mais `\dt` montre 0 tables

**Cause** : Transaction rollbackée à cause d'une erreur sur un index, MAIS l'exception "already exists" était catchée, donnant l'impression que tout allait bien.

**Solution** : AUTOCOMMIT pour que chaque CREATE soit commitée même si un index échoue ensuite.

---

## 🎯 Concepts Clés

### Qu'est-ce qu'un "Land" ?
Un **Land** est un projet de crawling/recherche qui contient :
- **URLs de départ** (`start_urls`) : Points d'entrée du crawl
- **Mots-clés** (`words`) : Termes à rechercher avec leurs lemmes
- **Configuration** : Langues supportées, limites, etc.
- **Résultats** : Expressions (pages) et médias découverts

### Qu'est-ce qu'une "Expression" ?
Une **Expression** est une page web crawlée qui contient :
- **URL** et **contenu** de la page
- **Profondeur** (`depth`) : Distance depuis les URLs de départ (0 = URL initiale, 1 = lien direct, etc.)
- **Pertinence** (`relevance`) : Score de correspondance avec les mots-clés
- **Médias** associés (images, vidéos, audio)

### Workflow Typique
1. **Créer un Land** avec URLs de départ et mots-clés
2. **Lancer le crawl** → Découverte d'expressions et médias
3. **Pipeline Readable** → Extraction de contenu lisible (Mercury-like)
4. **Analyser les médias** → Extraction de métadonnées (couleurs, dimensions, EXIF)
5. **Exporter les données** → CSV, GEXF, JSON

## 🚀 Démarrage Rapide

### Authentification
```bash
# Option 1 : depuis l’hôte
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin@example.com&password=changeme" | jq -r .access_token)

# Option 2 : via Docker Compose (container « api »)
TOKEN=$(docker compose exec api curl -s -X POST "http://localhost:8000/api/v1/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=${MYWI_USERNAME:-admin@example.com}&password=${MYWI_PASSWORD:-changeme}" | jq -r .access_token)

echo "Token JWT: $TOKEN"
```

### Serveur Docker
```bash
# (Re)déployer avec migrations fraîchement appliquées
docker compose down -v
docker compose up --build -d

# Vérifier les containers
docker ps | grep mywebintelligenceapi

# Redémarrer si nécessaire
docker restart mywebintelligenceapi

# Tester que le serveur répond
curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null
```

## 🏗️ Architecture de l'API

### Structure des Endpoints

#### API v1 (Legacy)
- `/api/v1/auth/` - Authentification
- `/api/v1/export/` - Export de données (CSV, GEXF)

#### API v2 (Moderne)
- `/api/v2/lands/` - Gestion des projets (lands)
- `/api/v2/lands/{id}/crawl` - Lancement de crawls
- `/api/v2/lands/{id}/readable` - Pipeline readable (extraction contenu)
- `/api/v2/lands/{id}/media-analysis-async` - Analyse des médias (asynchrone)
- `/api/v2/lands/{id}/stats` - Statistiques

### Modèles de Données

#### Land (Projet)
```python
id: int                    # ID unique
name: str                  # Nom du projet
description: str           # Description
owner_id: int              # Propriétaire (FK users.id)
lang: List[str]            # Langues ["fr", "en"]
start_urls: List[str]      # URLs de départ
crawl_status: str          # "pending", "running", "completed"
total_expressions: int     # Nombre d'expressions
total_domains: int         # Nombre de domaines
words: List[dict]          # Mots-clés avec lemmes
```

#### Expression (Page crawlée)
```python
id: int                    # ID unique
land_id: int               # Projet parent
domain_id: int             # Domaine parent
url: str                   # URL de la page
title: str                 # Titre
content: str               # Contenu HTML
readable: str              # Contenu lisible (markdown)
depth: int                 # Profondeur de crawl
relevance: float           # Score de pertinence
quality_score: float       # Score de qualité (0.0-1.0) ✨ NOUVEAU
language: str              # Langue détectée
word_count: int            # Nombre de mots
http_status: int           # Code HTTP (200, 404, etc.)
```

#### Media (Fichiers média)
```python
id: int                    # ID unique
expression_id: int         # Expression parent
url: str                   # URL du média
type: str                  # "img", "video", "audio"
is_processed: bool         # Analysé ou non
width: int                 # Largeur (images)
height: int                # Hauteur (images)
file_size: int             # Taille en bytes
metadata: dict             # Métadonnées EXIF, etc.
dominant_colors: List[str] # Couleurs dominantes
```

## 🆕 Mises à jour structurelles (juillet 2025)

- **Schéma SQLAlchemy réaligné**  
  - `domains` conserve `http_status` et `fetched_at`.  
  - `expressions` stocke désormais `published_at`, `approved_at`, `validllm`, `validmodel`, `seorank`, et la langue détectée.  
  - `words` embarque `language` et `frequency`. Une migration Alembic `006_add_legacy_crawl_columns.py` doit être appliquée.

- **Dictionnaire de land**  
  - `DictionaryService.populate_land_dictionary` accepte les seeds (`words`) fournis à la création et crée automatiquement des entrées `Word` multilingues.  
  - Les variations générées via `get_lemma` remplissent la table `land_dictionaries` sans manipuler directement la relation ORM.

- **Service de crawl**  
  - `start_crawl_for_land` renvoie un `CrawlJobResponse` typé (avec `ws_channel`) et convertit les filtres `http_status` en entiers avant insertion.  
  - `CrawlerEngine` persiste la langue, approuve les expressions pertinentes et peuple les nouveaux champs de métadonnées.
- **Migrations automatiques**  
  - Les services `api` et `celery_worker` exécutent `alembic upgrade head` à chaque démarrage du conteneur. Reconstruis la stack (`docker compose down -v && docker compose up --build`) après un pull pour appliquer les derniers schémas.

- **Tests & environnement**  
  - Les tests de crawling nécessitent `pytest`, `sqlalchemy`, `aiosqlite` dans le venv.  
  - Sous Python 3.13, certaines wheels (`pydantic-core`, `asyncpg`, `pillow`) échouent à la compilation ; privilégier Python 3.11/3.12 ou installer Rust + toolchain compatible.

## 🔄 Pipelines de Traitement

### 1. Pipeline de Crawl
```
Start URLs → Crawler → Pages → Content Extraction → Expressions
                          ↓
                     Media Detection → Media Records
```

**Endpoint:** `POST /api/v2/lands/{id}/crawl`
```json
{
  "limit": 10,              // Nombre max de pages
  "depth": 2,               // Profondeur max
  "analyze_media": true     // Analyser les médias
}
```

### 2. Pipeline d'Analyse Media
```
Expressions → Media URLs → Download → Analysis → Metadata Storage
                               ↓
                         PIL/OpenCV → Colors, Dimensions, EXIF
```

**Endpoint:** `POST /api/v2/lands/{id}/media-analysis-async`
```json
{
  "depth": 1,               // Profondeur max des expressions à analyser (0=URLs initiales, 1=liens directs, etc.)
  "minrel": 0.5             // Score de pertinence minimum des expressions
}
```

**IMPORTANT:** `depth` ne limite PAS le nombre d'unités/médias à analyser, mais la profondeur des expressions source !
- `depth: 0` = Analyser uniquement les médias des URLs de départ
- `depth: 1` = Inclure aussi les médias des pages liées directement 
- `depth: 999` = Analyser tous les médias sans limite de profondeur

**STRATÉGIE de LIMITATION:** Pour limiter le nombre de médias analysés, utiliser `minrel` (pertinence) :
- `minrel: 0.0` = Toutes les expressions
- `minrel: 1.0` = Expressions moyennement pertinentes  
- `minrel: 3.0` = Expressions très pertinentes seulement (recommandé pour tests)
- `minrel: 5.0` = Expressions extrêmement pertinentes

### 3. Pipeline Readable (Nouveau)
```
Expressions → Content Extraction → Readable Content → Text Processing → Paragraphs
                     ↓
            Mercury/Trafilatura → Clean Text → LLM Validation → Storage
```

**Endpoint:** `POST /api/v2/lands/{id}/readable`
```json
{
  "limit": 50,              // Nombre max d'expressions à traiter
  "depth": 1,               // Profondeur max des expressions
  "merge_strategy": "smart_merge",  // "mercury_priority", "preserve_existing"
  "enable_llm": false,      // Validation LLM (optionnel)
  "batch_size": 10,         // Expressions par batch
  "max_concurrent": 5       // Batches concurrents
}
```

**IMPORTANT:** Le pipeline readable transforme le contenu HTML brut des expressions en contenu lisible et structuré :
- **Extraction intelligente** : Utilise Trafilatura puis Mercury fallback
- **Nettoyage** : Supprime le markup, garde le contenu principal
- **Validation LLM** : Optionnelle, améliore la qualité du contenu
- **Segmentation** : Découpe en paragraphes pour l'embedding

### 4. Pipeline LLM Validation (Intégré) ✅
```
Expressions → OpenRouter API → Relevance Check → Database Update
                     ↓
              "oui"/"non" → valid_llm, valid_model → Relevance=0 si non pertinent
```

**Intégration dans les pipelines existants :**
- **Crawl avec LLM** : `POST /api/v2/lands/{id}/crawl` avec `"enable_llm": true`
- **Readable avec LLM** : `POST /api/v2/lands/{id}/readable` avec `"enable_llm": true`

**Configuration OpenRouter requise :**
```bash
export OPENROUTER_ENABLED=True
export OPENROUTER_API_KEY=sk-or-v1-your-key-here
export OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

**Exemples d'usage :**
```bash
# Crawl avec validation LLM
curl -X POST "http://localhost:8000/api/v2/lands/36/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"limit": 5, "enable_llm": true}'

# Readable avec validation LLM  
curl -X POST "http://localhost:8000/api/v2/lands/36/readable" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"limit": 3, "enable_llm": true}'
```

**Résultats stockés :**
- `valid_llm` : "oui" (pertinent) ou "non" (non pertinent)
- `valid_model` : Modèle utilisé (ex: "anthropic/claude-3.5-sonnet")
- `relevance` : Mis à 0 si expression jugée non pertinente

---

## 🏆 Quality Score System (Nouveau - Octobre 2025) ✅

### ⚠️ DOUBLE CRAWLER : Implémentation Complète

**✅ IMPLÉMENTÉ DANS LES DEUX CRAWLERS :**
- ✅ `crawler_engine.py` (AsyncCrawlerEngine) - lignes 269-317
- ✅ `crawler_engine_sync.py` (SyncCrawlerEngine) - lignes 341-389
- ✅ **Parité parfaite** : Même logique dans les deux crawlers

### 📊 Vue d'Ensemble

Le **Quality Score** est un indicateur de qualité automatique pour chaque expression (page crawlée), calculé à partir de métadonnées existantes. Score entre **0.0** (très faible) et **1.0** (excellent).

```
Quality Score = Σ (Bloc_i × Poids_i)

5 Blocs Heuristiques :
1️⃣  Access (30%)      → HTTP status, content-type
2️⃣  Structure (15%)   → Title, description, keywords, canonical
3️⃣  Richness (25%)    → Word count, ratio texte/HTML, reading time
4️⃣  Coherence (20%)   → Langue, relevance, fraîcheur
5️⃣  Integrity (10%)   → LLM validation, pipeline complet
```

**Catégories de Qualité :**
- `0.8-1.0` : **Excellent** ⭐ (Contenu riche, bien structuré)
- `0.6-0.8` : **Bon** ✅ (Contenu acceptable)
- `0.4-0.6` : **Moyen** ⚠️ (Contenu limité)
- `0.2-0.4` : **Faible** ❌ (Très pauvre)
- `0.0-0.2` : **Très faible** ❌❌ (Erreur d'accès)

### 🎯 Caractéristiques

- ✅ **100% déterministe** : Pas de ML/LLM, reproductible
- ✅ **Gratuit** : Pas d'appels API externes
- ✅ **Rapide** : <10ms par expression
- ✅ **Transparent** : Heuristiques documentées
- ✅ **Configurable** : Poids ajustables via settings

### ⚙️ Configuration

Dans `.env` ou `app/config.py` :
```python
# Master switch (activé par défaut)
ENABLE_QUALITY_SCORING=true

# Poids des 5 blocs (doivent sommer à 1.0)
QUALITY_WEIGHT_ACCESS=0.30      # Accès
QUALITY_WEIGHT_STRUCTURE=0.15   # Structure HTML/SEO
QUALITY_WEIGHT_RICHNESS=0.25    # Richesse contenu
QUALITY_WEIGHT_COHERENCE=0.20   # Cohérence land/langue
QUALITY_WEIGHT_INTEGRITY=0.10   # Intégrité pipeline
```

### 🚀 Usage Automatique

Le `quality_score` est **calculé automatiquement** lors du crawl :

```bash
# Via API
curl -X POST "http://localhost:8000/api/v2/lands/15/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"limit": 100}'

# Via Celery
from app.core.celery_app import crawl_land_task
crawl_land_task.delay(land_id=15, limit=100)
```

Le champ `quality_score` est automatiquement rempli dans la DB pour chaque expression crawlée.

### 🔄 Reprocessing Historique

Pour recalculer les quality_scores sur expressions existantes :

```bash
# Dry-run (simulation)
docker exec mywebintelligenceapi python -m app.scripts.reprocess_quality_scores --dry-run

# Reprocess toutes les expressions sans quality_score
docker exec mywebintelligenceapi python -m app.scripts.reprocess_quality_scores

# Reprocess un land spécifique
docker exec mywebintelligenceapi python -m app.scripts.reprocess_quality_scores --land-id 15

# Limiter le nombre d'expressions
docker exec mywebintelligenceapi python -m app.scripts.reprocess_quality_scores --limit 1000

# Forcer le recalcul même si quality_score existe
docker exec mywebintelligenceapi python -m app.scripts.reprocess_quality_scores --force
```

**Exemple de sortie :**
```
============================================================
REPROCESSING SUMMARY
============================================================
Total candidates:     70
Processed:            70
Updated:              70
Errors:               0
Duration:             9.5s

Quality Distribution:
  Excellent      :   25 ( 35.7%)
  Bon            :   45 ( 64.3%)
  Moyen          :    0 (  0.0%)
  Faible         :    0 (  0.0%)
  Très faible    :    0 (  0.0%)
============================================================
```

### 🔍 Requêtes SQL Utiles

**Statistiques globales :**
```sql
SELECT
  COUNT(*) as total,
  COUNT(quality_score) as with_quality,
  ROUND(AVG(quality_score)::numeric, 3) as avg_score
FROM expressions;
```

**Distribution par catégorie :**
```sql
SELECT
  CASE
    WHEN quality_score >= 0.8 THEN 'Excellent'
    WHEN quality_score >= 0.6 THEN 'Bon'
    WHEN quality_score >= 0.4 THEN 'Moyen'
    WHEN quality_score >= 0.2 THEN 'Faible'
    ELSE 'Très faible'
  END as category,
  COUNT(*) as count,
  ROUND(AVG(quality_score)::numeric, 3) as avg_score
FROM expressions
WHERE quality_score IS NOT NULL
GROUP BY category
ORDER BY avg_score DESC;
```

**Top 10 meilleures expressions :**
```sql
SELECT id, url, quality_score, word_count, relevance
FROM expressions
WHERE quality_score IS NOT NULL
ORDER BY quality_score DESC
LIMIT 10;
```

### 📚 Fichiers du Système

| Fichier | Description |
|---------|-------------|
| `app/services/quality_scorer.py` | Service de calcul (5 blocs) |
| `app/core/crawler_engine.py` | Intégration ASYNC (lignes 269-317) |
| `app/core/crawler_engine_sync.py` | Intégration SYNC (lignes 341-389) |
| `app/scripts/reprocess_quality_scores.py` | Script de reprocessing |
| `tests/unit/test_quality_scorer.py` | 33 tests unitaires ✅ |
| `tests/data/quality_truth_table.json` | 20 cas de validation |
| `.claude/docs/QUALITY_SCORE_GUIDE.md` | Documentation complète (500+ lignes) |

### 🧪 Tests

```bash
# Tests unitaires (33 tests)
docker exec mywebintelligenceapi pytest tests/unit/test_quality_scorer.py -v

# Validation truth table
docker exec mywebintelligenceapi pytest tests/unit/test_quality_scorer.py::TestTruthTable -v
```

### 🎓 Documentation Complète

Pour les détails complets (heuristiques, tuning, troubleshooting) :
**Voir** : `.claude/docs/QUALITY_SCORE_GUIDE.md`

---

### 5. Pipeline d'Export
```
Data Selection → Format Conversion → Response
     ↓
CSV/GEXF/JSON → Compressed → Download
```

**Endpoint:** `POST /api/v1/export/direct`
```json
{
  "land_id": 36,
  "export_type": "mediacsv", // "pagecsv", "nodecsv", etc.
  "limit": 100
}
```

## 🗄️ Base de Données

### Tables Principales
- `users` - Utilisateurs
- `lands` - Projets de crawl
- `domains` - Domaines web
- `expressions` - Pages crawlées
- `media` - Fichiers média
- `paragraphs` - Contenu segmenté
- `crawl_jobs` - Jobs Celery

### Relations Clés
```
users (1) → (n) lands
lands (1) → (n) domains
lands (1) → (n) expressions
expressions (1) → (n) media
expressions (1) → (n) paragraphs
```

## 🧪 Tests Rapides

### ⚠️ PROBLÈME DE PERSISTENCE DU TOKEN

Le token JWT ne persiste pas car `export TOKEN` dans un **sous-shell Docker** ne remonte pas au shell parent. Voici **3 solutions** :

---

### ✅ **Solution 1 : Script complet dans Docker** (recommandé pour les tests)

Exécuter tout le workflow dans un seul appel Docker pour que le token reste en mémoire :

```bash
docker compose exec mywebintelligenceapi bash -c '
  # 1. Authentification
  TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin@example.com&password=changethispassword" \
    | jq -r ".access_token")

  echo "✅ Token obtenu : ${TOKEN:0:20}..."

  # 2. Créer le land
  LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"Lecornu$(date +%s)\",\"description\":\"Test gilets jaunes\",\"words\":[\"lecornu\"]}" \
    | jq -r ".id // empty")

  if [ -z "$LAND_ID" ]; then
    echo "❌ Impossible de créer le land"
    exit 1
  fi

  echo "✅ Land créé : LAND_ID=${LAND_ID}"

  # 3. Ajouter les URLs
  curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/urls" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data "$(jq -Rs "{urls: split(\"\n\") | map(select(length>0))}" /app/scripts/data/lecornu.txt)" \
    | jq "."

  echo "✅ URLs ajoutées au land ${LAND_ID}"
'
```

---

### ✅ **Solution 2 : Appels depuis l'hôte** (si API accessible sur localhost)

Stocker le token dans un fichier temporaire pour le réutiliser :

```bash
# 1. Authentification (sauvegarder le token dans un fichier)
curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token' > /tmp/mywebintel_token.txt

export TOKEN=$(cat /tmp/mywebintel_token.txt)
echo "✅ Token obtenu : ${TOKEN:0:20}..."

# 2. Créer le land
LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Lecornu202535","description":"testprojet gilets jaunes","words":["lecornu"]}' \
  | jq -r '.id // empty')

if [ -z "$LAND_ID" ]; then
  echo "❌ Impossible de créer le land. Vérifiez les logs ou les permissions."
  exit 1
else
  echo "✅ Land créé : LAND_ID=${LAND_ID}"

  # 3. Ajouter la liste d'URLs
  curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/urls" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data "$(jq -Rs '{urls: split("\n") | map(select(length>0))}' MyWebIntelligenceAPI/scripts/data/lecornu.txt)"
fi
```

---

### ✅ **Solution 3 : Session interactive dans le container** (pour tests manuels)

Entrer directement dans le container pour garder le token en mémoire :

```bash
# 1. Entrer dans le container
docker compose exec mywebintelligenceapi bash

# 2. Dans le container, authentification + export
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin@example.com&password=changethispassword" | jq -r '.access_token')

export TOKEN
echo "✅ Token : ${TOKEN:0:20}..."

# 3. Maintenant toutes vos commandes curl peuvent utiliser $TOKEN
# Créer le land
LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Lecornu202540","description":"Test gilets jaunes","words":["lecornu"]}' \
  | jq -r '.id')

echo "✅ Land créé : $LAND_ID"

# Ajouter les URLs
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/urls" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data "$(jq -Rs '{urls: split("\n") | map(select(length>0))}' /app/scripts/data/lecornu.txt)"

# Pour sortir du container :
# exit
```

### 1. Lister les Lands
```bash
curl -X GET "http://localhost:8000/api/v2/lands/?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Détails d'un Land
```bash
curl -X GET "http://localhost:8000/api/v2/lands/${LAND_ID}" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Statistiques d'un Land
```bash
curl -X GET "http://localhost:8000/api/v2/lands/${LAND_ID}/stats" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Lancer un Crawl avec Analyse Media
```bash
curl -X POST "http://localhost:8000/api/v2/lands/7/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"analyze_media": false, "limit": 25, "llm_validation": false}'
```

### 5. Analyser les Médias (ASYNC)
```bash
# Analyser TOUS les médias (toutes profondeurs, toute pertinence)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depth": 0, "minrel": 3.0}'

# Analyser uniquement les médias des URLs de départ (depth=0)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depth": 0, "minrel": 0.0}'

# Analyser avec filtre de pertinence (expressions très pertinentes seulement)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"minrel": 3.0}'

# TEST RAPIDE - Analyser seulement les plus pertinents (recommandé)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"minrel": 3.0}'
```

### 6. Pipeline Readable - Extraction de Contenu (✅ FONCTIONNEL)
```bash
# 🎯 TEST DIRECT CELERY (recommandé pour vérifier que ça marche)
docker-compose exec celery_worker python -c "
from app.tasks.readable_working_task import readable_working_task
result = readable_working_task.delay(land_id=1, job_id=999, limit=2)
print(f'Task ID: {result.id}')
import time; time.sleep(15)
print(f'Result: {result.get()}')"

# 📋 PIPELINE COMPLET (via API - maintenant fonctionnel!)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/readable" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}' \
  --max-time 60

# 🔧 LOGS EN TEMPS RÉEL
docker-compose logs celery_worker --tail=20 -f

# ✅ RÉSULTATS ATTENDUS:
# - Content extraction avec Trafilatura + fallback Archive.org
# - Processing réussi avec logs détaillés
# - Extraction de 3000+ caractères de contenu readable
# - Durée: 15-20 secondes pour 2 URLs
# - Status: completed avec statistiques détaillées

# 📊 STATISTIQUES TYPIQUES:
# - processed: 2 URLs
# - successful: 1-2 selon le contenu disponible  
# - errors: 0-1 (example.com peut échouer)
# - readable_length: 3000+ caractères extraits
# - source: "archive_org" (fallback utilisé)
```

## 🐛 Débuggage Fréquent

### Erreurs SQL
- **Problème:** `should be explicitly declared as text()`
- **Solution:** Ajouter `from sqlalchemy import text` et wrapper les requêtes avec `text()`

### Erreurs de Modèle
- **Problème:** `'Land' object has no attribute 'user_id'`
- **Solution:** Utiliser `owner_id` au lieu de `user_id`

### Timeouts & Freeze
- **Problème:** L'analyse media timeout ou freeze (pas de réponse)
- **Cause:** Traitement lourd des images (PIL/sklearn) sur trop de médias
- **Solutions éprouvées:** 
  - **PRIORITÉ 1:** Utiliser `minrel: 3.0` ou plus pour réduire drastiquement le nombre d'expressions
  - Utiliser `depth: 0` pour analyser seulement les URLs initiales
  - Ajouter `--max-time 120` à curl pour éviter les timeouts infinis
  - Vérifier les logs Celery: `docker logs mywebintelligenceapi_celery_1`
  - Redémarrer le worker: `docker restart mywebintelligenceapi_celery_1`

### Résultats d'Analyse Typiques
- **Expressions totales:** ~1000+
- **Avec minrel=3.0:** ~2-5 expressions (filtrage très efficace)
- **Médias analysés:** 7-50 selon la pertinence
- **Échecs fréquents:** Images 404, SVG non supportés, URLs de tracking
- **Temps de traitement:** 60-120s avec filtrage, timeout sans filtrage

### 🚨 Problème URLs de Médias Incorrectes
- **Problème majeur:** URLs de médias générées incorrectement durant le crawl
- **Causes principales:**
  - Proxies WordPress (i0.wp.com, i1.wp.com) qui ne fonctionnent plus
  - URLs relatives mal résolues
  - Manque de validation d'URLs
  - Attributs alternatifs (srcset, data-src) ignorés
- **Solution:** Nouveau système de nettoyage d'URLs dans MediaProcessor
- **Impact:** Réduction drastique des erreurs 404 lors de l'analyse

### 🚨 PROBLÈME CRITIQUE : Dictionary Starvation - RÉSOLU ✅
- **Cause racine:** Lands créés sans dictionnaires de mots-clés peuplés
- **Symptômes:** 
  - Toutes les expressions ont pertinence = 0
  - Crawler suit tous les liens sans discrimination
  - Explosion du nombre d'expressions (1831 pour 10 URLs)
- **Impact:** Système de pertinence complètement cassé
- **Solution implémentée:** 
  - Auto-population des dictionnaires lors de la création des lands (`crud_land.py`)
  - Service `DictionaryService` pour gérer les dictionnaires
  - Endpoints `/populate-dictionary` et `/dictionary-stats` pour diagnostiquer
- **Code impacté:** `text_processing.expression_relevance()` retourne 0 si dictionnaire vide

### 🔧 Pipeline de Crawl - Logique des Timestamps ✅

**LOGIQUE STRICTE DES DATES (CRITIQUE) :**

1. **`created_at`** → Quand l'expression est **ajoutée en base** (découverte de l'URL)
   - Rempli automatiquement lors de l'INSERT
   - Permet de suivre l'ordre de découverte des URLs

2. **`crawled_at`** → Quand le **contenu HTTP a été récupéré** (fetch HTTP réussi)
   - Rempli après un GET HTTP réussi avec code HTTP valide
   - NULL si l'URL n'a jamais été fetchée

3. **`approved_at`** → Quand le crawler a **traité la réponse** (même si erreur)
   - ⚠️ **CRITÈRE DE SÉLECTION PRINCIPAL** : `approved_at IS NULL` = candidats au crawl
   - Rempli systématiquement après traitement (succès ou échec)
   - Marque l'expression comme "traitée par le crawler"

4. **`readable_at`** → Quand le **contenu readable** a été extrait et enregistré
   - Rempli après extraction réussie (Trafilatura/Mercury)
   - NULL si pas encore de contenu lisible

5. **`updated_at`** → Quand le contenu **readable a été modifié**
   - Mis à jour automatiquement à chaque modification de `readable`
   - Permet de tracker les re-extractions

**HTTP_STATUS - RÈGLE STRICTE :**

- **TOUJOURS** un code HTTP valide (200, 404, 500, etc.)
- **OU** `000` pour erreur inconnue non-HTTP (timeout, DNS, etc.)
- **JAMAIS** NULL après traitement

**WORKFLOW TYPIQUE :**

```text
1. Découverte URL     → created_at = NOW, approved_at = NULL, http_status = NULL
2. Fetch HTTP         → crawled_at = NOW, http_status = 200 (ou 404, etc.)
3. Traitement réponse → approved_at = NOW
4. Extraction readable → readable_at = NOW, updated_at = NOW
5. Modification readable → updated_at = NOW (updated_at > readable_at)
```

**REQUÊTE DE SÉLECTION DES CANDIDATS AU CRAWL :**

```sql
SELECT * FROM expressions
WHERE land_id = ?
  AND approved_at IS NULL  -- ⚠️ Clé principale !
  AND depth <= ?           -- Filtre optionnel de profondeur
ORDER BY depth ASC, created_at ASC
LIMIT ?
```

**Endpoints de diagnostic du pipeline:**
- `GET /api/v2/lands/{id}/pipeline-stats` - Statistiques complètes du pipeline
- `POST /api/v2/lands/{id}/fix-pipeline` - Répare les incohérences de dates

### Container Docker
- **Problème:** Changements de code non pris en compte
- **Solution:** `docker restart mywebintelligenceapi`

### Logs d'Analyse Média
- **IMPORTANT:** L'analyse média est **ASYNCHRONE** (avec Celery)
- **Logs à surveiller:** `docker logs mywebclient-celery_worker-1 -f`
- **Signaux d'activité:** 
  - `sklearn.base.py:1152: ConvergenceWarning` = Clustering couleurs dominantes
  - `PIL/Image.py:975: UserWarning` = Traitement d'images avec transparence
  - Task terminé avec succès dans les logs Celery

## 📊 Données de Test

### Land 36 "giletsjaunes"
- **ID:** 36
- **URLs:** Blogs gilets jaunes (over-blog.com, etc.)
- **Contenu:** Articles sur le mouvement
- **Médias:** ~850 images selon les stats mockées

### Autres Lands
- **37, 38, 39:** Lands de test avec URLs example.com
- **40:** Land basique avec example.org
- **41:** Autre land gilets jaunes

## 🔧 Technologies

### Backend
- **FastAPI** - Framework web moderne avec validation automatique
- **SQLAlchemy 2.0** - ORM async avec modèles déclaratifs
- **PostgreSQL 15+** - Base de données relationnelle
- **Celery** - Tâches asynchrones distribuées 
- **Redis** - Broker Celery et cache

### Analyse Media
- **PIL/Pillow** - Traitement d'images (dimensions, format, EXIF)
- **OpenCV** - Vision par ordinateur avancée
- **scikit-learn** - Machine learning (clustering couleurs dominantes)
- **httpx** - Client HTTP asynchrone pour téléchargement

### Architecture Async
- **AsyncSession** - Connexions DB non-bloquantes
- **async/await** - Gestion asynchrone des tâches lourdes
- **WebSocket** - Suivi temps réel des jobs

### Containerisation
- **Docker Compose** - Orchestration multi-services
- **Services:** API, Celery Worker, PostgreSQL, Redis, Flower (monitoring)
- **Volumes persistants** - Données et logs
- **Network isolation** - Sécurité inter-services

### Installation & Configuration
```bash
# Installation complète avec Docker
git clone <repository-url>
cd MyWebIntelligenceAPI
cp .env.example .env           # Configurer DATABASE_URL, REDIS_URL, SECRET_KEY
docker-compose up -d           # Lancer tous les services
docker-compose exec api alembic upgrade head    # Migrations DB

# Accès services
# API: http://localhost:8000
# Docs: http://localhost:8000/docs  
# Flower: http://localhost:5555
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3001
```

### Variables d'Environnement Critiques
```bash
# Base de données
DATABASE_URL=postgresql://user:pass@postgres:5432/mywebintelligence

# Cache/Queue  
REDIS_URL=redis://redis:6379

# Sécurité
SECRET_KEY=<générer-clé-aléatoire-64-chars>
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=changethispassword

# API Externe (optionnel)
OPENROUTER_API_KEY=<pour-analyse-sémantique>
```

---

## 🚀 TEST RAPIDE COMPLET - SCRIPT AUTOMATISÉ

### ✅ Script de Test Crawl SYNC (RECOMMANDÉ - 1 minute)

**Localisation**: `MyWebIntelligenceAPI/tests/test-crawl-simple.sh`

Ce script teste le **crawl synchrone** des 5 URLs Lecornu **sans les fonctionnalités async bugguées**.

```bash
#!/bin/bash
# Test SIMPLE crawl sync - 5 URLs Lecornu
# Sans media analysis async ni readable pipeline

get_fresh_token() {
    TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)
    if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
        echo "❌ Échec authentification"
        exit 1
    fi
}

echo "🔧 1/5 - Vérification serveur..."
if ! curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null | grep -q "200"; then
    echo "❌ Serveur API non accessible"
    exit 1
fi

echo "🔑 2/5 - Authentification..."
get_fresh_token
echo "✅ Token: ${TOKEN:0:20}..."

echo "🏗️ 3/5 - Création land..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LECORNU_FILE="${SCRIPT_DIR}/../scripts/data/lecornu.txt"

if [ ! -f "$LECORNU_FILE" ]; then
    echo "❌ Fichier lecornu.txt non trouvé"
    exit 1
fi

TEMP_JSON=$(mktemp)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cat > "$TEMP_JSON" <<EOF
{
  "name": "test_lecornu_${TIMESTAMP}",
  "description": "Test crawl sync Lecornu - ${TIMESTAMP}",
  "start_urls": [
EOF

head -n 5 "$LECORNU_FILE" | while IFS= read -r url; do
    if [ -n "$url" ]; then
        echo "    \"$url\"," >> "$TEMP_JSON"
    fi
done

sed -i '' '$ s/,$//' "$TEMP_JSON" 2>/dev/null || sed -i '$ s/,$//' "$TEMP_JSON"
cat >> "$TEMP_JSON" <<EOF

  ]
}
EOF

LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @"$TEMP_JSON" | jq -r '.id')
rm -f "$TEMP_JSON"

if [ "$LAND_ID" = "null" ] || [ -z "$LAND_ID" ]; then
    echo "❌ Échec création land"
    exit 1
fi
echo "✅ Land créé: LAND_ID=$LAND_ID"

echo "📝 4/5 - Ajout mots-clés..."
get_fresh_token
curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/terms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terms": ["lecornu", "sebastien", "macron", "matignon"]}' > /dev/null

echo "🕷️ 5/5 - Lancement crawl SYNC..."
get_fresh_token
CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}' --max-time 120)

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Échec crawl: $CRAWL_RESULT"
    exit 1
fi
echo "✅ Crawl lancé: JOB_ID=$JOB_ID"

echo ""
echo "⏳ Attente fin du crawl (60s)..."
sleep 60

echo ""
echo "📊 Vérification résultats..."
get_fresh_token
STATS=$(curl -s "http://localhost:8000/api/v2/lands/${LAND_ID}/stats" \
  -H "Authorization: Bearer $TOKEN")

echo ""
echo "🎯 RÉSULTATS:"
echo "$STATS" | jq '{
  land_id: .land_id,
  land_name: .land_name,
  total_expressions: .total_expressions,
  approved_expressions: .approved_expressions,
  total_links: .total_links,
  total_media: .total_media
}'

echo ""
echo "✅ Test terminé!"
echo "Land ID: $LAND_ID"
echo "Job ID: $JOB_ID"
```

**Résultats Attendus:**
```
✅ URLs Processed: 5
✅ Errors: 0
✅ Duration: ~50 seconds
✅ Content extrait: ~50,000 caractères
```

### Utilisation
```bash
# Depuis la racine du projet
./MyWebIntelligenceAPI/tests/test-crawl-simple.sh

# Vérifier les logs Celery
docker logs mywebclient-celery_worker-1 --tail=50 | grep "CRAWL COMPLETED" -A 5
```

---

### ⚠️ Script Complet avec Async (DÉPRÉCIÉ - contient des bugs)

Le script original avec analyse média async et pipeline readable contient des bugs asyncio et n'est **pas recommandé** pour le moment.

**Problèmes connus:**
- ❌ `RuntimeError: Task got Future attached to a different loop` dans media analysis async
- ❌ Pipeline Readable utilise des URLs de test hardcodées (example.com, httpbin.org)
- ❌ Erreurs `InterfaceError: another operation is in progress` dans les batch tasks

**Script disponible**: `MyWebIntelligenceAPI/tests/test-crawl.sh` (pour référence uniquement)

```

## 🐛 CORRECTIONS CRITIQUES AGENTS - Leçons Apprises

### ❌ **Erreurs Fréquentes à Éviter**

#### 1. **Bug `metadata_lang` non défini** (RÉSOLU - 2025-10-17)
- **Problème** : `name 'metadata_lang' is not defined` lors du crawl
- **Cause** : Variable renommée de `metadata_lang` → `final_lang` mais usage ancien non mis à jour
- **Fichier** : `/app/app/core/crawler_engine_sync.py:251,256`
- **Fix** : Remplacer `metadata_lang` par `final_lang` dans l'appel à `expression_relevance()`
- **Impact** : 100% des URLs échouaient avant le fix

**Code corrigé:**
```python
# AVANT (buggué)
relevance = asyncio.run(
    text_processing.expression_relevance(land_dict, temp_expr, metadata_lang or "fr")
)

# APRÈS (corrigé)
relevance = asyncio.run(
    text_processing.expression_relevance(land_dict, temp_expr, final_lang or "fr")
)
```

#### 2. **Bug job_id** (RÉSOLU)
- **Problème** : `job_id should be a valid integer [input_value=None]`
- **Cause** : `/app/api/v2/endpoints/lands_v2.py:582` cherchait `"id"` au lieu de `"job_id"`
- **Fix** : `job_payload.get("id")` → `job_payload.get("job_id")`

#### 3. **Tokens JWT Expirent Rapidement** ⚠️
- **Problème** : `Could not validate credentials` après quelques minutes
- **Solution** : Fonction `get_fresh_token()` avant chaque appel critique
- **Astuce** : Renouveler systématiquement avant crawl/analyse

#### 4. **Endpoint `/urls` Bugué** ⚠️
- **Problème** : Impossible d'ajouter URLs après création land
- **Solution** : URLs directement dans `start_urls` lors de création
- **Éviter** : `POST /api/v2/lands/{id}/urls`

#### 5. **Bugs Asyncio dans Media Analysis & Readable** ⚠️ **NON RÉSOLU**
- **Problème** : `RuntimeError: Task got Future attached to a different loop`
- **Fichiers affectés** :
  - `/app/app/tasks/media_analysis_task.py:51,237`
  - `/app/app/tasks/readable_working_task.py`
- **Erreurs associées** : `InterfaceError: another operation is in progress`
- **Impact** : L'analyse média async et le pipeline readable sont instables
- **Workaround** : Utiliser uniquement le crawl sync sans ces fonctionnalités
- **Status** : À corriger - problème de gestion des event loops asyncio dans Celery

#### 6. **Mots-clés Obligatoires** ⚠️
- **Problème** : Sans mots-clés, `relevance=0` pour toutes expressions
- **Solution** : Toujours ajouter termes via `/terms` après création land
- **Impact** : Détermine filtrage pertinence dans analyse média

#### 7. **DEPTH = Niveau de Crawl** 🔥 **CRITIQUE**
- **`depth: 0`** = Analyser médias des **start_urls** seulement
- **`depth: 1`** = Analyser médias des **liens directs** depuis start_urls
- **`depth: 2`** = Analyser médias des **liens de liens** (2e niveau)
- **`depth: 999`** = Analyser **TOUS** les médias sans limite de profondeur
- **⚠️ BUG ENDPOINT** : L'endpoint `/media-analysis-async` ignore le paramètre `depth` et force toujours `depth: 999`

### 🎯 **Workflow Anti-Erreurs (CRAWL SYNC)**

```bash
1. ✅ Créer land avec start_urls intégrées (pas d'endpoint /urls)
2. ✅ Ajouter termes OBLIGATOIREMENT via /terms
3. ✅ Renouveler token avant chaque action
4. ✅ Lancer crawl avec POST /crawl (limit, depth optionnels)
5. ✅ Attendre suffisamment (60s pour 5 URLs)
6. ✅ Vérifier logs Celery: docker logs mywebclient-celery_worker-1 --tail=50
7. ✅ Utiliser le script de test: ./MyWebIntelligenceAPI/tests/test-crawl-simple.sh
```

**Résultats attendus (5 URLs Lecornu):**
- Duration: ~50 secondes
- URLs Processed: 5
- Errors: 0
- Content extrait: ~50,000 caractères
- Liens découverts: ~1,200 liens
- Médias extraits: ~200-250 médias

---

## 🧪 Tests Manuels Détaillés

### Test 1 : Authentification
```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changeme" | jq -r .access_token)
echo "Token: $TOKEN"
```

### Test 2 : Création Land Complète
```bash
# Land avec URLs intégrées (évite l'endpoint /urls bugué)
LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_fonctionnel", 
    "description": "Test crawl fonctionnel",
    "start_urls": ["https://httpbin.org/html", "https://example.com"],
    "words": ["test", "example"]
  }' | jq -r '.id')
echo "Land créé: $LAND_ID"
```

### Test 3 : Ajout Mots-clés (Obligatoire pour pertinence)
```bash
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/terms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terms": ["html", "test", "example", "title"]}'
```

### Test 4 : Crawl Simple
```bash
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 3}' --max-time 120
```

### Test 5 : Analyse Média (ASYNC)
```bash
# Analyse rapide (expressions très pertinentes seulement)
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depth": 0, "minrel": 3.0}'

# Analyse complète (toutes expressions)  
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"minrel": 0.0}'
```

## 🧭 Scénario d'Usage Complet

### Script de Test Automatisé
Le script `scripts/land_scenario.py` reproduit l'ancien workflow CLI :

```bash
python scripts/land_scenario.py \
  --land-name "MyResearchTopic" \
  --terms "keyword1,keyword2" \
  --urls "https://example.org,https://example.com" \
  --crawl-limit 25
```

**Variables d'environnement:**
- `MYWI_BASE_URL` (défaut: `http://localhost:8000`)  
- `MYWI_USERNAME` / `MYWI_PASSWORD` (défaut: `admin@example.com` / `changeme`)

### Migration depuis SQLite
```bash
# Migration d'une base SQLite existante
python scripts/migrate_sqlite_to_postgres.py --source /path/to/mwi.db
```
## 📚 Documentation de référence

- [INDEX_DOCUMENTATION.md](INDEX_DOCUMENTATION.md) — carte et statuts des documents actifs
- [QUALITY_SCORE_GUIDE.md](.claude/docs/QUALITY_SCORE_GUIDE.md) — guide complet Quality Score System ✨ NOUVEAU
- [RÉSUMÉ_CORRECTIONS_17OCT2025.md](RÉSUMÉ_CORRECTIONS_17OCT2025.md) — synthèse produit & plan d'actions
- [TRANSFERT_API_CRAWL.md](TRANSFERT_API_CRAWL.md) — audit complet et cartographie Legacy → API
- [CORRECTIONS_PARITÉ_LEGACY.md](CORRECTIONS_PARITÉ_LEGACY.md) — corrections techniques (métadonnées, HTML, stockage)
- [Transfert_readable.md](Transfert_readable.md) — suivi de la parité du pipeline readable
- [CHAÎNE_FALLBACKS.md](CHAÎNE_FALLBACKS.md) — schéma détaillé des fallbacks d'extraction
- [METADATA_FIXES.md](METADATA_FIXES.md) — corrections métadonnées (journal complet)
- [CORRECTIONS_FINALES.md](CORRECTIONS_FINALES.md) — synthèse + plan de tests métadonnées
- [compare_addterms_analysis.md](compare_addterms_analysis.md) — état des lieux AddTerms et recommandations
- [Architecture.md](Architecture.md) — structure du dépôt et responsabilités par module
- [GEMINI.md](GEMINI.md) — guide opérateur/API (vue complémentaire)

**Dernière mise à jour**: 18 octobre 2025
**Version**: 1.2 (ajout Quality Score System)
**Mainteneur**: Équipe MyWebIntelligence
