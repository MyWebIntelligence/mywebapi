#!/bin/bash

# Test pour vérifier que le champ 'content' (HTML brut) est bien sauvegardé

echo "🔍 Testing HTML content field storage..."
echo ""

# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

echo "✅ Authenticated"

# Use land 21 and start a small crawl
LAND_ID=21

echo "Starting crawl for land $LAND_ID (max 2 pages)..."
CRAWL_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/$LAND_ID/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 2, "depth": 0}')

JOB_ID=$(echo "$CRAWL_RESPONSE" | jq -r '.job_id')

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
  echo "❌ Failed to start crawl"
  echo "$CRAWL_RESPONSE" | jq '.'
  exit 1
fi

echo "✅ Crawl job started: $JOB_ID"
echo "⏳ Waiting 15 seconds for crawl to process..."
sleep 15

echo ""
echo "📊 Checking database for HTML content..."

# Check the most recent expressions
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
SELECT
    id,
    url,
    title,
    CASE
        WHEN content IS NULL THEN 'NULL'
        WHEN LENGTH(content) = 0 THEN 'EMPTY'
        WHEN content LIKE '%<html%' OR content LIKE '%<!DOCTYPE%' THEN 'HTML ✅'
        ELSE 'DATA'
    END as content_status,
    LENGTH(COALESCE(content, '')) as content_len,
    LENGTH(COALESCE(readable, '')) as readable_len,
    crawled_at
FROM expressions
WHERE land_id = $LAND_ID
  AND crawled_at > NOW() - INTERVAL '30 seconds'
ORDER BY crawled_at DESC
LIMIT 5;
"

echo ""
echo "📋 Checking worker logs for 'Storing HTML' messages..."
docker logs mywebclient-celery_worker-1 2>&1 | grep -E "(Storing HTML|No HTML content)" | tail -5

echo ""
echo "✅ Test completed!"
