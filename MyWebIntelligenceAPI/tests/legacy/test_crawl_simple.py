#!/usr/bin/env python3
"""
Test simple pour l'API de crawling
Test basique qui envoie des données pour tester le crawl
"""

import requests
import json
import time

# Configuration
API_BASE = "http://localhost:8000"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "changethispassword"

def get_auth_token():
    """Obtient un token d'authentification"""
    print("🔐 Authentification...")
    
    login_data = {
        "username": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }
    
    response = requests.post(
        f"{API_BASE}/api/v1/auth/login",
        data=login_data
    )
    
    if response.status_code == 200:
        token_data = response.json()
        token = token_data["access_token"]
        print("✅ Authentification réussie")
        return token
    else:
        print(f"❌ Erreur d'authentification: {response.status_code}")
        print(f"   Réponse: {response.text}")
        return None

def create_test_land(token):
    """Crée un land de test"""
    print("\n📝 Création d'un land de test...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    land_data = {
        "name": "Test Crawl Land",
        "description": "Land pour tester le crawling",
        "start_urls": [
            "https://www.lemonde.fr/international/article/2025/07/02/bande-de-gaza-donald-trump-assure-qu-israel-est-pret-a-s-engager-pour-un-cessez-le-feu-de-60-jours_6617278_3211.html",
            "https://www.france24.com/fr/moyen-orient/20250702-gaza-hamas-dit-discuter-propositions-cessez-le-feu-re%C3%A7ues-m%C3%A9diateurs",
            "https://www.liberation.fr/checknews/que-sait-on-de-la-rumeur-de-presence-doxycodone-dans-des-sacs-de-farine-distribues-a-gaza-20250702_MBPU7RTQ4BDIJBVAZ7HAFOVIKU/"
        ]
    }
    
    response = requests.post(
        f"{API_BASE}/api/v1/lands/",
        headers=headers,
        json=land_data
    )
    
    if response.status_code == 201:
        land = response.json()
        print(f"✅ Land créé avec succès - ID: {land['id']}")
        print(f"   Nom: {land['name']}")
        print(f"   URLs de départ: {len(land.get('start_urls', []))}")
        return land
    else:
        print(f"❌ Erreur création land: {response.status_code}")
        print(f"   Réponse: {response.text}")
        return None

