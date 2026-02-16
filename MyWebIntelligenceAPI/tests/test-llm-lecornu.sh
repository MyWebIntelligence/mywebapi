#!/bin/bash

# Test LLM Validation avec création d'un nouveau land Lecornu
# Crée un land avec le format: lecornu_DDMMYYYY_HHMM
# Terme: "lecornu"
# URLs: depuis lecornu.txt

# Generate land name with timestamp
TIMESTAMP=$(date +"%d%m%Y_%H%M")
LAND_NAME="lecornu_${TIMESTAMP}"

echo "════════════════════════════════════════════════════════════════"
echo "🧪 TEST LLM VALIDATION - Nouveau Land Lecornu"
echo "════════════════════════════════════════════════════════════════"
echo "Land name: $LAND_NAME"
echo ""

# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
  echo "❌ Failed to get authentication token"
  exit 1
fi

echo "✅ Token obtained"
echo ""

# Read URLs from lecornu.txt
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URLS_FILE="$SCRIPT_DIR/../scripts/data/lecornu.txt"

if [ ! -f "$URLS_FILE" ]; then
  echo "❌ File not found: $URLS_FILE"
  exit 1
fi

# Read URLs into JSON array (skip empty lines)
START_URLS=$(grep -v '^$' "$URLS_FILE" | jq -R . | jq -s .)

echo "📄 URLs loaded from lecornu.txt: $(echo "$START_URLS" | jq 'length') URLs"
echo ""

# Create new land
echo "🌍 Creating new land: $LAND_NAME"
LAND_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"$LAND_NAME\",
    \"description\": \"Test validation LLM - Sébastien Lecornu\",
    \"start_urls\": $START_URLS,
    \"words\": [\"lecornu\", \"ministre\", \"gouvernement\"]
  }")

LAND_ID=$(echo "$LAND_RESULT" | jq -r '.id')

if [ -z "$LAND_ID" ] || [ "$LAND_ID" == "null" ]; then
  echo "❌ Failed to create land"
  echo "$LAND_RESULT" | jq '.'
  exit 1
fi

echo "✅ Land created successfully:"
echo "   - ID: $LAND_ID"
echo "   - Name: $LAND_NAME"
echo ""

# Launch crawl with LLM validation
echo "🕷️ Launching crawl with LLM validation..."
echo "   📝 Parameters: limit=5, enable_llm=true"

CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 5,
    "enable_llm": true
  }')

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
CELERY_TASK_ID=$(echo "$CRAWL_RESULT" | jq -r '.celery_task_id')

if [ -z "$JOB_ID" ] || [ "$JOB_ID" == "null" ]; then
  echo "❌ Failed to launch crawl"
  echo "$CRAWL_RESULT" | jq '.'
  exit 1
fi

echo "✅ Crawl lancé:"
echo "   - JOB_ID: $JOB_ID"
echo "   - CELERY_TASK_ID: $CELERY_TASK_ID"
echo ""

# Wait for crawl to complete
echo "⏳ Waiting for crawl to complete (checking DB)..."
MAX_WAIT=120
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
  # Check job status in database
  JOB_STATUS=$(docker compose exec -T db psql -U mwi_user -d mwi_db -t -A -c "
    SELECT status FROM crawl_jobs WHERE id = ${JOB_ID};
  " 2>/dev/null | tr -d '[:space:]')

  if [ "$JOB_STATUS" == "completed" ] || [ "$JOB_STATUS" == "failed" ]; then
    echo ""
    echo "✅ Crawl finished with status: $JOB_STATUS"
    break
  fi

  echo -n "."
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo ""
  echo "⚠️ Timeout waiting for crawl to complete"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📊 RESULTS - LLM Validation"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Get crawled expressions from database
EXPRESSIONS=$(docker compose exec -T db psql -U mwi_user -d mwi_db -t -A -F'|' -c "
SELECT
  id,
  url,
  title,
  relevance,
  validllm,
  validmodel,
  http_status
FROM expressions
WHERE land_id = ${LAND_ID}
  AND http_status IS NOT NULL
ORDER BY crawled_at DESC NULLS LAST
LIMIT 10;
" 2>/dev/null)

if [ -z "$EXPRESSIONS" ]; then
  echo "❌ No expressions found for land $LAND_ID"
else
  echo "Expression ID | URL | Title | Relevance | ValidLLM | Model | HTTP"
  echo "─────────────────────────────────────────────────────────────────"
  echo "$EXPRESSIONS" | while IFS='|' read -r id url title relevance validllm validmodel http_status; do
    # Truncate URL and title for display
    url_short=$(echo "$url" | cut -c1-50)
    title_short=$(echo "$title" | cut -c1-40)
    printf "%-13s | %-50s | %-40s | %-9s | %-8s | %-27s | %s\n" \
      "$id" "$url_short" "$title_short" "$relevance" "$validllm" "$validmodel" "$http_status"
  done
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📈 STATISTICS"
echo "════════════════════════════════════════════════════════════════"

# Count expressions by validation status
STATS=$(docker compose exec -T db psql -U mwi_user -d mwi_db -t -A -F'|' -c "
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN validllm = 'oui' THEN 1 ELSE 0 END) as validated,
  SUM(CASE WHEN validllm = 'non' THEN 1 ELSE 0 END) as rejected,
  SUM(CASE WHEN validllm IS NULL THEN 1 ELSE 0 END) as not_validated
FROM expressions
WHERE land_id = ${LAND_ID}
  AND http_status IS NOT NULL;
" 2>/dev/null)

IFS='|' read -r total validated rejected not_validated <<< "$STATS"

echo "Total crawled: $total"
echo "✅ Validated (oui): $validated"
echo "❌ Rejected (non): $rejected"
echo "⚠️ Not validated: $not_validated"

if [ "$total" -gt 0 ]; then
  validation_rate=$(echo "scale=2; $validated * 100 / $total" | bc)
  echo "Validation rate: ${validation_rate}%"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📋 CELERY LOGS (LLM validation)"
echo "════════════════════════════════════════════════════════════════"

# Show Celery logs for LLM validation
docker logs mywebclient-celery_worker-1 --tail=100 2>&1 | grep -i "\[LLM\]" || echo "No [LLM] logs found"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ Test completed for land: $LAND_NAME (ID: $LAND_ID)"
echo "════════════════════════════════════════════════════════════════"
