# Quality Score System - Guide Complet

## 📊 Vue d'ensemble

Le **Quality Score** est un indicateur de qualité pour chaque expression (page web crawlée), calculé automatiquement à partir de métadonnées existantes. Score entre **0.0** (très faible) et **1.0** (excellent).

### Caractéristiques
- ✅ **100% déterministe** : Pas de ML/LLM, reproductible
- ✅ **Gratuit** : Pas d'appels API externes
- ✅ **Rapide** : <10ms par expression
- ✅ **Transparent** : Heuristiques documentées
- ✅ **Configurable** : Poids ajustables via settings

---

## 🏗️ Architecture

### Composants

```
┌─────────────────────────────────────────────────────────────┐
│                    Quality Score System                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Crawler    │───▶│    Quality   │───▶│     DB       │  │
│  │  Engine      │    │    Scorer    │    │  Expression  │  │
│  │ (Async/Sync) │    │   Service    │    │quality_score │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Reprocess   │───▶│   Settings   │    │     API      │  │
│  │   Script     │    │  (Weights)   │    │   Filters    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Fichiers Clés

| Fichier | Rôle |
|---------|------|
| `app/services/quality_scorer.py` | Service de calcul (5 blocs heuristiques) |
| `app/core/crawler_engine.py` | Intégration dans le crawler (moteur unique V2) |
| `app/scripts/reprocess_quality_scores.py` | Script de recalcul pour historique |
| `app/config.py` | Configuration des poids |
| `tests/data/quality_truth_table.json` | 20 cas de test de validation |
| `tests/unit/test_quality_scorer.py` | 33 tests unitaires |

---

## 🧮 Les 5 Blocs Heuristiques

Le quality_score est calculé par agrégation pondérée de 5 blocs :

```
Quality Score = Σ (Bloc_i × Poids_i)
```

### 1. **Access** (30%) 🚪
**Critères** : Accessibilité de la page

| Critère | Score | Flags |
|---------|-------|-------|
| HTTP 2xx | 1.0 | - |
| HTTP 3xx (redirect) | 0.5 | `redirect` |
| HTTP 4xx/5xx | **0.0 (bloquant)** | `http_error` |
| Content-Type PDF | **0.0 (bloquant)** | `non_html_pdf` |
| Pas de crawled_at | **0.0 (bloquant)** | `not_crawled` |

**Philosophie** : Si la page n'est pas accessible, quality = 0 (bloquant).

### 2. **Structure** (15%) 🏗️
**Critères** : Qualité des métadonnées HTML/SEO

| Élément | Contribution | Flags si absent |
|---------|--------------|-----------------|
| Title présent | 40% (0.4) | `no_title` |
| Description >20 chars | 30% (0.3) | `no_description` |
| Keywords présents | 15% (0.15) | `no_keywords` |
| Canonical URL | 15% (0.15) | `no_canonical` |

**Score max** : 1.0 si tous présents

### 3. **Richness** (25%) 📝
**Critères** : Richesse du contenu textuel

#### A. Word Count (50% du bloc richness)
Courbe gaussienne centrée sur **1500 mots** :

| Word Count | Score | Flags |
|------------|-------|-------|
| <80 mots | 0.1 | `very_short_content` |
| 80-150 | 0.3 | `short_content` |
| 150-5000 | 0.8-1.0 (optimal autour de 1500) | - |
| >5000 | 0.5-0.8 (décroit doucement) | `very_long_content` si >10k |

#### B. Ratio Word Count / Content Length (30% du bloc richness)
Détecte le "boilerplate" (HTML lourd vs peu de texte) :

| Ratio | Score | Flags |
|-------|-------|-------|
| <0.05 | 0.2 | `poor_text_ratio` |
| 0.05-0.1 | 0.5 | `low_text_ratio` |
| **0.1-0.3** | **1.0** (optimal) | - |
| >0.3 | 0.9 | - |

#### C. Reading Time (20% du bloc richness)

| Reading Time | Score | Flags |
|--------------|-------|-------|
| <15s | 0.2 | `very_short_reading` |
| 15-30s | 0.5 | `short_reading` |
| **30s-15min** | **1.0** (optimal) | - |
| 15-25min | 0.8 | - |
| >25min | 0.3 | `very_long_reading` |

### 4. **Coherence** (20%) 🎯
**Critères** : Cohérence avec le land et logique métier

#### A. Langue (40% du bloc coherence)
| Match | Score | Flags |
|-------|-------|-------|
| Langue dans land.lang | 1.0 | - |
| Langue hors land.lang | 0.0 | `wrong_language` |
| Pas de langue détectée | 0.5 (neutre) | `no_language` |

#### B. Relevance (40% du bloc coherence)
Pertinence thématique (mot-clés du land) :
```
Score = min(relevance / 5.0, 1.0)
```
- relevance <0.5 → flag `low_relevance`

#### C. Fraîcheur (20% du bloc coherence)
| Âge du contenu | Score | Flags |
|----------------|-------|-------|
| <1 an | 1.0 | - |
| 1-2 ans | 0.9 | - |
| 2-5 ans | 0.7 | - |
| >5 ans | 0.5 | `old_content` |

### 5. **Integrity** (10%) ✅
**Critères** : Intégrité du pipeline de traitement

| Critère | Contribution | Flags |
|---------|--------------|-------|
| validllm="oui" | 40% (0.4) | `llm_rejected` si "non" |
| Readable content >100 chars | 40% (0.4) | `no_readable` |
| Pipeline complet (approved_at) | 20% (0.2) | `not_approved` |

---

## 📊 Catégories de Qualité

| Score | Catégorie | Interprétation |
|-------|-----------|----------------|
| 0.8-1.0 | **Excellent** ⭐ | Contenu riche, complet, bien structuré |
| 0.6-0.8 | **Bon** ✅ | Contenu acceptable, quelques améliorations possibles |
| 0.4-0.6 | **Moyen** ⚠️ | Contenu limité ou mal structuré |
| 0.2-0.4 | **Faible** ❌ | Contenu très pauvre ou problèmes majeurs |
| 0.0-0.2 | **Très faible** ❌❌ | Erreur d'accès ou contenu quasi-inexistant |

---

## 🚀 Utilisation

### 1. Activation/Désactivation

Dans `.env` ou `app/config.py` :
```python
ENABLE_QUALITY_SCORING=true  # Master switch
```

### 2. Configuration des Poids

Ajuster les pondérations dans `app/config.py` :
```python
QUALITY_WEIGHT_ACCESS=0.30      # Accès (30%)
QUALITY_WEIGHT_STRUCTURE=0.15   # Structure (15%)
QUALITY_WEIGHT_RICHNESS=0.25    # Richesse (25%)
QUALITY_WEIGHT_COHERENCE=0.20   # Cohérence (20%)
QUALITY_WEIGHT_INTEGRITY=0.10   # Intégrité (10%)
```

**Important** : La somme doit faire 1.0

### 3. Crawl Automatique

Le quality_score est calculé automatiquement lors du crawl :

```bash
# Via API
curl -X POST "http://localhost:8000/api/v2/lands/15/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"limit": 100}'

