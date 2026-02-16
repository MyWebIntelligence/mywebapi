#!/bin/bash
# Test d'intégration quality scoring
# Vérifie que le quality_score est calculé lors du crawl

set -e

echo "=== Quality Score Integration Test ==="
echo ""

# Configuration
API_URL="http://localhost:8000"
DB_CONTAINER="mywebclient-db-1"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}1. Vérification que ENABLE_QUALITY_SCORING est activé${NC}"
docker exec mywebintelligenceapi env | grep ENABLE_QUALITY_SCORING || echo "ENABLE_QUALITY_SCORING=true (default)"
echo ""

echo -e "${YELLOW}2. Création d'un land de test${NC}"
# Create test land via SQL
LAND_ID=$(docker exec $DB_CONTAINER psql -U mwi_user -d mwi_db -t -c "
INSERT INTO lands (name, description, lang, start_urls, created_at, updated_at)
VALUES (
    'Quality Test Land',
    'Land for quality scoring integration test',
    ARRAY['fr'],
    ARRAY['https://httpbin.org/html'],
    NOW(),
    NOW()
)
RETURNING id;
" | xargs)

echo "Created land_id: $LAND_ID"
echo ""

echo -e "${YELLOW}3. Vérification du land créé${NC}"
docker exec $DB_CONTAINER psql -U mwi_user -d mwi_db -c "
SELECT id, name, start_urls FROM lands WHERE id = $LAND_ID;
"
echo ""

echo -e "${YELLOW}4. Attente de 5 secondes pour que l'API démarre${NC}"
sleep 5

echo -e "${YELLOW}5. Déclenchement d'un crawl via Celery (sync crawler)${NC}"
# Get auth token (assuming default user exists)
AUTH_TOKEN=$(docker exec mywebintelligenceapi python3 -c "
from app.config import settings
from jose import jwt
from datetime import datetime, timedelta

payload = {
    'sub': 'test@example.com',
    'exp': datetime.utcnow() + timedelta(hours=1)
}
token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
print(token)
" 2>/dev/null || echo "test-token")

echo "Using auth token: ${AUTH_TOKEN:0:20}..."

# Trigger crawl via API (this will use Celery/sync crawler)
curl -X POST "${API_URL}/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 1}' \
  -w "\nHTTP Status: %{http_code}\n" || echo "Crawl endpoint may require valid auth"

echo ""

echo -e "${YELLOW}6. Attente de 15 secondes pour que le crawl se termine${NC}"
sleep 15

echo -e "${YELLOW}7. Vérification du quality_score dans la DB${NC}"
docker exec $DB_CONTAINER psql -U mwi_user -d mwi_db -c "
SELECT
    id,
    url,
    http_status,
    word_count,
    quality_score,
    CASE
        WHEN quality_score >= 0.8 THEN 'Excellent'
        WHEN quality_score >= 0.6 THEN 'Bon'
        WHEN quality_score >= 0.4 THEN 'Moyen'
        WHEN quality_score >= 0.2 THEN 'Faible'
        ELSE 'Très faible'
    END as quality_category
FROM expressions
WHERE land_id = $LAND_ID
ORDER BY id DESC
LIMIT 5;
"
echo ""

echo -e "${YELLOW}8. Statistiques quality pour le land${NC}"
QUALITY_COUNT=$(docker exec $DB_CONTAINER psql -U mwi_user -d mwi_db -t -c "
SELECT COUNT(*) FROM expressions WHERE land_id = $LAND_ID AND quality_score IS NOT NULL;
" | xargs)

TOTAL_COUNT=$(docker exec $DB_CONTAINER psql -U mwi_user -d mwi_db -t -c "
SELECT COUNT(*) FROM expressions WHERE land_id = $LAND_ID;
" | xargs)

echo "Expressions avec quality_score: $QUALITY_COUNT / $TOTAL_COUNT"

if [ "$QUALITY_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ SUCCESS: Quality score calculé !${NC}"

    # Show distribution
    docker exec $DB_CONTAINER psql -U mwi_user -d mwi_db -c "
    SELECT
        CASE
            WHEN quality_score >= 0.8 THEN 'Excellent'
            WHEN quality_score >= 0.6 THEN 'Bon'
            WHEN quality_score >= 0.4 THEN 'Moyen'
            WHEN quality_score >= 0.2 THEN 'Faible'
            ELSE 'Très faible'
        END as category,
        COUNT(*) as count,
        ROUND(AVG(quality_score)::numeric, 3) as avg_score
    FROM expressions
    WHERE land_id = $LAND_ID AND quality_score IS NOT NULL
    GROUP BY category
    ORDER BY avg_score DESC;
    "
else
    echo -e "${RED}❌ FAIL: Aucun quality_score calculé${NC}"
    echo "Vérifier les logs:"
    echo "  docker logs mywebintelligenceapi | grep -i quality | tail -20"
    echo "  docker logs mywebclient-celery_worker-1 | grep -i quality | tail -20"
fi

echo ""
echo -e "${YELLOW}9. Cleanup (optionnel)${NC}"
read -p "Supprimer le land de test ? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    docker exec $DB_CONTAINER psql -U mwi_user -d mwi_db -c "
    DELETE FROM expressions WHERE land_id = $LAND_ID;
    DELETE FROM lands WHERE id = $LAND_ID;
    "
    echo "Land $LAND_ID supprimé"
fi

echo ""
echo "=== Test terminé ==="
