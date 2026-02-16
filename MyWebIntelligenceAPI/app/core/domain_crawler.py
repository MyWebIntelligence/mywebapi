"""
Domain Crawler V2 SYNC

⚠️ V2 = SYNC UNIQUEMENT (voir AGENTS.md)
- ✅ Utilise requests (pas aiohttp)
- ✅ Pas d'async/await
- ✅ 3 stratégies de fallback : Trafilatura → Archive.org → HTTP direct

Stratégie de crawl:
1. Trafilatura (HTTPS puis HTTP si échec)
2. Archive.org Wayback Machine (si Trafilatura échoue)
3. HTTP direct (HTTPS puis HTTP si échec)
"""

from typing import Optional
from datetime import datetime
import time
import logging

import requests
import trafilatura
from bs4 import BeautifulSoup

from app.schemas.domain_crawl import DomainFetchResult
from app.config import settings

logger = logging.getLogger(__name__)


class DomainCrawler:
    """
    Crawler synchrone pour enrichissement de domaines.

    V2 SYNC UNIQUEMENT - pas d'async/await
    """

    def __init__(self):
        """Initialise le crawler avec configuration"""
        self.timeout = getattr(settings, 'DOMAIN_CRAWL_TIMEOUT', 30)
        self.user_agent = getattr(settings, 'DOMAIN_CRAWL_USER_AGENT',
                                   'MyWebIntelligence/2.0 (+https://mywebintelligence.com)')

        # Session requests pour réutilisation des connexions
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        logger.info(f"DomainCrawler initialized (timeout={self.timeout}s)")

    def fetch_domain(self, domain_name: str) -> DomainFetchResult:
        """
        Fetch un domaine avec stratégie multi-fallback (SYNC).

        Stratégie:
        1. Trafilatura (HTTPS → HTTP)
        2. Archive.org (si échec)
        3. HTTP direct (HTTPS → HTTP)

        Args:
            domain_name: Nom du domaine (ex: "example.com")

        Returns:
            DomainFetchResult avec toutes les métadonnées
        """
        start_time = time.time()
        retry_count = 0

        logger.info(f"🕷️  Fetching domain: {domain_name}")

        # Stratégie 1: Trafilatura
        result = self._try_trafilatura(domain_name)
        if result.http_status == 200:
            result.fetch_duration_ms = int((time.time() - start_time) * 1000)
            result.retry_count = retry_count
            logger.info(f"✅ {domain_name} - Success via Trafilatura (HTTP {result.http_status})")
            return result

        retry_count += 1
        logger.warning(f"⚠️  {domain_name} - Trafilatura failed: {result.error_code}")

        # Stratégie 2: Archive.org
        result = self._try_archive_org(domain_name)
        if result.http_status == 200:
            result.fetch_duration_ms = int((time.time() - start_time) * 1000)
            result.retry_count = retry_count
            logger.info(f"✅ {domain_name} - Success via Archive.org (HTTP {result.http_status})")
            return result

        retry_count += 1
        logger.warning(f"⚠️  {domain_name} - Archive.org failed: {result.error_code}")

        # Stratégie 3: HTTP direct
        result = self._try_http_direct(domain_name)
        result.fetch_duration_ms = int((time.time() - start_time) * 1000)
        result.retry_count = retry_count

        if result.http_status == 200:
            logger.info(f"✅ {domain_name} - Success via HTTP direct (HTTP {result.http_status})")
        else:
            logger.error(f"❌ {domain_name} - All strategies failed (HTTP {result.http_status})")

        return result

    def _try_trafilatura(self, domain_name: str) -> DomainFetchResult:
        """
        Tentative de fetch avec Trafilatura.

        Trafilatura gère automatiquement:
        - HTTPS → HTTP fallback
        - Extraction de contenu propre
        - Métadonnées (title, description, date, language)
        """
        try:
            # Trafilatura essaie HTTPS puis HTTP automatiquement
            url = f"https://{domain_name}"

            downloaded = trafilatura.fetch_url(url)

            if not downloaded:
                return DomainFetchResult(
                    domain_name=domain_name,
                    http_status=0,
                    source_method="error",
                    fetched_at=datetime.now(),
                    error_code="ERR_TRAFI_DOWNLOAD",
                    error_message="Trafilatura download failed",
                    fetch_duration_ms=0
                )

            # Extraction des métadonnées avec Trafilatura
            metadata = trafilatura.extract_metadata(downloaded)
            content = trafilatura.extract(downloaded)

            # Fallback BeautifulSoup si Trafilatura ne trouve pas tout
            soup = BeautifulSoup(downloaded, 'html.parser')

            title = None
            description = None
            keywords = None
            language = None

            if metadata:
                title = metadata.title
                description = metadata.description
                language = metadata.language

            # Fallback sur meta tags si nécessaire
            if not title:
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True)

            if not description:
                desc_tag = soup.find('meta', attrs={'name': 'description'})
                if desc_tag:
                    description = desc_tag.get('content', '').strip()

            if not keywords:
                kw_tag = soup.find('meta', attrs={'name': 'keywords'})
                if kw_tag:
                    keywords = kw_tag.get('content', '').strip()

            if not language:
                html_tag = soup.find('html')
                if html_tag:
                    language = html_tag.get('lang', '').strip()

            return DomainFetchResult(
                domain_name=domain_name,
                http_status=200,
                title=title,
                description=description,
                keywords=keywords,
                language=language,
                content=content,
                source_method="trafilatura",
                fetched_at=datetime.now(),
                fetch_duration_ms=0  # Sera rempli par fetch_domain()
            )

        except Exception as e:
            logger.warning(f"Trafilatura error for {domain_name}: {e}")
            return DomainFetchResult(
                domain_name=domain_name,
                http_status=0,
                source_method="error",
                fetched_at=datetime.now(),
                error_code="ERR_TRAFI",
                error_message=str(e),
                fetch_duration_ms=0
            )

    def _try_archive_org(self, domain_name: str) -> DomainFetchResult:
        """
        Tentative de fetch via Archive.org Wayback Machine.

        Récupère la dernière snapshot disponible.
        """
        try:
            # API Wayback Machine - dernière snapshot
            availability_url = f"http://archive.org/wayback/available?url={domain_name}"

            resp = self.session.get(availability_url, timeout=self.timeout)
            resp.raise_for_status()

            data = resp.json()

            # Vérifier si snapshot disponible
            if not data.get('archived_snapshots') or not data['archived_snapshots'].get('closest'):
                return DomainFetchResult(
                    domain_name=domain_name,
                    http_status=404,
                    source_method="error",
                    fetched_at=datetime.now(),
                    error_code="ERR_ARCHIVE_NOTFOUND",
                    error_message="No archive.org snapshot available",
                    fetch_duration_ms=0
                )

            snapshot_url = data['archived_snapshots']['closest']['url']

            # Récupérer le contenu de la snapshot
            snapshot_resp = self.session.get(snapshot_url, timeout=self.timeout)
            snapshot_resp.raise_for_status()

            html = snapshot_resp.text

            # Extraction avec BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            title = None
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)

            description = None
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag:
                description = desc_tag.get('content', '').strip()

            keywords = None
            kw_tag = soup.find('meta', attrs={'name': 'keywords'})
            if kw_tag:
                keywords = kw_tag.get('content', '').strip()

            language = None
            html_tag = soup.find('html')
            if html_tag:
                language = html_tag.get('lang', '').strip()

            # Extraction de contenu propre avec Trafilatura
            content = trafilatura.extract(html) or soup.get_text(separator=' ', strip=True)[:5000]

            return DomainFetchResult(
                domain_name=domain_name,
                http_status=200,
                title=title,
                description=description,
                keywords=keywords,
                language=language,
                content=content,
                source_method="archive_org",
                fetched_at=datetime.now(),
                fetch_duration_ms=0
            )

        except requests.exceptions.RequestException as e:
            logger.warning(f"Archive.org error for {domain_name}: {e}")
            return DomainFetchResult(
                domain_name=domain_name,
                http_status=0,
                source_method="error",
                fetched_at=datetime.now(),
                error_code="ERR_ARCHIVE_HTTP",
                error_message=str(e),
                fetch_duration_ms=0
            )
        except Exception as e:
            logger.warning(f"Archive.org unexpected error for {domain_name}: {e}")
            return DomainFetchResult(
                domain_name=domain_name,
                http_status=0,
                source_method="error",
                fetched_at=datetime.now(),
                error_code="ERR_ARCHIVE",
                error_message=str(e),
                fetch_duration_ms=0
            )

    def _try_http_direct(self, domain_name: str) -> DomainFetchResult:
        """
        Tentative de fetch HTTP direct (HTTPS puis HTTP).

        Dernier recours si Trafilatura et Archive.org échouent.
        """
        # Essayer HTTPS d'abord
        for protocol in ['https', 'http']:
            url = f"{protocol}://{domain_name}"

            try:
                resp = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=False  # Accepter les certificats SSL invalides
                )

                http_status = resp.status_code

                if http_status != 200:
                    logger.warning(f"HTTP {protocol} returned {http_status} for {domain_name}")
                    if protocol == 'http':  # Dernier essai échoué
                        return DomainFetchResult(
                            domain_name=domain_name,
                            http_status=http_status,
                            source_method="error",
                            fetched_at=datetime.now(),
                            error_code=f"ERR_HTTP_{http_status}",
                            error_message=f"HTTP {http_status} - {resp.reason}",
                            fetch_duration_ms=0
                        )
                    continue  # Essayer HTTP si HTTPS a échoué

                # Success - extraire les métadonnées
                html = resp.text
                soup = BeautifulSoup(html, 'html.parser')

                title = None
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True)

                description = None
                desc_tag = soup.find('meta', attrs={'name': 'description'})
                if not desc_tag:
                    desc_tag = soup.find('meta', attrs={'property': 'og:description'})
                if desc_tag:
                    description = desc_tag.get('content', '').strip()

                keywords = None
                kw_tag = soup.find('meta', attrs={'name': 'keywords'})
                if kw_tag:
                    keywords = kw_tag.get('content', '').strip()

                language = None
                html_tag = soup.find('html')
                if html_tag:
                    language = html_tag.get('lang', '').strip()

                # Extraction de contenu avec Trafilatura
                content = trafilatura.extract(html) or soup.get_text(separator=' ', strip=True)[:5000]

                return DomainFetchResult(
                    domain_name=domain_name,
                    http_status=200,
                    title=title,
                    description=description,
                    keywords=keywords,
                    language=language,
                    content=content,
                    source_method="http_direct",
                    fetched_at=datetime.now(),
                    fetch_duration_ms=0
                )

            except requests.exceptions.SSLError as e:
                logger.warning(f"SSL error for {protocol}://{domain_name}: {e}")
                if protocol == 'http':  # Dernier essai
                    return DomainFetchResult(
                        domain_name=domain_name,
                        http_status=0,
                        source_method="error",
                        fetched_at=datetime.now(),
                        error_code="ERR_SSL",
                        error_message=str(e),
                        fetch_duration_ms=0
                    )
                # Continuer avec HTTP

            except requests.exceptions.Timeout as e:
                logger.warning(f"Timeout for {protocol}://{domain_name}")
                if protocol == 'http':
                    return DomainFetchResult(
                        domain_name=domain_name,
                        http_status=0,
                        source_method="error",
                        fetched_at=datetime.now(),
                        error_code="ERR_TIMEOUT",
                        error_message=f"Timeout after {self.timeout}s",
                        fetch_duration_ms=0
                    )

            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error for {protocol}://{domain_name}: {e}")
                if protocol == 'http':
                    return DomainFetchResult(
                        domain_name=domain_name,
                        http_status=0,
                        source_method="error",
                        fetched_at=datetime.now(),
                        error_code="ERR_CONNECTION",
                        error_message=str(e),
                        fetch_duration_ms=0
                    )

            except Exception as e:
                logger.error(f"Unexpected error for {protocol}://{domain_name}: {e}")
                if protocol == 'http':
                    return DomainFetchResult(
                        domain_name=domain_name,
                        http_status=0,
                        source_method="error",
                        fetched_at=datetime.now(),
                        error_code="ERR_HTTP_UNKNOWN",
                        error_message=str(e),
                        fetch_duration_ms=0
                    )

        # Si on arrive ici, toutes les tentatives ont échoué
        return DomainFetchResult(
            domain_name=domain_name,
            http_status=0,
            source_method="error",
            fetched_at=datetime.now(),
            error_code="ERR_HTTP_ALL",
            error_message="All HTTP attempts failed",
            fetch_duration_ms=0
        )

    def close(self):
        """Ferme la session requests"""
        self.session.close()
        logger.info("DomainCrawler session closed")
