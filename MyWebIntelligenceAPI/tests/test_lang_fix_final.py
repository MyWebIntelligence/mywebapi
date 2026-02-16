#!/usr/bin/env python3
"""
Test final pour vérifier que la correction 'language' → 'lang' fonctionne.
Ce script teste directement la logique du crawler sans passer par l'API.
"""

import sys
sys.path.insert(0, '/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.crawler_engine_sync import SyncCrawlerEngine
from app.db.models import Expression
import os

# Configuration DB
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mwi_user:mwipassword@db:5432/mwi_db")

print("=" * 60)
print("Test final de correction 'language' → 'lang'")
print("=" * 60)

# Créer une session DB
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # 1. Trouver une expression avec readable mais sans langue
    print("\n1. Recherche d'une expression à tester...")
    expr = db.query(Expression).filter(
        Expression.readable.isnot(None),
        Expression.lang.is_(None)
    ).first()

    if not expr:
        print("   Aucune expression trouvée sans langue. Recherche d'une expression avec langue...")
        expr = db.query(Expression).filter(
            Expression.readable.isnot(None)
        ).first()

    if not expr:
        print("   ❌ Aucune expression avec readable trouvée")
        sys.exit(1)

    print(f"   ✓ Expression trouvée: ID={expr.id}")
    print(f"     URL: {expr.url[:60]}...")
    print(f"     Langue AVANT: {expr.lang}")
    print(f"     Word count AVANT: {expr.word_count}")

    # 2. Réinitialiser pour forcer le re-crawl
    print("\n2. Réinitialisation de l'expression...")
    expr.approved_at = None
    expr.lang = None
    db.commit()
    print("   ✓ Expression réinitialisée")

    # 3. Crawler l'expression
    print("\n3. Re-crawl de l'expression...")
    crawler = SyncCrawlerEngine(db)

    # Fetch de nouveau l'expression pour avoir l'objet frais
    expr = db.query(Expression).filter(Expression.id == expr.id).first()

    try:
        status_code = crawler.crawl_expression(expr, analyze_media=False)
        db.commit()
        print(f"   ✓ Crawl terminé avec status_code: {status_code}")
    except Exception as e:
        print(f"   ❌ Erreur pendant le crawl: {e}")
        db.rollback()
        raise

    # 4. Vérifier le résultat
    print("\n4. Vérification du résultat...")
    db.refresh(expr)

    print(f"   Langue APRÈS: {expr.lang}")
    print(f"   Word count APRÈS: {expr.word_count}")
    print(f"   Reading time: {expr.reading_time}")

    if expr.lang:
        print(f"\n   ✅ SUCCÈS ! La langue a été détectée et enregistrée: '{expr.lang}'")
    else:
        print(f"\n   ⚠️  La langue est toujours NULL")
        print(f"   Vérifiez les logs pour voir pourquoi la détection a échoué")

    # 5. Statistiques globales
    print("\n5. Statistiques globales:")
    from sqlalchemy import func
    stats = db.query(
        func.count(Expression.id).label('total'),
        func.count(Expression.readable).label('with_readable'),
        func.count(Expression.lang).label('with_lang')
    ).filter(
        Expression.readable.isnot(None)
    ).first()

    print(f"   Total expressions avec readable: {stats.with_readable}")
    print(f"   Expressions avec langue détectée: {stats.with_lang}")
    percentage = (stats.with_lang / stats.with_readable * 100) if stats.with_readable > 0 else 0
    print(f"   Pourcentage: {percentage:.1f}%")

finally:
    db.close()

print("\n" + "=" * 60)
print("Test terminé")
print("=" * 60)
