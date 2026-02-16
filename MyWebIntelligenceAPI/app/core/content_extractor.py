"""
Extracteur de contenu et de métadonnées à partir de HTML brut.
Adapté de readable_pipeline.py et des fonctions de core.py.
"""
from typing import Dict, Any, Optional, Tuple, List
from bs4 import BeautifulSoup
import trafilatura
import httpx
import asyncio
import json
import re
from urllib.parse import urljoin, urlparse

def get_readable_content(html: str) -> Tuple[str, BeautifulSoup, Optional[str]]:
    """
    Extrait le contenu lisible d'un HTML avec stratégie de fallback en cascade:
    1. Trafilatura with markdown format (primary)
    2. BeautifulSoup (fallback)

    Returns:
        Tuple[readable_text, soup, readable_html] where readable_html is the HTML version from Trafilatura
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Méthode 1: Trafilatura (preferred) - ALIGNED WITH LEGACY
    # Extract both markdown and HTML formats for media enrichment
    readable_text = trafilatura.extract(
        html,
        include_comments=False,
        include_links=True,
        include_images=True,
        output_format='markdown',
        include_tables=True,
        include_formatting=True,
        favor_precision=True
    )

    readable_html = trafilatura.extract(
        html,
        include_comments=False,
        include_links=True,
        include_images=True,
        output_format='html'
    )

    if readable_text and len(readable_text) > 100:
        print("Readable content extracted with Trafilatura (markdown format).")
        return readable_text, soup, readable_html

    # Méthode 2: BeautifulSoup fallback with smart extraction
    print("Trafilatura failed, falling back to BeautifulSoup with smart extraction.")

    # Try smart extraction first (intelligent heuristics)
    smart_content, filtered_soup_elem = _smart_content_extraction(soup)
    if smart_content and len(smart_content) > 100:
        print("Smart extraction succeeded on BeautifulSoup.")
        return smart_content, soup, None

    # Final fallback: basic text extraction
    print("Smart extraction failed, using basic text extraction.")
    clean_html(soup)
    text = soup.get_text(separator='\n', strip=True)
    return text, soup, None

def _smart_content_extraction(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[BeautifulSoup]]:
    """
    Extraction intelligente basée sur les heuristiques de contenu principal.
    Inspiré de la logique Mercury Parser du système ancien.

    Returns:
        Tuple[text_content, filtered_soup_element]:
            - text_content: Texte extrait du contenu principal
            - filtered_soup_element: Élément BeautifulSoup du contenu principal (pour extraction liens/médias)
    """
    # Priorité aux sélecteurs de contenu communs
    content_selectors = [
        'article', '[role="main"]', 'main', '.content', '.post-content',
        '.entry-content', '.article-content', '.post-body', '.story-body',
        '#content', '#main-content', '.main-content', '.article-body'
    ]

    for selector in content_selectors:
        elements = soup.select(selector)
        if elements:
            # Prendre le plus grand élément trouvé
            largest_element = max(elements, key=lambda x: len(x.get_text(strip=True)))
            text_content = largest_element.get_text(separator='\n', strip=True)
            if len(text_content) > 200:
                return text_content, largest_element  # ✅ Retourner aussi l'élément filtré

    # Fallback: chercher les paragraphes les plus substantiels
    paragraphs = soup.find_all('p')
    if paragraphs:
        content_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50]
        if content_paragraphs:
            return '\n\n'.join(content_paragraphs), None  # Pas de soup filtré dans ce cas

    return None, None

def get_metadata(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """
    Extrait les métadonnées (titre, description, etc.) d'un objet BeautifulSoup.
    """
    title = get_title(soup) or url
    description = get_description(soup)
    keywords = get_keywords(soup)
    lang = soup.html.get('lang', '') if soup.html else ''
    canonical_url = get_canonical_url(soup)
    published_at = get_published_date(soup)

    return {
        'title': title,
        'description': description,
        'keywords': keywords,
        'lang': lang,
        'canonical_url': canonical_url,
        'published_at': published_at
    }

def get_title(soup: BeautifulSoup) -> Optional[str]:
    """Extrait le titre avec une chaîne de fallbacks."""
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        return og_title['content'].strip()

    twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
    if twitter_title and twitter_title.get('content'):
        return twitter_title['content'].strip()

    title_tag = soup.find('title')
    if title_tag and title_tag.string:
        return title_tag.string.strip()
        
    return None

def get_description(soup: BeautifulSoup) -> Optional[str]:
    """Extrait la description avec une chaîne de fallbacks."""
    og_desc = soup.find('meta', property='og:description')
    if og_desc and og_desc.get('content'):
        return og_desc['content'].strip()

    twitter_desc = soup.find('meta', attrs={'name': 'twitter:description'})
    if twitter_desc and twitter_desc.get('content'):
        return twitter_desc['content'].strip()

    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        return meta_desc['content'].strip()

    return None

def get_keywords(soup: BeautifulSoup) -> Optional[str]:
    """Extrait les mots-clés."""
    keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
    if keywords_tag and keywords_tag.get('content'):
        return keywords_tag['content'].strip()
    return None

def get_canonical_url(soup: BeautifulSoup) -> Optional[str]:
    """Extrait l'URL canonique de la page."""
    # Chercher la balise <link rel="canonical">
    canonical_tag = soup.find('link', rel='canonical')
    if canonical_tag and canonical_tag.get('href'):
        return canonical_tag['href'].strip()

    # Fallback: og:url
    og_url = soup.find('meta', property='og:url')
    if og_url and og_url.get('content'):
        return og_url['content'].strip()

    return None