# Via Celery (asynchrone)
from app.core.celery_app import crawl_land_task
crawl_land_task.delay(land_id=15, limit=100)
```

Le champ `quality_score` est automatiquement rempli dans la DB.

### 4. Reprocessing Historique

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

# Batch processing (commit toutes les N expressions)
docker exec mywebintelligenceapi python -m app.scripts.reprocess_quality_scores --batch-size 50
```

**Exemple de sortie** :
```
============================================================
REPROCESSING SUMMARY
============================================================
Total candidates:     70
Processed:            70
Updated:              70
Skipped:              0
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

---

## 🔍 Requêtes SQL Utiles

### Statistiques Globales
```sql
SELECT
  COUNT(*) as total,
  COUNT(quality_score) as with_quality,
  ROUND(AVG(quality_score)::numeric, 3) as avg_score,
  ROUND(MIN(quality_score)::numeric, 3) as min_score,
  ROUND(MAX(quality_score)::numeric, 3) as max_score
FROM expressions;
```

### Distribution par Catégorie
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

### Top 10 Meilleures Expressions
```sql
SELECT
  id,
  url,
  quality_score,
  word_count,
  relevance,
  language
FROM expressions
WHERE quality_score IS NOT NULL
ORDER BY quality_score DESC
LIMIT 10;
```

### Expressions avec Score Faible
```sql
SELECT
  id,
  url,
  quality_score,
  http_status,
  word_count
FROM expressions
WHERE quality_score < 0.4
ORDER BY quality_score ASC
LIMIT 20;
```

---

## 🧪 Tests

### Tests Unitaires
```bash
# Tous les tests (33 tests)
docker exec mywebintelligenceapi pytest tests/unit/test_quality_scorer.py -v

# Tests par bloc
docker exec mywebintelligenceapi pytest tests/unit/test_quality_scorer.py::TestAccessBlock -v
docker exec mywebintelligenceapi pytest tests/unit/test_quality_scorer.py::TestRichnessBlock -v

