"""
Tests unitaires pour le WebSocketManager

Tests critiques pour la gestion des connexions WebSocket :
- Connexions multiples sur même channel
- Broadcast sur channels existants et inexistants
- Nettoyage des connexions fermées
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.websocket import WebSocketManager


@pytest.mark.asyncio
class TestWebSocketManager:
    """Tests pour le WebSocketManager"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.ws_manager = WebSocketManager()
    
    async def test_connect_single_websocket(self):
        """Test connexion d'un seul websocket"""
        mock_websocket = AsyncMock()
        channel = "test_channel_1"
        
        await self.ws_manager.connect(channel, mock_websocket)
        
        assert channel in self.ws_manager.active_connections
        assert mock_websocket in self.ws_manager.active_connections[channel]
        assert len(self.ws_manager.active_connections[channel]) == 1
    
    async def test_connect_multiple_websockets_same_channel(self):
        """Test connexion de plusieurs websockets au même channel"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()
        channel = "shared_channel"
        
        await self.ws_manager.connect(channel, mock_ws1)
        await self.ws_manager.connect(channel, mock_ws2)
        await self.ws_manager.connect(channel, mock_ws3)
        
        assert len(self.ws_manager.active_connections[channel]) == 3
        assert mock_ws1 in self.ws_manager.active_connections[channel]
        assert mock_ws2 in self.ws_manager.active_connections[channel]
        assert mock_ws3 in self.ws_manager.active_connections[channel]
    
    async def test_connect_multiple_channels(self):
        """Test connexion sur plusieurs channels différents"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        channel1 = "channel_1"
        channel2 = "channel_2"
        
        await self.ws_manager.connect(channel1, mock_ws1)
        await self.ws_manager.connect(channel2, mock_ws2)
        
        assert len(self.ws_manager.active_connections) == 2
        assert channel1 in self.ws_manager.active_connections
        assert channel2 in self.ws_manager.active_connections
        assert mock_ws1 in self.ws_manager.active_connections[channel1]
        assert mock_ws2 in self.ws_manager.active_connections[channel2]
    
    async def test_disconnect_websocket(self):
        """Test déconnexion d'un websocket"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        channel = "test_channel"
        
        # Connecter deux websockets
        await self.ws_manager.connect(channel, mock_ws1)
        await self.ws_manager.connect(channel, mock_ws2)
        
        # Déconnecter un websocket
        self.ws_manager.disconnect(channel, mock_ws1)
        
        assert len(self.ws_manager.active_connections[channel]) == 1
        assert mock_ws1 not in self.ws_manager.active_connections[channel]
        assert mock_ws2 in self.ws_manager.active_connections[channel]
    
    async def test_disconnect_last_websocket_removes_channel(self):
        """Test que déconnecter le dernier websocket supprime le channel"""
        mock_websocket = AsyncMock()
        channel = "test_channel"
        
        # Connecter un websocket
        await self.ws_manager.connect(channel, mock_websocket)
        assert channel in self.ws_manager.active_connections
        
        # Déconnecter le websocket
        self.ws_manager.disconnect(channel, mock_websocket)
        
        # Le channel devrait être supprimé
        assert channel not in self.ws_manager.active_connections
    
    async def test_disconnect_nonexistent_channel(self):
        """Test déconnexion sur un channel inexistant"""
        mock_websocket = AsyncMock()
        
        # Ne devrait pas lever d'exception
        self.ws_manager.disconnect("nonexistent_channel", mock_websocket)
        
        assert len(self.ws_manager.active_connections) == 0
    
    async def test_disconnect_nonexistent_websocket(self):
        """Test déconnexion d'un websocket non connecté"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        channel = "test_channel"
        
        # Connecter seulement mock_ws1
        await self.ws_manager.connect(channel, mock_ws1)
        
        # Essayer de déconnecter mock_ws2 (pas connecté)
        self.ws_manager.disconnect(channel, mock_ws2)
        
        # mock_ws1 devrait toujours être connecté
        assert len(self.ws_manager.active_connections[channel]) == 1
        assert mock_ws1 in self.ws_manager.active_connections[channel]
    
    async def test_broadcast_to_existing_channel(self):
        """Test broadcast vers un channel existant"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        channel = "test_channel"
        message = "Test message"
        
        # Connecter deux websockets
        await self.ws_manager.connect(channel, mock_ws1)
        await self.ws_manager.connect(channel, mock_ws2)
        
        # Broadcaster un message
        await self.ws_manager.broadcast(channel, message)
        
        # Vérifier que les deux websockets ont reçu le message
        mock_ws1.send_text.assert_called_once_with(message)
        mock_ws2.send_text.assert_called_once_with(message)
    
    async def test_broadcast_to_nonexistent_channel(self):
        """Test broadcast vers un channel inexistant"""
        message = "Test message"
        
        # Ne devrait pas lever d'exception
        await self.ws_manager.broadcast("nonexistent_channel", message)
        
        # Aucun websocket ne devrait être appelé
        assert len(self.ws_manager.active_connections) == 0
    
    async def test_broadcast_to_empty_channel(self):
        """Test broadcast vers un channel vide (après déconnexions)"""
        mock_websocket = AsyncMock()
        channel = "test_channel"
        message = "Test message"
        
        # Connecter puis déconnecter
        await self.ws_manager.connect(channel, mock_websocket)
        self.ws_manager.disconnect(channel, mock_websocket)
        
        # Le channel devrait être supprimé, donc broadcast ne fait rien
        await self.ws_manager.broadcast(channel, message)
        
        # Aucun appel ne devrait être fait
        mock_websocket.send_text.assert_not_called()
    
    async def test_broadcast_with_failing_websocket(self):
        """Test broadcast avec un websocket qui échoue"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        channel = "test_channel"
        message = "Test message"
        
        # Configurer mock_ws1 pour lever une exception
        mock_ws1.send_text.side_effect = Exception("Connection closed")
        
        await self.ws_manager.connect(channel, mock_ws1)
        await self.ws_manager.connect(channel, mock_ws2)
        
        # Le broadcast devrait échouer sur mock_ws1 mais continuer pour mock_ws2
        with pytest.raises(Exception):
            await self.ws_manager.broadcast(channel, message)
        
        # mock_ws1 devrait avoir été appelé (mais a échoué)
        mock_ws1.send_text.assert_called_once_with(message)
        # mock_ws2 pourrait ne pas être appelé à cause de l'exception
    
    async def test_multiple_channels_broadcast(self):
        """Test broadcast sur plusieurs channels simultanément"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        channel1 = "channel_1"
        channel2 = "channel_2"
        message1 = "Message for channel 1"
        message2 = "Message for channel 2"
        
        await self.ws_manager.connect(channel1, mock_ws1)
        await self.ws_manager.connect(channel2, mock_ws2)
        
        # Broadcaster sur les deux channels
        await self.ws_manager.broadcast(channel1, message1)
        await self.ws_manager.broadcast(channel2, message2)
        
        # Vérifier que chaque websocket a reçu le bon message
        mock_ws1.send_text.assert_called_once_with(message1)
        mock_ws2.send_text.assert_called_once_with(message2)
    
    async def test_websocket_manager_singleton_instance(self):
        """Test que le manager est bien une instance globale"""
        from app.core.websocket import websocket_manager
        
        assert isinstance(websocket_manager, WebSocketManager)
        assert websocket_manager.active_connections == {}
    
    async def test_complex_scenario_connect_disconnect_broadcast(self):
        """Test scénario complexe avec connexions, déconnexions et broadcasts"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()
        channel = "complex_channel"
        
        # Étape 1: Connecter 3 websockets
        await self.ws_manager.connect(channel, mock_ws1)
        await self.ws_manager.connect(channel, mock_ws2)
        await self.ws_manager.connect(channel, mock_ws3)
        
        # Étape 2: Broadcaster un message
        await self.ws_manager.broadcast(channel, "Message 1")
        
        # Tous devraient avoir reçu le message
        mock_ws1.send_text.assert_called_with("Message 1")
        mock_ws2.send_text.assert_called_with("Message 1")
        mock_ws3.send_text.assert_called_with("Message 1")
        
        # Étape 3: Déconnecter ws2
        self.ws_manager.disconnect(channel, mock_ws2)
        
        # Étape 4: Broadcaster un autre message
        await self.ws_manager.broadcast(channel, "Message 2")
        
        # Seuls ws1 et ws3 devraient recevoir le deuxième message
        assert mock_ws1.send_text.call_count == 2
        assert mock_ws2.send_text.call_count == 1  # Seulement le premier message
        assert mock_ws3.send_text.call_count == 2
        
        # Vérifier les derniers appels
        mock_ws1.send_text.assert_called_with("Message 2")
        mock_ws3.send_text.assert_called_with("Message 2")
