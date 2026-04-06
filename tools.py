"""
Search tools — plain functions, no framework decorators.
Uses Serper (Google Search proxy) to retrieve movie and music data.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

_SERPER_KEY = os.getenv("SERPER_API_KEY", "")
_SERPER_URL = "https://google.serper.dev/search"


def _serper(query: str, num: int = 6) -> list[dict]:
    """Run a Google search via Serper and return organic results."""
    if not _SERPER_KEY:
        return [{"title": "No API key", "snippet": "SERPER_API_KEY is not set."}]
    try:
        resp = requests.post(
            _SERPER_URL,
            headers={"X-API-KEY": _SERPER_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("organic", [])
    except requests.RequestException as exc:
        return [{"title": "Search error", "snippet": str(exc)}]


def _format(results: list[dict]) -> str:
    lines = []
    for r in results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        link = r.get("link", "")
        lines.append(f"- {title}\n  {snippet}\n  {link}")
    return "\n".join(lines) if lines else "No results found."


def search_movies(query: str) -> str:
    """Search IMDB and Rotten Tomatoes for movies matching the query."""
    results = _serper(
        f"{query} best movies site:imdb.com OR site:rottentomatoes.com"
    )
    return _format(results)


def search_music(query: str) -> str:
    """Search Last.fm, Spotify editorial, and Genius for music matching the query."""
    results = _serper(
        f"best {query} songs playlist site:last.fm OR site:open.spotify.com OR site:genius.com"
    )
    return _format(results)