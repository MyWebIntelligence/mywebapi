#!/usr/bin/env python3
"""
Script pour vérifier que l'analyse média respecte bien le paramètre depth.
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "admin@example.com"
PASSWORD = "changeme"
LAND_ID = 8

def get_token():
    """Obtient un token JWT."""
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=f"username={USERNAME}&password={PASSWORD}"
    )
    return response.json()["access_token"]

def get_expressions_by_depth(token, land_id):
    """Récupère les expressions par profondeur via un endpoint direct."""
    # On va faire une requête custom pour voir les expressions
    headers = {"Authorization": f"Bearer {token}"}
    
    # Créons une requête SQL directe via le endpoint debug (si disponible)
    # ou via l'export
    response = requests.post(
        f"{BASE_URL}/api/v1/export/direct",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "land_id": land_id,
            "export_type": "pagecsv",
            "limit": 1000
        }
    )
    
    if response.status_code == 200:
        # Parse les données CSV pour extraire les profondeurs
        lines = response.text.strip().split('\n')
        if len(lines) > 1:  # Skip header
            depths = []
            for line in lines[1:]:  # Skip header
                parts = line.split(',')
                if len(parts) > 2:  # Assume depth is in a column
                    try:
                        # Try to find depth column (usually contains integers 0,1,2,...)
                        for part in parts:
                            if part.strip().isdigit():
                                depths.append(int(part.strip()))
                                break
                    except:
                        continue
            return depths
    
    return []

def main():
    print("🔍 Vérification du respect du paramètre depth=0 dans l'analyse média")
    print("=" * 70)
    
    token = get_token()
    print(f"✅ Token obtenu: {token[:20]}...")
    
    # Vérifier les expressions existantes
    print(f"\n📊 Récupération des expressions du land {LAND_ID}...")
    depths = get_expressions_by_depth(token, LAND_ID)
    
    if depths:
        print(f"📈 Expressions trouvées avec profondeurs: {depths}")
        print(f"📊 Répartition par profondeur:")
        depth_counts = {}
        for d in depths:
            depth_counts[d] = depth_counts.get(d, 0) + 1
        
        for depth, count in sorted(depth_counts.items()):
            print(f"   - Profondeur {depth}: {count} expressions")
        
        # Vérifier s'il y a des expressions de profondeur 0
        depth_0_count = depth_counts.get(0, 0)
        if depth_0_count > 0:
            print(f"\n✅ {depth_0_count} expressions de profondeur 0 disponibles")
            print("🚀 Prêt pour l'analyse média avec depth=0")
        else:
            print("\n❌ Aucune expression de profondeur 0 trouvée")
            print("⚠️  L'analyse média avec depth=0 ne trouvera aucun média")
    else:
        print("❌ Aucune expression trouvée ou erreur d'export")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()