# Tests de la truth table
docker exec mywebintelligenceapi pytest tests/unit/test_quality_scorer.py::TestTruthTable -v
```

### Test d'Intégration
```bash
# Test crawl complet avec quality scoring
bash tests/integration/test_quality_integration.sh
```

### Truth Table

La truth table contient **20 cas de test** validés dans `tests/data/quality_truth_table.json` :
1. Article optimal 1500 mots → Excellent (0.85-1.0)
2. Erreur 404 → Très faible (0.0)
3. Page courte 50 mots → Moyen (0.3-0.6)
4. Langue incorrecte → Moyen (0.4-0.6)
5. PDF → Très faible (0.0)
6. Redirect 302 → Très faible (0.0-0.3)
7. Erreur serveur 500 → Très faible (0.0)
8. Contenu moyen 800 mots → Bon (0.6-0.8)
9. Ratio texte/HTML faible → Faible (0.25-0.45)
10. Contenu très long 8000 mots → Bon (0.7-0.9)
... (10 autres cas)

---

## 📈 Monitoring

### Métriques à Surveiller

1. **Taux de couverture** : % d'expressions avec quality_score
2. **Distribution** : Répartition par catégorie
3. **Score moyen** par land
4. **Corrélation** avec relevance/word_count

### Alertes Recommandées

- Score moyen <0.5 sur un land → Problème de crawl
- >50% expressions "Très faible" → Revue des start_urls
- quality_score NULL sur expressions récentes → Bug pipeline

---

## 🎯 Tuning des Poids

### Méthodologie

1. **Identifier l'objectif** : Favoriser contenu long ? Structure ? Relevance ?
2. **Ajuster les poids** dans `app/config.py`
3. **Tester sur truth table** :
   ```bash
   docker exec mywebintelligenceapi pytest tests/unit/test_quality_scorer.py::TestTruthTable -v
   ```
4. **Reprocess historique** avec nouveaux poids :
   ```bash
   docker exec mywebintelligenceapi python -m app.scripts.reprocess_quality_scores --force
   ```
5. **Analyser la distribution** et itérer

### Exemples de Tuning

**Favoriser contenu long et riche** :
```python
QUALITY_WEIGHT_ACCESS=0.25      # ↓
QUALITY_WEIGHT_STRUCTURE=0.10   # ↓
QUALITY_WEIGHT_RICHNESS=0.40    # ↑↑
QUALITY_WEIGHT_COHERENCE=0.15   # ↓
QUALITY_WEIGHT_INTEGRITY=0.10   # =
```

**Favoriser pertinence thématique** :
```python
QUALITY_WEIGHT_ACCESS=0.25      # ↓
QUALITY_WEIGHT_STRUCTURE=0.10   # ↓
QUALITY_WEIGHT_RICHNESS=0.20    # ↓
QUALITY_WEIGHT_COHERENCE=0.35   # ↑↑
QUALITY_WEIGHT_INTEGRITY=0.10   # =
```

**Pénaliser fortement les erreurs** :
```python
QUALITY_WEIGHT_ACCESS=0.50      # ↑↑
QUALITY_WEIGHT_STRUCTURE=0.15   # =
QUALITY_WEIGHT_RICHNESS=0.15    # ↓
QUALITY_WEIGHT_COHERENCE=0.10   # ↓
QUALITY_WEIGHT_INTEGRITY=0.10   # =
```

---

## 🛠️ Troubleshooting

### Quality Score NULL
**Symptôme** : `quality_score` reste NULL après crawl

**Causes possibles** :
1. `ENABLE_QUALITY_SCORING=false` dans config
2. Erreur dans `compute_quality_score()` (vérifier logs)
3. Expression sans `http_status` (pas encore crawlée)

**Solutions** :
```bash
# Vérifier config
docker exec mywebintelligenceapi env | grep ENABLE_QUALITY

# Vérifier logs
docker logs mywebintelligenceapi | grep -i quality | tail -20

# Reprocess manuellement
docker exec mywebintelligenceapi python -m app.scripts.reprocess_quality_scores --land-id 15
```

### Scores Incohérents
**Symptôme** : Scores ne correspondent pas aux attentes

**Causes possibles** :
1. Poids mal configurés (somme ≠ 1.0)
2. Métadonnées manquantes (title, description, etc.)
3. Truth table obsolète

**Solutions** :
```bash
# Valider configuration
docker exec mywebintelligenceapi python -c "
from app.services.quality_scorer import QualityScorer
scorer = QualityScorer()
print(scorer.weights)
print('Sum:', sum(scorer.weights.values()))
"

# Tester sur truth table
docker exec mywebintelligenceapi pytest tests/unit/test_quality_scorer.py::TestTruthTable -v

# Analyser une expression spécifique
docker exec mywebintelligenceapi python -c "
from app.db.session import SessionLocal
from app.db import models
from app.services.quality_scorer import QualityScorer

db = SessionLocal()
expr = db.query(models.Expression).filter(models.Expression.id == 123).first()
scorer = QualityScorer()
result = scorer.compute_quality_score(expr, expr.land)
print('Score:', result['score'])
print('Category:', result['category'])
print('Flags:', result['flags'])
print('Details:', result['details'])
"
```

---

## 📚 Références

- **Architecture** : `app/services/quality_scorer.py`
- **Tests** : `tests/unit/test_quality_scorer.py`
- **Truth Table** : `tests/data/quality_truth_table.json`
- **Configuration** : `app/config.py`
- **Reprocessing** : `app/scripts/reprocess_quality_scores.py`

---

## 🎓 Best Practices

1. **Toujours tester les changements** sur truth table avant déploiement
2. **Reprocesser l'historique** après ajustement des poids
3. **Monitorer la distribution** pour détecter anomalies
4. **Documenter les ajustements** de poids dans git commit
5. **Valider avec dry-run** avant reprocessing massif

---

**Version** : 1.0
**Dernière mise à jour** : 2025-10-18
**Auteur** : MyWebIntelligence Team
