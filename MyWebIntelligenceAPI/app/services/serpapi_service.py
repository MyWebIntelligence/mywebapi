"""
SerpAPI integration helpers migrated from the legacy crawler core.
"""
from __future__ import annotations

import calendar
import random
import re
import time
from datetime import date, datetime, timedelta
from typing import Callable, Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse

import requests

from app.config import settings


class SerpApiError(Exception):
    """Raised when a SerpAPI request or response fails."""


def fetch_serpapi_url_list(
    api_key: str,
    query: str,
    engine: str = "google",
    lang: str = "fr",
    datestart: Optional[str] = None,
    dateend: Optional[str] = None,
    timestep: str = "week",
    sleep_seconds: float = 1.0,
    progress_hook: Optional[Callable[[Optional[date], Optional[date], int], None]] = None,
) -> List[Dict[str, Optional[Union[str, int]]]]:
    """
    Query SerpAPI for organic results and return URL metadata.
    """
    normalized_query = (query or "").strip()
    if not normalized_query:
        raise SerpApiError("Query must be a non-empty string")

    engine = (engine or "google").strip().lower() or "google"
    allowed_engines = {"google", "bing", "duckduckgo"}
    if engine not in allowed_engines:
        raise SerpApiError(f'Unsupported SerpAPI engine "{engine}"')

    lang = (lang or "fr").strip().lower() or "fr"
    timestep = (timestep or "week").strip().lower() or "week"

    if bool(datestart) ^ bool(dateend):
        raise SerpApiError("Both datestart and dateend must be provided together")

    date_capable_engines = {"google", "duckduckgo"}
    if (datestart or dateend) and engine not in date_capable_engines:
        raise SerpApiError("Date filtering is only supported with the google or duckduckgo engines")

    normalized_start: Optional[date] = None
    normalized_end: Optional[date] = None
    if datestart and dateend:
        normalized_start = _parse_serpapi_date(datestart)
        normalized_end = _parse_serpapi_date(dateend)
        if normalized_start > normalized_end:
            raise SerpApiError("datestart must be earlier than or equal to dateend")

    date_windows: List[Tuple[Optional[date], Optional[date]]] = []
    if engine in date_capable_engines and normalized_start and normalized_end:
        date_windows = list(_build_serpapi_windows(datestart, dateend, timestep))
    if not date_windows:
        date_windows = [(normalized_start, normalized_end)]

    aggregated: List[Dict[str, Optional[Union[str, int]]]] = []

    base_url = getattr(settings, "SERPAPI_BASE_URL", "https://serpapi.com/search")
    timeout = getattr(settings, "SERPAPI_TIMEOUT", 15)
    jitter_floor, jitter_ceil = 0.8, 1.2
    page_size = _serpapi_page_size(engine)

    for window_start, window_end in date_windows:
        start_index = 0
        window_count = 0
        while True:
            params: Dict[str, Union[str, int]] = {
                "api_key": api_key,
                "engine": engine,
                "q": normalized_query,
            }
            params.update(
                _build_serpapi_params(
                    engine,
                    lang,
                    start_index,
                    page_size,
                    window_start=window_start,
                    window_end=window_end,
                    use_date_filter=bool(window_start and window_end),
                )
            )

            if engine == "google" and window_start and window_end:
                params["tbs"] = _build_serpapi_tbs(window_start, window_end)

            try:
                response = requests.get(base_url, params=params, timeout=timeout)
            except requests.RequestException as exc:
                raise SerpApiError(f"HTTP error during SerpAPI request: {exc}") from exc

            if response.status_code != 200:
                snippet = response.text[:200]
                raise SerpApiError(f"SerpAPI request failed with status {response.status_code}: {snippet}")

            try:
                payload = response.json()
            except ValueError as exc:
                raise SerpApiError("Invalid JSON payload returned by SerpAPI") from exc

            if "error" in payload:
                message = str(payload.get("error", "")).strip()
                lowered = message.lower()
                if engine == "duckduckgo" and "hasn't returned any results" in lowered:
                    break
                raise SerpApiError(f"SerpAPI error: {message}")

            organic_results = payload.get("organic_results") or []
            if not organic_results:
                break

            for entry in organic_results:
                aggregated.append(
                    {
                        "position": entry.get("position"),
                        "title": entry.get("title"),
                        "link": entry.get("link"),
                        "date": entry.get("date"),
                    }
                )
                window_count += 1

            serp_pagination = payload.get("serpapi_pagination") or {}
            next_link = serp_pagination.get("next_link") or serp_pagination.get("next")
            has_next_page = bool(next_link)

            if not has_next_page:
                break

            next_offset_raw = serp_pagination.get("next_offset")
            next_index: Optional[int] = None
            if next_offset_raw is not None:
                try:
                    next_index = int(next_offset_raw)
                except (TypeError, ValueError):
                    next_index = None

            if next_index is None and isinstance(next_link, str):
                try:
                    parsed = urlparse(next_link)
                    query_params = parse_qs(parsed.query)
                except Exception:
                    query_params = {}

                for key in ("start", "first", "offset"):
                    values = query_params.get(key)
                    if not values:
                        continue
                    try:
                        candidate = int(values[0])
                    except (TypeError, ValueError):
                        continue
                    if candidate > start_index:
                        next_index = candidate
                        break

            if next_index is not None and next_index > start_index:
                start_index = next_index
                continue

            increment = len(organic_results)
            if increment <= 0:
                break
            start_index += increment

            effective_sleep = max(0.0, float(sleep_seconds)) * random.uniform(jitter_floor, jitter_ceil)
            if effective_sleep > 0:
                time.sleep(effective_sleep)

        if progress_hook:
            progress_hook(window_start, window_end, window_count)

    return aggregated


