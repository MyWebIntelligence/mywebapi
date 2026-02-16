# Quickstart — Test Crawler Sync V2

Ce guide express permet de valider le moteur de crawl unique introduit en V2.

## Étapes

1. **Préparation**
   ```bash
   docker compose up -d api celery worker db
   export TOKEN="$(./scripts/get-token.sh)"
   export LAND_ID="$(./scripts/get-test-land.sh)"
   ```

2. **Déclencher un crawl depuis l'API**
   ```bash
   curl -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
     -H "Authorization: Bearer ${TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"depth": 1, "llm_validation": false}'
   ```

3. **Suivre l'exécution côté Celery**
   ```bash
   docker logs -f mywebclient-celery_worker-1 | grep "SyncCrawlerEngine"
   ```

4. **Contrôle de cohérence**
   ```bash
   docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
   "SELECT url, http_status, readable IS NOT NULL FROM expressions ORDER BY created_at DESC LIMIT 5;"
   ```

5. **Nettoyage (optionnel)**
   ```bash
   docker compose down
   ```

## Validation

- Les logs doivent montrer l'utilisation de `SyncCrawlerEngine`.  
- Aucune erreur ne doit mentionner de coroutine ou de boucle événementielle.  
- Les enregistrements insérés comportent les champs enrichis attendus.

