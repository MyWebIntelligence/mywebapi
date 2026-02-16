#!/bin/bash
# Test complet crawl + analyse média ASYNC Celery - AGENTS.md
# Version robuste qui évite les pièges courants

# Fonction pour renouveler le token (expire rapidement)
get_fresh_token() {
    TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)
    if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
        echo "❌ Échec authentification"
        exit 1
    fi
}

echo "🔧 1/7 - Vérification serveur..."
if ! curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null | grep -q "200"; then
    echo "❌ Serveur API non accessible. Lancez: docker compose up -d"
    exit 1
fi

echo "🔑 2/7 - Authentification..."
get_fresh_token
echo "✅ Token obtenu: ${TOKEN:0:20}..."

echo "🏗️ 3/7 - Création land avec URLs intégrées..."
# Lecture des 5 premières URLs du fichier lecornu.txt
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LECORNU_FILE="${SCRIPT_DIR}/../scripts/data/lecornu.txt"

if [ ! -f "$LECORNU_FILE" ]; then
    echo "❌ Fichier lecornu.txt non trouvé: $LECORNU_FILE"
    exit 1
fi

echo "📋 URLs sélectionnées:"
head -n 5 "$LECORNU_FILE" | nl

# Créer un fichier JSON temporaire avec les URLs
TEMP_JSON=$(mktemp)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LAND_NAME="test_lecornu_${TIMESTAMP}"

cat > "$TEMP_JSON" <<EOF
{
  "name": "$LAND_NAME",
  "description": "Test crawl Lecornu avec 5 URLs - $TIMESTAMP",
  "start_urls": [
EOF

# Ajouter les URLs au JSON
head -n 5 "$LECORNU_FILE" | while IFS= read -r url; do
    if [ -n "$url" ]; then
        echo "    \"$url\"," >> "$TEMP_JSON"
    fi
done

# Retirer la dernière virgule et fermer le JSON
sed -i '' '$ s/,$//' "$TEMP_JSON" 2>/dev/null || sed -i '$ s/,$//' "$TEMP_JSON"
cat >> "$TEMP_JSON" <<EOF

  ]
}
EOF

# Créer le land avec le fichier JSON
LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @"$TEMP_JSON" | jq -r '.id')

# Nettoyer le fichier temporaire
rm -f "$TEMP_JSON"

if [ "$LAND_ID" = "null" ] || [ -z "$LAND_ID" ]; then
    echo "❌ Échec création land"
    exit 1
fi
echo "✅ Land créé: LAND_ID=$LAND_ID"

echo "📝 4/7 - Ajout mots-clés (OBLIGATOIRE pour pertinence)..."
get_fresh_token  # Token peut expirer
curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/terms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terms": ["lecornu", "sebastien", "macron", "matignon"]}' > /dev/null

echo "🕷️ 5/7 - Lancement crawl..."
get_fresh_token  # Renouveler avant chaque action importante
CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}' --max-time 60)

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Échec crawl: $CRAWL_RESULT"
    exit 1
fi
echo "✅ Crawl lancé: JOB_ID=$JOB_ID"

echo "⏳ 6/7 - Attente crawl (45s)..."
sleep 45

echo "🎨 7/8 - Test analyse média ASYNC avec Celery..."
get_fresh_token  # Token frais pour dernière étape
ASYNC_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depth": 0, "minrel": 0.0}')

ASYNC_JOB_ID=$(echo "$ASYNC_RESULT" | jq -r '.job_id')
CELERY_TASK_ID=$(echo "$ASYNC_RESULT" | jq -r '.celery_task_id')

if [ "$ASYNC_JOB_ID" = "null" ]; then
    echo "❌ Échec analyse async: $ASYNC_RESULT"
    exit 1
fi

echo "✅ Analyse média ASYNC lancée:"
echo "  - Job ID: $ASYNC_JOB_ID"
echo "  - Celery Task: $CELERY_TASK_ID"

echo "📖 8/8 - Test pipeline Readable (NOUVEAU)..."
get_fresh_token  # Token frais pour dernière étape
READABLE_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/readable" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "depth": 1, "merge_strategy": "smart_merge"}' \
  --max-time 120)

READABLE_JOB_ID=$(echo "$READABLE_RESULT" | jq -r '.job_id')
READABLE_TASK_ID=$(echo "$READABLE_RESULT" | jq -r '.celery_task_id')

if [ "$READABLE_JOB_ID" = "null" ]; then
    echo "❌ Échec pipeline readable: $READABLE_RESULT"
    # Ne pas exit ici, c'est un test de la nouvelle fonctionnalité
else
    echo "✅ Pipeline Readable lancé:"
    echo "  - Job ID: $READABLE_JOB_ID"
    echo "  - Celery Task: $READABLE_TASK_ID"
fi

echo ""
echo "📋 SUIVI LOGS CELERY (20s):"
echo "docker logs mywebclient-celery_worker-1 --tail=10 -f"
echo ""
docker logs mywebclient-celery_worker-1 --tail=10 -f &
TAIL_PID=$!
sleep 20
kill $TAIL_PID 2>/dev/null

echo ""
echo "🎯 RÉSUMÉ FINAL:"
echo "- Land ID: $LAND_ID"
echo "- Crawl Job: $JOB_ID"
echo "- Media Analysis Job: $ASYNC_JOB_ID"
echo "- Readable Processing Job: $READABLE_JOB_ID"
echo "- Celery Tasks: $CELERY_TASK_ID, $READABLE_TASK_ID"
echo ""
echo "🔍 Commandes utiles:"
echo "# Statut job: curl -H \"Authorization: Bearer \$TOKEN\" \"http://localhost:8000/api/v2/jobs/${ASYNC_JOB_ID}\""
echo "# Statut readable: curl -H \"Authorization: Bearer \$TOKEN\" \"http://localhost:8000/api/v2/jobs/${READABLE_JOB_ID}\""
echo "# Stats land: curl -H \"Authorization: Bearer \$TOKEN\" \"http://localhost:8000/api/v2/lands/${LAND_ID}/stats\""
echo "# Logs Celery: docker logs mywebclient-celery_worker-1 --tail=20 -f"
