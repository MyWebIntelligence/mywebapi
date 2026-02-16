#!/usr/bin/env python3
"""
End-to-end scenario script for MyWebIntelligence API.

Mirrors the legacy CLI workflow:
1. Authenticate and obtain a JWT.
2. Create a land (topic/project).
3. List lands to confirm creation.
4. Add terms (keywords) to the land.
5. Add seed URLs to the land.
6. Trigger a crawl job for the land.
7. Fetch land statistics.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, Any, List

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a full land-management scenario against the MyWI API.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("MYWI_BASE_URL", "http://localhost:8000"),
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("MYWI_USERNAME", "admin@example.com"),
        help="Username for authentication (default: admin@example.com)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("MYWI_PASSWORD", "changeme"),
        help="Password for authentication (default: changeme)",
    )
    parser.add_argument(
        "--land-name",
        default=None,
        help="Name of the land to create (default: generated from timestamp)",
    )
    parser.add_argument(
        "--description",
        default="Research land created via scenario script.",
        help="Land description.",
    )
    parser.add_argument(
        "--lang",
        default="fr",
        help="Comma-separated list of language codes (default: fr).",
    )
    parser.add_argument(
        "--terms",
        default="keyword1,keyword2",
        help="Comma-separated keywords to add to the land.",
    )
    parser.add_argument(
        "--terms-file",
        default=None,
        help="Optional path to a file containing one keyword per line.",
    )
    parser.add_argument(
        "--urls",
        default="",
        help="Comma-separated URLs to seed the land with.",
    )
    parser.add_argument(
        "--urls-file",
        default=None,
        help="Optional path to a file containing one URL per line.",
    )
    parser.add_argument(
        "--crawl-limit",
        type=int,
        default=25,
        help="Optional crawl limit when launching the crawl job.",
    )
    parser.add_argument(
        "--analysemedia",
        default="FALSE",
        help="Set to TRUE to enable media analysis during the crawl (default: FALSE).",
    )
    return parser.parse_args()


def _load_entries_from_file(path: str | None) -> List[str]:
    if not path:
        return []
    entries: List[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            candidate = line.strip()
            if candidate and not candidate.startswith("#"):
                entries.append(candidate)
    return entries


def authenticate(base_url: str, username: str, password: str) -> str:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/v1/auth/login",
        data={"username": username, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["access_token"]


def create_land(
    session: requests.Session,
    base_url: str,
    name: str,
    description: str,
    langs: List[str],
    start_urls: List[str],
) -> Dict[str, Any]:
    payload = {
        "name": name,
        "description": description,
        "lang": langs,
        "start_urls": start_urls,
    }
    response = session.post(
        f"{base_url.rstrip('/')}/api/v2/lands/",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def list_lands(session: requests.Session, base_url: str) -> Dict[str, Any]:
    response = session.get(
        f"{base_url.rstrip('/')}/api/v2/lands/",
        params={"page": 1, "page_size": 50},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def add_terms(session: requests.Session, base_url: str, land_id: int, terms: List[str]) -> Dict[str, Any]:
    response = session.post(
        f"{base_url.rstrip('/')}/api/v2/lands/{land_id}/terms",
        json={"terms": terms},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def add_urls(session: requests.Session, base_url: str, land_id: int, urls: List[str]) -> Dict[str, Any]:
    response = session.post(
        f"{base_url.rstrip('/')}/api/v2/lands/{land_id}/urls",
        json={"urls": urls},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def trigger_crawl(
    session: requests.Session,
    base_url: str,
    land_id: int,
    limit: int | None,
    analyze_media: bool,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if limit is not None:
        payload["limit"] = limit
    if analyze_media:
        payload["analyze_media"] = True

    response = session.post(
        f"{base_url.rstrip('/')}/api/v2/lands/{land_id}/crawl",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def land_stats(session: requests.Session, base_url: str, land_id: int) -> Dict[str, Any]:
    response = session.get(
        f"{base_url.rstrip('/')}/api/v2/lands/{land_id}/stats",
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def pretty(title: str, data: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(data)


def main() -> None:
    args = parse_args()

    land_name = args.land_name or f"Land_{int(time.time())}"
    langs = [lang.strip() for lang in args.lang.split(",") if lang.strip()]

    terms = [term.strip() for term in args.terms.split(",") if term.strip()]
    terms.extend(_load_entries_from_file(args.terms_file))
    # Deduplicate while preserving order
    seen_terms = set()
    terms = [t for t in terms if not (t in seen_terms or seen_terms.add(t))]

    urls = [url.strip() for url in args.urls.split(",") if url.strip()]
    urls.extend(_load_entries_from_file(args.urls_file))
    seen_urls = set()
    urls = [u for u in urls if not (u in seen_urls or seen_urls.add(u))]
    if not urls:
        urls = ["https://example.org"]

    print(f"Authenticating as {args.username}...")
    token = authenticate(args.base_url, args.username, args.password)
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})

    print(f"Creating land '{land_name}'...")
    land = create_land(session, args.base_url, land_name, args.description, langs, urls)
    pretty("Created Land", land)
    land_id = land["id"]

    analyze_media_flag = str(getattr(args, "analysemedia", "FALSE")).strip().lower() in {"true", "1", "yes", "y"}

    lands = list_lands(session, args.base_url)
    pretty("Lands (paginated)", lands)

    if terms:
        print("Adding terms to land...")
        updated = add_terms(session, args.base_url, land_id, terms)
        pretty("Land After Terms", {"id": updated["id"], "words": updated.get("words", [])})

    additional_urls = [url for url in urls if url]
    if additional_urls:
        print("Re-appending URLs to ensure deduplication logic works...")
        updated = add_urls(session, args.base_url, land_id, additional_urls)
        pretty("Land After URLs", {"id": updated["id"], "start_urls": updated.get("start_urls", [])})

    print(f"Triggering crawl job... (analysemedia={'TRUE' if analyze_media_flag else 'FALSE'})")
    crawl_job = trigger_crawl(session, args.base_url, land_id, args.crawl_limit, analyze_media_flag)
    pretty("Crawl Job Response", crawl_job)

    stats = land_stats(session, args.base_url, land_id)
    pretty("Land Stats (mock data)", stats)

    print("\nScenario completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as http_err:
        print("HTTP error:", file=sys.stderr)
        if http_err.response is not None:
            print(http_err.response.text, file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
