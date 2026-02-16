#!/bin/bash
# Script de test complet projet 'lecornu' avec validation LLM
# Basé sur le modèle d'AGENTS.md

set -e  # Arrêter en cas d'erreur

echo "🚀 TEST COMPLET PROJET LECORNU avec LLM VALIDATION"
echo "================================================="

# Fonction pour renouveler le token (expire rapidement)
get_fresh_token() {
    TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=admin@example.com&password=changeme" | jq -r .access_token)
    if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
        echo "❌ Échec authentification"
        exit 1
    fi
}

echo "🔧 1/8 - Vérification serveur..."
if ! curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null | grep -q "200"; then
    echo "❌ Serveur API non accessible. Lancez: docker compose up -d"
    exit 1
fi

echo "🔧 2/8 - Vérification configuration OpenRouter..."
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "⚠️ OPENROUTER_API_KEY non configurée. Pour activer LLM validation:"
    echo "export OPENROUTER_ENABLED=True"
    echo "export OPENROUTER_API_KEY=sk-or-v1-your-key"
    echo "Continuons sans validation LLM..."
    ENABLE_LLM=false
else
    echo "✅ OpenRouter configuré"
    ENABLE_LLM=true
fi

echo "🔑 3/8 - Authentification..."
get_fresh_token
echo "✅ Token obtenu: ${TOKEN:0:20}..."

echo "🏗️ 4/8 - Création land 'lecornu' avec URLs intégrées..."
# Générer un nom unique avec timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LAND_NAME="lecornu_${TIMESTAMP}"

# Lire le fichier lecornu.txt et créer un tableau JSON
URLS_JSON=$(cat MyWebIntelligenceAPI/scripts/data/lecornu.txt | grep -v '^$' | jq -R . | jq -s .)

# Créer le land avec les URLs intégrées
LAND_DATA=$(jq -n \
  --arg name "$LAND_NAME" \
  --arg desc "Test Sébastien Lecornu - Premier ministre - $TIMESTAMP" \
  --argjson urls "$URLS_JSON" \
  --argjson words '["lecornu"]' \
  '{
    name: $name,
    description: $desc,
    start_urls: $urls,
    words: $words
  }')

LAND_ID=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$LAND_DATA" | jq -r '.id')

if [ "$LAND_ID" = "null" ] || [ -z "$LAND_ID" ]; then
    echo "❌ Échec création land"
    exit 1
fi
echo "✅ Land '$LAND_NAME' créé: LAND_ID=$LAND_ID"

echo "📊 5/8 - Vérification URLs ajoutées..."
get_fresh_token
LAND_INFO=$(curl -s -X GET "http://localhost:8000/api/v2/lands/${LAND_ID}" \
  -H "Authorization: Bearer $TOKEN")
URL_COUNT=$(echo "$LAND_INFO" | jq '.start_urls | length')
echo "✅ $URL_COUNT URLs ajoutées au land"

echo "📝 6/8 - Ajout terme 'lecornu' (OBLIGATOIRE pour pertinence)..."
get_fresh_token
curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/terms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terms": ["lecornu", "sebastien", "matignon", "premier ministre"]}' > /dev/null
echo "✅ Termes ajoutés pour améliorer la pertinence"

echo "🕷️ 7/8 - Lancement crawl de 20 URLs avec LLM validation..."
get_fresh_token

# Préparer la requête de crawl
if [ "$ENABLE_LLM" = "true" ]; then
    CRAWL_DATA='{"limit": 20, "analyze_media": false, "enable_llm": true}'
    echo "✅ Crawl avec validation LLM activée"
else
    CRAWL_DATA='{"limit": 20, "analyze_media": false, "enable_llm": false}'
    echo "⚠️ Crawl sans validation LLM (clé API manquante)"
fi

CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$CRAWL_DATA" --max-time 60)

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
CELERY_TASK_ID=$(echo "$CRAWL_RESULT" | jq -r '.celery_task_id')

if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Échec crawl: $CRAWL_RESULT"
    exit 1
