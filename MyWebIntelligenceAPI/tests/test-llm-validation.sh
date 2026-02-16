#!/bin/bash
# Test LLM Validation - Crawl avec validation DeepSeek
# Vérifie que la validation LLM fonctionne pendant le crawl

set -e  # Exit on error

get_fresh_token() {
    TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)
    if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
        echo "❌ Échec authentification"
        exit 1
    fi
}

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🧪 TEST VALIDATION LLM (OpenRouter DeepSeek)"
echo "════════════════════════════════════════════════════════════════"
echo ""

echo "🔧 1/7 - Vérification serveur API..."
if ! curl -s -w "%{http_code}" "http://localhost:8000/" -o /dev/null | grep -q "200"; then
    echo "❌ Serveur API non accessible sur http://localhost:8000"
    exit 1
fi
echo "✅ Serveur accessible"

echo ""
echo "🔍 2/7 - Vérification configuration OpenRouter..."
# Vérifier via un endpoint qui expose les settings (si disponible)
# Ou directement dans le container
docker compose exec -T mywebintelligenceapi python -c "
from app.config import settings
import sys

if not settings.OPENROUTER_ENABLED:
    print('❌ OPENROUTER_ENABLED=False dans .env')
    sys.exit(1)

if not settings.OPENROUTER_API_KEY:
    print('❌ OPENROUTER_API_KEY non configuré')
    sys.exit(1)

print(f'✅ OPENROUTER_ENABLED=True')
print(f'✅ OPENROUTER_MODEL={settings.OPENROUTER_MODEL}')
print(f'✅ API Key configurée: {settings.OPENROUTER_API_KEY[:20]}...')
" || exit 1

echo ""
echo "🔑 3/7 - Authentification..."
get_fresh_token
echo "✅ Token obtenu: ${TOKEN:0:20}..."

echo ""
echo "🏗️ 4/7 - Création land de test..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Créer un land avec URLs de test pertinentes
LAND_PAYLOAD=$(cat <<EOF
{
  "name": "test_llm_validation_${TIMESTAMP}",
  "description": "Test validation LLM avec DeepSeek - Intelligence artificielle et machine learning",
  "start_urls": [
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Deep_learning"
  ],
  "words": [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural network",
    "AI",
    "ML"
  ]
}
EOF
)

LAND_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$LAND_PAYLOAD")

LAND_ID=$(echo "$LAND_RESPONSE" | jq -r '.id')
if [ "$LAND_ID" = "null" ] || [ -z "$LAND_ID" ]; then
    echo "❌ Échec création land"
    echo "Réponse API: $LAND_RESPONSE"
    exit 1
fi
echo "✅ Land créé: LAND_ID=$LAND_ID (test_llm_validation_${TIMESTAMP})"

echo ""
echo "🕷️ 5/7 - Lancement crawl avec validation LLM..."
echo "   📝 Paramètres: limit=3, enable_llm=true"
get_fresh_token

CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 3,
    "enable_llm": true
  }' --max-time 180)

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Échec lancement crawl"
    echo "Réponse: $CRAWL_RESULT"
    exit 1
fi

CELERY_TASK_ID=$(echo "$CRAWL_RESULT" | jq -r '.celery_task_id')
echo "✅ Crawl lancé:"
echo "   - JOB_ID: $JOB_ID"
echo "   - CELERY_TASK_ID: $CELERY_TASK_ID"

echo ""
echo "⏳ 6/7 - Attente fin du crawl (validation LLM en cours)..."
echo "   💡 La validation LLM peut prendre 2-3s par expression"
echo "   🔍 Monitoring via base de données..."