def get_published_date(soup: BeautifulSoup) -> Optional[str]:
    """
    Extrait la date de publication de la page avec une chaîne de fallbacks.

    Retourne la date au format ISO 8601 string ou None.
    """
    # Priority 1: article:published_time (Open Graph)
    published_time = soup.find('meta', property='article:published_time')
    if published_time and published_time.get('content'):
        return published_time['content'].strip()

    # Priority 2: datePublished (Schema.org)
    date_published = soup.find('meta', attrs={'itemprop': 'datePublished'})
    if date_published and date_published.get('content'):
        return date_published['content'].strip()

    # Priority 3: dc.date (Dublin Core)
    dc_date = soup.find('meta', attrs={'name': 'dc.date'})
    if dc_date and dc_date.get('content'):
        return dc_date['content'].strip()

    # Priority 4: date (generic meta tag)
    date_meta = soup.find('meta', attrs={'name': 'date'})
    if date_meta and date_meta.get('content'):
        return date_meta['content'].strip()

    # Priority 5: published_time (generic)
    published = soup.find('meta', attrs={'name': 'published_time'})
    if published and published.get('content'):
        return published['content'].strip()

    return None

def clean_html(soup: BeautifulSoup):
    """Supprime les balises inutiles du HTML."""
    for selector in ['script', 'style', 'nav', 'footer', 'aside']:
        for tag in soup.select(selector):
            tag.decompose()

def resolve_url(base_url: str, url: str) -> str:
    """Resolve relative URL to absolute URL."""
    if not url or url.startswith('data:'):
        return url
    return urljoin(base_url, url)

