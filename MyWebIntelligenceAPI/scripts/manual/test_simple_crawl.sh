#!/bin/bash
# Test crawl avec URLs simples (httpbin)

set -e

echo "🧪 TEST CRAWL SIMPLE - URLs httpbin"
echo ""

echo "🔑 Authentification..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

echo "✅ Token obtenu"
echo ""

echo "🏗️ Création land de test avec httpbin/links..."
LAND_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TestSimpleCrawl",
    "description": "Test crawl avec URLs simples",
    "start_urls": ["https://httpbin.org/links/5/0"],
    "words": ["link", "page"]
  }')

LAND_ID=$(echo "$LAND_RESPONSE" | jq -r '.id')
echo "✅ Land créé: LAND_ID=$LAND_ID"
echo ""

echo "🕷️ Lancement crawl (limit=3, depth=1)..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 3, "depth": 1}' --max-time 60)

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
echo "✅ Crawl lancé: Job ID = $JOB_ID"
echo ""

echo "⏳ Attente crawl (20s)..."
sleep 20

echo ""
echo "📊 Résultats du crawl..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

LAND_DETAILS=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v2/lands/${LAND_ID}")

TOTAL_EXPRESSIONS=$(echo "$LAND_DETAILS" | jq -r '.total_expressions')
CRAWL_STATUS=$(echo "$LAND_DETAILS" | jq -r '.crawl_status')

echo "Land ID: $LAND_ID"
echo "Total expressions: $TOTAL_EXPRESSIONS"
echo "Crawl status: $CRAWL_STATUS"
echo ""

if [ "$TOTAL_EXPRESSIONS" -gt 0 ]; then
    echo "✅ SUCCÈS: $TOTAL_EXPRESSIONS expressions crawlées"
else
    echo "❌ ÉCHEC: 0 expressions crawlées"
    echo ""
    echo "Logs Celery (dernières lignes):"
    docker logs mywebclient-celery_worker-1 --tail=20
fi

echo ""
echo "📋 Détails complets du land:"
echo "$LAND_DETAILS" | jq
