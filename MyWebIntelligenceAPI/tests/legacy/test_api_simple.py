#!/usr/bin/env python3
"""
Test de workflow simple et direct pour l'API en utilisant requests.
"""
import requests
import json
import asyncio
from rich.console import Console
from rich.table import Table

# --- Configuration ---
API_BASE = "http://localhost:8000"
API_V1_URL = f"{API_BASE}/api/v1"

# NOTE: Ce script de test est conçu pour être exécuté dans l'environnement Docker,
# où il peut interagir avec la base de données via les fonctions CRUD.

async def setup_test_environment():
    """Prépare l'environnement de test."""
    from app.db.base import engine, Base, AsyncSessionLocal
    from app.crud import crud_user
    from app.schemas.user import UserCreate

    async with engine.begin() as conn:
        # Supprimer les tables existantes et les recréer
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        print("Création de l'utilisateur admin pour le test...")
        user_in = UserCreate(
            username="admin@example.com", # Le nom d'utilisateur est l'email pour la connexion
            email="admin@example.com",
            password="changethispassword",
            is_superuser=True
        )
        await crud_user.user.create(session, obj_in=user_in)
        print("✅ Utilisateur admin créé.")


def get_auth_token():
    """Obtient un token d'authentification."""
    print("🔐 Obtention du token d'authentification...")
    try:
        response = requests.post(f"{API_V1_URL}/auth/login", data={
            "username": "admin@example.com",
            "password": "changethispassword"
        })
        response.raise_for_status()
        token = response.json().get("access_token")
        assert token is not None
        print("✅ Token obtenu avec succès!")
        return token
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur d'authentification: {e}")
        return None

def display_land_details(land: dict):
    """Affiche les détails d'un land dans un tableau."""
    console = Console()
    table = Table(show_header=True, header_style="bold magenta", title="Détails du Land Créé")
    table.add_column("Attribut", style="dim", width=20)
    table.add_column("Valeur")

    table.add_row("ID", str(land.get('id')))
    table.add_row("Nom", land.get('name'))
    table.add_row("Description", land.get('description'))
    table.add_row("Langues", str(land.get('lang')))
    table.add_row("Créé le", land.get('created_at'))
    
    console.print(table)

    # Afficher les termes du dictionnaire
    words = land.get('words', [])
    if words:
        dict_table = Table(show_header=True, header_style="bold cyan", title="Termes du Dictionnaire")
        dict_table.add_column("Terme", style="green")
        dict_table.add_column("Stem/Lemme", style="yellow")
        dict_table.add_column("Poids", style="blue")
        
        for word_obj in words:
            term = word_obj.get('word', 'N/A')
            lemma = word_obj.get('lemma', 'N/A')
            weight = 'N/A'  # Le poids n'est plus dans cette structure
            dict_table.add_row(term, lemma, weight)
        
        console.print(dict_table)

def test_workflow():
    """
    Exécute un workflow de test complet :
    1. Prépare l'environnement.
    2. Obtient un token.
    3. Crée un land.
    4. Ajoute des termes à ce land.
    5. Récupère et affiche les détails du land.
    """
    # Étape 0: Préparer l'environnement de test
    asyncio.run(setup_test_environment())

    token = get_auth_token()
    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # --- Étape 1: Création du Land ---
    print("\n[ÉTAPE 1/2] Création d'un nouveau land...")
    land_data = {
        "name": "SimpleWorkflowTestLand",
        "description": "Land pour un test simple de workflow",
        "lang": ["fr", "en"]
    }
    
    create_url = f"{API_V1_URL}/lands/"
    try:
        create_response = requests.post(create_url, headers=headers, json=land_data)
        create_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la création du land: {e}")
        return False

    assert create_response.status_code == 201
    created_land = create_response.json()
    land_id = created_land.get("id")
    assert land_id is not None
    print(f"✅ Land créé avec succès! ID: {land_id}")

    # --- Étape 2: Ajout de termes au Land ---
    print(f"\n[ÉTAPE 2/2] Ajout de termes au land ID: {land_id}...")
    terms_data = {
        "terms": ["simple", "workflow", "test", "réussi", "managment"]
    }
    
    add_terms_url = f"{API_V1_URL}/lands/{land_id}/terms"
    try:
        add_terms_response = requests.post(add_terms_url, headers=headers, json=terms_data)
        add_terms_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de l'ajout des termes: {e}")
        return False

    assert add_terms_response.status_code == 200
    print("✅ Termes ajoutés avec succès!")

    # --- Étape 3: Récupération et affichage des détails du Land ---
    print(f"\n[ÉTAPE 3/3] Récupération des détails du land ID: {land_id}...")
    get_land_url = f"{API_V1_URL}/lands/{land_id}"
    try:
        get_land_response = requests.get(get_land_url, headers=headers)
        get_land_response.raise_for_status()
        
        land_details = get_land_response.json()
        
        print("\n--- DÉTAILS DU LAND ---")
        display_land_details(land_details)
        print("-----------------------\n")

    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la récupération du land: {e}")
        return False

    print("\n🎉 WORKFLOW DE TEST SIMPLE RÉUSSI!")
    return True

if __name__ == "__main__":
    test_workflow()
