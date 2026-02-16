# Guide Complet : Validation LLM (OpenRouter)

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Coûts et estimation](#coûts-et-estimation)
5. [Troubleshooting](#troubleshooting)
6. [Architecture technique](#architecture-technique)

---

## 🎯 Vue d'ensemble

La **validation LLM** permet d'utiliser un modèle de langage (via OpenRouter) pour valider la pertinence des expressions crawlées par rapport au sujet de recherche du land.

### Fonctionnement

1. **Après crawl** : Pour chaque expression avec `relevance > 0` (pertinent selon mots-clés)
2. **Prompt LLM** : Demande au modèle si l'expression est pertinente pour le projet
3. **Réponse** : Le LLM répond "oui" ou "non"
4. **Action** :
   - **"oui"** → Expression validée (`valid_llm='oui'`)
   - **"non"** → `relevance=0`, `valid_llm='non'` (expression rejetée)

### Avantages

- ✅ Réduit les faux positifs (expressions matchant les mots-clés mais hors-sujet)
- ✅ Améliore la précision du corpus
- ✅ Validé par un modèle de pointe (Claude 3.5 Sonnet par défaut)

### Limitations

- ❌ Coût par validation (~0.007$ avec Claude 3.5 Sonnet)
- ❌ Latence (~2-3s par expression)
- ❌ Rate limiting (~60 req/min sur OpenRouter)

---

## 🔧 Configuration

### Étape 1 : Obtenir une clé API OpenRouter

Voir le guide détaillé : [.claude/tasks/OPENROUTER_SETUP.md](.claude/tasks/OPENROUTER_SETUP.md)

**Résumé rapide :**
1. Créer un compte sur https://openrouter.ai/
2. Obtenir une clé API (commence par `sk-or-v1-...`)
3. Ajouter des crédits si nécessaire (5-10$ offerts à l'inscription)

### Étape 2 : Configuration MyWebIntelligence

Ajouter dans votre fichier `.env` :

```bash
# OpenRouter LLM Validation
OPENROUTER_ENABLED=True
OPENROUTER_API_KEY=sk-or-v1-your-actual-api-key-here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_TIMEOUT=30
OPENROUTER_MAX_RETRIES=3
```

### Étape 3 : Redémarrer les services

```bash
docker compose restart api celery_worker
```

### Vérification

```bash
# Vérifier que la config est chargée
docker compose exec api python -c "from app.config import settings; print(f'OPENROUTER_ENABLED={settings.OPENROUTER_ENABLED}')"
```

---

## 💻 Usage

### Option 1 : Validation pendant le crawl

**Endpoint :** `POST /api/v2/lands/{id}/crawl`

```bash
# 1. Authentification
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changeme" | jq -r .access_token)

# 2. Crawl avec validation LLM
curl -X POST "http://localhost:8000/api/v2/lands/36/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 10,
    "enable_llm": true
  }'
```

**Résultat :** Les champs `valid_llm` et `valid_model` sont remplis automatiquement pendant le crawl.

### Option 2 : Reprocessing batch (expressions existantes)

#### Via script CLI

```bash
# Reprocessing d'un land spécifique
docker exec mywebintelligenceapi python -m app.scripts.reprocess_llm_validation --land-id 36

# Avec limite
docker exec mywebintelligenceapi python -m app.scripts.reprocess_llm_validation --land-id 36 --limit 50

# Dry-run (simulation)
docker exec mywebintelligenceapi python -m app.scripts.reprocess_llm_validation --land-id 36 --dry-run

# Force (revalider même si valid_llm existe)
docker exec mywebintelligenceapi python -m app.scripts.reprocess_llm_validation --land-id 36 --force
```

#### Via API

**Endpoint :** `POST /api/v2/lands/{id}/llm-validate`

```bash
# Reprocessing via API
curl -X POST "http://localhost:8000/api/v2/lands/36/llm-validate?limit=50&force=false" \
  -H "Authorization: Bearer $TOKEN"
```

**Réponse :**
```json
{
  "land_id": 36,
  "land_name": "giletsjaunes",
  "stats": {
    "total_candidates": 50,
    "processed": 50,
    "validated": 42,
    "rejected": 8,
    "errors": 0,
    "api_calls": 50,
    "total_tokens": 12500
  },
  "message": "LLM validation completed: 42 validated, 8 rejected"
}
```

---

## 💰 Coûts et estimation

### Modèles recommandés

| Modèle | Coût / 1K tokens | Coût par validation | Recommandation |
|--------|------------------|---------------------|----------------|
| `anthropic/claude-3.5-sonnet` | ~$0.015 | ~$0.007 | ✅ Recommandé (précis) |
| `anthropic/claude-3-haiku` | ~$0.003 | ~$0.0015 | 💰 Économique |
| `openai/gpt-4o-mini` | ~$0.002 | ~$0.001 | 💰 Très économique |

### Estimation mensuelle

**Hypothèse :** 1 validation = ~500 tokens (prompt) + 2 tokens (réponse) = 502 tokens

| Expressions/jour | Coût/jour (Claude 3.5) | Coût/mois |
|------------------|------------------------|-----------|
| 100 | $0.70 | $21 |
| 500 | $3.50 | $105 |
| 1000 | $7.00 | $210 |

### Optimisations

1. **Utiliser Claude Haiku** : Réduction de 70% des coûts
2. **Filtrer par relevance** : Valider seulement `relevance >= 2.0`
3. **Valider après readable** : Contenu plus riche = meilleure validation

---

## 🐛 Troubleshooting

### Erreur 401 "Unauthorized"

**Symptôme :**
```
Failed to validate: OpenRouter API error 401: Unauthorized
```

**Solution :**
1. Vérifier que `OPENROUTER_API_KEY` est correct
2. S'assurer que la clé commence par `sk-or-v1-`
3. Vérifier que `OPENROUTER_ENABLED=True`

### Erreur 429 "Rate Limited"

**Symptôme :**
```
Rate limit hit, waiting Xs before retry
```

**Explication :** OpenRouter limite à ~60 requêtes/minute

**Solution :**
- Le système retry automatiquement avec backoff exponentiel
- Réduire `batch_size` si nécessaire
- Attendre quelques minutes entre les runs

### Erreur 402 "Insufficient Credits"

**Symptôme :**
```
OpenRouter API error 402: Insufficient credits
```

**Solution :**
1. Ajouter des crédits sur https://openrouter.ai/account
2. Vérifier le solde : Account → Billing

### Timeouts

**Symptôme :**
```
Timeout (attempt 1) ... (attempt 2) ... (attempt 3)
OpenRouter API failed after 3 attempts
```

**Solution :**
1. Augmenter `OPENROUTER_TIMEOUT` dans `.env` (ex: 60)
2. Vérifier la connectivité réseau
3. Certains modèles sont plus lents → changer de modèle

### Validation échoue mais crawl continue

**Comportement normal :** La validation LLM est **non-bloquante**

Si la validation échoue :
- ✅ Le crawl continue normalement
- ✅ L'expression est sauvegardée avec sa relevance calculée
- ❌ Les champs `valid_llm` et `valid_model` restent NULL
- ⚠️ Un log ERROR est émis

**Vérification :**
```bash
# Logs de validation
docker logs mywebclient-celery_worker-1 --tail=50 | grep -i "llm"
```

---

## 🏗️ Architecture technique

### Composants

```
┌────────────────────────────────────────────────────────────┐
│  Endpoint API                                               │
│  POST /api/v2/lands/{id}/crawl?enable_llm=true            │
│  POST /api/v2/lands/{id}/llm-validate                     │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│  Celery Task (crawling_task.py)                           │
│  - Récupère flag enable_llm                               │
│  - Passe à SyncCrawlerEngine                              │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│  SyncCrawlerEngine (crawler_engine.py)                    │
│  - Calcule relevance (mots-clés)                          │
│  - Si enable_llm ET relevance > 0 :                       │
│    └─ Appelle LLMValidationService                        │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│  LLMValidationService (llm_validation_service.py)         │
│  - validate_expression_relevance_sync()                   │
│  - Construit le prompt                                    │
│  - Appelle OpenRouter API                                 │
│  - Parse "oui"/"non"                                      │
│  - Retourne ValidationResult                              │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│  OpenRouter API                                            │
│  https://openrouter.ai/api/v1/chat/completions            │
│  - Modèle: anthropic/claude-3.5-sonnet (défaut)          │
│  - Timeout: 30s (configurable)                            │
│  - Retries: 3 (avec backoff)                              │
└────────────────────────────────────────────────────────────┘
```

### Fichiers impactés

| Fichier | Modification | Description |
|---------|-------------|-------------|
| [`llm_validation_service.py`](MyWebIntelligenceAPI/app/services/llm_validation_service.py) | ✅ Ajout méthode sync | Wrapper sync pour contexts non-async |
| [`crawler_engine.py`](MyWebIntelligenceAPI/app/core/crawler_engine.py) | ✅ Intégration LLM | Validation après calcul relevance |
| [`crawling_task.py`](MyWebIntelligenceAPI/app/tasks/crawling_task.py) | ✅ Propagation flag | Récupère `enable_llm` des params |
| [`reprocess_llm_validation.py`](MyWebIntelligenceAPI/app/scripts/reprocess_llm_validation.py) | ✅ Nouveau script | Batch reprocessing |
| [`lands_v2.py`](MyWebIntelligenceAPI/app/api/v2/endpoints/lands_v2.py) | ✅ Nouveau endpoint | API de reprocessing |

### Champs de base de données

```sql
-- Table: expressions
valid_llm VARCHAR(3)      -- "oui" ou "non"
valid_model VARCHAR(100)  -- Ex: "anthropic/claude-3.5-sonnet"
relevance FLOAT           -- Mis à 0 si valid_llm='non'
```

### Logique de décision

```python
# Pendant le crawl
if enable_llm and OPENROUTER_ENABLED and relevance > 0:
    validation_result = llm_service.validate_expression_relevance_sync(expr, land)

    expr.valid_llm = 'oui' if validation_result.is_relevant else 'non'
    expr.valid_model = validation_result.model_used

    if not validation_result.is_relevant:
        expr.relevance = 0  # Rejeter l'expression
```

---

## 📊 Monitoring

### Logs à surveiller

```bash
# Logs de validation pendant crawl
docker logs mywebclient-celery_worker-1 --tail=50 -f | grep -i "llm"

# Logs typiques
# ✅ Succès
[INFO] [LLM] Expression 123 validated as relevant by anthropic/claude-3.5-sonnet

# ❌ Rejet
[INFO] [LLM] Expression 456 marked as non-relevant by anthropic/claude-3.5-sonnet

# ⚠️ Erreur
[ERROR] [LLM] Validation failed for https://example.com: Rate limit hit
```

### Statistiques de validation

```bash
# Vérifier les résultats dans la DB
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
SELECT
  valid_llm,
  COUNT(*) as count,
  ROUND(AVG(relevance)::numeric, 2) as avg_relevance
FROM expressions
WHERE land_id = 36 AND valid_llm IS NOT NULL
GROUP BY valid_llm;
"
```

**Résultat exemple :**
```
 valid_llm | count | avg_relevance
-----------+-------+---------------
 oui       |   142 |          3.45
 non       |    23 |          0.00
```

### Métriques API

Via l'endpoint de reprocessing, vous obtenez :
```json
{
  "api_calls": 165,
  "total_tokens": 41250,
  "validated": 142,
  "rejected": 23,
  "estimated_cost": 0.61875
}
```

---

## 🧪 Tests

### Test rapide de configuration

```bash
# Test avec curl direct sur OpenRouter
curl -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "HTTP-Referer: https://mywebintelligence.io" \
  -H "X-Title: MyWebIntelligence API" \
  -d '{
    "model": "anthropic/claude-3.5-sonnet",
    "messages": [{"role": "user", "content": "Réponds juste par oui ou non : Est-ce que Paris est en France ?"}],
    "max_tokens": 10
  }'
```

### Test avec MyWebIntelligence

```bash
# 1. Créer un land de test
LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_llm",
    "description": "Test validation LLM",
    "start_urls": ["https://example.com"],
    "words": ["test"]
  }' | jq -r '.id')

# 2. Crawl avec LLM
curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"limit": 3, "enable_llm": true}'

# 3. Vérifier les résultats
curl "http://localhost:8000/api/v2/lands/${LAND_ID}/stats" \
  -H "Authorization: Bearer $TOKEN" | jq '.validation_stats'
```

---

## 📖 Ressources complémentaires

- **Configuration OpenRouter** : [.claude/tasks/OPENROUTER_SETUP.md](.claude/tasks/OPENROUTER_SETUP.md)
- **Playbook principal** : [.claude/AGENTS.md](.claude/AGENTS.md)
- **Tests unitaires** : [tests/unit/test_llm_validation_service.py](MyWebIntelligenceAPI/tests/unit/test_llm_validation_service.py)
- **Site OpenRouter** : https://openrouter.ai/
- **Documentation API** : https://openrouter.ai/docs
- **Modèles disponibles** : https://openrouter.ai/models

---

**Dernière mise à jour** : 19 octobre 2025
**Version** : 1.0
**Mainteneur** : Équipe MyWebIntelligence
