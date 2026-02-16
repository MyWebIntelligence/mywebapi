#!/bin/bash

# Script de test pour vérifier la détection de langue après les corrections

echo "=========================================="
echo "Test de détection de langue - Corrections"
echo "=========================================="

# Tester la détection de langue avec Python
echo ""
echo "1. Test direct de la fonction detect_language()"
echo "------------------------------------------------"

docker exec -i mywebintelligenceapi python3 << 'PYTHON_EOF'
import sys
sys.path.insert(0, '/app')

from app.utils.text_utils import detect_language, analyze_text_metrics

# Test 1: Texte français
text_fr = """
La détection de langue est une fonctionnalité essentielle pour notre système.
Nous utilisons langdetect qui est basé sur le détecteur de Google.
Cette bibliothèque supporte plus de 55 langues différentes.
"""

print("Test 1 - Texte français:")
print(f"  Texte: {text_fr[:80]}...")
lang_fr = detect_language(text_fr)
print(f"  Langue détectée: {lang_fr}")

# Test 2: Texte anglais
text_en = """
Language detection is an essential feature for our system.
We use langdetect which is based on Google's language detector.
This library supports more than 55 different languages.
"""

print("\nTest 2 - Texte anglais:")
print(f"  Texte: {text_en[:80]}...")
lang_en = detect_language(text_en)
print(f"  Langue détectée: {lang_en}")

# Test 3: Texte court (fallback)
text_short = "Bonjour le monde et merci pour tout"

print("\nTest 3 - Texte court (fallback):")
print(f"  Texte: {text_short}")
lang_short = detect_language(text_short)
print(f"  Langue détectée: {lang_short}")

# Test 4: Texte avec analyze_text_metrics
print("\nTest 4 - analyze_text_metrics():")
metrics = analyze_text_metrics(text_fr)
print(f"  word_count: {metrics.get('word_count')}")
print(f"  language: {metrics.get('language')}")

print("\n✓ Tests de détection de langue terminés")
PYTHON_EOF

echo ""
echo "2. Test de crawl réel avec détection de langue"
echo "------------------------------------------------"

# Utiliser une expression existante pour re-crawler
EXPRESSION_ID=$(docker exec mywebclient-db-1 psql -U mywebintelligence -d mywebintelligence -t -c "SELECT id FROM expressions WHERE readable IS NOT NULL AND language IS NULL LIMIT 1;" | xargs)

if [ -z "$EXPRESSION_ID" ]; then
    echo "Aucune expression trouvée sans langue détectée. Recherche d'une expression avec langue..."
    EXPRESSION_ID=$(docker exec mywebclient-db-1 psql -U mywebintelligence -d mywebintelligence -t -c "SELECT id FROM expressions WHERE readable IS NOT NULL LIMIT 1;" | xargs)
fi

if [ -n "$EXPRESSION_ID" ]; then
    echo "Expression ID: $EXPRESSION_ID"

    # Réinitialiser approved_at pour forcer le re-crawl
    echo "Réinitialisation de l'expression pour re-crawl..."
    docker exec mywebclient-db-1 psql -U mywebintelligence -d mywebintelligence -c "UPDATE expressions SET approved_at = NULL, language = NULL WHERE id = $EXPRESSION_ID;"

    # Obtenir le land_id
    LAND_ID=$(docker exec mywebclient-db-1 psql -U mywebintelligence -d mywebintelligence -t -c "SELECT land_id FROM expressions WHERE id = $EXPRESSION_ID;" | xargs)

    echo "Re-crawl de l'expression $EXPRESSION_ID (Land: $LAND_ID)..."

    # Lancer le crawl via l'API
    docker exec mywebintelligenceapi curl -X POST "http://localhost:8000/api/lands/$LAND_ID/crawl?limit=1" \
        -H "Content-Type: application/json" 2>/dev/null | python3 -m json.tool

    # Vérifier la langue détectée
    echo ""
    echo "Vérification de la langue détectée:"
    docker exec mywebclient-db-1 psql -U mywebintelligence -d mywebintelligence -c "SELECT id, url, language, word_count FROM expressions WHERE id = $EXPRESSION_ID;"

else
    echo "❌ Aucune expression trouvée pour le test"
fi

echo ""
echo "=========================================="
echo "Test terminé"
echo "=========================================="
