#!/bin/bash
# Test complet basé sur AGENTS.md

set -e  # Exit on error

echo "🔧 1/7 - Vérification serveur..."
if ! curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null | grep -q "200"; then
    echo "❌ Serveur API non accessible"
    exit 1
fi
echo "✅ Serveur accessible"

echo ""
echo "🔑 2/7 - Authentification..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Échec authentification"
    exit 1
fi
echo "✅ Token obtenu: ${TOKEN:0:20}..."

echo ""
echo "🏗️ 3/7 - Création land avec URLs intégrées..."
LAND_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TestComplet_Oct13",
    "description": "Test complet basé sur AGENTS.md",
    "start_urls": ["https://www.lemonde.fr/politique/article/2025/10/11/emmanuel-macron-maintient-sebastien-lecornu-a-matignon-malgre-l-hostilite-de-l-ensemble-de-la-classe-politique_6645724_823448.html"],
    "words": ["lecornu", "sebastien", "macron", "matignon"]
  }')

LAND_ID=$(echo "$LAND_RESPONSE" | jq -r '.id')

if [ "$LAND_ID" = "null" ] || [ -z "$LAND_ID" ]; then
    echo "❌ Échec création land:"
    echo "$LAND_RESPONSE"
    exit 1
fi
echo "✅ Land créé: LAND_ID=$LAND_ID"

echo ""
echo "📝 4/7 - Ajout mots-clés supplémentaires..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/terms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terms": ["politique", "ministre", "gouvernement"]}' > /dev/null
echo "✅ Mots-clés ajoutés"

echo ""
echo "🕷️ 5/7 - Lancement crawl..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "depth": 1, "analyze_media": false}' --max-time 90)

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Échec crawl:"
    echo "$CRAWL_RESULT"
    exit 1
fi
echo "✅ Crawl lancé: JOB_ID=$JOB_ID"

echo ""
echo "⏳ 6/8 - Attente crawl (45s)..."
sleep 45

echo ""
echo "🎨 7/8 - Test analyse média ASYNC..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

ASYNC_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depth": 0, "minrel": 0.0}')

ASYNC_JOB_ID=$(echo "$ASYNC_RESULT" | jq -r '.job_id')
CELERY_TASK_ID=$(echo "$ASYNC_RESULT" | jq -r '.celery_task_id')

if [ "$ASYNC_JOB_ID" = "null" ]; then
    echo "⚠️ Analyse média async non lancée:"
    echo "$ASYNC_RESULT"
else
    echo "✅ Analyse média ASYNC lancée:"
    echo "  - Job ID: $ASYNC_JOB_ID"
    echo "  - Celery Task: $CELERY_TASK_ID"
fi

echo ""
echo "📖 8/8 - Test pipeline Readable..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

READABLE_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/readable" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 3, "depth": 1, "merge_strategy": "smart_merge"}' \
  --max-time 120)

READABLE_JOB_ID=$(echo "$READABLE_RESULT" | jq -r '.job_id')
READABLE_TASK_ID=$(echo "$READABLE_RESULT" | jq -r '.celery_task_id')

if [ "$READABLE_JOB_ID" = "null" ]; then
    echo "⚠️ Pipeline readable non lancé:"
    echo "$READABLE_RESULT"
else
    echo "✅ Pipeline Readable lancé:"
    echo "  - Job ID: $READABLE_JOB_ID"
    echo "  - Celery Task: $READABLE_TASK_ID"
fi

echo ""
echo "📋 SUIVI LOGS CELERY (20s):"
docker logs mywebclient-celery_worker-1 --tail=15 -f &
TAIL_PID=$!
sleep 20
kill $TAIL_PID 2>/dev/null || true

echo ""
echo "═══════════════════════════════════════════════════"
echo "🎯 RÉSUMÉ FINAL"
echo "═══════════════════════════════════════════════════"
echo "Land ID: $LAND_ID"
echo "Crawl Job: $JOB_ID"
echo "Media Analysis Job: $ASYNC_JOB_ID"
echo "Readable Processing Job: $READABLE_JOB_ID"
echo "Celery Tasks: $CELERY_TASK_ID, $READABLE_TASK_ID"
echo ""
echo "🔍 Commandes utiles:"
echo "# Stats land:"
echo "curl -H 'Authorization: Bearer \$TOKEN' 'http://localhost:8000/api/v2/lands/${LAND_ID}/stats' | jq"
echo ""
echo "# Statut jobs:"
echo "curl -H 'Authorization: Bearer \$TOKEN' 'http://localhost:8000/api/v2/jobs/${JOB_ID}' | jq"
echo "curl -H 'Authorization: Bearer \$TOKEN' 'http://localhost:8000/api/v2/jobs/${ASYNC_JOB_ID}' | jq"
echo "curl -H 'Authorization: Bearer \$TOKEN' 'http://localhost:8000/api/v2/jobs/${READABLE_JOB_ID}' | jq"
echo ""
echo "# Logs Celery:"
echo "docker logs mywebclient-celery_worker-1 --tail=30 -f"
echo "═══════════════════════════════════════════════════"
