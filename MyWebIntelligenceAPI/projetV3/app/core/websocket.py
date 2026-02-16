import asyncio
import json
from typing import Dict, Set

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, Set] = {}
        
    async def connect(self, channel: str, websocket):
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        
    def disconnect(self, channel: str, websocket):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]
                
    async def broadcast(self, channel: str, message: str):
        if channel in self.active_connections:
            for websocket in self.active_connections[channel]:
                await websocket.send_text(message)
    
    async def send_crawl_progress(self, channel: str, processed: int, total: int, message: str):
        """Send crawl progress update to WebSocket channel"""
        progress_data = {
            "type": "crawl_progress",
            "processed": processed,
            "total": total,
            "progress_percent": (processed / total * 100) if total > 0 else 0,
            "message": message
        }
        await self.broadcast(channel, json.dumps(progress_data))

websocket_manager = WebSocketManager()
