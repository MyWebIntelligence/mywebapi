#!/usr/bin/env python3
"""
Script de vérification rapide de la parité legacy.

Ce script effectue des vérifications de base pour s'assurer que toutes les fonctions
critiques sont présentes et fonctionnelles.

Usage:
    python scripts/verify_legacy_parity.py
"""

import sys
import importlib.util
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
script_dir = Path(__file__).parent
project_dir = script_dir.parent
sys.path.insert(0, str(project_dir))


def check_module_exists(module_path: str) -> bool:
    """Vérifie qu'un module existe."""
    try:
        spec = importlib.util.find_spec(module_path)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False


def check_function_exists(module_path: str, function_name: str) -> bool:
    """Vérifie qu'une fonction existe dans un module."""
    try:
        module = importlib.import_module(module_path)
        return hasattr(module, function_name)
    except (ModuleNotFoundError, AttributeError):
        return False


def verify_content_extractor():
    """Vérifie les fonctions du content_extractor."""
    print("\n🔍 Vérification de app.core.content_extractor...")

    checks = [
        ("Fonction resolve_url", "app.core.content_extractor", "resolve_url"),
        ("Fonction enrich_markdown_with_media", "app.core.content_extractor", "enrich_markdown_with_media"),
        ("Fonction extract_md_links", "app.core.content_extractor", "extract_md_links"),
        ("Fonction get_readable_content_with_fallbacks", "app.core.content_extractor", "get_readable_content_with_fallbacks"),
    ]

    all_passed = True
    for check_name, module, function in checks:
        exists = check_function_exists(module, function)
        status = "✅" if exists else "❌"
        print(f"  {status} {check_name}")
        if not exists:
            all_passed = False

    return all_passed


def verify_crawler_engine():
    """Vérifie les méthodes du crawler_engine."""
    print("\n🔍 Vérification de app.core.crawler_engine...")

    try:
        from app.core.crawler_engine import CrawlerEngine

        checks = [
            ("Méthode _create_links_from_markdown", "_create_links_from_markdown"),
            ("Méthode _save_media_from_list", "_save_media_from_list"),
            ("Méthode _extract_and_save_links", "_extract_and_save_links"),
            ("Méthode _extract_and_save_media", "_extract_and_save_media"),
        ]

        all_passed = True
        for check_name, method in checks:
            exists = hasattr(CrawlerEngine, method)
            status = "✅" if exists else "❌"
            print(f"  {status} {check_name}")
            if not exists:
                all_passed = False

        return all_passed

    except ImportError as e:
        print(f"  ❌ Erreur d'import: {e}")
        return False


def verify_schemas():
    """Vérifie les schémas Pydantic."""
    print("\n🔍 Vérification de app.schemas.expression...")

    try:
        from app.schemas.expression import ExpressionUpdate

        checks = [
            ("Champ content", "content"),
            ("Champ http_status", "http_status"),
            ("Champ language", "language"),
        ]

        all_passed = True
        schema_fields = ExpressionUpdate.__fields__

        for check_name, field in checks:
            exists = field in schema_fields
            status = "✅" if exists else "❌"
            print(f"  {status} {check_name}")
            if not exists:
                all_passed = False

        # Vérifier le type de http_status
        if "http_status" in schema_fields:
            field_type = schema_fields["http_status"].outer_type_
            is_string = "str" in str(field_type).lower()
            status = "✅" if is_string else "⚠️"
            print(f"  {status} http_status est de type string: {is_string}")
            if not is_string:
                print(f"       Type actuel: {field_type}")
                all_passed = False

        return all_passed

    except ImportError as e:
        print(f"  ❌ Erreur d'import: {e}")
        return False


def verify_tests():
    """Vérifie que les tests existent."""
    print("\n🔍 Vérification des tests...")

    test_file = Path("tests/test_legacy_parity.py")
    exists = test_file.exists()
    status = "✅" if exists else "❌"
    print(f"  {status} Fichier de tests test_legacy_parity.py")

    return exists


def verify_documentation():
    """Vérifie que la documentation est à jour."""
    print("\n🔍 Vérification de la documentation...")

    # Les docs sont dans le répertoire parent
    parent_dir = project_dir.parent

    docs = [
        (parent_dir / ".claude" / "TRANSFERT_API_CRAWL.md", "Audit mis à jour"),
        (parent_dir / ".claude" / "CORRECTIONS_PARITÉ_LEGACY.md", "Document de corrections"),
    ]

    all_exist = True
    for doc_path, description in docs:
        exists = doc_path.exists()
        status = "✅" if exists else "❌"
        print(f"  {status} {description} ({doc_path.name})")
        if not exists:
            all_exist = False

    return all_exist


def main():
    """Fonction principale."""
    print("=" * 60)
    print("🔧 VÉRIFICATION DE LA PARITÉ LEGACY")
    print("=" * 60)

    results = {
        "content_extractor": verify_content_extractor(),
        "crawler_engine": verify_crawler_engine(),
        "schemas": verify_schemas(),
        "tests": verify_tests(),
        "documentation": verify_documentation(),
    }

    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print("=" * 60)

    for component, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {component}")

    all_passed = all(results.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ TOUTES LES VÉRIFICATIONS SONT PASSÉES !")
        print("🚀 Vous pouvez maintenant exécuter les tests:")
        print("   pytest tests/test_legacy_parity.py -v")
        return 0
    else:
        print("❌ CERTAINES VÉRIFICATIONS ONT ÉCHOUÉ")
        print("⚠️  Vérifiez les erreurs ci-dessus avant de continuer")
        return 1


if __name__ == "__main__":
    sys.exit(main())
