"""
Synchronous media processor used by Celery workers.

This mirrors the behaviour of the async MediaProcessor but relies on the
synchronous SQLAlchemy session and httpx.Client so it can run safely in a
prefork Celery worker without the async greenlet bridge.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse
import os

import httpx
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available. Dynamic media extraction will be skipped.")


def _generate_web_safe_palette() -> List[tuple[int, int, int]]:
    """Generate the 216 RGB values of the classic web safe palette."""
    levels = [0, 51, 102, 153, 204, 255]
    return [(r, g, b) for r in levels for g in levels for b in levels]


def _rgb_distance(color_a: tuple[int, int, int], color_b: tuple[int, int, int]) -> int:
    """Squared euclidean distance between two RGB triples."""
    return sum((a - b) ** 2 for a, b in zip(color_a, color_b))


def _convert_to_web_safe(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return the closest colour in the web safe palette."""
    palette = _generate_web_safe_palette()
    return min(palette, key=lambda candidate: _rgb_distance(rgb, candidate))


class MediaProcessorSync:
    """Synchronous replacement for the async media processor."""

    def __init__(self, db: Session, http_client: httpx.Client):
        self.db = db
        self.http_client = http_client
        self.max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    # ------------------------------------------------------------------ #
    # Public helpers                                                     #
    # ------------------------------------------------------------------ #
    def extract_media_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract media URLs from soup using the same heuristics as async version."""
        urls = set()
        media_tags = soup.find_all(['img', 'video', 'audio'])

        for tag in media_tags:
            src = tag.get('src') or tag.get('data-src') or tag.get('data-original')
            if src:
                clean_url = self._clean_media_url(src, base_url)
                if clean_url:
                    urls.add(clean_url)

            srcset = tag.get('srcset')
            if srcset:
                for item in srcset.split(','):
                    candidate = item.strip().split(' ')[0]
                    if not candidate:
                        continue
                    clean_url = self._clean_media_url(candidate, base_url)
                    if clean_url:
                        urls.add(clean_url)

        return list(urls)

    def analyze_image(self, url: str) -> Dict[str, Any]:
        """Synchronously download and analyse an image."""
        result: Dict[str, Any] = {
            'url': url,
            'error': None,
            'width': None,
            'height': None,
            'format': None,
            'file_size': None,
            'color_mode': None,
            'has_transparency': False,
            'aspect_ratio': None,
            'exif_data': None,
            'image_hash': None,
            'dominant_colors': [],
            'websafe_colors': {},
            'mime_type': None,
        }

        try:
            response = self.http_client.get(url, timeout=30.0)
            response.raise_for_status()

            result['mime_type'] = response.headers.get('Content-Type')
            content = response.content

            if len(content) > self.max_size:
                raise ValueError(f"File size exceeds limit ({len(content)} bytes)")

            result['file_size'] = len(content)
            result['image_hash'] = hashlib.sha256(content).hexdigest()

            with Image.open(io.BytesIO(content)) as img:
                self._analyse_image_properties(img, result)
                if settings.ANALYZE_MEDIA:
                    self._extract_colors(img, result)
                    self._extract_exif(img, result)

        except Exception as exc:  # noqa: BLE001 - keep unexpected errors surfaced
            result['error'] = str(exc)

        return result

    def media_exists(self, expression_id: int, url: str) -> bool:
        """Return True if a media entry already exists for expression/url pair."""
        url_hash = models.Media.compute_url_hash(url)
        return (
            self.db.query(models.Media.id)
            .filter(
                models.Media.expression_id == expression_id,
                models.Media.url_hash == url_hash,
                models.Media.url == url,
            )
            .first()
            is not None
        )

    def create_media(self, expression_id: int, media_data: Dict[str, Any]) -> models.Media:
        """Create a media row with normalised metadata."""
        prepared = self._prepare_media_data(media_data)
        media_obj = models.Media(expression_id=expression_id, **prepared)
        self.db.add(media_obj)
        self.db.commit()
        self.db.refresh(media_obj)
        return media_obj

    def extract_dynamic_medias(self, url: str, expression: models.Expression) -> None:
        """
        Extract media URLs using Playwright while keeping DB access synchronous.
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.debug("Playwright not available, skipping dynamic media extraction for %s", url)
            return

        if os.getenv("PYTEST_CURRENT_TEST"):
            logger.debug("Test environment detected, skipping dynamic media extraction for %s", url)
            return

        max_retries = max(1, getattr(settings, "PLAYWRIGHT_MAX_RETRIES", 1))
        timeout_ms = getattr(settings, "PLAYWRIGHT_TIMEOUT_MS", 7000)

        async def _run_playwright():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.set_extra_http_headers({"User-Agent": "MyWebIntelligence-Crawler/1.0"})

                    for attempt in range(max_retries):
                        try:
                            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                            await page.wait_for_timeout(3000)

                            await self._collect_media_from_page(page, url, expression)
                            break
                        except Exception as exc:
                            if attempt >= max_retries - 1:
                                logger.warning("Dynamic media extraction failed for %s: %s", url, exc)
                            else:
                                await page.wait_for_timeout(250)
                finally:
                    await browser.close()

        try:
            asyncio.run(_run_playwright())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_run_playwright())
            loop.close()

    async def _collect_media_from_page(self, page, base_url: str, expression: models.Expression) -> None:
        media_selectors = {
            'IMAGE': 'img[src], img[data-src], img[data-original]',
            'VIDEO': 'video[src], video source[src]',
            'AUDIO': 'audio[src], audio source[src]',
        }
        media_type_map = {
            'IMAGE': models.MediaType.IMAGE,
            'VIDEO': models.MediaType.VIDEO,
            'AUDIO': models.MediaType.AUDIO,
        }

        for media_type, selector in media_selectors.items():
            elements = await page.query_selector_all(selector)
            for element in elements:
                src = await element.get_attribute('src') or await element.get_attribute('data-src') or await element.get_attribute('data-original')
                if not src or src.startswith('data:'):
                    continue
                resolved = urljoin(base_url, src)
                if not self.media_exists(expression.id, resolved):
                    self.create_media(
                        expression.id,
                        {
                            'url': resolved,
                            'type': media_type_map.get(media_type, models.MediaType.IMAGE),
                            'is_processed': False,
                        },
                    )

        lazy_img_selectors = [
            'img[data-src]',
            'img[data-lazy-src]',
            'img[data-original]',
            'img[data-url]',
        ]

        for selector in lazy_img_selectors:
            elements = await page.query_selector_all(selector)
            for element in elements:
                for attr in ('data-src', 'data-lazy-src', 'data-original', 'data-url'):
                    src = await element.get_attribute(attr)
                    if src and not src.startswith('data:'):
                        resolved = urljoin(base_url, src)
                        if not self.media_exists(expression.id, resolved):
                            self.create_media(
                                expression.id,
                                {'url': resolved, 'type': models.MediaType.IMAGE, 'is_processed': False},
                            )
                        break

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _clean_media_url(self, url: str, base_url: str) -> Optional[str]:
        """Normalise and validate a media URL."""
        try:
            full_url = urljoin(base_url, url)
            parsed = urlparse(full_url)

            if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
                return None

            if parsed.scheme.startswith('data'):
                return None

            if parsed.netloc.startswith(('i0.wp.com', 'i1.wp.com', 'i2.wp.com')):
                parts = parsed.path.split('/', 2)
                if len(parts) >= 3:
                    original_domain = parts[1]
                    original_path = '/' + parts[2]
                    clean_url = urlunparse(
                        (
                            'https',
                            original_domain,
                            original_path,
                            parsed.params,
                            parsed.query.replace('ssl=1', '').strip('&'),
                            parsed.fragment,
                        )
                    )
                    return clean_url

            return full_url
        except Exception:
            return None

    def _prepare_media_data(self, media_data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter incoming media payload to match the ORM model."""
        data = dict(media_data)

        url_value = data.get('url')
        if url_value:
            data['url_hash'] = models.Media.compute_url_hash(url_value)

        media_type = data.pop('media_type', None) or data.get('type')
        data['type'] = self._normalise_media_type(media_type)

        if data.get('analysis_error'):
            data.setdefault('is_processed', False)
            data.setdefault('processing_error', data['analysis_error'])
        else:
            has_metrics = any(
                data.get(key) is not None
                for key in ('width', 'height', 'file_size', 'format', 'dominant_colors', 'image_hash')
            )
            if has_metrics:
                data.setdefault('is_processed', True)
                data.setdefault('processed_at', datetime.now(timezone.utc))
                data.setdefault('processing_error', None)

        allowed_fields = {column.key for column in models.Media.__table__.columns}  # type: ignore[attr-defined]
        filtered = {key: value for key, value in data.items() if key in allowed_fields}

        unexpected = set(data.keys()) - allowed_fields
        if unexpected:
            logger.debug("Ignored non model fields for media: %s", ", ".join(sorted(unexpected)))

        return filtered

    @staticmethod
    def _normalise_media_type(value: Any) -> models.MediaType:
        """Coerce different representations into a MediaType enum."""
        if isinstance(value, models.MediaType):
            return value

        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return models.MediaType.IMAGE

            upper_candidate = candidate.upper()
            if upper_candidate in models.MediaType.__members__:
                return models.MediaType[upper_candidate]

            lower_candidate = candidate.lower()
            for enum_value in models.MediaType:
                if enum_value.value == lower_candidate:
                    return enum_value

        return models.MediaType.IMAGE

    @staticmethod
    def _analyse_image_properties(img: Image.Image, result: Dict[str, Any]) -> None:
        """Populate basic image properties."""
        result.update(
            {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'color_mode': img.mode,
                'has_transparency': 'A' in img.getbands(),
                'aspect_ratio': round(img.width / img.height, 2) if img.height else 0,
            }
        )

    def _extract_colors(self, img: Image.Image, result: Dict[str, Any]) -> None:
        """Run KMeans to determine dominant colours."""
        n_colors = settings.N_DOMINANT_COLORS
        try:
            resized = img.resize((100, 100)).convert('RGB')
            pixels = np.array(resized).reshape(-1, 3)

            kmeans = KMeans(n_clusters=n_colors, n_init='auto', random_state=42)
            kmeans.fit(pixels)

            counts = np.bincount(kmeans.labels_)
            total = sum(counts)

            sorted_colors = sorted(zip(kmeans.cluster_centers_, counts), key=lambda pair: pair[1], reverse=True)
            dominant = [
                {'rgb': tuple(map(int, colour)), 'percentage': round(count / total * 100, 2)}
                for colour, count in sorted_colors
            ]
            result['dominant_colors'] = dominant

            websafe: Dict[str, float] = {}
            for item in dominant:
                websafe_colour = _convert_to_web_safe(tuple(item['rgb']))
                websafe_hex = '#%02x%02x%02x' % websafe_colour
                websafe.setdefault(websafe_hex, 0.0)
                websafe[websafe_hex] += item['percentage']
            result['websafe_colors'] = websafe
        except Exception as exc:
            if not result.get('error'):
                result['error'] = f"Color analysis error: {exc}"

    @staticmethod
    def _extract_exif(img: Image.Image, result: Dict[str, Any]) -> None:
        """Extract a set of EXIF metadata fields."""
        try:
            exif_data = img.getexif()
            if not exif_data:
                return
            extracted = {
                "ImageWidth": exif_data.get(256),
                "ImageLength": exif_data.get(257),
                "Make": exif_data.get(271),
                "Model": exif_data.get(272),
                "DateTime": exif_data.get(306),
            }
            result['exif_data'] = {key: value for key, value in extracted.items() if value is not None}
        except Exception as exc:
            if not result.get('error'):
                result['error'] = f"EXIF error: {exc}"
