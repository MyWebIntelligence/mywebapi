#!/bin/bash
# Test de la solution Dictionary Starvation

set -e

echo "🔧 Test de correction du dictionnaire vide"
echo ""

echo "🔑 Authentification..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Échec authentification"
    exit 1
fi
echo "✅ Token obtenu"

echo ""
echo "📖 1/4 - Vérifier l'état actuel du dictionnaire du Land 4..."
DICT_BEFORE=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v2/lands/4/dictionary-stats")
echo "$DICT_BEFORE" | jq

echo ""
echo "🔄 2/4 - Peupler le dictionnaire manuellement..."
POPULATE_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/4/populate-dictionary" \
  -H "Authorization: Bearer $TOKEN")
echo "$POPULATE_RESULT" | jq

echo ""
echo "📊 3/4 - Vérifier le dictionnaire après peuplement..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

DICT_AFTER=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v2/lands/4/dictionary-stats")
echo "$DICT_AFTER" | jq

echo ""
echo "🕷️ 4/4 - Relancer le crawl avec dictionnaire peuplé..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

RECRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/4/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 3, "depth": 0}' --max-time 60)

echo "$RECRAWL_RESULT" | jq

NEW_JOB_ID=$(echo "$RECRAWL_RESULT" | jq -r '.job_id')
echo ""
echo "✅ Nouveau crawl lancé: Job ID = $NEW_JOB_ID"

echo ""
echo "⏳ Attente crawl (30s)..."
sleep 30

echo ""
echo "📊 Statistiques finales du Land 4..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v2/lands/4" | jq '.total_expressions, .total_domains, .crawl_status'

echo ""
echo "✅ Test terminé. Vérifiez si total_expressions > 0"
