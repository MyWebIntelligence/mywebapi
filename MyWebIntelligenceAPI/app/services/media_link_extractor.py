"""
Media and Link Extractor Service.
Extracts media and links from markdown content, similar to the crawl implementation.
"""
import re
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urljoin, urlparse

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Expression, Media, ExpressionLink
from app.schemas.readable import MediaInfo, LinkInfo
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MediaLinkExtractor:
    """Service for extracting and processing media and links from markdown content."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def extract_media_from_markdown(
        self,
        markdown_content: str,
        base_url: str
    ) -> List[MediaInfo]:
        """
        Extract media information from markdown content.
        Supports images in markdown format and HTML img tags.
        """
        if not markdown_content:
            return []
        
        media_list = []
        
        # Pattern for markdown images: ![alt](url "title")
        image_pattern = r'!\[([^\]]*)\]\(([^\s")]+)(?:\s+"([^"]*)")?\)'
        
        # Pattern for HTML img tags that might be embedded in markdown
        html_img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*?(?:alt=["\']([^"\']*)["\'][^>]*?)?(?:title=["\']([^"\']*)["\'][^>]*)?>'
        
        # Extract markdown images
        for match in re.finditer(image_pattern, markdown_content):
            alt_text = match.group(1).strip() or None
            url = match.group(2).strip()
            title = match.group(3).strip() if match.group(3) else None
            
            if url and self._is_valid_media_url(url):
                absolute_url = urljoin(base_url, url)
                media_type = self._determine_media_type(absolute_url)
                
                media_list.append(MediaInfo(
                    url=absolute_url,
                    alt_text=alt_text,
                    title=title,
                    media_type=media_type
                ))
        
        # Extract HTML images
        for match in re.finditer(html_img_pattern, markdown_content, re.IGNORECASE):
            url = match.group(1).strip()
            alt_text = match.group(2).strip() if match.group(2) else None
            title = match.group(3).strip() if match.group(3) else None
            
            if url and self._is_valid_media_url(url):
                absolute_url = urljoin(base_url, url)
                
                media_list.append(MediaInfo(
                    url=absolute_url,
                    alt_text=alt_text,
                    title=title,
                    media_type='image'
                ))
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_media = []
        for media in media_list:
            if media.url not in seen_urls:
                seen_urls.add(media.url)
                unique_media.append(media)
        
        return unique_media
    
    def extract_links_from_markdown(
        self,
        markdown_content: str,
        base_url: str
    ) -> List[LinkInfo]:
        """
        Extract link information from markdown content.
        Supports markdown links and HTML anchor tags.
        """
        if not markdown_content:
            return []
        
        link_list = []
        
        # Pattern for markdown links: [text](url "title")
        link_pattern = r'(?<!!)\[([^\]]*)\]\(([^\s")]+)(?:\s+"([^"]*)")?\)'
        
        # Pattern for HTML anchor tags
        html_link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*?(?:title=["\']([^"\']*)["\'][^>]*)?>(.*?)</a>'
        
        base_domain = urlparse(base_url).netloc
        
        # Extract markdown links
        for match in re.finditer(link_pattern, markdown_content):
            anchor_text = match.group(1).strip() or None
            url = match.group(2).strip()
            title = match.group(3).strip() if match.group(3) else None
            
            if url and self._is_valid_link_url(url):
                absolute_url = urljoin(base_url, url)
                link_type = self._determine_link_type(absolute_url, base_domain)
                
                link_list.append(LinkInfo(
                    url=absolute_url,
                    anchor_text=anchor_text,
                    title=title,
                    link_type=link_type
                ))
        
        # Extract HTML links
        for match in re.finditer(html_link_pattern, markdown_content, re.IGNORECASE | re.DOTALL):
            url = match.group(1).strip()
            title = match.group(2).strip() if match.group(2) else None
            anchor_text = re.sub(r'<[^>]+>', '', match.group(3)).strip() or None
            
            if url and self._is_valid_link_url(url):
                absolute_url = urljoin(base_url, url)
                link_type = self._determine_link_type(absolute_url, base_domain)
                
                link_list.append(LinkInfo(
                    url=absolute_url,
                    anchor_text=anchor_text,
                    title=title,
                    link_type=link_type
                ))
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_links = []
        for link in link_list:
            if link.url not in seen_urls:
                seen_urls.add(link.url)
                unique_links.append(link)
        
        return unique_links
    
    async def create_media_records(
        self,
        expression_id: int,
        media_list: List[MediaInfo]
    ) -> int:
        """
        Create Media records in database for extracted media.
        Follows the same pattern as crawl media creation.
        """
        try:
            # Delete existing media for this expression (like in crawl)
            existing_media_query = select(Media).where(Media.expression_id == expression_id)
            existing_media_result = await self.db.execute(existing_media_query)
            existing_media = existing_media_result.scalars().all()
            
            for media in existing_media:
                await self.db.delete(media)
            
            # Create new media records
            created_count = 0
            for media_info in media_list:
                # Clean and validate URL (similar to crawl implementation)
                cleaned_url = self._clean_media_url(media_info.url)
                
                if cleaned_url:
                    media = Media(
                        expression_id=expression_id,
                        url=cleaned_url,
                        type=media_info.media_type,
                        alt_text=media_info.alt_text,
                        caption=media_info.title,
                        is_processed=False,
                    )
                    self.db.add(media)
                    created_count += 1
            
            await self.db.flush()  # Ensure IDs are assigned
            return created_count
            
        except Exception as e:
            logger.error(f"Error creating media records for expression {expression_id}: {e}")
            return 0
    
    async def create_expression_links(
        self,
        source_expression_id: int,
        link_list: List[LinkInfo]
    ) -> int:
        """
        Create ExpressionLink records for discovered URLs.
        Similar to the crawl implementation but from markdown links.
        """
        try:
            created_count = 0
            
            for link_info in link_list:
                # Check if target expression exists in the database
                target_query = select(Expression).where(Expression.url == link_info.url)
                target_result = await self.db.execute(target_query)
                target_expression = target_result.scalar_one_or_none()
                
                if target_expression:
                    # Check if link already exists
                    existing_link_query = select(ExpressionLink).where(
                        and_(
                            ExpressionLink.source_id == source_expression_id,
                            ExpressionLink.target_id == target_expression.id
                        )
                    )
                    existing_link_result = await self.db.execute(existing_link_query)
                    existing_link = existing_link_result.scalar_one_or_none()
                    
                    if not existing_link:
                        # Create new expression link
                        expression_link = ExpressionLink(
                            source_id=source_expression_id,
                            target_id=target_expression.id,
                            anchor_text=link_info.anchor_text,
                            link_type=link_info.link_type
                        )
                        self.db.add(expression_link)
                        created_count += 1
                else:
                    # Target URL not in our database yet - could be external or not crawled
                    logger.debug(f"Target URL not found in database: {link_info.url}")
            
            await self.db.flush()
            return created_count
            
        except Exception as e:
            logger.error(f"Error creating expression links for {source_expression_id}: {e}")
            return 0
    
    async def process_expression_media_and_links(
        self,
        expression: Expression,
        markdown_content: str
    ) -> Tuple[int, int]:
        """
        Process both media and links for an expression.
        Returns tuple of (media_created, links_created).
        """
        media_created = 0
        links_created = 0
        
        try:
            # Extract media and links
            media_list = self.extract_media_from_markdown(markdown_content, expression.url)
            link_list = self.extract_links_from_markdown(markdown_content, expression.url)
            
            # Create database records
            if media_list:
                media_created = await self.create_media_records(expression.id, media_list)
                logger.debug(f"Created {media_created} media records for expression {expression.id}")
            
            if link_list:
                links_created = await self.create_expression_links(expression.id, link_list)
                logger.debug(f"Created {links_created} expression links for expression {expression.id}")
            
            return media_created, links_created
            
        except Exception as e:
            logger.error(f"Error processing media and links for expression {expression.id}: {e}")
            return 0, 0
    
    def _is_valid_media_url(self, url: str) -> bool:
        """Check if URL is a valid media URL."""
        if not url or url.startswith('#') or url.startswith('javascript:'):
            return False
        
        # Skip data URLs (too long for database)
        if url.startswith('data:'):
            return False
        
        # Skip mailto and tel links
        if url.startswith(('mailto:', 'tel:')):
            return False
        
        return True
    
    def _is_valid_link_url(self, url: str) -> bool:
        """Check if URL is a valid link URL."""
        if not url or url.startswith('#'):  # Skip empty and anchor links
            return False
        
        # Skip javascript and data URLs
        if url.startswith(('javascript:', 'data:')):
            return False
        
        return True
    
    def _determine_media_type(self, url: str) -> str:
        """Determine media type from URL."""
        url_lower = url.lower()
        
        # Image extensions
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico']
        if any(url_lower.endswith(ext) for ext in image_extensions):
            return 'image'
        
        # Video extensions
        video_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv']
        if any(url_lower.endswith(ext) for ext in video_extensions):
            return 'video'
        
        # Audio extensions
        audio_extensions = ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a']
        if any(url_lower.endswith(ext) for ext in audio_extensions):
            return 'audio'
        
        # Default to image for media extracted from markdown images
        return 'image'
    
    def _determine_link_type(self, url: str, base_domain: str) -> str:
        """Determine if link is internal or external."""
        try:
            link_domain = urlparse(url).netloc
            return 'internal' if link_domain == base_domain else 'external'
        except Exception:
            return 'external'
    
    def _clean_media_url(self, url: str) -> Optional[str]:
        """
        Clean media URL similar to the crawl implementation.
        Remove tracking parameters and fix common issues.
        """
        if not url:
            return None
        
        # Remove common tracking parameters
        tracking_params = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
            'fbclid', 'gclid', 'ref', 'source'
        ]
        
        try:
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # Remove tracking parameters
            cleaned_params = {
                k: v for k, v in query_params.items()
                if k not in tracking_params
            }
            
            # Rebuild URL
            clean_query = urlencode(cleaned_params, doseq=True)
            cleaned_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                clean_query,
                ''  # Remove fragment
            ))
            
            # Fix common WordPress proxy issues (like in crawl)
            if 'i0.wp.com' in cleaned_url or 'i1.wp.com' in cleaned_url:
                # Extract original URL from WordPress proxy
                if '?url=' in cleaned_url:
                    original_url = cleaned_url.split('?url=')[1].split('&')[0]
                    from urllib.parse import unquote
                    cleaned_url = unquote(original_url)
            
            return cleaned_url
            
        except Exception as e:
            logger.warning(f"Failed to clean URL {url}: {e}")
            return url