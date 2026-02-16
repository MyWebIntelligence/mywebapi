"""
WebSocket endpoints pour le suivi en temps réel
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set
import json
import asyncio
from datetime import datetime
from app.api import dependencies
from app.db.models import User

router = APIRouter()

# Dictionnaire pour stocker les connexions WebSocket actives par job_id
active_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict, job_id: str):
        if job_id in self.active_connections:
            # Convertir le message en JSON
            json_message = json.dumps(message)
            # Envoyer à toutes les connexions pour ce job
            disconnected = set()
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_text(json_message)
                except:
                    # La connexion est fermée, la marquer pour suppression
                    disconnected.add(connection)
            
            # Supprimer les connexions fermées
            for connection in disconnected:
                self.active_connections[job_id].discard(connection)


manager = ConnectionManager()


@router.websocket("/jobs/{job_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    job_id: str,
    token: str = Query(None)
):
    """
    WebSocket endpoint pour suivre la progression d'un job en temps réel.
    
    Le token JWT doit être passé en query parameter car les WebSocket
    ne supportent pas les headers Authorization.
    
    Exemple de connexion:
    ws://localhost:8000/api/v1/ws/jobs/123?token=YOUR_JWT_TOKEN
    """
    # Valider le token
    try:
        if not token:
            await websocket.close(code=1008, reason="Missing token")
            return
            
        # Valider le token JWT
        # Note: Cette validation pourrait être améliorée
        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        if not payload:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=1008, reason="Authentication failed")
        return

    # Connecter le WebSocket
    await manager.connect(websocket, job_id)
    
    try:
        # Envoyer un message de bienvenue
        await manager.send_personal_message(
            json.dumps({
                "type": "connection",
                "message": f"Connected to job {job_id}",
                "job_id": job_id
            }),
            websocket
        )
        
        # Garder la connexion ouverte
        while True:
            # Attendre un message du client (ping/pong pour garder la connexion)
            data = await websocket.receive_text()
            
            # Echo le message (ou traiter des commandes si nécessaire)
            if data == "ping":
                await manager.send_personal_message("pong", websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)
        # Optionnel: broadcaster que quelqu'un s'est déconnecté
        await manager.broadcast(
            {
                "type": "disconnection",
                "message": "A client disconnected"
            },
            job_id
        )


async def send_job_update(job_id: str, update: dict):
    """
    Fonction utilitaire pour envoyer des mises à jour à tous les clients
    connectés à un job spécifique.
    
    Cette fonction peut être appelée depuis les tâches Celery ou d'autres
    parties de l'application pour envoyer des mises à jour en temps réel.
    
    Args:
        job_id: L'ID du job
        update: Dictionnaire contenant les informations de mise à jour
    """
    await manager.broadcast(update, job_id)


# Exemple d'utilisation depuis une tâche Celery
from typing import Optional

async def notify_crawl_progress(job_id: str, progress: float, status: str, details: Optional[dict] = None):
    """
    Envoie une notification de progression pour un job de crawling.
    
    Args:
        job_id: L'ID du job
        progress: Pourcentage de progression (0-100)
        status: Statut actuel (running, completed, failed, etc.)
        details: Détails supplémentaires (optionnel)
    """
    update = {
        "type": "progress",
        "job_id": job_id,
        "progress": progress,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {}
    }
    
    await send_job_update(job_id, update)
