#!/usr/bin/env python3
"""
Script pour créer l'utilisateur admin
"""
import asyncio
import psycopg2
from passlib.context import CryptContext

def create_admin_user():
    """Créer l'utilisateur admin directement dans PostgreSQL"""
    
    # Configuration de cryptage des mots de passe
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("changethispassword")
    
    try:
        # Connexion à PostgreSQL (paramètres Docker)
        conn = psycopg2.connect(
            host="db",
            port="5432",
            database="mwi_db",
            user="mwi_user",
            password="mwi_password"
        )
        
        cursor = conn.cursor()
        
        # Vérifier si l'utilisateur existe déjà
        cursor.execute("SELECT id FROM users WHERE username = %s", ("admin@example.com",))
        existing_user = cursor.fetchone()
        
        if existing_user:
            print("L'utilisateur admin existe déjà")
            return
        
        # Créer l'utilisateur admin
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
        print("📧 Email: admin@example.com")
        print("🔑 Mot de passe: changethispassword")
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'utilisateur admin: {e}")
    
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    create_admin_user()