def enrich_markdown_with_media(markdown_content: str, readable_html: Optional[str], base_url: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Enrichit le contenu markdown avec les marqueurs IMAGE/VIDEO/AUDIO.
    Retourne le markdown enrichi et la liste des médias détectés.

    Cette fonction reproduit la logique legacy de _legacy/core.py:1759-1786.
    """
    media_list = []
    media_lines = []

    if readable_html:
        soup_readable = BeautifulSoup(readable_html, 'html.parser')

        # Extract images
        for img in soup_readable.find_all('img'):
            src = img.get('src')
            if src:
                resolved_url = resolve_url(base_url, src)
                media_lines.append(f"![IMAGE]({resolved_url})")
                media_list.append({'url': resolved_url, 'type': 'img'})

        # Extract videos
        for video in soup_readable.find_all('video'):
            src = video.get('src')
            if src:
                resolved_url = resolve_url(base_url, src)
                media_lines.append(f"[VIDEO: {resolved_url}]")
                media_list.append({'url': resolved_url, 'type': 'video'})

        # Extract audio
        for audio in soup_readable.find_all('audio'):
            src = audio.get('src')
            if src:
                resolved_url = resolve_url(base_url, src)
                media_lines.append(f"[AUDIO: {resolved_url}]")
                media_list.append({'url': resolved_url, 'type': 'audio'})

    # Also extract images from markdown format (for images converted to markdown)
    img_md_links = re.findall(r'!\[.*?\]\((.*?)\)', markdown_content)
    for img_url in img_md_links:
        resolved_url = resolve_url(base_url, img_url)
        # Avoid duplicates
        if not any(m['url'] == resolved_url for m in media_list):
            media_list.append({'url': resolved_url, 'type': 'img'})

    # Append media lines to markdown content
    enriched_content = markdown_content
    if media_lines:
        enriched_content += "\n\n" + "\n".join(media_lines)

    return enriched_content, media_list

def extract_md_links(markdown_content: str) -> List[str]:
    """
    Extrait tous les liens markdown du contenu.
    Retourne une liste d'URLs.

    Cette fonction reproduit extract_md_links() du legacy.
    """
    # Extract markdown links: [text](url)
    md_links = re.findall(r'\[.*?\]\((.*?)\)', markdown_content)

    # Filter out image links (starting with !)
    links = [link for link in md_links if not link.startswith('!')]

    return links

async def get_readable_content_with_fallbacks(url: str, html: Optional[str] = None) -> Dict[str, Any]:
    """
    Extrait le contenu lisible avec fallbacks avancés (ALIGNED WITH LEGACY):
    1. Trafilatura sur HTML fourni (markdown + enrichissement médias)
    2. Archive.org + Trafilatura (si échec #1)
    3. BeautifulSoup fallback

    Returns:
        Dict with:
            - readable: Contenu principal extrait (markdown ou texte)
            - content: HTML brut complet
            - soup: BeautifulSoup du HTML complet
            - filtered_soup: BeautifulSoup du contenu principal uniquement (None si Trafilatura/markdown)
            - extraction_source: Source d'extraction ('trafilatura_direct', 'archive_org', 'beautifulsoup_smart', 'beautifulsoup_basic', 'all_failed')
            - media_list: Liste des médias extraits
            - links: Liste des liens extraits
            - title, description, keywords, language, canonical_url, published_at: Métadonnées
    """
    soup = None
    readable_html = None
    raw_html = html

    # Method 1: Trafilatura on provided HTML with markdown format
    if html:
        soup = BeautifulSoup(html, 'html.parser')

        # Extract with Trafilatura in markdown format
        readable_text = trafilatura.extract(
            html,
            include_comments=False,
            include_links=True,
            include_images=True,
            output_format='markdown',
            include_tables=True,
            include_formatting=True,
            favor_precision=True
        )

        readable_html = trafilatura.extract(
            html,
            include_comments=False,
            include_links=True,
            include_images=True,
            output_format='html'
        )

        if readable_text and len(readable_text) > 100:
            # Enrich markdown with media markers (legacy behavior)
            enriched_content, media_list = enrich_markdown_with_media(readable_text, readable_html, url)
            links = extract_md_links(enriched_content)

            # Extract metadata robustly from soup
            metadata = get_metadata(soup, url)

            return {
                'readable': enriched_content,
                'content': raw_html,
                'soup': soup,
                'readable_html': readable_html,
                'filtered_soup': None,  # Trafilatura: pas besoin de soup filtré (markdown déjà extrait)
                'extraction_source': 'trafilatura_direct',
                'media_list': media_list,
                'links': links,
                'title': metadata.get('title'),
                'description': metadata.get('description'),
                'keywords': metadata.get('keywords'),
                'language': metadata.get('lang'),
                'canonical_url': metadata.get('canonical_url'),
                'published_at': metadata.get('published_at')
            }

    # Method 2: Archive.org fallback (before BeautifulSoup, aligned with legacy)
    try:
        archived_result = await _extract_from_archive_org(url)
        if archived_result and archived_result.get('readable'):
            return archived_result
    except Exception as e:
        print(f"Archive.org fallback failed for {url}: {e}")

    # Method 3: BeautifulSoup fallback on original HTML with smart extraction
    if soup:
        # Extract metadata before any modifications
        metadata = get_metadata(soup, url)

        # Try smart extraction first (intelligent heuristics)
        smart_content, smart_soup_element = _smart_content_extraction(soup)
        if smart_content and len(smart_content) > 100:
            return {
                'readable': smart_content,
                'content': raw_html,
                'soup': soup,
                'readable_html': None,
                'filtered_soup': smart_soup_element,  # ✅ Élément filtré (article/main/etc.)
                'extraction_source': 'beautifulsoup_smart',
                'media_list': [],
                'links': [],
                'title': metadata.get('title'),
                'description': metadata.get('description'),
                'keywords': metadata.get('keywords'),
                'language': metadata.get('lang'),
                'canonical_url': metadata.get('canonical_url'),
                'published_at': metadata.get('published_at')
            }

        # Final fallback: basic text extraction
        clean_html(soup)  # Supprime nav, footer, aside, script, style
        text = soup.get_text(separator='\n', strip=True)
        if len(text) > 100:
            return {
                'readable': text,
                'content': raw_html,
                'soup': soup,
                'readable_html': None,
                'filtered_soup': soup,  # ✅ Soup nettoyé (sans nav/footer/aside)
                'extraction_source': 'beautifulsoup_basic',
                'media_list': [],
                'links': [],
                'title': metadata.get('title'),
                'description': metadata.get('description'),
                'keywords': metadata.get('keywords'),
                'language': metadata.get('lang'),
                'canonical_url': metadata.get('canonical_url'),
                'published_at': metadata.get('published_at')
            }

    # All methods failed - still extract metadata if soup is available
    final_metadata = get_metadata(soup, url) if soup else {}
    return {
        'readable': None,
        'content': raw_html,
        'soup': soup,
        'readable_html': None,
        'filtered_soup': None,  # Aucune extraction réussie
        'extraction_source': 'all_failed',
        'media_list': [],
        'links': [],
        'title': final_metadata.get('title'),
        'description': final_metadata.get('description'),
        'keywords': final_metadata.get('keywords'),
        'language': final_metadata.get('lang'),
        'canonical_url': final_metadata.get('canonical_url'),
        'published_at': final_metadata.get('published_at')
    }

async def _extract_from_archive_org(url: str) -> Optional[Dict[str, Any]]:
    """
    Extract content from Archive.org archived version of the URL.
    ALIGNED WITH LEGACY (_legacy/core.py:1812-1857).

    Uses trafilatura.fetch_url and reproduces full markdown enrichment pipeline.
    """
    try:
        # Get archived snapshot info
        archive_api_url = f"http://archive.org/wayback/available?url={url}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(archive_api_url)
            response.raise_for_status()
            archive_data = response.json()

            archived_url = archive_data.get('archived_snapshots', {}).get('closest', {}).get('url')
            if not archived_url:
                return None

            print(f"Archive.org snapshot found: {archived_url}")

            # Use trafilatura.fetch_url (legacy behavior) instead of httpx
            archived_html = await asyncio.to_thread(trafilatura.fetch_url, archived_url)

            if not archived_html:
                return None

            # Extract with Trafilatura in markdown format (legacy behavior)
            extracted_content = trafilatura.extract(
                archived_html,
                include_comments=False,
                include_links=True,
                include_images=True,
                output_format='markdown',
                include_tables=True,
                include_formatting=True,
                favor_precision=True
            )

            readable_html = trafilatura.extract(
                archived_html,
                include_comments=False,
                include_links=True,
                include_images=True,
                output_format='html'
            )

            if extracted_content and len(extracted_content) > 100:
                # Enrich markdown with media markers (legacy behavior)
                enriched_content, media_list = enrich_markdown_with_media(extracted_content, readable_html, url)
                links = extract_md_links(enriched_content)

                soup = BeautifulSoup(archived_html, 'html.parser')
                metadata = get_metadata(soup, url)

                return {
                    'readable': enriched_content,
                    'content': archived_html,
                    'soup': soup,
                    'readable_html': readable_html,
                    'filtered_soup': None,  # Archive.org: Trafilatura markdown (pas besoin de soup filtré)
                    'extraction_source': 'archive_org',
                    'media_list': media_list,
                    'links': links,
                    'title': metadata.get('title'),
                    'description': metadata.get('description'),
                    'keywords': metadata.get('keywords'),
                    'language': metadata.get('lang'),
                    'canonical_url': metadata.get('canonical_url'),
                    'published_at': metadata.get('published_at')
                }

    except Exception as e:
        print(f"Error in Archive.org extraction for {url}: {e}")

    return None


class ContentExtractor:
    """
    Content extractor class that wraps the extraction functions.
    """

    def __init__(self):
        pass

    def get_readable_content(self, html: str) -> Tuple[str, BeautifulSoup, Optional[str]]:
        """Extract readable content from HTML."""
        return get_readable_content(html)

    def get_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract metadata from BeautifulSoup object."""
        return get_metadata(soup, url)

    async def get_readable_content_with_fallbacks(self, url: str, html: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract readable content with fallbacks and return structured result.
        Returns enriched markdown with media markers and extracted links.

        Metadata priority (LEGACY ALIGNED):
        1. Trafilatura native metadata (extract_metadata)
        2. BeautifulSoup meta tags (OG, Twitter, Schema.org)
        """
        result = await get_readable_content_with_fallbacks(url, html)

        if not result.get('readable'):
            return {
                'readable': None,
                'content': html or '',
                'soup': result.get('soup'),
                'title': url,
                'description': None,
                'language': None,
                'extraction_source': result.get('extraction_source', 'all_failed'),
                'media_list': [],
                'links': []
            }

        # Extract metadata with priority: Trafilatura > BeautifulSoup
        trafi_metadata = {}
        bs_metadata = {}

        # 1. Try Trafilatura native metadata first (PRIORITY 1)
        if html:
            try:
                import trafilatura
                meta_obj = trafilatura.extract_metadata(html)
                if meta_obj:
                    trafi_metadata = {
                        'title': meta_obj.title,
                        'description': meta_obj.description,
                        'keywords': ', '.join(meta_obj.tags) if meta_obj.tags else None,
                        'lang': meta_obj.language,
                        'published_at': meta_obj.date  # Trafilatura extrait la date de publication
                    }
            except Exception:
                pass

        # 2. BeautifulSoup fallback (PRIORITY 2)
        if result.get('soup'):
            bs_metadata = get_metadata(result['soup'], url)

        # 3. Combine with Trafilatura priority
        final_metadata = {
            'title': trafi_metadata.get('title') or bs_metadata.get('title') or url,
            'description': trafi_metadata.get('description') or bs_metadata.get('description'),
            'keywords': trafi_metadata.get('keywords') or bs_metadata.get('keywords'),
            'lang': trafi_metadata.get('lang') or bs_metadata.get('lang'),
            'published_at': trafi_metadata.get('published_at') or bs_metadata.get('published_at'),
            'canonical_url': bs_metadata.get('canonical_url')  # Canonical URL vient toujours de BeautifulSoup
        }

        return {
            'readable': result['readable'],
            'content': result.get('content', html or ''),
            'readable_html': result.get('readable_html'),
            'soup': result.get('soup'),
            'title': final_metadata['title'],
            'description': final_metadata['description'],
            'keywords': final_metadata['keywords'],
            'language': final_metadata['lang'],
            'published_at': final_metadata['published_at'],
            'canonical_url': final_metadata['canonical_url'],
            'extraction_source': result.get('extraction_source'),
            'media_list': result.get('media_list', []),
            'links': result.get('links', [])
        }