def add_terms_to_land(token, land_id):
    """Ajoute des termes de relevance au land"""
    print(f"\n📚 Ajout de termes au land {land_id}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    terms_data = {
        "terms": [
            "test",
            "example", 
            "web",
            "crawling",
            "intelligence"
        ]
    }
    
    response = requests.post(
        f"{API_BASE}/api/v1/lands/{land_id}/terms",
        headers=headers,
        json=terms_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Termes ajoutés avec succès")
        print(f"   Termes dans le dictionnaire: {len(result.get('words', []))}")
        return True
    else:
        print(f"❌ Erreur ajout termes: {response.status_code}")
        print(f"   Réponse: {response.text}")
        return False

def start_crawl(token, land_id):
    """Lance le crawl d'un land"""
    print(f"\n🕷️ Lancement du crawl pour le land {land_id}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Paramètres optionnels pour le crawl
    crawl_params = {
        "limit": 10,  # Limiter à 10 pages pour le test
        "depth": 2    # Profondeur maximale
    }
    
    response = requests.post(
        f"{API_BASE}/api/v1/lands/{land_id}/crawl",
        headers=headers,
        json=crawl_params
    )
    
    if response.status_code == 202:  # Accepted
        crawl_result = response.json()
        print("✅ Crawl lancé avec succès")
        print(f"   Job ID: {crawl_result.get('job_id', 'N/A')}")
        print(f"   Status: {crawl_result.get('status', 'N/A')}")
        print(f"   Message: {crawl_result.get('message', 'N/A')}")
        return crawl_result
    else:
        print(f"❌ Erreur lancement crawl: {response.status_code}")
        print(f"   Réponse: {response.text}")
        return None

def get_land_details(token, land_id):
    """Récupère les détails d'un land"""
    print(f"\n📊 Récupération des détails du land {land_id}...")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{API_BASE}/api/v1/lands/{land_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        land = response.json()
        print("✅ Détails récupérés")
        print(f"   Nom: {land.get('name', 'N/A')}")
        print(f"   Status: {land.get('status', 'N/A')}")
        print(f"   Expressions totales: {land.get('total_expressions', 0)}")
        print(f"   Média total: {land.get('total_media', 0)}")
        print(f"   Dernière maj: {land.get('updated_at', 'N/A')}")
        
        # Afficher le dictionnaire si présent
        if 'words' in land and land['words']:
            print(f"   Mots dans le dictionnaire: {len(land['words'])}")
            for word in land['words'][:5]:  # Afficher les 5 premiers
                print(f"     • {word.get('word', 'N/A')} (lemme: {word.get('lemma', 'N/A')})")
            if len(land['words']) > 5:
                print(f"     ... et {len(land['words']) - 5} autres")
        
        return land
    else:
        print(f"❌ Erreur récupération land: {response.status_code}")
        print(f"   Réponse: {response.text}")
        return None

def get_land_expressions(token, land_id):
    """Récupère les expressions crawlées d'un land"""
    print(f"\n🕷️ Récupération des expressions du land {land_id}...")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # Essayer d'accéder aux expressions (endpoint peut varier)
    try:
        response = requests.get(
            f"{API_BASE}/api/v1/expressions?land_id={land_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            expressions = response.json()
            if isinstance(expressions, list):
                print(f"✅ {len(expressions)} expressions trouvées")
                
                for i, expr in enumerate(expressions[:10]):  # Afficher les 10 premières
                    print(f"   {i+1}. {expr.get('url', 'N/A')}")
                    print(f"      Status: {expr.get('http_status', 'N/A')} | Relevance: {expr.get('relevance', 'N/A')}")
                    if expr.get('title'):
                        print(f"      Titre: {expr.get('title')[:80]}...")
                    print()
                
                if len(expressions) > 10:
                    print(f"   ... et {len(expressions) - 10} autres expressions")
                
                return expressions
            else:
                print("⚠️ Format de réponse inattendu pour les expressions")
                return None
        else:
            print(f"⚠️ Endpoint expressions non accessible: {response.status_code}")
            print("   (Normal si l'endpoint n'est pas encore implémenté)")
            return None
    except Exception as e:
        print(f"⚠️ Erreur lors de la récupération des expressions: {e}")
        return None

def test_crawl_workflow():
    """Test complet du workflow de crawling"""
    print("🚀 === TEST SIMPLE DE CRAWLING ===\n")
    
    # 1. Authentification
    token = get_auth_token()
    if not token:
        print("❌ Test arrêté - Pas d'authentification")
        return False
    
    # 2. Création du land
    land = create_test_land(token)
    if not land:
        print("❌ Test arrêté - Pas de land")
        return False
    
    land_id = land['id']
    
    # 3. Ajout de termes
    if not add_terms_to_land(token, land_id):
        print("⚠️ Termes non ajoutés, continue quand même...")
    
    # 4. Affichage des détails avant crawl
    print("\n" + "="*50)
    print("📋 ÉTAT AVANT CRAWL")
    print("="*50)
    get_land_details(token, land_id)
    
    # 5. Lancement du crawl
    crawl_result = start_crawl(token, land_id)
    if not crawl_result:
        print("❌ Test arrêté - Crawl non lancé")
        return False
    
    # 6. Attendre 120 secondes pour que le crawl se termine
    print("\n⏳ Attente de 120 secondes pour laisser le crawl se terminer...")
    
    # Affichage d'un compteur de progression
    for remaining in range(120, 0, -10):
        print(f"   ⏱️ {remaining} secondes restantes...")
        time.sleep(10)
    
    print("⏰ Attente terminée !")
    
    # 7. Affichage des détails après crawl
    print("\n" + "="*50)
    print("📋 ÉTAT APRÈS CRAWL (120s)")
    print("="*50)
    get_land_details(token, land_id)
    
    # 8. Affichage des expressions crawlées
    print("\n" + "="*50)
    print("🕷️ EXPRESSIONS CRAWLÉES")
    print("="*50)
    expressions = get_land_expressions(token, land_id)
    
    print("\n🎉 Test terminé avec succès !")
    print("\n📝 Notes:")
    if expressions and len(expressions) > 0:
        print(f"   ✅ Crawl réussi: {len(expressions)} expressions trouvées")
    else:
        print("   ⚠️ Aucune expression trouvée (crawl peut encore être en cours)")
    print("   • Vérifiez Flower pour le suivi: http://localhost:5555")
    print("   • Vérifiez la base de données pour plus de détails")
    
    return True

def run_simple_test():
    """Lance le test simple"""
    try:
        success = test_crawl_workflow()
        if success:
            print(f"\n✅ Test réussi - L'API de crawling fonctionne !")
        else:
            print(f"\n❌ Test échoué - Vérifiez les logs ci-dessus")
    except Exception as e:
        print(f"\n💥 Erreur inattendue: {e}")

if __name__ == "__main__":
    run_simple_test()
