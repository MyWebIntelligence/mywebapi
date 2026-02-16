# Pipeline "Readable" (V2 sync) — COMPLETE

> **Statut** : IMPLEMENTE (16 fevrier 2026)

## Implementation realisee

- `app/tasks/readable_working_task.py` : Celery task V2 sync
  - Selectionne les expressions (approved_at, http_status=200, sans readable)
  - Utilise `content_extractor.get_readable_content_with_fallbacks()` (Trafilatura -> Archive.org -> BeautifulSoup)
  - Strategies de merge : smart_merge, mercury_priority, preserve_existing
  - Cree Media et ExpressionLink depuis le contenu extrait
  - Met a jour readable_at, job progress et status

- Endpoint : `POST /api/v2/lands/{id}/readable`
- Import fixe : n'importe plus de projetV3

## Tests existants
- `test_readable_service` (12 tests)
- `test_readable_endpoints` (10 tests)
- `test_legacy_parity` (17 tests)

## Reste a faire
- Verifier que les tests existants passent avec la nouvelle task
- Ajouter tests d'integration pour le workflow complet Celery
