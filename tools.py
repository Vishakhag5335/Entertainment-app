"""
Search tools — plain functions, no framework decorators.
Uses Serper (Google Search proxy) to retrieve movie and music data.
"""

import logging
import os
import time
from typing import Any, Optional

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)

_SERPER_KEY = os.getenv("SERPER_API_KEY", "").strip()
_SERPER_URL = "https://google.serper.dev/search"

SERPER_CACHE_TTL_SECONDS = 60 * 60  # Cache for 1 hour
SERPER_CACHE: dict[tuple[str, int], tuple[float, list[dict]]] = {}


def _serper(query: str, num: int = 6) -> list[dict]:
    """Run a Google search via Serper and return organic results."""
    if not _SERPER_KEY:
        logger.warning("SERPER_API_KEY is not configured; returning empty search fallback.")
        return [{"title": "Search unavailable", "snippet": "SERPER_API_KEY is not set."}]

    cache_key = (query, num)
    now = time.time()
    if cache_key in SERPER_CACHE:
        expires_at, payload = SERPER_CACHE[cache_key]
        if now < expires_at:
            logger.info("Serper cache hit for query: '%s'", query)
            return payload
        else:
            SERPER_CACHE.pop(cache_key, None)

    logger.info("Serper cache miss. Fetching query='%s' from Serper API", query)
    try:
        resp = requests.post(
            _SERPER_URL,
            headers={"X-API-KEY": _SERPER_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num},
            timeout=12,
        )
        resp.raise_for_status()
        payload = resp.json()
        organic = payload.get("organic") if isinstance(payload, dict) else None
        if isinstance(organic, list):
            SERPER_CACHE[cache_key] = (now + SERPER_CACHE_TTL_SECONDS, organic)
            return organic
        if isinstance(payload, dict):
            message = payload.get("message") or payload.get("error") or "No results found."
            logger.warning("Serper returned an unexpected payload: %s", message)
        return [{"title": "No results found", "snippet": "Serper returned no organic results."}]
    except requests.RequestException as exc:
        status_code = exc.response.status_code if getattr(exc, 'response', None) is not None else None
        if status_code == 429:
            logger.warning("Serper API rate limit reached. Status 429.")
        logger.warning("Serper search request failed: %s", exc)
        return [{"title": "Search error", "snippet": f"Serper request failed: {exc}"}]
    except ValueError as exc:
        logger.warning("Serper returned invalid JSON: %s", exc)
        return [{"title": "Search error", "snippet": f"Serper returned invalid JSON: {exc}"}]


def _format(results: list[dict]) -> str:
    lines = []
    for r in results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        link = r.get("link", "")
        lines.append(f"- {title}\n  {snippet}\n  {link}")
    return "\n".join(lines) if lines else "No results found."


def search_movies(query: str) -> str:
    """Search TMDB for movies matching the query, falling back to OMDb, Serper, or Mock data."""
    from tmdb_service import search_movies_tmdb, _omdb_api_key, _omdb_request
    
    logger.info("search_movies called with query: '%s'", query)
    
    # 1. Try TMDB Search/Discover
    try:
        tmdb_results = search_movies_tmdb(query)
        if tmdb_results:
            logger.info("Provider used for search: TMDB")
            formatted = []
            for m in tmdb_results[:8]:
                title = m.get("title") or m.get("original_title") or "Untitled"
                year = (m.get("release_date") or "")[:4]
                rating = m.get("vote_average", 0.0)
                overview = m.get("overview") or "No description available."
                formatted.append(f"- {title} ({year}) - Rating: {rating:.1f}\n  Plot: {overview}")
            return "\n".join(formatted)
    except Exception as e:
        logger.warning("TMDB search failed: %s", e)

    # 2. Try OMDb Search fallback
    omdb_key = _omdb_api_key()
    if omdb_key:
        try:
            logger.info("Trying OMDb search fallback for query: '%s'", query)
            r = requests.get(
                "http://www.omdbapi.com/",
                params={"apikey": omdb_key, "s": query, "type": "movie"},
                timeout=8
            )
            r.raise_for_status()
            payload = r.json()
            if payload.get("Response") == "True" and payload.get("Search"):
                logger.info("Provider used for search: OMDb")
                formatted = []
                for m in payload["Search"][:8]:
                    title = m.get("Title", "Untitled")
                    year = m.get("Year", "")
                    
                    # Fetch plot and details for formatting
                    detail_payload = _omdb_request(title, year=year)
                    plot = (detail_payload or {}).get("Plot") or "No description available."
                    rating = (detail_payload or {}).get("imdbRating") or "0.0"
                    formatted.append(f"- {title} ({year}) - Rating: {rating}\n  Plot: {plot}")
                return "\n".join(formatted)
        except Exception as e:
            logger.warning("OMDb search fallback failed: %s", e)

    # 3. Try Serper Search fallback
    try:
        logger.info("Trying Serper search fallback for query: '%s'", query)
        serper_results = _serper(f"{query} best movies site:imdb.com OR site:rottentomatoes.com")
        if serper_results and serper_results[0].get("title") not in {"Search unavailable", "No results found", "Search error"}:
            logger.info("Provider used for search: Serper")
            return _format(serper_results)
    except Exception as e:
        logger.warning("Serper search fallback failed: %s", e)

    # 4. Mock Search fallback
    logger.info("Provider used for search: Mock")
    query_lower = query.lower()
    if "horror" in query_lower or "scary" in query_lower:
        mock_list = [
            "- The Others (2001) - Rating: 7.6\n  Plot: A woman who lives in a darkened old house with her two photosensitive children becomes convinced that her home is haunted.",
            "- The Conjuring (2013) - Rating: 7.5\n  Plot: Paranormal investigators Ed and Lorraine Warren work to help a family terrorized by a dark presence in their farmhouse.",
            "- Inception (2010) - Rating: 8.4\n  Plot: A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea."
        ]
    elif "comedy" in query_lower or "funny" in query_lower:
        mock_list = [
            "- Little Miss Sunshine (2006) - Rating: 7.7\n  Plot: A family determined to get their young daughter into the finals of a beauty pageant take a cross-country trip in their VW bus.",
            "- Inception (2010) - Rating: 8.4\n  Plot: Cobb and his team enter dreams to pull off inception."
        ]
    else:
        # Default popular list
        mock_list = [
            "- Inception (2010) - Rating: 8.4\n  Plot: A thief who steals corporate secrets through dream-sharing is given a task to plant an idea.",
            "- Interstellar (2014) - Rating: 8.4\n  Plot: A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
            "- The Dark Knight (2008) - Rating: 9.0\n  Plot: When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological tests."
        ]
    return "\n".join(mock_list)


def search_music(query: str) -> str:
    """Search Last.fm, Spotify editorial, and Genius for music matching the query."""
    results = _serper(
        f"best {query} songs playlist site:last.fm OR site:open.spotify.com OR site:genius.com"
    )
    return _format(results)