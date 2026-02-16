"""
Processeur de médias, adapté de media_analyzer.py.
Analyse les images pour en extraire les métadonnées, les couleurs dominantes, etc.
"""
import io
import hashlib
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse, urlunparse
import httpx
import numpy as np
from PIL import Image, UnidentifiedImageError
from sklearn.cluster import KMeans
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import models
from app.crud import crud_media

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: Playwright not available. Dynamic media extraction will be skipped.")

def generer_palette_web_safe():
    """Génère les 216 couleurs RGB de la palette Web Safe."""
    niveaux = [0, 51, 102, 153, 204, 255]
    return [(r, g, b) for r in niveaux for g in niveaux for b in niveaux]

def distance_rgb(c1, c2):
    """Calcule la distance euclidienne au carré entre deux couleurs RGB."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2))

def convertir_vers_web_safe(rgb):
    """Convertit une couleur RGB en sa correspondante la plus proche dans la palette Web Safe."""
    palette = generer_palette_web_safe()
    return min(palette, key=lambda c: distance_rgb(rgb, c))

class MediaProcessor:
    """Analyseur de médias avec traitement asynchrone."""
    
    def __init__(self, db: AsyncSession, http_client: httpx.AsyncClient):
        self.db = db
        self.http_client = http_client
        self.max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    async def analyze_image(self, url: str) -> Dict[str, Any]:
        """Analyse complète d'une image."""
        result: Dict[str, Any] = {
            'url': url,
            'error': None, 'width': None, 'height': None, 'format': None,
            'file_size': None, 'color_mode': None, 'has_transparency': False,
            'aspect_ratio': None, 'exif_data': None, 'image_hash': None,
            'dominant_colors': [], 'websafe_colors': {}, 'mime_type': None
        }

        try:
            response = await self.http_client.get(url, timeout=30)
            response.raise_for_status()
            result['mime_type'] = response.headers.get('Content-Type')
            
            content = await response.aread()
            if len(content) > self.max_size:
                raise ValueError(f"File size exceeds limit ({len(content)} bytes)")

            result['file_size'] = len(content)
            result['image_hash'] = hashlib.sha256(content).hexdigest()
            
            with Image.open(io.BytesIO(content)) as img:
                self._analyze_image_properties(img, result)
                if settings.ANALYZE_MEDIA:
                    self._extract_colors(img, result)
                    self._extract_exif(img, result)

        except Exception as e:
            result['error'] = str(e)
        
        return result

    def _analyze_image_properties(self, img: Image.Image, result: Dict):
        """Extrait les propriétés basiques de l'image."""
        result.update({
            'width': img.width,
            'height': img.height,
            'format': img.format,
            'color_mode': img.mode,
            'has_transparency': 'A' in img.getbands(),
            'aspect_ratio': round(img.width / img.height, 2) if img.height else 0
        })

    def _extract_colors(self, img: Image.Image, result: Dict[str, Any]):
        """Extrait les couleurs dominantes avec K-means."""
        n_colors = settings.N_DOMINANT_COLORS
        try:
            img_resized = img.resize((100, 100)).convert('RGB')
            pixels = np.array(img_resized).reshape(-1, 3)
            
            kmeans = KMeans(n_clusters=n_colors, n_init='auto', random_state=42)
            kmeans.fit(pixels)
            
            counts = np.bincount(kmeans.labels_)
            total = sum(counts)
            
            sorted_colors = sorted(zip(kmeans.cluster_centers_, counts), key=lambda x: x[1], reverse=True)
            
            dominant_colors = [{'rgb': tuple(map(int, color)), 'percentage': round(count / total * 100, 2)} for color, count in sorted_colors]
            result['dominant_colors'] = dominant_colors
            
            websafe_palette = {}
            for item in dominant_colors:
                websafe_color = convertir_vers_web_safe(item['rgb'])
                websafe_hex = '#%02x%02x%02x' % websafe_color
                websafe_palette.setdefault(websafe_hex, 0)
                websafe_palette[websafe_hex] += item['percentage']
            result['websafe_colors'] = websafe_palette

        except Exception as e:
            if not result.get('error'):
                result['error'] = f"Color analysis error: {str(e)}"

    def _extract_exif(self, img: Image.Image, result: Dict[str, Any]):
        """Extrait les métadonnées EXIF."""
        try:
            exif_data = img.getexif()
            if exif_data:
                exif = {
                    "ImageWidth": exif_data.get(256), "ImageLength": exif_data.get(257),
                    "Make": exif_data.get(271), "Model": exif_data.get(272),
                    "DateTime": exif_data.get(306),
                }
                result['exif_data'] = {k: v for k, v in exif.items() if v is not None}
        except Exception as e:
            if not result.get('error'):
                result['error'] = f"EXIF error: {str(e)}"

    def _clean_media_url(self, url: str, base_url: str) -> Optional[str]:
        """Nettoie et valide une URL de média."""
        try:
            # Résoudre l'URL relative
            full_url = urljoin(base_url, url)
            parsed = urlparse(full_url)
            
            # Validation de base
            if not parsed.scheme in ['http', 'https']:
                return None
            if not parsed.netloc:
                return None
            
            # Skip data URLs et autres schemes problématiques
            if parsed.scheme.startswith('data'):
                return None
            
            # Nettoyer les proxies WordPress problématiques
            if parsed.netloc.startswith('i0.wp.com') or parsed.netloc.startswith('i1.wp.com') or parsed.netloc.startswith('i2.wp.com'):
                # Extraire l'URL originale depuis le proxy WP
                # Format: i0.wp.com/original-domain.com/path?params
                path_parts = parsed.path.split('/', 2)
                if len(path_parts) >= 3:
                    original_domain = path_parts[1]
                    original_path = '/' + path_parts[2]
                    
                    # Reconstruire l'URL sans le proxy
                    clean_url = urlunparse((
                        'https',
                        original_domain,
                        original_path,
                        parsed.params,
                        parsed.query.replace('ssl=1', '').strip('&'),
                        parsed.fragment
                    ))
                    return clean_url
            
            return full_url
            
        except Exception:
            return None

    def extract_media_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extrait les URLs des médias d'un objet BeautifulSoup."""
        urls = set()
        media_tags = soup.find_all(['img', 'video', 'audio'])
        for tag in media_tags:
            # Essayer plusieurs attributs sources
            src = tag.get('src') or tag.get('data-src') or tag.get('data-original')
            if src:
                clean_url = self._clean_media_url(src, base_url)
                if clean_url:
                    urls.add(clean_url)
                    
            # Traiter srcset pour les images responsives
            srcset = tag.get('srcset')
            if srcset:
                for srcset_item in srcset.split(','):
                    src_part = srcset_item.strip().split(' ')[0]
                    if src_part:
                        clean_url = self._clean_media_url(src_part, base_url)
                        if clean_url:
                            urls.add(clean_url)
                            
        return list(urls)

    async def extract_dynamic_medias(self, url: str, expression: models.Expression):
        """
        Extract media URLs from a webpage using a headless browser.
        """
        if not PLAYWRIGHT_AVAILABLE:
            print(f"Playwright not available, skipping dynamic media extraction for {url}")
            return
        
        # Skip dynamic media extraction in test environment
        import os
        if os.getenv('PYTEST_CURRENT_TEST'):
            print(f"Test environment detected, skipping dynamic media extraction for {url}")
            return

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": "MyWebIntelligence-Crawler/1.0"})
            
            max_retries = max(1, getattr(settings, "PLAYWRIGHT_MAX_RETRIES", 1))
            timeout_ms = getattr(settings, "PLAYWRIGHT_TIMEOUT_MS", 7000)
            
            try:
                for attempt in range(max_retries):
                    try:
                        await page.goto(url, wait_until='networkidle', timeout=timeout_ms)
                        await page.wait_for_timeout(3000)

                        media_selectors = {
                            'IMAGE': 'img[src]',
                            'VIDEO': 'video[src], video source[src]',
                            'AUDIO': 'audio[src], audio source[src]'
                        }
                        media_type_map = {
                            'IMAGE': models.MediaType.IMAGE,
                            'VIDEO': models.MediaType.VIDEO,
                            'AUDIO': models.MediaType.AUDIO,
                        }

                        for media_type, selector in media_selectors.items():
                            elements = await page.query_selector_all(selector)
                            for element in elements:
                                src = await element.get_attribute('src')
                                if not src or src.startswith('data:'):
                                    continue
                                resolved_url = urljoin(url, src)
                                if not await crud_media.media.media_exists(self.db, expression_id=expression.id, url=resolved_url):
                                    await crud_media.media.create_media(
                                        self.db,
                                        expression_id=expression.id,
                                        media_data={'url': resolved_url, 'type': media_type_map.get(media_type, models.MediaType.IMAGE)},
                                    )

                        lazy_img_selectors = [
                            'img[data-src]', 'img[data-lazy-src]',
                            'img[data-original]', 'img[data-url]'
                        ]

                        for selector in lazy_img_selectors:
                            elements = await page.query_selector_all(selector)
                            for element in elements:
                                for attr in ['data-src', 'data-lazy-src', 'data-original', 'data-url']:
                                    src = await element.get_attribute(attr)
                                    if not src or src.startswith('data:'):
                                        continue
                                    resolved_url = urljoin(url, src)
                                    if not await crud_media.media.media_exists(self.db, expression_id=expression.id, url=resolved_url):
                                        await crud_media.media.create_media(
                                            self.db,
                                            expression_id=expression.id,
                                            media_data={'url': resolved_url, 'type': models.MediaType.IMAGE},
                                        )
                                    break
                        break
                    except Exception as e:
                        if attempt >= max_retries - 1:
                            print(f"Error during dynamic media extraction for {url}: {e}")
                        else:
                            await page.wait_for_timeout(250)
                            continue
            finally:
                await page.close()
                await browser.close()
