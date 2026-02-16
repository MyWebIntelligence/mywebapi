"""
Media extraction helpers migrated from _legacy.core.extract_medias.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.content_extractor import resolve_url
from app.crud import crud_media
from app.db import models


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")
VIDEO_EXTENSIONS = (".mp4", ".webm", ".ogg", ".ogv", ".mov", ".avi", ".mkv")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg", ".aac", ".flac", ".m4a")


def has_allowed_extension(url: str, extensions: Tuple[str, ...]) -> bool:
    """
    Check if a URL ends with one of the allowed extensions.
    """
    if not url:
        return False
    if url.lower().startswith("data:"):
        return True
    path_only = urlparse(url).path.lower()
    return any(path_only.endswith(ext) for ext in extensions)


async def register_media(
    db: AsyncSession,
    expression: models.Expression,
    collected_urls: Set[str],
    base_url: str,
    raw_url: Optional[str],
    media_type: models.MediaType,
) -> Optional[models.Media]:
    """
    Normalise and persist a media reference if it has not been stored yet.
    """
    if not raw_url:
        return None

    clean_url = raw_url.strip()
    if media_type == models.MediaType.IMAGE and not has_allowed_extension(clean_url, IMAGE_EXTENSIONS):
        return None

    resolved_url = resolve_url(base_url, clean_url)
    if not resolved_url or resolved_url in collected_urls:
        return None

    if await crud_media.media.media_exists(db, expression_id=expression.id, url=resolved_url):
        collected_urls.add(resolved_url)
        return None

    collected_urls.add(resolved_url)
    created = await crud_media.media.create_media(
        db,
        expression_id=expression.id,
        media_data={
            "url": resolved_url,
            "type": media_type,
        },
    )
    return created


async def extract_medias(
    db: AsyncSession,
    content: Union[str, BeautifulSoup],
    expression: models.Expression,
) -> List[models.Media]:
    """
    Extract media references from HTML or Markdown content and save to database.
    """
    base_url = str(expression.url)
    soup = content if hasattr(content, "find_all") else BeautifulSoup(str(content), "html.parser")

    result = await db.execute(select(models.Media.url).where(models.Media.expression_id == expression.id))
    collected_urls: Set[str] = {row[0] for row in result.fetchall() if row[0]}

    created_medias: List[models.Media] = []

    media_type_map = {
        "img": models.MediaType.IMAGE,
        "video": models.MediaType.VIDEO,
        "audio": models.MediaType.AUDIO,
    }

    for tag in ("img", "video", "audio"):
        for element in soup.find_all(tag):
            primary_src = element.get("src")
            media_type = media_type_map[tag]
            created = await register_media(db, expression, collected_urls, base_url, primary_src, media_type)
            if created:
                created_medias.append(created)

            if tag == "img":
                srcset = element.get("srcset")
                if srcset:
                    for candidate in srcset.split(","):
                        candidate_url = candidate.strip().split(" ")[0]
                        created = await register_media(
                            db, expression, collected_urls, base_url, candidate_url, media_type_map["img"]
                        )
                        if created:
                            created_medias.append(created)
            if tag in ("video", "audio"):
                for source in element.find_all("source"):
                    created = await register_media(
                        db,
                        expression,
                        collected_urls,
                        base_url,
                        source.get("src"),
                        media_type_map[tag],
                    )
                    if created:
                        created_medias.append(created)

    raw_representation = str(content)
    markdown_text = raw_representation if raw_representation else soup.get_text(separator="\n")

    for match in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown_text):
        created = await register_media(
            db,
            expression,
            collected_urls,
            base_url,
            match,
            models.MediaType.IMAGE,
        )
        if created:
            created_medias.append(created)

    for label, url in re.findall(r"\[(IMAGE|VIDEO|AUDIO):\s*([^\]]+)\]", markdown_text, flags=re.IGNORECASE):
        label_lower = label.lower()
        media_type = {
            "image": models.MediaType.IMAGE,
            "video": models.MediaType.VIDEO,
            "audio": models.MediaType.AUDIO,
        }.get(label_lower, models.MediaType.IMAGE)
        created = await register_media(db, expression, collected_urls, base_url, url, media_type)
        if created:
            created_medias.append(created)

    return created_medias
