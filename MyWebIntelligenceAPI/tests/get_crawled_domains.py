#!/usr/bin/env python3
"""
Script pour récupérer et afficher les domaines crawlés d'un land.

Usage:
    python tests/get_crawled_domains.py <land_id> [limit]
    docker exec mywebintelligenceapi python tests/get_crawled_domains.py 69 10

Arguments:
    land_id: ID du land
    limit: Nombre max de domaines à afficher (défaut: 10)
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import get_sync_db_context
from app.db.models import Domain
from sqlalchemy import desc


def get_crawled_domains(land_id: int, limit: int = 10):
    """Récupère les domaines crawlés d'un land"""
    with get_sync_db_context() as db:
        # Récupérer les domaines fetchés
        domains = db.query(Domain).filter(
            Domain.land_id == land_id,
            Domain.fetched_at.isnot(None)
        ).order_by(
            desc(Domain.fetched_at)
        ).limit(limit).all()

        return domains


def display_domains(domains, land_id: int):
    """Affiche les domaines de manière formatée"""
    print(f"\n{'=' * 80}")
    print(f"🌐 DOMAINES CRAWLÉS - Land ID: {land_id}")
    print(f"{'=' * 80}\n")

    if not domains:
        print("❌ Aucun domaine crawlé trouvé pour ce land.")
        print("\n💡 Conseils:")
        print("   - Vérifiez que le land_id est correct")
        print("   - Lancez un crawl avec: ./tests/test-domain-crawl.sh")
        print("   - Attendez la fin du job de crawl\n")
        return

    for i, domain in enumerate(domains, 1):
        # Symbole selon le statut HTTP (http_status est VARCHAR)
        try:
            http_code = int(domain.http_status) if domain.http_status else 0
        except (ValueError, TypeError):
            http_code = 0

        if http_code == 200:
            status_symbol = "✅"
        elif http_code >= 400:
            status_symbol = "❌"
        elif http_code >= 300:
            status_symbol = "🔄"
        else:
            status_symbol = "⚠️"

        print(f"{i}. {status_symbol} {domain.name}")
        print(f"   {'─' * 70}")
        print(f"   ID:              {domain.id}")
        print(f"   Titre:           {domain.title or '(non défini)'}")
        print(f"   Description:     {(domain.description or '(non défini)')[:80]}")
        if domain.description and len(domain.description) > 80:
            print(f"                    ...")
        print(f"   Mots-clés:       {domain.keywords or '(non défini)'}")
        print(f"   Langue:          {domain.language or '(non défini)'}")
        print(f"   Statut HTTP:     {domain.http_status or 'N/A'}")
        print(f"   Crawlé le:       {domain.fetched_at.strftime('%Y-%m-%d %H:%M:%S') if domain.fetched_at else 'N/A'}")
        print(f"   Dernier crawl:   {domain.last_crawled.strftime('%Y-%m-%d %H:%M:%S') if domain.last_crawled else 'N/A'}")

        print()

    print(f"{'=' * 80}")
    print(f"Total affiché: {len(domains)} domaine(s)")
    print(f"{'=' * 80}\n")


def export_to_json(domains, land_id: int, filename: str = None):
    """Exporte les domaines en JSON"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"domains_land{land_id}_{timestamp}.json"

    domains_data = []
    for domain in domains:
        domain_dict = {
            "id": domain.id,
            "land_id": domain.land_id,
            "name": domain.name,
            "title": domain.title,
            "description": domain.description,
            "keywords": domain.keywords,
            "language": domain.language,
            "http_status": domain.http_status,
            "fetched_at": domain.fetched_at.isoformat() if domain.fetched_at else None,
            "last_crawled": domain.last_crawled.isoformat() if domain.last_crawled else None,
        }

        domains_data.append(domain_dict)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(domains_data, f, indent=2, ensure_ascii=False)

    return filename


def get_stats(land_id: int):
    """Récupère les statistiques des domaines d'un land"""
    with get_sync_db_context() as db:
        total = db.query(Domain).filter(Domain.land_id == land_id).count()
        fetched = db.query(Domain).filter(
            Domain.land_id == land_id,
            Domain.fetched_at.isnot(None)
        ).count()

        # Stats par statut HTTP (http_status est VARCHAR dans la DB)
        http_200 = db.query(Domain).filter(
            Domain.land_id == land_id,
            Domain.http_status == '200'
        ).count()

        http_4xx = db.query(Domain).filter(
            Domain.land_id == land_id,
            Domain.http_status.like('4%')
        ).count()

        http_5xx = db.query(Domain).filter(
            Domain.land_id == land_id,
            Domain.http_status.like('5%')
        ).count()

        return {
            "total": total,
            "fetched": fetched,
            "unfetched": total - fetched,
            "success_200": http_200,
            "client_error_4xx": http_4xx,
            "server_error_5xx": http_5xx,
            "success_rate": round((http_200 / fetched * 100) if fetched > 0 else 0, 2)
        }


def display_stats(stats):
    """Affiche les statistiques"""
    print(f"\n📊 STATISTIQUES")
    print(f"{'─' * 40}")
    print(f"Total domaines:       {stats['total']}")
    print(f"Domaines fetchés:     {stats['fetched']} ({stats['fetched']/stats['total']*100:.1f}%)" if stats['total'] > 0 else "Domaines fetchés:     0")
    print(f"Non fetchés:          {stats['unfetched']}")
    print(f"")
    print(f"Succès (200):         {stats['success_200']}")
    print(f"Erreurs client (4xx): {stats['client_error_4xx']}")
    print(f"Erreurs serveur (5xx):{stats['server_error_5xx']}")
    print(f"Taux de succès:       {stats['success_rate']}%")
    print(f"{'─' * 40}\n")


def main():
    if len(sys.argv) < 2:
        print("❌ Usage: python get_crawled_domains.py <land_id> [limit]")
        print("\nExemple:")
        print("  python tests/get_crawled_domains.py 69 10")
        print("  docker exec mywebintelligenceapi python tests/get_crawled_domains.py 69 10")
        sys.exit(1)

    try:
        land_id = int(sys.argv[1])
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    except ValueError:
        print("❌ Erreur: land_id et limit doivent être des nombres entiers")
        sys.exit(1)

    # Options
    export_json = "--json" in sys.argv or "-j" in sys.argv
    show_stats = "--stats" in sys.argv or "-s" in sys.argv or True  # Stats par défaut

    try:
        # Récupérer les domaines
        domains = get_crawled_domains(land_id, limit)

        # Afficher les statistiques
        if show_stats:
            stats = get_stats(land_id)
            display_stats(stats)

        # Afficher les domaines
        display_domains(domains, land_id)

        # Exporter en JSON si demandé
        if export_json and domains:
            filename = export_to_json(domains, land_id)
            print(f"✅ Domaines exportés dans: {filename}\n")

        # Message de succès
        if domains:
            print(f"✅ Successfully retrieved {len(domains)} domain(s).\n")

            # Suggestions
            print("💡 Options supplémentaires:")
            print("   --json, -j     Exporter en JSON")
            print("   --stats, -s    Afficher uniquement les stats")
            print()
            print("   Exemple: python tests/get_crawled_domains.py 69 10 --json")
            print()

    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
