# MyWebIntelligence API - Guide Agents

MyWebIntelligence est une API FastAPI (V2 sync-only) encapsulant un crawler web. Elle permet l'integration avec MyWebClient via Docker Compose (API + Celery + PostgreSQL + Redis).

---

## SOURCE UNIQUE DU CRAWL

Toute la logique de crawl vit dans **un unique moteur** : `app/core/crawler_engine.py`

**Checklist avant tout commit touchant le crawl :**
1. Mettre a jour `app/core/crawler_engine.py`
2. Lancer `tests/test-crawl-simple.sh`
3. Verifier les logs Celery : `docker logs mywebclient-celery_worker-1 --tail 50`
4. Controler les ecritures en base (content, metadonnees, scores)

---

## Recommandations Dev

- **Attributs ORM** : utiliser les noms mappes (`expr.lang`, `expr.content`) et non les noms de colonnes (`"language"`)
- **Chaine d'extraction** : Trafilatura -> Archive.org -> requetes directes. Voir [docs/CHAINE_FALLBACKS.md](docs/CHAÎNE_FALLBACKS.md)
- **Enrichissement markdown** : passer par `content_extractor.get_readable_content_with_fallbacks()`
- **Nouvelles metriques** : service dedie + integration crawler + script batch + tests

---

## DB Init : Lecon critique

Tables creees dans `@app.on_event("startup")` de `app/main.py` avec `isolation_level="AUTOCOMMIT"`.
Ne PAS utiliser de script externe ni de transactions pour CREATE TABLE.
Utiliser `print(flush=True)` pour le debug (pas `logger.info`).

---

## Concepts Cles

**Land** = projet de crawling contenant : `start_urls`, `words` (mots-cles), config langues, resultats.

**Expression** = page web crawlee avec : url, content, readable, depth, relevance, quality_score, sentiment_score, language, http_status.

**Workflow** : Creer Land -> Crawl -> Readable -> Media Analysis -> Export (CSV/GEXF/JSON)

---

## Demarrage Rapide

### Authentification
```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changeme" | jq -r .access_token)
```

### Docker
```bash
docker compose down -v && docker compose up --build -d
curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null
```

---

## Endpoints Principaux

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/auth/login` | Authentification JWT |
| `POST /api/v2/lands/` | Creer un land |
| `POST /api/v2/lands/{id}/crawl` | Lancer un crawl |
| `POST /api/v2/lands/{id}/readable` | Pipeline readable |
| `POST /api/v2/lands/{id}/media-analysis` | Analyse medias (Celery) |
| `POST /api/v2/lands/{id}/llm-validate` | Validation LLM batch |
| `POST /api/v2/domains/crawl` | Domain crawl |
| `GET /api/v2/lands/{id}/stats` | Statistiques |
| `POST /api/v2/lands/{id}/consolidate` | Consolidation land |
| `POST /api/v2/lands/{id}/seorank` | Enrichissement SEO Rank |
| `POST /api/v2/lands/{id}/serpapi-urls` | Ajout URLs via SerpAPI |
| `POST /api/v2/lands/{id}/heuristic-update` | Mise a jour heuristiques domaines |
| `DELETE /api/v2/lands/{id}/expressions` | Supprimer expressions par maxrel |
| `POST /api/v1/export/direct` | Export CSV/GEXF/Corpus |
| `POST /api/v1/export/nodelinkcsv` | Export reseau (ZIP 4 CSVs) |
| `POST /api/v2/export/` | Export universel V2 (Celery) |

---

## Modeles de Donnees

### Land
```
id, name, description, owner_id, lang[], start_urls[], crawl_status, words[]
```

### Expression
```
id, land_id, domain_id, url, title, content, readable, depth, relevance,
quality_score, language, word_count, http_status, sentiment_score,
sentiment_label, valid_llm, valid_model, seorank
```

### Media
```
id, expression_id, url, type (img/video/audio), is_processed,
width, height, file_size, metadata, dominant_colors[]
```

### Relations
```
users 1->N lands 1->N domains
lands 1->N expressions 1->N media
expressions 1->N paragraphs
expressions 1->N expression_links
```

---

## Pipelines

### 1. Crawl
`POST /api/v2/lands/{id}/crawl` avec `{"limit": 10, "depth": 2, "enable_llm": false}`

Calcule automatiquement : relevance, quality_score, sentiment_score, language.

### 2. Media Analysis
`POST /api/v2/lands/{id}/media-analysis` avec `{"depth": 0, "minrel": 3.0}`

`depth` = profondeur des expressions source (pas nombre de medias).
`minrel` = filtre de pertinence (3.0 recommande pour tests).

### 3. Readable
`POST /api/v2/lands/{id}/readable` avec `{"limit": 50, "depth": 1}`

Extraction : Trafilatura -> Archive.org -> BeautifulSoup smart -> basic.
Details : [docs/CHAINE_FALLBACKS.md](docs/CHAÎNE_FALLBACKS.md)

### 4. LLM Validation
`POST /api/v2/lands/{id}/crawl` avec `"enable_llm": true`
ou batch : `POST /api/v2/lands/{id}/llm-validate?limit=50`

Necessite OpenRouter. Details : [docs/LLM_VALIDATION_GUIDE.md](docs/LLM_VALIDATION_GUIDE.md)
Config : [tasks/OPENROUTER_SETUP.md](tasks/OPENROUTER_SETUP.md)

### 5. Quality Score
Calcul automatique lors du crawl. 5 blocs heuristiques (Access 30%, Structure 15%, Richness 25%, Coherence 20%, Integrity 10%). Score 0.0-1.0.

Reprocessing : `docker exec mywebintelligenceapi python -m app.scripts.reprocess_quality_scores --land-id <id>`

Details : [docs/QUALITY_SCORE_GUIDE.md](docs/QUALITY_SCORE_GUIDE.md)

### 6. Domain Crawl
`POST /api/v2/domains/crawl` avec `{"land_id": 69, "limit": 10}`

Details : [docs/domain_crawl.md](docs/domain_crawl.md)

### 7. Export
`POST /api/v1/export/direct` avec `{"land_id": 36, "export_type": "pagecsv"}`

---

## Logique des Timestamps (Critique)

| Champ | Signification |
|-------|--------------|
| `created_at` | URL decouverte (INSERT) |
| `crawled_at` | Contenu HTTP recupere |
| `approved_at` | Reponse traitee par le crawler. **`approved_at IS NULL` = candidat au crawl** |
| `readable_at` | Contenu readable extrait |
| `updated_at` | Readable modifie |

`http_status` : toujours un code valide (200, 404...) ou `000` pour erreur non-HTTP. Jamais NULL apres traitement.

```sql
-- Candidats au crawl
SELECT * FROM expressions
WHERE land_id = ? AND approved_at IS NULL AND depth <= ?
ORDER BY depth ASC, created_at ASC LIMIT ?
```

---

## Pieges et Erreurs Frequentes

1. **Tokens JWT expirent vite** : renouveler avec `get_fresh_token()` avant chaque action
2. **Mots-cles obligatoires** : sans termes via `/terms`, `relevance=0` partout
3. **Endpoint `/urls` instable** : preferer `start_urls` lors de la creation du land
4. **Media analysis saturee** : toujours utiliser `minrel >= 1.0`, surveiller logs Celery
5. **`depth`** = niveau de crawl, pas nombre d'items

### Workflow Anti-Erreurs
```
1. Creer land avec start_urls integrees
2. Ajouter termes via POST /terms
3. Renouveler token avant chaque action
4. Lancer crawl : POST /crawl {"limit": 5}
5. Attendre ~60s pour 5 URLs
6. Verifier : docker logs mywebclient-celery_worker-1 --tail=50
```

---

## Tests

**Script recommande** : `./MyWebIntelligenceAPI/tests/test-crawl-simple.sh`

```bash
# Logs Celery
docker logs mywebclient-celery_worker-1 --tail=50

