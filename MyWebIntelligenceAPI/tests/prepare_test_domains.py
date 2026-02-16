#!/usr/bin/env python3
"""
Script pour préparer des domaines de test dans un land.
Extrait les domaines des liens existants ou crée des domaines de test.

Usage:
    python tests/prepare_test_domains.py <land_id>
    docker exec mywebintelligenceapi python tests/prepare_test_domains.py 69
"""

import sys
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.base import get_sync_db
from app.db.models import Domain, Land, Link
from sqlalchemy import select


def extract_domain_from_url(url: str) -> str:
    """Extrait le domaine d'une URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        # Retirer www. si présent
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain.lower()
    except:
        return None


def create_domains_from_links(land_id: int):
    """Crée des domaines à partir des liens existants d'un land"""
    with get_sync_db() as db:
        # Vérifier que le land existe
        land = db.query(Land).filter(Land.id == land_id).first()
        if not land:
            print(f"❌ Land {land_id} not found")
            return 0

        print(f"📊 Land: {land.name} (ID: {land_id})")

        # Récupérer les liens du land
        links = db.query(Link).join(Link.expression).filter(
            Link.expression.has(land_id=land_id)
        ).limit(100).all()

        print(f"   Found {len(links)} links")

        if not links:
            print("⚠️  No links found. Creating default test domains...")
            return create_default_test_domains(land_id, db)

        # Extraire les domaines uniques
        domains_set = set()
        for link in links:
            domain_name = extract_domain_from_url(link.url)
            if domain_name and domain_name not in domains_set:
                domains_set.add(domain_name)

        print(f"   Extracted {len(domains_set)} unique domains")

        # Créer les domaines en DB
        created_count = 0
        for domain_name in domains_set:
            # Vérifier si le domaine existe déjà
            existing = db.query(Domain).filter(
                Domain.name == domain_name,
                Domain.land_id == land_id
            ).first()

            if not existing:
                domain = Domain(
                    name=domain_name,
                    land_id=land_id,
                    created_at=datetime.now()
                )
                db.add(domain)
                created_count += 1

        db.commit()

        print(f"✅ Created {created_count} new domains")
        return created_count


def create_default_test_domains(land_id: int, db):
    """Crée des domaines de test par défaut"""
    test_domains = [
        "example.com",
        "wikipedia.org",
        "github.com",
        "stackoverflow.com",
        "reddit.com",
        "mozilla.org",
        "python.org",
        "npmjs.com",
        "docker.com",
        "kubernetes.io"
    ]

    created_count = 0
    for domain_name in test_domains:
        # Vérifier si existe
        existing = db.query(Domain).filter(
            Domain.name == domain_name,
            Domain.land_id == land_id
        ).first()

        if not existing:
            domain = Domain(
                name=domain_name,
                land_id=land_id,
                created_at=datetime.now()
            )
            db.add(domain)
            created_count += 1

    db.commit()
    return created_count


def show_domains(land_id: int):
    """Affiche les domaines du land"""
    with get_sync_db() as db:
        domains = db.query(Domain).filter(
            Domain.land_id == land_id
        ).all()

        print(f"\n📋 Domaines du land {land_id}:")
        print("─" * 60)

        if not domains:
            print("   (aucun)")
        else:
            for i, domain in enumerate(domains, 1):
                status = "✅" if domain.fetched_at else "⏳"
                http = f"({domain.http_status})" if domain.http_status else ""
                print(f"   {i}. {status} {domain.name} {http}")

        print("─" * 60)
        print(f"Total: {len(domains)} domaine(s)")

        unfetched = sum(1 for d in domains if not d.fetched_at)
        print(f"Non fetchés: {unfetched}")
        print()


def main():
    if len(sys.argv) < 2:
        print("❌ Usage: python prepare_test_domains.py <land_id>")
        print("\nExemple:")
        print("  python tests/prepare_test_domains.py 69")
        print("  docker exec mywebintelligenceapi python tests/prepare_test_domains.py 69")
        sys.exit(1)

    try:
        land_id = int(sys.argv[1])
    except ValueError:
        print("❌ Erreur: land_id doit être un nombre entier")
        sys.exit(1)

    print("🔧 Préparation des domaines de test\n")

    # Créer les domaines
    count = create_domains_from_links(land_id)

    # Afficher les résultats
    show_domains(land_id)

    if count > 0:
        print(f"✅ {count} domaine(s) créé(s) avec succès!")
        print(f"\n💡 Vous pouvez maintenant tester le domain crawl:")
        print(f"   ./MyWebIntelligenceAPI/tests/test-domain-crawl.sh {land_id} 5")
    else:
        print("ℹ️  Tous les domaines existent déjà")


if __name__ == "__main__":
    main()
