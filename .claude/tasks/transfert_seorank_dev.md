# Pipeline SEO Rank (v2) — COMPLETE

> **Statut** : IMPLEMENTE (16 fevrier 2026)

## Implementation realisee

### Celery Task
- `app/tasks/seorank_task.py` : task V2 sync
  - Appelle l'API SEO Rank (seo-rank.my-addr.com) via httpx
  - Filtres : limit, depth, min_relevance, force_refresh
  - URL encoding : `quote(url, safe=":/?&=%")`
  - Delai configurable entre requetes (`SEORANK_REQUEST_DELAY`)
  - Stocke le JSON brut dans `Expression.seo_rank`
  - Progress tracking via Celery state updates

### Endpoints
- V2 : `POST /api/v2/lands/{id}/seorank` (avec body SeoRankRequest)
- V1 : `POST /api/v1/lands/{id}/seorank` (query params)

### Configuration (app/config.py)
- `SEORANK_API_KEY` : cle API
- `SEORANK_API_BASE_URL` : `https://seo-rank.my-addr.com/api2/moz+sr+fb`
- `SEORANK_TIMEOUT` : 15s
- `SEORANK_REQUEST_DELAY` : 1.0s

### Export integration
- `write_nodelinkcsv()` parse et expande le JSON seorank en colonnes dynamiques
- Les exports CSV incluent les donnees SEO Rank

## Reste a faire
- Tests unitaires avec mocks HTTP (respx)
- Tests d'integration (endpoint -> Celery -> DB)
- Verifier quota API et ajouter rate limiting si necessaire
