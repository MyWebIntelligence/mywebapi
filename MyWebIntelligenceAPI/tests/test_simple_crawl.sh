#!/bin/bash

# Test simple : crawl avec validation LLM sur land 72
# Teste le crawl avec enable_llm=true et vérifie les champs valid_llm/valid_model

# Use land 72 (test_llm_giletsjaunes)
LAND_ID=72

echo "════════════════════════════════════════════════════════════════"
echo "🧪 TEST CRAWL + VALIDATION LLM (Land 72 - giletsjaunes)"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

echo "✅ Token obtained"
echo ""

# Get land info
LANDS=$(curl -s -X GET "http://localhost:8000/api/v2/lands/?page=1&page_size=100" \
  -H "Authorization: Bearer $TOKEN")

LAND_NAME=$(echo "$LANDS" | jq -r ".items[] | select(.id == $LAND_ID) | .name")

if [ -z "$LAND_NAME" ]; then
  echo "❌ Land $LAND_ID not found"
  exit 1
fi

echo "Using land: $LAND_NAME (ID: $LAND_ID)"
echo ""

# 🕷️ Launch crawl with LLM validation
echo "🕷️ Launching crawl with LLM validation..."
echo "   📝 Parameters: limit=3, enable_llm=true"

CRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 3,
    "enable_llm": true
  }')

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
CELERY_TASK_ID=$(echo "$CRAWL_RESULT" | jq -r '.celery_task_id')

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
  echo "❌ Failed to start crawl"
  echo "$CRAWL_RESULT" | jq '.'
  exit 1
fi

echo "✅ Crawl lancé:"
echo "   - JOB_ID: $JOB_ID"
echo "   - CELERY_TASK_ID: $CELERY_TASK_ID"
echo ""

# ⏳ Wait for crawl to complete
echo "⏳ Waiting for crawl to complete (checking DB)..."
for i in {1..40}; do
  sleep 3

  JOB_STATUS=$(docker compose exec -T db psql -U mwi_user -d mwi_db -t -A -c "
    SELECT status FROM crawl_jobs WHERE id = ${JOB_ID};
  " 2>/dev/null | tr -d '[:space:]')

  if [ "$JOB_STATUS" = "completed" ]; then
    echo ""
    echo "✅ Crawl completed after $((i * 3))s"
    break
  elif [ "$JOB_STATUS" = "failed" ]; then
    echo ""
    echo "❌ Crawl failed"
    docker compose exec -T db psql -U mwi_user -d mwi_db -c "
      SELECT error_message FROM crawl_jobs WHERE id = ${JOB_ID};
    "
    exit 1
  fi

  echo -n "."

  if [ $i -eq 40 ]; then
    echo ""
    echo "⚠️  Timeout after 120s"
  fi
done

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📊 RESULTS - LLM VALIDATION"
echo "════════════════════════════════════════════════════════════════"

# Get expressions with LLM validation from DB
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
ORDER BY crawled_at DESC NULLS LAST
LIMIT 10;
")

TOTAL_COUNT=0
VALIDATED_COUNT=0
REJECTED_COUNT=0
NO_VALIDATION_COUNT=0

if [ -n "$EXPRESSIONS" ]; then
    echo ""
    echo "📋 Recently crawled expressions:"
    echo ""

    while IFS='|' read -r id url title relevance valid_llm valid_model http_status; do
        TOTAL_COUNT=$((TOTAL_COUNT + 1))

        # Truncate for display
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
            echo "  ⚠️  LLM Validation: Not performed"
            NO_VALIDATION_COUNT=$((NO_VALIDATION_COUNT + 1))
        fi
        echo ""
    done <<< "$EXPRESSIONS"
else
    echo "⚠️  No expressions found"
fi

echo "════════════════════════════════════════════════════════════════"
echo "📊 STATISTICS"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Total expressions checked:      $TOTAL_COUNT"
echo "✅ Validated (oui):             $VALIDATED_COUNT"
echo "❌ Rejected (non):              $REJECTED_COUNT"
echo "⚠️  Without validation:         $NO_VALIDATION_COUNT"

if [ $TOTAL_COUNT -gt 0 ]; then
    VALIDATION_RATE=$(awk "BEGIN {printf \"%.1f\", (($VALIDATED_COUNT + $REJECTED_COUNT) / $TOTAL_COUNT) * 100}")
    echo "📈 Validation rate:             ${VALIDATION_RATE}%"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📝 Celery Logs (last LLM validations)"
echo "════════════════════════════════════════════════════════════════"
docker logs mywebclient-celery_worker-1 --tail=30 2>/dev/null | grep -i "\[LLM\]" || echo "No LLM logs found"

echo ""
echo "════════════════════════════════════════════════════════════════"
if [ $VALIDATED_COUNT -gt 0 ] || [ $REJECTED_COUNT -gt 0 ]; then
    echo "✅ TEST PASSED - LLM Validation is working!"
else
    echo "⚠️  WARNING - No LLM validations performed"
    echo "   Check OpenRouter configuration and Celery logs"
fi
echo "════════════════════════════════════════════════════════════════"
echo ""