def parse_serp_result_date(value: Optional[str]) -> Optional[datetime]:
    """
    Parse the ``date`` field returned by SerpAPI organic results.
    """
    if not value:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    normalized = re.sub(r"(?i)^(updated|publié[e]?)[:\s-]+", "", normalized)
    normalized = normalized.replace("·", " ")
    normalized = normalized.replace("\u2013", " ").replace("\u2014", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip(" .-")
    normalized = re.sub(r"(?i)\b([A-Za-z]{3,9})\.", r"\1", normalized)
    normalized = re.sub(r"(?<=\d)(st|nd|rd|th)", "", normalized, flags=re.IGNORECASE)

    iso_candidate = normalized.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate)
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%m.%d.%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
    ):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    lowered = normalized.lower()
    if lowered == "today":
        return datetime.now()
    if lowered == "yesterday":
        return datetime.now() - timedelta(days=1)

    relative_match = re.match(r"(?i)^(?:about\\s+)?(\\d+)\\s+(minute|hour|day|week|month|year)s?\\s+ago$", normalized)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2).lower()
        delta_kwargs = {
            "minute": {"minutes": amount},
            "hour": {"hours": amount},
            "day": {"days": amount},
            "week": {"weeks": amount},
            "month": {"days": amount * 30},
            "year": {"days": amount * 365},
        }.get(unit)
        if delta_kwargs:
            return datetime.now() - timedelta(**delta_kwargs)

    return None


def prefer_earlier_datetime(
    current_value: Optional[datetime], candidate: Optional[datetime]
) -> Optional[datetime]:
    """
    Return the earliest non-null datetime between current and candidate values.
    """
    if candidate is None:
        return current_value
    if current_value is None:
        return candidate
    return candidate if candidate < current_value else current_value


def _serpapi_page_size(engine: str) -> int:
    if engine == "google":
        return 100
    return 50


def _build_serpapi_params(
    engine: str,
    lang: str,
    start_index: int,
    page_size: int,
    window_start: Optional[date] = None,
    window_end: Optional[date] = None,
    use_date_filter: bool = False,
) -> Dict[str, Union[str, int]]:
    normalized_lang = (lang or "fr").strip().lower() or "fr"

    if engine == "google":
        params: Dict[str, Union[str, int]] = {
            "google_domain": _serpapi_google_domain(normalized_lang),
            "gl": normalized_lang,
            "hl": normalized_lang,
            "lr": f"lang_{normalized_lang}",
            "safe": "off",
            "start": start_index,
        }
        if not use_date_filter:
            params["num"] = page_size
        return params

    if engine == "bing":
        return {
            "mkt": _serpapi_bing_market(normalized_lang),
            "count": page_size,
            "first": start_index + 1,
        }

    if engine == "duckduckgo":
        params = {
            "kl": _serpapi_duckduckgo_region(normalized_lang),
            "start": start_index,
            "m": page_size,
        }
        if window_start and window_end:
            params["df"] = f"{window_start.isoformat()}..{window_end.isoformat()}"
        return params

    return {}


def _build_serpapi_windows(datestart: Optional[str], dateend: Optional[str], timestep: str) -> Iterable[Tuple[date, date]]:
    if not datestart or not dateend:
        return []

    start_date = _parse_serpapi_date(datestart)
    end_date = _parse_serpapi_date(dateend)
    if start_date > end_date:
        raise SerpApiError("datestart must be earlier than or equal to dateend")

    current_start = start_date
    step = timestep.lower()
    windows: List[Tuple[date, date]] = []

    while current_start <= end_date:
        next_start = _advance_date(current_start, step)
        window_end = min(end_date, next_start - timedelta(days=1))
        windows.append((current_start, window_end))
        current_start = next_start

    return windows


def _advance_date(current: date, timestep: str) -> date:
    if timestep == "day":
        return current + timedelta(days=1)
    if timestep == "week":
        return current + timedelta(weeks=1)
    if timestep == "month":
        year = current.year + (current.month // 12)
        month = current.month % 12 + 1
        day = min(current.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    raise SerpApiError("timestep must be one of: day, week, month")


def _parse_serpapi_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SerpApiError(f'Invalid date "{value}" — expected YYYY-MM-DD') from exc


def _build_serpapi_tbs(start: date, end: date) -> str:
    return "cdr:1,cd_min:{},cd_max:{}".format(start.strftime("%m/%d/%Y"), end.strftime("%m/%d/%Y"))


def _serpapi_google_domain(lang: str) -> str:
    lang = lang.lower()
    if lang == "fr":
        return "google.fr"
    if lang == "en":
        return "google.com"
    return "google.com"


def _serpapi_bing_market(lang: str) -> str:
    mapping = {"fr": "fr-FR", "en": "en-US"}
    return mapping.get(lang, "en-US")


def _serpapi_duckduckgo_region(lang: str) -> str:
    mapping = {"fr": "fr-fr", "en": "us-en"}
    return mapping.get(lang, "us-en")
