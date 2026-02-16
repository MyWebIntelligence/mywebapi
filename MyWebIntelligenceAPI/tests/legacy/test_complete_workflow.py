#!/usr/bin/env python3
"""
Test complet de l'API MyWebIntelligenceAPI
- Création d'utilisateur admin
- Test d'authentification 
- Création d'un land
- Test des endpoints principaux
"""

import requests
import json
import psycopg2
from passlib.context import CryptContext

API_BASE = "http://localhost:8000"

def create_admin_user():
    """Créer l'utilisateur admin directement en base"""
    print("🔧 Création de l'utilisateur admin...")
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("changethispassword")
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="5432", 
            database="mywebintelligence",
            user="postgres",
            password="password"
        )
        
        cursor = conn.cursor()
        
        # Vérifier si l'utilisateur existe
        cursor.execute("SELECT id FROM users WHERE username = %s", ("admin@example.com",))
        existing_user = cursor.fetchone()
        
        if existing_user:
            print("✅ Utilisateur admin existe déjà")
        else:
            cursor.execute("""
                INSERT INTO users (username, email, hashed_password, is_active, is_admin, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (
                "admin@example.com",
                "admin@example.com", 
                hashed_password,
                True,
                True
            ))
            
            conn.commit()
            print("✅ Utilisateur admin créé avec succès!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'utilisateur: {e}")
        return False

def test_authentication():
    """Tester l'authentification"""
    print("\n🔐 Test d'authentification...")
    
    try:
        # Les endpoints ont une duplication /v1/, testons les deux formats
        login_urls = [
            f"{API_BASE}/api/v1/auth/login",
            f"{API_BASE}/api/v1/v1/auth/login"
        ]
        
        for url in login_urls:
            print(f"   Tentative de connexion sur: {url}")
            
            response = requests.post(url, data={
                "username": "admin@example.com",
                "password": "changethispassword"
            })
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Authentification réussie!")
                print(f"   Token: {data.get('access_token', 'N/A')[:50]}...")
                return data.get('access_token')
            elif response.status_code == 404:
                print("   ⚠️  Endpoint non trouvé")
            else:
                print(f"   ⚠️  Erreur: {response.text}")
        
        print("❌ Aucun endpoint d'authentification fonctionnel trouvé")
        return None
        
    except Exception as e:
        print(f"❌ Erreur d'authentification: {e}")
        return None

def test_create_land(token):
    """Créer un land de test"""
    print("\n🌍 Test de création d'un Land...")
    
    if not token:
        print("❌ Pas de token d'authentification")
        return None
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    land_data = {
        "name": "Test Land",
        "description": "Land de test créé automatiquement",
        "start_urls": ["https://example.com"],
        "crawl_depth": 2,
        "crawl_limit": 100
    }
    
    try:
        # Tester les deux formats d'URL
        create_urls = [
            f"{API_BASE}/api/v1/lands/",
            f"{API_BASE}/api/v1/v1/lands/"
        ]
        
        for url in create_urls:
            print(f"   Tentative de création sur: {url}")
            
            response = requests.post(url, headers=headers, json=land_data)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 201:
                land = response.json()
                print("✅ Land créé avec succès!")
                print(f"   ID: {land.get('id')}")
                print(f"   Nom: {land.get('name')}")
                return land
            elif response.status_code == 404:
                print("   ⚠️  Endpoint non trouvé")
            else:
                print(f"   ⚠️  Erreur: {response.text}")
        
        print("❌ Impossible de créer le land")
        return None
        
    except Exception as e:
        print(f"❌ Erreur lors de la création du land: {e}")
        return None

def test_add_terms_to_land(token, land):
    """Tester l'ajout de termes à un land"""
    print("\n🔤 Test d'ajout de termes au Land...")
    
    if not token or not land:
        print("❌ Token ou Land manquant")
        return False
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    terms_data = {
        "terms": ["intelligence", "artificielle", "web", "crawling", "test"]
    }
    
    try:
        # Tester les deux formats d'URL
        land_id = land.get('id')
        add_terms_urls = [
            f"{API_BASE}/api/v1/lands/{land_id}/terms",
            f"{API_BASE}/api/v1/v1/lands/{land_id}/terms"
        ]
        
        for url in add_terms_urls:
            print(f"   Tentative d'ajout de termes sur: {url}")
            
            response = requests.post(url, headers=headers, json=terms_data)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                updated_land = response.json()
                print("✅ Termes ajoutés avec succès!")
                print(f"   Land ID: {updated_land.get('id')}")
                print(f"   Termes ajoutés: {', '.join(terms_data['terms'])}")
                return True
            elif response.status_code == 404:
                print("   ⚠️  Endpoint non trouvé")
            else:
                print(f"   ⚠️  Erreur: {response.text}")
        
        print("❌ Impossible d'ajouter les termes")
        return False
        
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout des termes: {e}")
        return False

def run_complete_test():
    """Exécuter le test complet"""
    print("🚀 === TEST COMPLET WORKFLOW MYWEBINTELLIGENCEAPI ===\n")
    
    # 1. Créer l'utilisateur admin
    if not create_admin_user():
        print("❌ Impossible de créer l'utilisateur admin")
        return
    
    # 2. Tester l'authentification
    token = test_authentication()
    
    # 3. Créer un land
    if token:
        land = test_create_land(token)
        if land:
            # 4. Tester l'ajout de termes au land
            terms_success = test_add_terms_to_land(token, land)
            
            print(f"\n🎉 RÉSULTATS DU TEST COMPLET:")
            print(f"✅ Utilisateur admin créé")
            print(f"✅ Authentification fonctionnelle")  
            print(f"✅ Land créé (ID: {land.get('id')})")
            
            if terms_success:
                print(f"✅ Ajout de termes au land réussi")
                print(f"\n🎊 TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS!")
            else:
                print(f"❌ Ajout de termes au land échoué")
                print(f"\n⚠️  Tests partiellement réussis")
        else:
            print(f"\n⚠️  Authentification OK mais création de land échouée")
    else:
        print(f"\n❌ Test échoué à l'authentification")

if __name__ == "__main__":
    run_complete_test()
