#!/bin/bash

echo "=========================================="
echo "Test de correction language → lang"
echo "=========================================="

# Stats AVANT
echo ""
echo "1. Statistiques AVANT correction:"
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db << 'SQL'
SELECT
    COUNT(*) FILTER (WHERE readable IS NOT NULL) as with_readable,
    COUNT(*) FILTER (WHERE language IS NOT NULL) as with_language,
    COUNT(*) FILTER (WHERE readable IS NOT NULL AND language IS NULL) as readable_no_lang
FROM expressions;
SQL

# Prendre une expression
EXPR_ID=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c "SELECT id FROM expressions WHERE readable IS NOT NULL LIMIT 1;" | xargs)

if [ -z "$EXPR_ID" ]; then
    echo "❌ Aucune expression trouvée"
    exit 1
fi

echo ""
echo "2. Expression sélectionnée: $EXPR_ID"

# Afficher l'état AVANT
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db << SQL
SELECT
    id,
    LEFT(url, 50) as url,
    language,
    word_count,
    approved_at IS NOT NULL as is_approved
FROM expressions
WHERE id = $EXPR_ID;
SQL

# Réinitialiser
echo ""
echo "3. Réinitialisation (approved_at = NULL, language = NULL)..."
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "UPDATE expressions SET approved_at = NULL, language = NULL WHERE id = $EXPR_ID;"

# Obtenir le land_id
LAND_ID=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c "SELECT land_id FROM expressions WHERE id = $EXPR_ID;" | xargs)

echo ""
echo "4. Test Python direct du crawler..."

# Lancer un test Python qui fait le crawl
docker exec mywebintelligenceapi python3 << PYTHON_EOF
import sys
sys.path.insert(0, '/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.crawler_engine_sync import SyncCrawlerEngine
from app.db.models import Expression

engine = create_engine("postgresql://mwi_user:mwipassword@db:5432/mwi_db")
SessionMaker = sessionmaker(bind=engine)
db: Session = SessionMaker()

try:
    expr = db.query(Expression).filter(Expression.id == $EXPR_ID).first()
    if not expr:
        print(f"Expression {$EXPR_ID} not found")
        sys.exit(1)

    print(f"Crawling expression {expr.id}: {expr.url}")
    print(f"  AVANT: lang={expr.lang}, word_count={expr.word_count}")

    crawler = SyncCrawlerEngine(db)
    status = crawler.crawl_expression(expr, analyze_media=False)
    db.commit()

    # Refresh pour voir les changements
    db.refresh(expr)

    print(f"  APRÈS: lang={expr.lang}, word_count={expr.word_count}")
    print(f"  Status code: {status}")

    if expr.lang:
        print(f"\\n✅ SUCCÈS ! Langue détectée: '{expr.lang}'")
    else:
        print(f"\\n⚠️ Langue toujours NULL")

except Exception as e:
    print(f"Erreur: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
PYTHON_EOF

echo ""
echo "5. Vérification finale dans la DB:"
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db << SQL
SELECT
    id,
    LEFT(url, 50) as url,
    language,
    word_count,
    approved_at IS NOT NULL as is_approved
FROM expressions
WHERE id = $EXPR_ID;
SQL

echo ""
echo "6. Logs de détection de langue:"
docker logs mywebintelligenceapi 2>&1 | grep -i "language detection" | tail -5

echo ""
echo "=========================================="
echo "Test terminé"
echo "=========================================="