# Quality Score tests
docker exec mywebintelligenceapi pytest tests/unit/test_quality_scorer.py -v

# Scenario complet
python scripts/land_scenario.py --land-name "Test" --terms "keyword1" --urls "https://example.com" --crawl-limit 10
```

---

## Variables d'Environnement

```bash
DATABASE_URL=postgresql://user:pass@postgres:5432/mywebintelligence
REDIS_URL=redis://redis:6379
SECRET_KEY=<64-chars>
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=changethispassword

# Optionnel : LLM Validation
OPENROUTER_ENABLED=True
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Optionnel : Quality & Sentiment
ENABLE_QUALITY_SCORING=true
ENABLE_SENTIMENT_ANALYSIS=true
```

---

## Documentation Detaillee

| Document | Contenu |
|----------|---------|
| [system/Architecture.md](system/Architecture.md) | Architecture V2, pipelines, modele de donnees, Docker |
| [docs/CHAINE_FALLBACKS.md](docs/CHAÎNE_FALLBACKS.md) | Pipeline extraction contenu (Trafilatura/Archive/BS) |
| [docs/QUALITY_SCORE_GUIDE.md](docs/QUALITY_SCORE_GUIDE.md) | Quality Score : 5 blocs, tuning, SQL, tests |
| [docs/LLM_VALIDATION_GUIDE.md](docs/LLM_VALIDATION_GUIDE.md) | Validation LLM via OpenRouter |
| [docs/SENTIMENT_ANALYSIS_FEATURE.md](docs/SENTIMENT_ANALYSIS_FEATURE.md) | Analyse sentiment (TextBlob + LLM) |
| [docs/domain_crawl.md](docs/domain_crawl.md) | Domain Crawl V2 : endpoints, fallbacks, tests |

### Audit Transfert Legacy -> API
Voir [docs/TRANSFERT_AUDIT.md](docs/TRANSFERT_AUDIT.md) pour l'audit complet fonction par fonction.

**Resume** : **30/30 fonctions implementees (100%)**. 14 necessitent encore des tests dedies.

### Prochaines etapes
| Tache | Priorite | Notes |
|-------|----------|-------|
| Ecrire tests pour les nouvelles fonctions | HAUTE | seorank, heuristic, exports, serpapi, delete maxrel |
| Verifier tests existants readable/media | HAUTE | Les tasks ont ete recrees, verifier les tests |
| OpenRouter setup | Reference | [tasks/OPENROUTER_SETUP.md](tasks/OPENROUTER_SETUP.md) |

---

**Derniere mise a jour** : 16 fevrier 2026
