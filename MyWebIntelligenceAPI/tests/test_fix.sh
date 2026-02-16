#!/bin/bash

# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

echo "✅ Token obtained"
echo ""

# Create a land with a unique name and the word "lecornu" (which already exists in DB)
LAND_NAME="LecornuTest_$(date +%Y%m%d_%H%M%S)"
echo "Creating land '$LAND_NAME' with word 'lecornu'..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$LAND_NAME\",\"description\":\"Test with existing word\",\"words\":[\"lecornu\"]}")

echo ""
echo "Response:"
echo "$RESPONSE" | jq '.'

LAND_ID=$(echo "$RESPONSE" | jq -r '.id')
echo ""
if [ "$LAND_ID" != "null" ] && [ -n "$LAND_ID" ]; then
  echo "✅ SUCCESS! Land created with ID: $LAND_ID"
else
  echo "❌ FAILED to create land"
  echo "Error:"
  echo "$RESPONSE" | jq -r '.detail'
fi
