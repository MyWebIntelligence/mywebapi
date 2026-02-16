# Guide de test — Crawler V2 (Sync Only)

Ce fichier remplace l'ancien guide dédié au moteur parallèle.  
Objectif : vérifier le fonctionnement du moteur unique `SyncCrawlerEngine` de bout en bout.

## Pré-requis

- Docker compose démarré (`api`, `celery`, `db`).  
- Base de données peuplée avec au moins un land de test.  
- Accès au script `tests/test-crawl-simple.sh`.

## Scénario de test rapide

1. Ouvrir un shell dans le conteneur API :
   ```bash
   docker exec -it mywebintelligenceapi bash
   ```
2. Lancer le script de crawl :
   ```bash
   tests/test-crawl-simple.sh
   ```
3. Vérifier les logs Celery :
   ```bash
   docker logs mywebclient-celery_worker-1 --tail 50
   ```
4. Contrôler la base :
   ```bash
   docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
   "SELECT url, readable IS NOT NULL AS has_readable FROM expressions ORDER BY created_at DESC LIMIT 5;"
   ```

## Points d'attention

- L'appel au crawl doit instancier `SyncCrawlerEngine` uniquement.  
- Aucun message de log ne doit mentionner un moteur parallèle ou une coroutine.  
- Les champs enrichis (readable, sentiment, quality, media) doivent être présents après exécution.

## Dépannage

- Si la tâche Celery ne démarre pas, vérifier la connexion Redis et la file `crawl`.  
- Si les expressions restent sans contenu, vérifier `trafilatura` et les paramètres réseau du conteneur API.  
- En cas d'erreur SQL, exécututer `alembic upgrade head` puis relancer le test.

