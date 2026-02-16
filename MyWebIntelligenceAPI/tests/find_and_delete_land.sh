#!/bin/bash

# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

echo "✅ Token obtained"
echo ""

# List all lands to find the one with name "Lecornu202543"
echo "Searching for land 'Lecornu202543'..."
LANDS=$(curl -s -X GET "http://localhost:8000/api/v2/lands/?page=1&page_size=100" \
  -H "Authorization: Bearer $TOKEN")

EXISTING_LAND_ID=$(echo "$LANDS" | jq -r '.items[] | select(.name == "Lecornu202543") | .id')

if [ -z "$EXISTING_LAND_ID" ] || [ "$EXISTING_LAND_ID" == "null" ]; then
  echo "❌ Land 'Lecornu202543' not found"
  exit 1
fi

echo "✅ Found land with ID: $EXISTING_LAND_ID"
echo ""

# Delete the land
echo "Deleting land $EXISTING_LAND_ID..."
DELETE_RESPONSE=$(curl -s -X DELETE "http://localhost:8000/api/v2/lands/$EXISTING_LAND_ID" \
  -H "Authorization: Bearer $TOKEN")

echo "$DELETE_RESPONSE" | jq '.'
echo ""

# Now create the new land
echo "Creating new land 'Lecornu202543'..."
CREATE_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Lecornu202543","description":"Test gilets jaunes","words":["lecornu"]}')

NEW_LAND_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id')
echo "✅ New land created with ID: $NEW_LAND_ID"
echo ""
echo "Full response:"
echo "$CREATE_RESPONSE" | jq '.'
