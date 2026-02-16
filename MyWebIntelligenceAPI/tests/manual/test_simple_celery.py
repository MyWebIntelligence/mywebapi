#!/usr/bin/env python3
"""
Test simple pour identifier le problème de session dans Celery
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.base import AsyncSessionLocal
from app.db.models import Land

async def test_simple_db():
    """Test simple d'accès à la DB."""
    print("Testing simple DB access...")
    
    async with AsyncSessionLocal() as db:
        land = await db.get(Land, 8)
        if land:
            print(f"Found land: {land.name}")
        else:
            print("Land not found")

if __name__ == "__main__":
    asyncio.run(test_simple_db())
