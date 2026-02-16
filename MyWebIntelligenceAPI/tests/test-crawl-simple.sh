#!/bin/bash
# Test SIMPLE crawl sync - 5 URLs Lecornu
# Sans media analysis async ni readable pipeline

get_fresh_token() {
    TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)
    if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
        echo "❌ Échec authentification"
        exit 1
    fi
}

echo "🔧 1/5 - Vérification serveur..."
if ! curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null | grep -q "200"; then
    echo "❌ Serveur API non accessible"
    exit 1
fi

echo "🔑 2/5 - Authentification..."
get_fresh_token
echo "✅ Token: ${TOKEN:0:20}..."

echo "🏗️ 3/5 - Création land..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LECORNU_FILE="${SCRIPT_DIR}/../scripts/data/lecornu.txt"

if [ ! -f "$LECORNU_FILE" ]; then
    echo "❌ Fichier lecornu.txt non trouvé"
    exit 1
fi

TEMP_JSON=$(mktemp)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cat > "$TEMP_JSON" <<EOF
{
  "name": "test_lecornu_${TIMESTAMP}",
  "description": "Test crawl sync Lecornu - ${TIMESTAMP}",
  "start_urls": [
EOF

head -n 5 "$LECORNU_FILE" | while IFS= read -r url; do
    if [ -n "$url" ]; then
        echo "    \"$url\"," >> "$TEMP_JSON"
    fi
done

sed -i '' '$ s/,$//' "$TEMP_JSON" 2>/dev/null || sed -i '$ s/,$//' "$TEMP_JSON"
cat >> "$TEMP_JSON" <<EOF

  ]
}
EOF

LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @"$TEMP_JSON" | jq -r '.id')
rm -f "$TEMP_JSON"

if [ "$LAND_ID" = "null" ] || [ -z "$LAND_ID" ]; then
    echo "❌ Échec création land"
    exit 1
fi
echo "✅ Land créé: LAND_ID=$LAND_ID"

echo "📝 4/5 - Ajout mots-clés..."
get_fresh_token
curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/terms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terms": ["lecornu", "sebastien", "macron", "matignon"]}' > /dev/null

echo "🕷️ 5/5 - Lancement crawl SYNC..."
get_fresh_token
CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}' --max-time 120)

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Échec crawl: $CRAWL_RESULT"
    exit 1
fi
echo "✅ Crawl lancé: JOB_ID=$JOB_ID"

echo ""
echo "⏳ Attente fin du crawl (20s)..."
sleep 20

echo ""
echo "📊 Vérification résultats..."
get_fresh_token
STATS=$(curl -s "http://localhost:8000/api/v2/lands/${LAND_ID}/stats" \
  -H "Authorization: Bearer $TOKEN")

echo ""
echo "🎯 RÉSULTATS:"
echo "$STATS" | jq '{
  land_id: .land_id,
  land_name: .land_name,
  total_expressions: .total_expressions,
  approved_expressions: .approved_expressions,
  total_links: .total_links,
  total_media: .total_media
}'

echo ""
echo "✅ Test terminé!"
echo "Land ID: $LAND_ID"
echo "Job ID: $JOB_ID"