fi

echo "✅ Crawl lancé:"
echo "  - Job ID: $JOB_ID"
echo "  - Celery Task: $CELERY_TASK_ID"
echo "  - URLs à crawler: 20"
echo "  - LLM validation: $ENABLE_LLM"

echo "⏳ 8/8 - Attente crawl (90s) et suivi des logs..."
echo ""
echo "📋 SUIVI LOGS CELERY:"
echo "docker logs mywebclient-celery_worker-1 --tail=20 -f"
echo ""

# Suivre les logs en parallèle pendant 90s
timeout 90s docker logs mywebclient-celery_worker-1 --tail=10 -f &
TAIL_PID=$!

# Attendre 90s pour le crawl
sleep 90

# Arrêter le suivi des logs
kill $TAIL_PID 2>/dev/null || true

echo ""
echo "📊 VÉRIFICATION DES RÉSULTATS:"

# Récupérer les statistiques finales
get_fresh_token
STATS=$(curl -s -X GET "http://localhost:8000/api/v2/lands/${LAND_ID}/stats" \
  -H "Authorization: Bearer $TOKEN")

TOTAL_EXPRESSIONS=$(echo "$STATS" | jq -r '.total_expressions // 0')
TOTAL_DOMAINS=$(echo "$STATS" | jq -r '.total_domains // 0')

echo "✅ Statistiques finales:"
echo "  - Land ID: $LAND_ID"
echo "  - Expressions crawlées: $TOTAL_EXPRESSIONS"
echo "  - Domaines découverts: $TOTAL_DOMAINS"
echo "  - Job ID: $JOB_ID"
echo "  - Celery Task: $CELERY_TASK_ID"

# Vérifier le statut du job
JOB_STATUS=$(curl -s -X GET "http://localhost:8000/api/v2/jobs/${JOB_ID}" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.status // "unknown"')
echo "  - Statut job: $JOB_STATUS"

if [ "$ENABLE_LLM" = "true" ]; then
    echo ""
    echo "🤖 RÉSULTATS VALIDATION LLM:"
    # TODO: Ajouter requête pour vérifier les validations LLM
    echo "  - Vérifiez les champs valid_llm et valid_model en base"
    echo "  - Ou utilisez l'endpoint stats pour voir les résultats"
fi

echo ""
echo "🔍 COMMANDES UTILES POUR LA SUITE:"
echo ""
echo "# Statut job détaillé:"
echo "curl -H \"Authorization: Bearer \$TOKEN\" \"http://localhost:8000/api/v2/jobs/${JOB_ID}\""
echo ""
echo "# Statistiques land détaillées:"
echo "curl -H \"Authorization: Bearer \$TOKEN\" \"http://localhost:8000/api/v2/lands/${LAND_ID}/stats\""
echo ""
echo "# Relancer readable avec LLM (si pas fait pendant crawl):"
echo "curl -X POST \"http://localhost:8000/api/v2/lands/${LAND_ID}/readable\" \\"
echo "  -H \"Authorization: Bearer \$TOKEN\" \\"
echo "  -d '{\"limit\": 10, \"enable_llm\": true}'"
echo ""
echo "# Analyser les médias:"
echo "curl -X POST \"http://localhost:8000/api/v2/lands/${LAND_ID}/media-analysis-async\" \\"
echo "  -H \"Authorization: Bearer \$TOKEN\" \\"
echo "  -d '{\"depth\": 1, \"minrel\": 2.0}'"
echo ""
echo "# Logs Celery en temps réel:"
echo "docker logs mywebclient-celery_worker-1 --tail=20 -f"

echo ""
echo "🎯 TEST TERMINÉ AVEC SUCCÈS!"
echo "Projet 'lecornu' créé avec $TOTAL_EXPRESSIONS expressions crawlées"
if [ "$ENABLE_LLM" = "true" ]; then
    echo "Validation LLM activée - vérifiez les résultats en base"
else
    echo "Pour activer LLM: configurez OPENROUTER_API_KEY et relancez"
fi