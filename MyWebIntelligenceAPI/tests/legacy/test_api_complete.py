#!/usr/bin/env python3
"""
Script de test complet pour MyWebIntelligenceAPI
"""

import requests
import json
import time

API_BASE = "http://localhost:8000"

def test_api_health():
    """Test la santé de l'API"""
    print("🔍 Test de santé de l'API...")
    try:
        response = requests.get(f"{API_BASE}/")
        if response.status_code == 200:
            print("✅ API accessible :", response.json())
            return True
        else:
            print(f"❌ API non accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False

def test_api_v1_info():
    """Test les informations de l'API v1"""
    print("\n🔍 Test API v1...")
    try:
        response = requests.get(f"{API_BASE}/api/v1/")
        if response.status_code == 200:
            print("✅ API v1 accessible :", response.json())
            return True
        else:
            print(f"❌ API v1 non accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_swagger_docs():
    """Test l'accès à la documentation Swagger"""
    print("\n🔍 Test documentation Swagger...")
    try:
        response = requests.get(f"{API_BASE}/docs")
        if response.status_code == 200:
            print("✅ Documentation Swagger accessible")
            return True
        else:
            print(f"❌ Documentation non accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_openapi_schema():
    """Test l'accès au schéma OpenAPI"""
    print("\n🔍 Test schéma OpenAPI...")
    try:
        response = requests.get(f"{API_BASE}/api/v1/openapi.json")
        if response.status_code == 200:
            schema = response.json()
            print("✅ Schéma OpenAPI accessible")
            print(f"📊 Endpoints disponibles: {len(schema.get('paths', {}))}")
            
            # Afficher les endpoints principaux
            paths = schema.get('paths', {})
            for path, methods in paths.items():
                for method in methods.keys():
                    if method.upper() in ['GET', 'POST', 'PUT', 'DELETE']:
                        print(f"   • {method.upper()} {path}")
            return True
        else:
            print(f"❌ Schéma non accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_auth_endpoint_structure():
    """Test la structure des endpoints d'authentification"""
    print("\n🔍 Test structure endpoints auth...")
    
    # Test endpoint login (sans authentifier, juste pour voir s'il existe)
    try:
        response = requests.post(f"{API_BASE}/api/v1/auth/login", 
                                data={"username": "test", "password": "test"})
        
        if response.status_code == 422:  # Erreur de validation = endpoint existe
            print("✅ Endpoint /api/v1/auth/login existe (erreur de validation attendue)")
            return True
        elif response.status_code == 401:  # Non autorisé = endpoint existe
            print("✅ Endpoint /api/v1/auth/login existe (erreur d'auth attendue)")
            return True
        else:
            print(f"⚠️  Endpoint login répond avec le code: {response.status_code}")
            print(f"   Réponse: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_monitoring_endpoints():
    """Test les endpoints de monitoring"""
    print("\n🔍 Test endpoints de monitoring...")
    
    services = {
        "Flower (Celery)": "http://localhost:5555",
        "Prometheus": "http://localhost:9090", 
        "Grafana": "http://localhost:3001"
    }
    
    for service, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {service} accessible")
            else:
                print(f"⚠️  {service} répond avec le code: {response.status_code}")
        except Exception as e:
            print(f"❌ {service} non accessible: {e}")

def run_all_tests():
    """Lance tous les tests"""
    print("🚀 === TEST COMPLET DE L'API MYWEBINTELLIGENCEAPI ===\n")
    
    tests = [
        test_api_health,
        test_api_v1_info, 
        test_swagger_docs,
        test_openapi_schema,
        test_auth_endpoint_structure,
        test_monitoring_endpoints
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Erreur dans le test {test.__name__}: {e}")
            results.append(False)
        time.sleep(0.5)  # Petite pause entre les tests
    
    # Résumé
    print(f"\n📊 === RÉSUMÉ DES TESTS ===")
    print(f"✅ Tests réussis: {sum(results)}/{len(results)}")
    print(f"❌ Tests échoués: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 Tous les tests sont passés ! L'API est opérationnelle.")
        print("\n🔗 Liens utiles:")
        print("   • Documentation API: http://localhost:8000/docs")
        print("   • API v1 Info: http://localhost:8000/api/v1/")
        print("   • Flower (Celery): http://localhost:5555")
        print("   • Prometheus: http://localhost:9090")
        print("   • Grafana: http://localhost:3001")
    else:
        print("\n⚠️  Certains tests ont échoué. Vérifiez les logs ci-dessus.")

if __name__ == "__main__":
    run_all_tests()
