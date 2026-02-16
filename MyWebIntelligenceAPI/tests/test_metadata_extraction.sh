#!/bin/bash

# Script pour tester l'extraction de métadonnées et du contenu HTML
# Créé suite aux modifications du 14 octobre 2025

# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

echo "✅ Token obtained"
echo ""

# Create a test land with timestamp
LAND_NAME="MetadataTest_$(date +%Y%m%d_%H%M%S)"
echo "Creating test land '$LAND_NAME'..."
LAND_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$LAND_NAME\",\"description\":\"Test metadata extraction\",\"words\":[\"test\"],\"start_urls\":[\"https://example.com\"]}")

LAND_ID=$(echo "$LAND_RESPONSE" | jq -r '.id')

if [ "$LAND_ID" == "null" ] || [ -z "$LAND_ID" ]; then
  echo "❌ Failed to create land"
  echo "$LAND_RESPONSE" | jq '.'
  exit 1
fi

echo "✅ Land created with ID: $LAND_ID"
echo ""

# Start a crawl
echo "Starting crawl for land $LAND_ID..."
CRAWL_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/$LAND_ID/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 1, "depth": 1}')

JOB_ID=$(echo "$CRAWL_RESPONSE" | jq -r '.job_id')

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
  echo "❌ Failed to start crawl"
  echo "$CRAWL_RESPONSE" | jq '.'
  exit 1
fi

echo "✅ Crawl started with job ID: $JOB_ID"
echo ""

# Wait for crawl to complete
echo "Waiting for crawl to complete (checking every 2 seconds)..."
MAX_WAIT=30
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
  sleep 2
  WAITED=$((WAITED + 2))

  JOB_STATUS=$(curl -s -X GET "http://localhost:8000/api/v1/jobs/$JOB_ID" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')

  echo "Job status: $JOB_STATUS (waited ${WAITED}s)"

  if [ "$JOB_STATUS" == "completed" ]; then
    echo "✅ Crawl completed!"
    break
  fi

  if [ "$JOB_STATUS" == "failed" ]; then
    echo "❌ Crawl failed"
    exit 1
  fi
done

if [ $WAITED -ge $MAX_WAIT ]; then
  echo "⚠️  Crawl still running after ${MAX_WAIT}s, continuing anyway..."
fi

echo ""

# Get expressions for this land
echo "Fetching expressions for land $LAND_ID..."
EXPRESSIONS=$(curl -s -X GET "http://localhost:8000/api/v1/lands/$LAND_ID/expressions?page=1&per_page=5" \
  -H "Authorization: Bearer $TOKEN")

# Check the first expression
FIRST_EXPR=$(echo "$EXPRESSIONS" | jq '.items[0]')

if [ "$FIRST_EXPR" == "null" ]; then
  echo "❌ No expressions found"
  exit 1
fi

echo ""
echo "========================================="
echo "First Expression Analysis"
echo "========================================="

EXPR_ID=$(echo "$FIRST_EXPR" | jq -r '.id')
EXPR_URL=$(echo "$FIRST_EXPR" | jq -r '.url')
EXPR_TITLE=$(echo "$FIRST_EXPR" | jq -r '.title')
EXPR_DESC=$(echo "$FIRST_EXPR" | jq -r '.description')
EXPR_KEYWORDS=$(echo "$FIRST_EXPR" | jq -r '.keywords')

echo "Expression ID: $EXPR_ID"
echo "URL: $EXPR_URL"
echo "Title: $EXPR_TITLE"
echo "Description: $EXPR_DESC"
echo "Keywords: $EXPR_KEYWORDS"
echo ""

# Export to JSON to check the 'content' field
echo "Exporting expression to JSON to check 'content' field..."
EXPORT_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/export/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"land_id\": $LAND_ID, \"depth\": 1, \"minrel\": 0}")

EXPORT_JOB_ID=$(echo "$EXPORT_RESPONSE" | jq -r '.job_id')

echo "Export job ID: $EXPORT_JOB_ID"

# Wait a bit for export
sleep 3

# Get the export file URL
EXPORT_JOB=$(curl -s -X GET "http://localhost:8000/api/v1/jobs/$EXPORT_JOB_ID" \
  -H "Authorization: Bearer $TOKEN")

EXPORT_FILE=$(echo "$EXPORT_JOB" | jq -r '.result.file_path // .result.output_file // empty')

if [ -n "$EXPORT_FILE" ] && [ "$EXPORT_FILE" != "null" ]; then
  echo "✅ Export file: $EXPORT_FILE"

  # Try to read the file from inside the container
  docker exec mywebintelligenceapi cat "$EXPORT_FILE" 2>/dev/null | jq '.[0] | {title, description, keywords, content: (.content[:200])}' 2>/dev/null || echo "⚠️  Could not read export file"
else
  echo "⚠️  Export file not available yet"
fi

echo ""
echo "========================================="
echo "Summary"
echo "========================================="
echo "✅ Land created: $LAND_ID"
echo "✅ Crawl job: $JOB_ID"
echo "✅ Expressions found: $(echo "$EXPRESSIONS" | jq '.total // 0')"
echo ""

if [ "$EXPR_TITLE" != "null" ] && [ -n "$EXPR_TITLE" ]; then
  echo "✅ Title extraction: WORKING"
else
  echo "⚠️  Title extraction: EMPTY"
fi

if [ "$EXPR_DESC" != "null" ] && [ -n "$EXPR_DESC" ]; then
  echo "✅ Description extraction: WORKING"
else
  echo "⚠️  Description extraction: EMPTY"
fi

echo ""
echo "Test completed!"
