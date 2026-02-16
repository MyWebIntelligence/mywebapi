"""
Client HTTP asynchrone pour les requêtes web
"""

import httpx
from typing import Optional, Dict, AsyncGenerator

class AsyncHttpClient:
    """Wrapper pour httpx.AsyncClient"""

    def __init__(self, base_url: str = "", headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url
        self.headers = headers or {
            "User-Agent": "MyWebIntelligenceBot/1.0 (+http://mywebintelligence.com/bot)"
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, follow_redirects=True, timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def get(self, url: str, params: Optional[Dict] = None) -> httpx.Response:
        """Effectuer une requête GET"""
        if not self._client:
            raise RuntimeError("HttpClient not initialized. Use 'async with'.")
        return await self._client.get(url, params=params)

async def get_http_client() -> AsyncGenerator[AsyncHttpClient, None]:
    """Dépendance pour obtenir un client HTTP"""
    async with AsyncHttpClient() as client:
        yield client