# Attendre et vérifier dans la DB
for i in {1..40}; do
    sleep 3

    # Vérifier le statut dans la DB directement
    JOB_STATUS=$(docker compose exec -T db psql -U mwi_user -d mwi_db -t -A -c "
        SELECT status FROM crawl_jobs WHERE id = ${JOB_ID};
    " 2>/dev/null | tr -d '[:space:]')

    if [ "$JOB_STATUS" = "completed" ]; then
        echo ""
        echo "✅ Crawl terminé après $((i * 3))s"
        break
    elif [ "$JOB_STATUS" = "failed" ]; then
        echo ""
        echo "❌ Le crawl a échoué"
        # Afficher le message d'erreur
        docker compose exec -T db psql -U mwi_user -d mwi_db -c "
            SELECT error_message FROM crawl_jobs WHERE id = ${JOB_ID};
        "
        exit 1
    fi

    # Afficher un point toutes les 3 secondes
    echo -n "."

    if [ $i -eq 40 ]; then
        echo ""
        echo "⚠️  Timeout après 120s, vérification des résultats quand même..."
    fi
done

echo ""
echo "📊 7/7 - Vérification des résultats..."

# Récupérer les expressions avec détails
get_fresh_token
EXPRESSIONS=$(docker compose exec -T db psql -U mwi_user -d mwi_db -t -A -F'|' -c "
SELECT
    id,
    url,
    title,
    relevance,
    valid_llm,
    valid_model,
    http_status
FROM expressions
WHERE land_id = ${LAND_ID}
ORDER BY id
LIMIT 10;
")

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🎯 RÉSULTATS DE LA VALIDATION LLM"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Compter les validations
TOTAL_COUNT=0
VALIDATED_COUNT=0
REJECTED_COUNT=0
NO_VALIDATION_COUNT=0

if [ -n "$EXPRESSIONS" ]; then
    echo "📋 Expressions crawlées:"
    echo ""

    while IFS='|' read -r id url title relevance valid_llm valid_model http_status; do
        TOTAL_COUNT=$((TOTAL_COUNT + 1))

        # Tronquer l'URL et le titre pour l'affichage
        SHORT_URL=$(echo "$url" | cut -c1-60)
        SHORT_TITLE=$(echo "$title" | cut -c1-50)

        echo "─────────────────────────────────────────────────────────────"
        echo "Expression #$id"
        echo "  URL: $SHORT_URL"
        echo "  Title: $SHORT_TITLE"
        echo "  HTTP: $http_status"
        echo "  Relevance: $relevance"

        if [ -n "$valid_llm" ] && [ "$valid_llm" != "" ]; then
            if [ "$valid_llm" = "oui" ]; then
                echo "  ✅ LLM Validation: OUI (pertinent)"
                echo "  🤖 Model: $valid_model"
                VALIDATED_COUNT=$((VALIDATED_COUNT + 1))
            else
                echo "  ❌ LLM Validation: NON (rejeté)"
                echo "  🤖 Model: $valid_model"
                REJECTED_COUNT=$((REJECTED_COUNT + 1))
            fi
        else
            echo "  ⚠️  LLM Validation: Non effectuée"
            NO_VALIDATION_COUNT=$((NO_VALIDATION_COUNT + 1))
        fi
        echo ""
    done <<< "$EXPRESSIONS"
else
    echo "⚠️  Aucune expression trouvée"
fi

echo "════════════════════════════════════════════════════════════════"
echo "📊 STATISTIQUES"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Total expressions crawlées:     $TOTAL_COUNT"
echo "✅ Validées (oui):              $VALIDATED_COUNT"
echo "❌ Rejetées (non):              $REJECTED_COUNT"
echo "⚠️  Sans validation:            $NO_VALIDATION_COUNT"

if [ $TOTAL_COUNT -gt 0 ]; then
    VALIDATION_RATE=$(awk "BEGIN {printf \"%.1f\", (($VALIDATED_COUNT + $REJECTED_COUNT) / $TOTAL_COUNT) * 100}")
    echo "📈 Taux de validation:          ${VALIDATION_RATE}%"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"

# Afficher les logs Celery pour voir les détails LLM
echo ""
echo "📝 Logs de validation LLM (dernières lignes):"
echo "────────────────────────────────────────────────────────────────"
docker logs mywebclient-celery_worker-1 --tail=30 2>/dev/null | grep -i "\[LLM\]" || echo "Aucun log LLM trouvé"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ TEST TERMINÉ"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📋 Informations de test:"
echo "   - Land ID: $LAND_ID"
echo "   - Job ID: $JOB_ID"
echo "   - Expressions traitées: $TOTAL_COUNT"
echo "   - Validations réussies: $VALIDATED_COUNT"
echo ""

# Vérifier que la validation LLM a bien fonctionné
if [ $VALIDATED_COUNT -eq 0 ] && [ $REJECTED_COUNT -eq 0 ] && [ $TOTAL_COUNT -gt 0 ]; then
    echo "⚠️  AVERTISSEMENT: Aucune validation LLM effectuée!"
    echo "   Vérifiez la configuration OpenRouter et les logs Celery"
    echo ""
    echo "   Commandes de debug:"
    echo "   docker logs mywebclient-celery_worker-1 --tail=100 | grep -i llm"
    echo "   docker compose exec mywebintelligenceapi python -c 'from app.config import settings; print(settings.OPENROUTER_ENABLED)'"
    exit 1
fi

if [ $VALIDATED_COUNT -gt 0 ] || [ $REJECTED_COUNT -gt 0 ]; then
    echo "🎉 Validation LLM fonctionne correctement!"
fi

echo ""
