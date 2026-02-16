#!/bin/bash

# Test pour vérifier que les nouveaux champs sont bien remplis

echo "🔍 Testing new fields extraction..."
echo ""

# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

echo "✅ Authenticated"

# Use land 21 and start a small crawl
LAND_ID=21

echo "Starting crawl for land $LAND_ID (max 3 pages)..."
CRAWL_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/$LAND_ID/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 3, "depth": 0}')

JOB_ID=$(echo "$CRAWL_RESPONSE" | jq -r '.job_id')

echo "✅ Crawl job started: $JOB_ID"
echo "⏳ Waiting 20 seconds for crawl to process..."
sleep 20

echo ""
echo "📊 Checking database for NEW fields..."

# Check the most recent expressions with readable content
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
SELECT
    id,
    LEFT(url, 60) as url_short,
    LEFT(title, 40) as title_short,
    word_count,
    reading_time,
    canonical_url IS NOT NULL as has_canonical,
    LEFT(content_type, 20) as content_type_short,
    content_length,
    LENGTH(COALESCE(readable, '')) as readable_len
FROM expressions
WHERE land_id = $LAND_ID
  AND crawled_at > NOW() - INTERVAL '30 seconds'
  AND readable IS NOT NULL
  AND LENGTH(readable) > 100
ORDER BY crawled_at DESC
LIMIT 5;
"

echo ""
echo "✅ Test completed!"
