#!/bin/bash

echo "=========================================="
echo "Test rapide de détection de langue"
echo "=========================================="

# Statistiques avant
echo "1. Statistiques AVANT corrections:"
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
SELECT
    COUNT(*) as total,
    COUNT(readable) as with_readable,
    COUNT(language) as with_language,
    COUNT(CASE WHEN readable IS NOT NULL AND language IS NULL THEN 1 END) as readable_no_lang
FROM expressions;"

# Prendre une expression avec readable mais sans langue
EXPRESSION_ID=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c "SELECT id FROM expressions WHERE readable IS NOT NULL AND language IS NULL LIMIT 1;" | xargs)

if [ -n "$EXPRESSION_ID" ]; then
    echo ""
    echo "2. Expression sélectionnée: $EXPRESSION_ID"

    # Afficher les détails
    docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
    SELECT
        id,
        LEFT(url, 60) as url,
        language,
        word_count,
        LENGTH(readable) as readable_length
    FROM expressions
    WHERE id = $EXPRESSION_ID;"

    # Obtenir le land_id
    LAND_ID=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c "SELECT land_id FROM expressions WHERE id = $EXPRESSION_ID;" | xargs)

    # Réinitialiser pour forcer le re-crawl
    echo ""
    echo "3. Réinitialisation de l'expression pour re-crawl..."
    docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "UPDATE expressions SET approved_at = NULL WHERE id = $EXPRESSION_ID;"

    # Lancer le crawl
    echo ""
    echo "4. Lancement du crawl (Land: $LAND_ID, Expression: $EXPRESSION_ID)..."
    docker exec mywebintelligenceapi curl -s -X POST "http://localhost:8000/api/lands/$LAND_ID/crawl?limit=1" \
        -H "Content-Type: application/json" | python3 -m json.tool

    # Vérifier le résultat
    echo ""
    echo "5. Résultat APRÈS crawl:"
    docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
    SELECT
        id,
        LEFT(url, 60) as url,
        language,
        word_count,
        LENGTH(readable) as readable_length
    FROM expressions
    WHERE id = $EXPRESSION_ID;"

    # Vérifier les logs
    echo ""
    echo "6. Logs de détection de langue (dernières 20 lignes):"
    docker logs mywebintelligenceapi 2>&1 | grep -i "language" | tail -20

else
    echo "❌ Aucune expression trouvée pour le test"
fi

echo ""
echo "=========================================="
echo "Test terminé"
echo "=========================================="
