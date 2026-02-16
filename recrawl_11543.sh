#!/bin/bash

# Script pour tester la détection de langue en recrawlant l'expression 11543

echo "==================================================="
echo "Test de détection de langue - Expression 11543"
echo "==================================================="
echo ""

# 1. Login
echo "1. Connexion..."
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Erreur d'authentification"
    exit 1
fi

echo "✅ Token obtenu"
echo ""

# 2. Recrawler l'expression
echo "2. Recrawl de l'expression 11543..."
RECRAWL_RESULT=$(curl -s -X POST "http://localhost:8000/api/v2/lands/21/expressions/11543/recrawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "Résultat du recrawl:"
echo "$RECRAWL_RESULT" | jq '.'
echo ""

# Attendre quelques secondes pour le traitement
echo "3. Attente de 10 secondes pour le traitement..."
sleep 10

# 3. Vérifier les champs de l'expression
echo "4. Vérification de l'expression 11543..."
EXPR_DATA=$(curl -s -X GET "http://localhost:8000/api/v2/lands/21/expressions/11543" \
  -H "Authorization: Bearer $TOKEN")

echo "==================================================="
echo "Champs extraits:"
echo "==================================================="

# Extraire les champs clés
LANGUAGE=$(echo "$EXPR_DATA" | jq -r '.language // "NULL"')
WORD_COUNT=$(echo "$EXPR_DATA" | jq -r '.word_count // "NULL"')
READING_TIME=$(echo "$EXPR_DATA" | jq -r '.reading_time // "NULL"')
CANONICAL_URL=$(echo "$EXPR_DATA" | jq -r '.canonical_url // "NULL"')
CONTENT_TYPE=$(echo "$EXPR_DATA" | jq -r '.content_type // "NULL"')
CONTENT_LENGTH=$(echo "$EXPR_DATA" | jq -r '.content_length // "NULL"')
CONTENT_SIZE=$(echo "$EXPR_DATA" | jq -r '.content // "NULL"' | wc -c)

echo "language:       $LANGUAGE"
echo "word_count:     $WORD_COUNT"
echo "reading_time:   $READING_TIME"
echo "canonical_url:  $CANONICAL_URL"
echo "content_type:   $CONTENT_TYPE"
echo "content_length: $CONTENT_LENGTH"
echo "content size:   $CONTENT_SIZE chars"
echo ""

# Vérification
echo "==================================================="
echo "Résultat:"
echo "==================================================="

ERRORS=0

if [ "$LANGUAGE" == "NULL" ]; then
    echo "❌ language est NULL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ language détectée: $LANGUAGE"
fi

if [ "$WORD_COUNT" == "NULL" ] || [ "$WORD_COUNT" == "0" ]; then
    echo "❌ word_count est NULL ou 0"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ word_count: $WORD_COUNT"
fi

if [ "$READING_TIME" == "NULL" ]; then
    echo "❌ reading_time est NULL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ reading_time: $READING_TIME min"
fi

if [ "$CONTENT_SIZE" -lt 100 ]; then
    echo "❌ content est vide ou trop petit"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ content présent: $CONTENT_SIZE chars"
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "✅ TOUS LES TESTS PASSÉS - Détection de langue fonctionne!"
else
    echo "❌ $ERRORS erreur(s) détectée(s)"
fi
echo "==================================================="
