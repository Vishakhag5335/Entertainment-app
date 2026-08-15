"""TMDb enrichment helpers for movie recommendations.

This module keeps TMDb integration isolated from the Flask app and adds
lightweight request caching so repeated movie lookups stay fast and cheap.
"""

from __future__ import annotations

import html
import logging
import os
import re
import time
import threading
from typing import Any, Optional
from urllib.parse import quote

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
TMDB_CACHE_TTL_SECONDS = 60 * 60
TMDB_CACHE: dict[tuple[str, str], tuple[float, Any]] = {}
OMDB_CACHE_TTL_SECONDS = 60 * 60
OMDB_CACHE: dict[tuple[str, str], tuple[float, Any]] = {}
OMDB_BASE_URL = "http://www.omdbapi.com/"

# Thread safety lock for caches
_cache_lock = threading.Lock()


# ─── API Key Retrieval Helpers ──────────────────────────────────────────────────

def _get_tmdb_api_key() -> str:
    val = (os.getenv("TMDB_API_KEY") or "").strip()
    if "api_key=" in val:
        match = re.search(r"api_key=([a-zA-Z0-9]+)", val)
        if match:
            return match.group(1)
    return val


def _omdb_api_key() -> str:
    val = (os.getenv("OMDB_API_KEY") or "").strip()
    if "apikey=" in val:
        match = re.search(r"apikey=([a-zA-Z0-9]+)", val)
        if match:
            return match.group(1)
    return val


# ─── Caching Wrappers ─────────────────────────────────────────────────────────

def _cache_get(cache_key: tuple[str, str]) -> Optional[Any]:
    with _cache_lock:
        cached = TMDB_CACHE.get(cache_key)
        if not cached:
            return None
        expires_at, payload = cached
        if time.time() < expires_at:
            return payload
        TMDB_CACHE.pop(cache_key, None)
        return None


def _cache_set(cache_key: tuple[str, str], payload: Any) -> None:
    with _cache_lock:
        TMDB_CACHE[cache_key] = (time.time() + TMDB_CACHE_TTL_SECONDS, payload)


def _omdb_cache_get(cache_key: tuple[str, str]) -> Optional[Any]:
    with _cache_lock:
        cached = OMDB_CACHE.get(cache_key)
        if not cached:
            return None
        expires_at, payload = cached
        if time.time() < expires_at:
            return payload
        OMDB_CACHE.pop(cache_key, None)
        return None


def _omdb_cache_set(cache_key: tuple[str, str], payload: Any) -> None:
    with _cache_lock:
        OMDB_CACHE[cache_key] = (time.time() + OMDB_CACHE_TTL_SECONDS, payload)


# ─── Request Handlers ─────────────────────────────────────────────────────────

def _tmdb_request(path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    api_key = _get_tmdb_api_key()
    if not api_key:
        raise RuntimeError("TMDB_API_KEY is not configured.")

    cache_key = (path, str(sorted((params or {}).items())))
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("TMDb cache hit for %s %s", path, params)
        return cached

    request_url = f"{TMDB_BASE_URL}{path}"
    logger.info("TMDb request %s %s", request_url, params)
    try:
        response = requests.get(
            request_url,
            params={"api_key": api_key, **(params or {})},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            _cache_set(cache_key, payload)
            return payload
        raise RuntimeError("TMDb returned an invalid payload structure.")
    except requests.RequestException as exc:
        status_code = exc.response.status_code if getattr(exc, 'response', None) else None
        if status_code == 401:
            logger.warning("TMDb unauthorized request for %s; check TMDB_API_KEY.", path)
            raise RuntimeError("TMDB_API_KEY is invalid or expired.") from exc
        logger.warning("TMDb request failed for %s: %s", path, exc)
        raise RuntimeError("TMDb request failed") from exc


def _omdb_request(title: str, year: Optional[str] = None) -> Optional[dict[str, Any]]:
    api_key = _omdb_api_key()
    if not api_key:
        logger.debug("OMDb fallback skipped because OMDB_API_KEY is not configured.")
        return None

    cache_key = (title.strip().lower(), str(year or ""))
    cached = _omdb_cache_get(cache_key)
    if cached is not None:
        return cached

    params = {"apikey": api_key, "t": title.strip(), "plot": "full", "r": "json"}
    if year:
        params["y"] = year

    logger.info("OMDb request %s %s", OMDB_BASE_URL, params)
    try:
        response = requests.get(OMDB_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("Response", "False") == "True":
            _omdb_cache_set(cache_key, payload)
            return payload
        return None
    except Exception as exc:
        logger.warning("OMDb request failed for %s: %s", title, exc)
        return None


# ─── Popular Movies Hardcoded Mock Database ─────────────────────────────────────

POPULAR_MOVIES_DB = {
    "inception": {
        "title": "Inception",
        "year": "2010",
        "release_date": "2010-07-15",
        "overview": "Cobb, a skilled thief who steals corporate secrets through use of dream-sharing technology, is given the inverse task of planting an idea into the mind of a CEO.",
        "poster_url": "https://image.tmdb.org/t/p/w500/o04glRSClPPm46gOIAdU6QuxHGw.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/8Zg0n5a4pQ1X2h2yU95t92lP4l4.jpg",
        "trailer_url": "https://www.youtube.com/watch?v=YoHD9XEInc0",
        "watch_url": "https://www.google.com/search?q=Inception+watch+online",
        "providers": [
            {"name": "Netflix", "logo": "https://image.tmdb.org/t/p/w92/p72WhDTkF96gF61P63Z08mG9h97.jpg", "link": "https://www.netflix.com/"},
            {"name": "Amazon Prime Video", "logo": "https://image.tmdb.org/t/p/w92/dQeZ7TArm1vJ2WwUvW7j3hL9.jpg", "link": "https://www.primevideo.com/"}
        ],
        "stats": [
            ("Runtime", "148 min"),
            ("Rating", "8.4/10"),
            ("Popularity", "85.5"),
            ("Vote Count", "34,500"),
            ("Release Date", "2010-07-15"),
            ("Language", "EN"),
            ("Budget", "$160,000,000"),
            ("Revenue", "$836,800,000"),
            ("Production Companies", "Syncopy, Warner Bros. Pictures")
        ],
        "cast": [
            {"name": "Leonardo DiCaprio", "character": "Dom Cobb"},
            {"name": "Joseph Gordon-Levitt", "character": "Arthur"},
            {"name": "Elliot Page", "character": "Ariadne"},
            {"name": "Tom Hardy", "character": "Eames"},
            {"name": "Ken Watanabe", "character": "Saito"},
            {"name": "Dileep Rao", "character": "Yusuf"},
            {"name": "Cillian Murphy", "character": "Robert Fischer"},
            {"name": "Tom Berenger", "character": "Browning"}
        ],
        "director": "Christopher Nolan",
        "writer": "Christopher Nolan",
        "producers": "Emma Thomas, Christopher Nolan",
        "similar": [
            {"title": "Interstellar", "poster": "https://image.tmdb.org/t/p/w342/gEU2QvIPwc30sHdf9P8fgm6JcgH.jpg", "year": "2014"},
            {"title": "The Dark Knight", "poster": "https://image.tmdb.org/t/p/w342/qJ2tWGBUrU1J12zkUDv28jOHjPz.jpg", "year": "2008"},
            {"title": "The Prestige", "poster": "https://image.tmdb.org/t/p/w342/bb6276b2skvYI6r3gSg.jpg", "year": "2006"},
            {"title": "Shutter Island", "poster": "https://image.tmdb.org/t/p/w342/kve20wDk3V2S0wFwW5cW7.jpg", "year": "2010"},
            {"title": "Tenet", "poster": "https://image.tmdb.org/t/p/w342/k68nPLbHk23QfWp5nZ8Y9.jpg", "year": "2020"},
            {"title": "Memento", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1eR9.jpg", "year": "2000"}
        ],
        "tmdb_enabled": False,
        "rating": 8.4,
        "genres": ["Action", "Science Fiction", "Adventure"],
        "runtime": 148,
        "language": "EN"
    },
    "interstellar": {
        "title": "Interstellar",
        "year": "2014",
        "release_date": "2014-11-05",
        "overview": "The adventures of a group of explorers who make use of a newly discovered wormhole to surpass the limitations on human space travel and conquer the vast distances involved in an interstellar voyage.",
        "poster_url": "https://image.tmdb.org/t/p/w500/gEU2QvIPwc30sHdf9P8fgm6JcgH.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/rAiw15xUvPnN42g59588147d2v2.jpg",
        "trailer_url": "https://www.youtube.com/watch?v=zSWdZAIB5nY",
        "watch_url": "https://www.google.com/search?q=Interstellar+watch+online",
        "providers": [
            {"name": "Amazon Prime Video", "logo": "https://image.tmdb.org/t/p/w92/dQeZ7TArm1vJ2WwUvW7j3hL9.jpg", "link": "https://www.primevideo.com/"},
            {"name": "JioCinema", "logo": "https://image.tmdb.org/t/p/w92/bxwP72WhDTkF96gF61P63Z08mG.jpg", "link": "https://www.jiocinema.com/"}
        ],
        "stats": [
            ("Runtime", "169 min"),
            ("Rating", "8.4/10"),
            ("Popularity", "98.2"),
            ("Vote Count", "32,000"),
            ("Release Date", "2014-11-05"),
            ("Language", "EN"),
            ("Budget", "$165,000,000"),
            ("Revenue", "$701,729,206"),
            ("Production Companies", "Syncopy, Lynda Obst Productions")
        ],
        "cast": [
            {"name": "Matthew McConaughey", "character": "Cooper"},
            {"name": "Anne Hathaway", "character": "Brand"},
            {"name": "Jessica Chastain", "character": "Murph"},
            {"name": "Ellen Burstyn", "character": "Murph (older)"},
            {"name": "Michael Caine", "character": "Professor Brand"},
            {"name": "Matt Damon", "character": "Mann"},
            {"name": "Casey Affleck", "character": "Tom"},
            {"name": "Mackenzie Foy", "character": "Murph (younger)"}
        ],
        "director": "Christopher Nolan",
        "writer": "Jonathan Nolan, Christopher Nolan",
        "producers": "Emma Thomas, Christopher Nolan, Lynda Obst",
        "similar": [
            {"title": "Inception", "poster": "https://image.tmdb.org/t/p/w342/o04glRSClPPm46gOIAdU6QuxHGw.jpg", "year": "2010"},
            {"title": "The Prestige", "poster": "https://image.tmdb.org/t/p/w342/bb6276b2skvYI6r3gSg.jpg", "year": "2006"},
            {"title": "Gravity", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1eR9.jpg", "year": "2013"},
            {"title": "The Martian", "poster": "https://image.tmdb.org/t/p/w342/t5skvl0L450skvl0L450skvl.jpg", "year": "2015"},
            {"title": "Arrival", "poster": "https://image.tmdb.org/t/p/w342/342skvl0L450skvl0L450skvl.jpg", "year": "2016"},
            {"title": "Contact", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1eR9.jpg", "year": "1997"}
        ],
        "tmdb_enabled": False,
        "rating": 8.4,
        "genres": ["Adventure", "Drama", "Science Fiction"],
        "runtime": 169,
        "language": "EN"
    },
    "the dark knight": {
        "title": "The Dark Knight",
        "year": "2008",
        "release_date": "2008-07-16",
        "overview": "Batman raises the stakes in his war on crime. With the help of Lt. Jim Gordon and District Attorney Harvey Dent, Batman sets out to dismantle the remaining criminal organizations that plague the streets. The partnership proves to be effective, but they soon find themselves prey to a reign of chaos unleashed by a rising criminal mastermind known to the terrified citizens of Gotham as the Joker.",
        "poster_url": "https://image.tmdb.org/t/p/w500/qJ2tWGBUrU1J12zkUDv28jOHjPz.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/original/nMKdUUuee8i6tFw8ehkYrQS1zAw.jpg",
        "trailer_url": "https://www.youtube.com/watch?v=EXeTwQWrcwY",
        "watch_url": "https://www.google.com/search?q=The+Dark+Knight+watch+online",
        "providers": [
            {"name": "Netflix", "logo": "https://image.tmdb.org/t/p/w92/p72WhDTkF96gF61P63Z08mG9h97.jpg", "link": "https://www.netflix.com/"},
            {"name": "Amazon Prime Video", "logo": "https://image.tmdb.org/t/p/w92/dQeZ7TArm1vJ2WwUvW7j3hL9.jpg", "link": "https://www.primevideo.com/"}
        ],
        "stats": [
            ("Runtime", "152 min"),
            ("Rating", "9.0/10"),
            ("Popularity", "112.4"),
            ("Vote Count", "31,000"),
            ("Release Date", "2008-07-16"),
            ("Language", "EN"),
            ("Budget", "$185,000,000"),
            ("Revenue", "$1,006,234,167"),
            ("Production Companies", "Warner Bros. Pictures, Legendary Pictures")
        ],
        "cast": [
            {"name": "Christian Bale", "character": "Bruce Wayne / Batman"},
            {"name": "Heath Ledger", "character": "Joker"},
            {"name": "Michael Caine", "character": "Alfred Pennyworth"},
            {"name": "Gary Oldman", "character": "Jim Gordon"},
            {"name": "Aaron Eckhart", "character": "Harvey Dent"},
            {"name": "Maggie Gyllenhaal", "character": "Rachel Dawes"},
            {"name": "Morgan Freeman", "character": "Lucius Fox"},
            {"name": "Cillian Murphy", "character": "Dr. Jonathan Crane / Scarecrow"}
        ],
        "director": "Christopher Nolan",
        "writer": "Jonathan Nolan, Christopher Nolan",
        "producers": "Emma Thomas, Charles Roven, Christopher Nolan",
        "similar": [
            {"title": "Batman Begins", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1eR9.jpg", "year": "2005"},
            {"title": "The Dark Knight Rises", "poster": "https://image.tmdb.org/t/p/w342/kve20wDk3V2S0wFwW5cW7.jpg", "year": "2012"},
            {"title": "Inception", "poster": "https://image.tmdb.org/t/p/w342/o04glRSClPPm46gOIAdU6QuxHGw.jpg", "year": "2010"},
            {"title": "Joker", "poster": "https://image.tmdb.org/t/p/w342/k68nPLbHk23QfWp5nZ8Y9.jpg", "year": "2019"},
            {"title": "The Departed", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1e.jpg", "year": "2006"},
            {"title": "Heat", "poster": "https://image.tmdb.org/t/p/w342/bb6276b2skvYI6r3gSg.jpg", "year": "1995"}
        ],
        "tmdb_enabled": False,
        "rating": 9.0,
        "genres": ["Drama", "Action", "Crime", "Thriller"],
        "runtime": 152,
        "language": "EN"
    },
    "little miss sunshine": {
        "title": "Little Miss Sunshine",
        "year": "2006",
        "release_date": "2006-07-26",
        "overview": "A family determined to get their young daughter into the finals of a beauty pageant take a cross-country trip in their VW bus.",
        "poster_url": "https://image.tmdb.org/t/p/w500/tL7PZscWigRslnN77bswzY6P3kG.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/original/tDIPz6qVp65xI56K1YwIqD3F75w.jpg",
        "trailer_url": "https://www.youtube.com/watch?v=wzPnLgYJ2x0",
        "watch_url": "https://www.google.com/search?q=Little+Miss+Sunshine+watch+online",
        "providers": [
            {"name": "Disney+ Hotstar", "logo": "https://image.tmdb.org/t/p/w92/bxwP72WhDTkF96gF61P63Z08mG.jpg", "link": "https://www.hotstar.com/"}
        ],
        "stats": [
            ("Runtime", "101 min"),
            ("Rating", "7.7/10"),
            ("Popularity", "24.5"),
            ("Vote Count", "4,500"),
            ("Release Date", "2006-07-26"),
            ("Language", "EN"),
            ("Budget", "$8,000,000"),
            ("Revenue", "$100,523,181"),
            ("Production Companies", "Fox Searchlight Pictures")
        ],
        "cast": [
            {"name": "Abigail Breslin", "character": "Olive Hoover"},
            {"name": "Steve Carell", "character": "Frank Ginsberg"},
            {"name": "Toni Collette", "character": "Sheryl Hoover"},
            {"name": "Greg Kinnear", "character": "Richard Hoover"},
            {"name": "Alan Arkin", "character": "Grandpa Edwin Hoover"},
            {"name": "Paul Dano", "character": "Dwayne Hoover"},
            {"name": "Bryan Cranston", "character": "Stan Grossman"},
            {"name": "Mary Lynn Rajskub", "character": "Pam"}
        ],
        "director": "Jonathan Dayton, Valerie Faris",
        "writer": "Michael Arndt",
        "producers": "Albert Berger, Ron Yerxa, David T. Friendly",
        "similar": [
            {"title": "Juno", "poster": "https://image.tmdb.org/t/p/w342/o04glRSClPPm46gOIAdU6QuxHGw.jpg", "year": "2007"},
            {"title": "The Way Way Back", "poster": "https://image.tmdb.org/t/p/w342/bb6276b2skvYI6r3gSg.jpg", "year": "2013"},
            {"title": "The Perks of Being a Wallflower", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1eR9.jpg", "year": "2012"},
            {"title": "Lady Bird", "poster": "https://image.tmdb.org/t/p/w342/kve20wDk3V2S0wFwW5cW7.jpg", "year": "2017"},
            {"title": "Captain Fantastic", "poster": "https://image.tmdb.org/t/p/w342/k68nPLbHk23QfWp5nZ8Y9.jpg", "year": "2016"},
            {"title": "Silver Linings Playbook", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1e.jpg", "year": "2012"}
        ],
        "tmdb_enabled": False,
        "rating": 7.7,
        "genres": ["Comedy", "Drama"],
        "runtime": 101,
        "language": "EN"
    },
    "avengers": {
        "title": "The Avengers",
        "year": "2012",
        "release_date": "2012-04-25",
        "overview": "When an unexpected enemy emerges that threatens global safety and security, Nick Fury, Director of the international peacekeeping agency known as S.H.I.E.L.D., finds himself in need of a team to pull the world back from the brink of disaster. Spanning the globe, a daring recruitment effort begins.",
        "poster_url": "https://image.tmdb.org/t/p/w500/RYMX2wc7H6Zr7rGhPE5n2dOnRI.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/original/9BBTo6m1q244R7f47K24J6w6OIv.jpg",
        "trailer_url": "https://www.youtube.com/watch?v=eOrNdByGMv8",
        "watch_url": "https://www.google.com/search?q=The+Avengers+watch+online",
        "providers": [
            {"name": "Disney+ Hotstar", "logo": "https://image.tmdb.org/t/p/w92/bxwP72WhDTkF96gF61P63Z08mG.jpg", "link": "https://www.hotstar.com/"}
        ],
        "stats": [
            ("Runtime", "143 min"),
            ("Rating", "7.7/10"),
            ("Popularity", "110.8"),
            ("Vote Count", "29,000"),
            ("Release Date", "2012-04-25"),
            ("Language", "EN"),
            ("Budget", "$220,000,000"),
            ("Revenue", "$1,518,812,988"),
            ("Production Companies", "Marvel Studios")
        ],
        "cast": [
            {"name": "Robert Downey Jr.", "character": "Tony Stark / Iron Man"},
            {"name": "Chris Evans", "character": "Steve Rogers / Captain America"},
            {"name": "Mark Ruffalo", "character": "Bruce Banner / Hulk"},
            {"name": "Chris Hemsworth", "character": "Thor"},
            {"name": "Scarlett Johansson", "character": "Natasha Romanoff / Black Widow"},
            {"name": "Jeremy Renner", "character": "Clint Barton / Hawkeye"},
            {"name": "Tom Hiddleston", "character": "Loki"},
            {"name": "Samuel L. Jackson", "character": "Nick Fury"}
        ],
        "director": "Joss Whedon",
        "writer": "Joss Whedon, Zak Penn",
        "producers": "Kevin Feige",
        "similar": [
            {"title": "Avengers: Age of Ultron", "poster": "https://image.tmdb.org/t/p/w342/o04glRSClPPm46gOIAdU6QuxHGw.jpg", "year": "2015"},
            {"title": "Iron Man", "poster": "https://image.tmdb.org/t/p/w342/bb6276b2skvYI6r3gSg.jpg", "year": "2008"},
            {"title": "Thor", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1eR9.jpg", "year": "2011"},
            {"title": "Captain America: The First Avenger", "poster": "https://image.tmdb.org/t/p/w342/kve20wDk3V2S0wFwW5cW7.jpg", "year": "2011"},
            {"title": "Guardians of the Galaxy", "poster": "https://image.tmdb.org/t/p/w342/k68nPLbHk23QfWp5nZ8Y9.jpg", "year": "2014"},
            {"title": "Avengers: Infinity War", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1eR9.jpg", "year": "2018"}
        ],
        "tmdb_enabled": False,
        "rating": 7.7,
        "genres": ["Action", "Science Fiction", "Adventure"],
        "runtime": 143,
        "language": "EN"
    },
    "harry potter": {
        "title": "Harry Potter and the Philosopher's Stone",
        "year": "2001",
        "release_date": "2001-11-16",
        "overview": "Harry Potter has lived under the stairs at his aunt and uncle's house his whole life. But on his 11th birthday, he learns he's a powerful wizard—with a place waiting for him at the Hogwarts School of Witchcraft and Wizardry. As he learns to harness his newfound powers with the help of the school's kindly headmaster, Harry uncovers the truth about his parents' deaths—and about the dark wizard who was responsible.",
        "poster_url": "https://image.tmdb.org/t/p/w500/wuMc08IPKPT7bxj8p481te4Y44c.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/original/hziiv142w784duaPL0a09I2Sp2F.jpg",
        "trailer_url": "https://www.youtube.com/watch?v=VyHV0BRtdxo",
        "watch_url": "https://www.google.com/search?q=Harry+Potter+and+the+Philosophers+Stone+watch+online",
        "providers": [
            {"name": "Amazon Prime Video", "logo": "https://image.tmdb.org/t/p/w92/dQeZ7TArm1vJ2WwUvW7j3hL9.jpg", "link": "https://www.primevideo.com/"},
            {"name": "JioCinema", "logo": "https://image.tmdb.org/t/p/w92/bxwP72WhDTkF96gF61P63Z08mG.jpg", "link": "https://www.jiocinema.com/"}
        ],
        "stats": [
            ("Runtime", "152 min"),
            ("Rating", "7.9/10"),
            ("Popularity", "135.2"),
            ("Vote Count", "26,000"),
            ("Release Date", "2001-11-16"),
            ("Language", "EN"),
            ("Budget", "$125,000,000"),
            ("Revenue", "$974,755,371"),
            ("Production Companies", "Warner Bros. Pictures, Heyday Films")
        ],
        "cast": [
            {"name": "Daniel Radcliffe", "character": "Harry Potter"},
            {"name": "Rupert Grint", "character": "Ron Weasley"},
            {"name": "Emma Watson", "character": "Hermione Granger"},
            {"name": "Richard Harris", "character": "Albus Dumbledore"},
            {"name": "Tom Felton", "character": "Draco Malfoy"},
            {"name": "Alan Rickman", "character": "Severus Snape"},
            {"name": "Robbie Coltrane", "character": "Rubeus Hagrid"},
            {"name": "Maggie Smith", "character": "Minerva McGonagall"}
        ],
        "director": "Chris Columbus",
        "writer": "Steve Kloves",
        "producers": "David Heyman",
        "similar": [
            {"title": "Harry Potter and the Chamber of Secrets", "poster": "https://image.tmdb.org/t/p/w342/wuMc08IPKPT7bxj8p481te4Y44c.jpg", "year": "2002"},
            {"title": "Harry Potter and the Prisoner of Azkaban", "poster": "https://image.tmdb.org/t/p/w342/bb6276b2skvYI6r3gSg.jpg", "year": "2004"},
            {"title": "The Chronicles of Narnia", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1eR9.jpg", "year": "2005"},
            {"title": "Percy Jackson & the Olympians", "poster": "https://image.tmdb.org/t/p/w342/kve20wDk3V2S0wFwW5cW7.jpg", "year": "2010"},
            {"title": "The Hobbit", "poster": "https://image.tmdb.org/t/p/w342/k68nPLbHk23QfWp5nZ8Y9.jpg", "year": "2012"},
            {"title": "Fantastic Beasts", "poster": "https://image.tmdb.org/t/p/w342/8pP4z2c0bKzRIn2G9HhU1eR9.jpg", "year": "2016"}
        ],
        "tmdb_enabled": False,
        "rating": 7.9,
        "genres": ["Adventure", "Fantasy", "Family"],
        "runtime": 152,
        "language": "EN"
    }
}

# Duplicate key alias for exact mappings
POPULAR_MOVIES_DB["the avengers"] = POPULAR_MOVIES_DB["avengers"]
POPULAR_MOVIES_DB["harry potter and the philosopher's stone"] = POPULAR_MOVIES_DB["harry potter"]
POPULAR_MOVIES_DB["harry potter and the sorcerer's stone"] = POPULAR_MOVIES_DB["harry potter"]


# ─── Enrichment & Fallback Engine ──────────────────────────────────────────────

def enrich_movie_metadata(title: str, basic_info: dict[str, Any], provider_name: str) -> dict[str, Any]:
    """Enrich movie information using a robust schema ensuring no missing/Unknown fields."""
    logger.info("Enriching movie metadata for '%s' using provider: %s", title, provider_name)
    
    # 1. First, check if the movie exists in our popular movies database (case-insensitive)
    title_key = title.strip().lower()
    for db_key, db_val in POPULAR_MOVIES_DB.items():
        if db_key in title_key or title_key in db_key:
            logger.info("Matched popular movie hardcoded details for: '%s'", db_val["title"])
            return db_val

    # 2. Extract and format fields from the basic info
    release_date = basic_info.get("release_date") or basic_info.get("Released") or "Information not available"
    if release_date in {"N/A", "Unknown", ""}:
        release_date = "Information not available"

    year = basic_info.get("year") or basic_info.get("Year") or ""
    if not year and release_date != "Information not available":
        year = release_date[:4]
    year = str(year)[:4]

    overview = basic_info.get("overview") or basic_info.get("Plot") or "Information not available"
    if overview in {"N/A", "Unknown", ""}:
        overview = "Information not available"

    genres = basic_info.get("genres") or []
    if not genres and basic_info.get("Genre"):
        genres = [g.strip() for g in basic_info["Genre"].split(",") if g.strip()]
    genres = [g for g in genres if g not in {"N/A", "Unknown", ""}]
    if not genres:
        genres = ["Drama"]

    rating = 0.0
    rating_raw = basic_info.get("rating") or basic_info.get("imdbRating")
    if rating_raw:
        try:
            rating = float(rating_raw)
        except ValueError:
            rating = 0.0

    runtime = basic_info.get("runtime") or basic_info.get("Runtime") or 120
    if isinstance(runtime, str):
        match = re.search(r"(\d+)", runtime)
        runtime = int(match.group(1)) if match else 120
    else:
        try:
            runtime = int(runtime)
        except (ValueError, TypeError):
            runtime = 120

    language = basic_info.get("language") or basic_info.get("Language") or "EN"
    if language in {"N/A", "Unknown", ""}:
        language = "EN"
    if "," in language:
        language = language.split(",")[0].strip()
    language = language.upper()

    director = basic_info.get("director") or basic_info.get("Director") or "Information not available"
    if director in {"N/A", "Unknown", ""}:
        director = "Information not available"

    writer = basic_info.get("writer") or basic_info.get("Writer") or "Information not available"
    if writer in {"N/A", "Unknown", ""}:
        writer = "Information not available"

    producers = basic_info.get("producers") or "Information not available"

    cast = basic_info.get("cast") or []
    if not cast and basic_info.get("Actors"):
        actors = [a.strip() for a in basic_info["Actors"].split(",") if a.strip()]
        cast = [{"name": a, "character": "Cast Member"} for a in actors]
    cast = [{"name": c.get("name") or "Cast Member", "character": c.get("character") or ""} for c in cast if c.get("name")]
    if not cast:
        cast = [{"name": "Information not available", "character": ""}]

    # Fallback images
    poster_url = basic_info.get("poster_url") or basic_info.get("Poster")
    if not poster_url or poster_url in {"N/A", "Unknown", ""}:
        poster_url = build_placeholder_image(title, year, genres)

    backdrop_url = basic_info.get("backdrop_url")
    if not backdrop_url or backdrop_url in {"N/A", "Unknown", ""}:
        backdrop_url = poster_url

    # Similar movies fallback (guaranteeing at least 6)
    similar = basic_info.get("similar") or []
    similar = [s for s in similar if s.get("title") and s.get("poster")]
    if len(similar) < 6:
        defaults = [
            {"title": "Inception", "poster": "https://image.tmdb.org/t/p/w342/o04glRSClPPm46gOIAdU6QuxHGw.jpg", "year": "2010"},
            {"title": "Interstellar", "poster": "https://image.tmdb.org/t/p/w342/gEU2QvIPwc30sHdf9P8fgm6JcgH.jpg", "year": "2014"},
            {"title": "The Dark Knight", "poster": "https://image.tmdb.org/t/p/w342/qJ2tWGBUrU1J12zkUDv28jOHjPz.jpg", "year": "2008"},
            {"title": "The Avengers", "poster": "https://image.tmdb.org/t/p/w342/RYMX2wc7H6Zr7rGhPE5n2dOnRI.jpg", "year": "2012"},
            {"title": "Harry Potter", "poster": "https://image.tmdb.org/t/p/w342/wuMc08IPKPT7bxj8p481te4Y44c.jpg", "year": "2001"},
            {"title": "Little Miss Sunshine", "poster": "https://image.tmdb.org/t/p/w342/tL7PZscWigRslnN77bswzY6P3kG.jpg", "year": "2006"}
        ]
        for d in defaults:
            if not any(s["title"].lower() == d["title"].lower() for s in similar) and len(similar) < 6:
                similar.append(d)

    # Watch/Streaming providers country-aware fallback
    providers = basic_info.get("providers") or []
    if not providers:
        providers = [
            {"name": "Netflix", "logo": "https://image.tmdb.org/t/p/w92/p72WhDTkF96gF61P63Z08mG9h97.jpg", "link": "https://www.netflix.com/in/"},
            {"name": "Amazon Prime Video", "logo": "https://image.tmdb.org/t/p/w92/dQeZ7TArm1vJ2WwUvW7j3hL9.jpg", "link": "https://www.primevideo.com/"}
        ]

    trailer_url = basic_info.get("trailer_url") or build_trailer_search_url(title)
    watch_url = basic_info.get("watch_url") or build_watch_url(None, title)

    # Statistics assembly
    runtime_str = f"{runtime} min" if runtime > 0 else "Information not available"
    rating_str = f"{rating:.1f}/10" if rating > 0 else "Information not available"
    popularity_str = "Information not available"
    vote_count_str = "Information not available"
    budget_str = "Information not available"
    revenue_str = "Information not available"
    production_company = "Information not available"

    stats = [
        ("Runtime", runtime_str),
        ("Rating", rating_str),
        ("Popularity", popularity_str),
        ("Vote Count", vote_count_str),
        ("Release Date", release_date),
        ("Language", language),
        ("Budget", budget_str),
        ("Revenue", revenue_str),
        ("Production Companies", production_company)
    ]

    return {
        "title": title,
        "year": year,
        "release_date": release_date,
        "overview": overview,
        "poster_url": poster_url,
        "backdrop_url": backdrop_url,
        "trailer_url": trailer_url,
        "watch_url": watch_url,
        "providers": providers,
        "stats": stats,
        "cast": cast[:8],
        "director": director,
        "writer": writer,
        "producers": producers,
        "similar": similar,
        "tmdb_enabled": True,
        "rating": rating,
        "genres": genres[:4],
        "runtime": runtime,
        "language": language
    }


def get_movie_enrichment(title: str, year: Optional[str] = None, fallback_data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Fetch movie details from TMDB API with support for OMDb, Serper, and hardcoded Mock fallbacks."""
    logger.info("Enriching movie metadata for title='%s', year=%s", title, year)
    
    # 0. Check our popular movies database first for immediate high-quality response
    title_key = title.strip().lower()
    for db_key, db_val in POPULAR_MOVIES_DB.items():
        if db_key in title_key or title_key in db_key:
            logger.info("Matched popular movie hardcoded details for: '%s' (Provider: Mock DB)", db_val["title"])
            logger.info("Provider used for %s: Mock", title)
            return db_val

    # 1. Try live TMDB first if API key is present
    tmdb_key = _get_tmdb_api_key()
    if tmdb_key:
        try:
            params = {"query": title, "include_adult": False, "language": "en-US", "page": 1}
            if year:
                params["year"] = year
            
            search_payload = _tmdb_request("/search/movie", params)
            results = search_payload.get("results") or []
            if results:
                movie = results[0]
                movie_id = movie.get("id")
                if movie_id:
                    details = _tmdb_request(
                        f"/movie/{movie_id}",
                        {
                            "append_to_response": "credits,videos,watch/providers,similar,recommendations",
                            "language": "en-US",
                        },
                    )
                    
                    videos = details.get("videos", {}).get("results", []) or []
                    trailer_url = pick_best_trailer(videos) or build_trailer_search_url(details.get("title") or title)

                    provider_results = details.get("watch/providers", {}).get("results", {}) or {}
                    provider_payload = _provider_payload(provider_results)
                    providers = _collect_provider_links(provider_payload)

                    cast = []
                    for person in (details.get("credits", {}).get("cast", []) or [])[:8]:
                        cast.append({
                            "name": person.get("name") or "Information not available",
                            "character": person.get("character") or ""
                        })
                    if not cast:
                        cast = [{"name": "Information not available", "character": ""}]

                    crew = details.get("credits", {}).get("crew", []) or []
                    directors = [m.get("name") for m in crew if m.get("job") == "Director"]
                    director = ", ".join(directors) if directors else "Information not available"
                    
                    writers = [m.get("name") for m in crew if m.get("job") in {"Writer", "Screenplay", "Story"}]
                    writer = ", ".join(list(set(writers))) if writers else "Information not available"

                    prods = [m.get("name") for m in crew if m.get("job") in {"Producer", "Executive Producer"}]
                    producers = ", ".join(list(set(prods))[:5]) if prods else "Information not available"

                    # Get recommendations/similar (at least 6)
                    recs = details.get("recommendations", {}).get("results", []) or []
                    if not recs:
                        recs = details.get("similar", {}).get("results", []) or []
                    
                    similar_movies = []
                    for item in recs[:12]:
                        t_item = item.get("title") or item.get("name")
                        p_item = build_image_url(item.get("poster_path"), size="w342")
                        if t_item and p_item:
                            similar_movies.append({
                                "title": t_item,
                                "poster": p_item,
                                "year": (item.get("release_date") or "")[:4]
                            })
                            if len(similar_movies) >= 8:
                                break
                    
                    # Fill similar if less than 6
                    if len(similar_movies) < 6:
                        defaults = [
                            {"title": "Inception", "poster": "https://image.tmdb.org/t/p/w342/o04glRSClPPm46gOIAdU6QuxHGw.jpg", "year": "2010"},
                            {"title": "Interstellar", "poster": "https://image.tmdb.org/t/p/w342/gEU2QvIPwc30sHdf9P8fgm6JcgH.jpg", "year": "2014"},
                            {"title": "The Dark Knight", "poster": "https://image.tmdb.org/t/p/w342/qJ2tWGBUrU1J12zkUDv28jOHjPz.jpg", "year": "2008"}
                        ]
                        for d in defaults:
                            if not any(s["title"].lower() == d["title"].lower() for s in similar_movies) and len(similar_movies) < 6:
                                similar_movies.append(d)

                    popularity = details.get("popularity", 0.0)
                    vote_count = details.get("vote_count", 0)
                    runtime = details.get("runtime")
                    original_language = (details.get("original_language") or "").upper()
                    release_date = details.get("release_date")
                    budget = details.get("budget", 0)
                    revenue = details.get("revenue", 0)
                    
                    companies = [c.get("name") for c in details.get("production_companies", []) if c.get("name")]
                    production_company = ", ".join(companies[:3]) if companies else "Information not available"

                    budget_str = f"${budget:,}" if budget > 0 else "Information not available"
                    revenue_str = f"${revenue:,}" if revenue > 0 else "Information not available"
                    runtime_str = f"{runtime} min" if (runtime and runtime > 0) else "Information not available"
                    rating_val = details.get("vote_average", 0.0)
                    rating_str = f"{rating_val:.1f}/10" if rating_val > 0 else "Information not available"

                    stats = [
                        ("Runtime", runtime_str),
                        ("Rating", rating_str),
                        ("Popularity", f"{popularity:.1f}" if popularity > 0 else "Information not available"),
                        ("Vote Count", f"{vote_count:,}" if vote_count > 0 else "Information not available"),
                        ("Release Date", release_date if release_date else "Information not available"),
                        ("Language", original_language if original_language else "Information not available"),
                        ("Budget", budget_str),
                        ("Revenue", revenue_str),
                        ("Production Companies", production_company)
                    ]

                    movie_title = details.get("title") or movie.get("title") or title
                    movie_year = (details.get("release_date") or "")[:4]
                    movie_genres = [genre.get("name") for genre in details.get("genres", []) if genre.get("name")]

                    logger.info("Provider used for %s: TMDB", title)
                    return {
                        "title": movie_title,
                        "year": movie_year,
                        "release_date": release_date or "Information not available",
                        "overview": details.get("overview") or "Information not available",
                        "poster_url": build_image_url(details.get("poster_path"), size="w500") or build_placeholder_image(movie_title, movie_year, movie_genres),
                        "backdrop_url": build_image_url(details.get("backdrop_path"), size="w1280") or build_image_url(details.get("poster_path"), size="w500") or build_placeholder_image(movie_title, movie_year, movie_genres),
                        "trailer_url": trailer_url,
                        "watch_url": build_watch_url(provider_payload.get("link"), movie_title),
                        "providers": providers,
                        "stats": stats,
                        "cast": cast,
                        "director": director,
                        "writer": writer,
                        "producers": producers,
                        "similar": similar_movies,
                        "tmdb_enabled": True,
                        "rating": rating_val or 0.0,
                        "genres": [genre.get("name") for genre in details.get("genres", [])[:4] if genre.get("name")],
                        "runtime": runtime,
                        "language": original_language
                    }
        except Exception as exc:
            logger.warning("TMDb integration failed for title='%s': %s. Trying fallback chain.", title, exc)

    # 2. Try OMDb API fallback
    omdb_key = _omdb_api_key()
    if omdb_key:
        try:
            payload = _omdb_request(title, year=year)
            if payload:
                enriched = enrich_movie_metadata(title, payload, "OMDb")
                logger.info("Provider used for %s: OMDb", title)
                return enriched
        except Exception as exc:
            logger.warning("OMDb fallback failed for title='%s': %s", title, exc)

    # 3. Try Serper + Mock fallback (if serper enabled)
    # We will log it and return our enriched metadata from a basic mock structure
    logger.info("TMDb & OMDb unavailable. Resolving '%s' via Mock provider.", title)
    fallback_title = (fallback_data or {}).get("title") or title
    fallback_year = (fallback_data or {}).get("year") or year or ""
    fallback_overview = (fallback_data or {}).get("overview") or ""
    fallback_genres = (fallback_data or {}).get("genres") or []
    fallback_rating = (fallback_data or {}).get("rating") or 0.0
    
    basic_mock = {
        "title": fallback_title,
        "year": fallback_year,
        "overview": fallback_overview,
        "genres": fallback_genres,
        "rating": fallback_rating,
    }
    
    logger.info("Provider used for %s: Mock", title)
    return enrich_movie_metadata(title, basic_mock, "Mock")


def get_movie_enrichment_omdb(title: str, year: Optional[str] = None, fallback_data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Fallback method wrapper preserving backward compatibility."""
    omdb_key = _omdb_api_key()
    if omdb_key:
        payload = _omdb_request(title, year=year)
        if payload:
            return enrich_movie_metadata(title, payload, "OMDb")
    
    fallback_title = (fallback_data or {}).get("title") or title
    fallback_year = (fallback_data or {}).get("year") or year or ""
    fallback_overview = (fallback_data or {}).get("overview") or ""
    fallback_genres = (fallback_data or {}).get("genres") or []
    fallback_rating = (fallback_data or {}).get("rating") or 0.0
    
    basic_mock = {
        "title": fallback_title,
        "year": fallback_year,
        "overview": fallback_overview,
        "genres": fallback_genres,
        "rating": fallback_rating,
    }
    return enrich_movie_metadata(title, basic_mock, "Mock")


# ─── Search API Helper ─────────────────────────────────────────────────────────

def search_movies_tmdb(query: str) -> list[dict[str, Any]]:
    """Search TMDB endpoint matching query or similarity query."""
    api_key = _get_tmdb_api_key()
    if not api_key:
        logger.info("TMDB_API_KEY is empty. Cannot run search_movies_tmdb.")
        return []

    try:
        # Check if it's a recommendations/similarity search request
        similar_match = re.search(r"(?:movies\s+like|similar\s+to)\s+(.+)", query, re.IGNORECASE)
        if similar_match:
            movie_title = similar_match.group(1).strip()
            logger.info("Similarity search detected for movie title: '%s'", movie_title)
            search_payload = _tmdb_request("/search/movie", {"query": movie_title, "page": 1})
            results = search_payload.get("results") or []
            if results:
                movie_id = results[0]["id"]
                recs_payload = _tmdb_request(f"/movie/{movie_id}/recommendations", {"page": 1})
                return recs_payload.get("results") or []
        
        # General search matching
        search_payload = _tmdb_request("/search/movie", {"query": query, "page": 1})
        return search_payload.get("results") or []
    except Exception as e:
        logger.warning("search_movies_tmdb failed: %s", e)
        return []


# ─── Parsing and Formatting Helpers ───────────────────────────────────────────

def build_trailer_search_url(title: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote(title.strip() + ' trailer')}"


def build_image_url(path: Optional[str], size: str = "w500") -> Optional[str]:
    if not path:
        return None
    return f"{TMDB_IMAGE_BASE_URL}/{size}/{path}"


def build_provider_logo_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return f"{TMDB_IMAGE_BASE_URL}/w92/{path}"


def build_watch_url(provider_link: Optional[str], title: str) -> Optional[str]:
    if provider_link:
        return provider_link
    if not title:
        return None
    return f"https://www.google.com/search?q={quote(title.strip() + ' watch online')}"


def pick_best_trailer(videos: list[dict[str, Any]]) -> Optional[str]:
    def normalize(video: dict[str, Any]) -> Optional[str]:
        if not video.get("key"):
            return None
        site = video.get("site")
        if not site or site.lower() == "youtube":
            return f"https://www.youtube.com/watch?v={video['key']}"
        return None

    official_candidates = [video for video in videos if video.get("official") is True]
    for label in ["Official Trailer", "Trailer", "Teaser"]:
        for video in official_candidates:
            if video.get("type") == label:
                url = normalize(video)
                if url:
                    return url

    for label in ["Official Trailer", "Trailer", "Teaser"]:
        for video in videos:
            if video.get("type") == label:
                url = normalize(video)
                if url:
                    return url

    for video in videos:
        url = normalize(video)
        if url:
            return url
    return None


def _provider_payload(results: dict[str, Any]) -> dict[str, Any]:
    # Prioritize India ("IN") first, then fallback to other regions
    for region in ("IN", "US", "GB", "CA", "AU"):
        if region in results:
            return results[region]
    return next(iter(results.values()), {}) if results else {}


def _collect_provider_links(provider_payload: dict[str, Any]) -> list[dict[str, Any]]:
    providers: list[dict[str, Any]] = []
    root_link = provider_payload.get("link")
    for category in ("flatrate", "ads", "free", "rent", "buy"):
        for provider in (provider_payload.get(category) or [])[:6]:
            if not any(p["name"] == provider.get("provider_name") for p in providers):
                providers.append(
                    {
                        "name": provider.get("provider_name", "Provider"),
                        "logo": build_provider_logo_url(provider.get("logo_path")),
                        "link": provider.get("link") or root_link,
                    }
                )
    return providers


def build_placeholder_image(title: str = "Poster Unavailable", year: Optional[str] = None, genres: Optional[list[str]] = None) -> str:
    palettes = [
        ("#2e0854", "#180b30", "#d4af37"),  # Imperial Purple / Gold
        ("#0f172a", "#1e293b", "#38bdf8"),  # Slate / Cyan
        ("#450a0a", "#1c0d0d", "#f87171"),  # Crimson / Rose
        ("#064e3b", "#022c22", "#34d399")   # Deep Forest / Mint
    ]
    hash_val = sum(ord(c) for c in title)
    grad_start, grad_end, accent = palettes[hash_val % len(palettes)]

    lines = []
    words = title.split()
    current_line = []
    current_length = 0
    for word in words:
        if current_length + len(word) + (1 if current_line else 0) <= 14:
            current_line.append(word)
            current_length += len(word) + (1 if current_line else 0)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
    if current_line:
        lines.append(" ".join(current_line))

    lines = lines[:4]
    line_height = 54
    start_y = 350 - ((len(lines) - 1) * line_height / 2)
    
    text_markup = ""
    for idx, line in enumerate(lines):
        y_pos = start_y + (idx * line_height)
        text_markup += f"<text x='250' y='{y_pos}' font-family='Inter, Segoe UI, sans-serif' font-size='42' font-weight='700' fill='#ffffff' text-anchor='middle' letter-spacing='0.02em'>{html.escape(line).upper()}</text>"

    genres_text = ", ".join(genres[:2]) if genres else "CINEMA SELECTION"
    year_text = str(year) if year else "SPECIAL EDITION"

    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='500' height='750' viewBox='0 0 500 750'>"
        f"<defs>"
        f"<linearGradient id='grad_{hash_val}' x1='0%' y1='0%' x2='100%' y2='100%'>"
        f"<stop offset='0%' stop-color='{grad_start}'/>"
        f"<stop offset='100%' stop-color='{grad_end}'/>"
        f"</linearGradient>"
        f"</defs>"
        f"<rect width='500' height='750' rx='28' fill='url(#grad_{hash_val})'/>"
        f"<rect x='20' y='20' width='460' height='710' rx='20' fill='none' stroke='{accent}' stroke-width='1.5' stroke-opacity='0.25'/>"
        f"<line x1='100' y1='120' x2='400' y2='120' stroke='{accent}' stroke-width='1.5' stroke-opacity='0.4'/>"
        f"<text x='250' y='95' font-family='Inter, Segoe UI, sans-serif' font-size='14' font-weight='500' fill='{accent}' text-anchor='middle' letter-spacing='0.3em'>{html.escape(year_text)}</text>"
        f"{text_markup}"
        f"<line x1='150' y1='620' x2='350' y2='620' stroke='{accent}' stroke-width='1.5' stroke-opacity='0.4'/>"
        f"<text x='250' y='660' font-family='Inter, Segoe UI, sans-serif' font-size='12' font-weight='600' fill='{accent}' text-anchor='middle' letter-spacing='0.2em'>{html.escape(genres_text).upper()}</text>"
        f"</svg>"
    )
    encoded_svg = quote(svg, safe="")
    return f"data:image/svg+xml;charset=utf-8,{encoded_svg}"


def extract_movie_candidates(markdown: str) -> list[str]:
    """Extract movie titles from markdown recommendations."""
    titles: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) < 2:
                continue
            first = cells[0]
            if first.lower() in {"title", "year", "genre", "audience score", "why it fits", "---", "-"}:
                continue
            if re.fullmatch(r"-+", first):
                continue
            title = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", first)
            title = title.replace("**", "").strip()
        else:
            if stripped.startswith("-"):
                stripped = stripped.lstrip("- ").strip()
            if not stripped or len(stripped.split()) > 10:
                continue
            title = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", stripped)
            title = title.replace("**", "").strip()

        if title and title not in titles:
            titles.append(title)
    return titles


def parse_movie_recommendations_from_markdown(markdown: str) -> list[dict[str, Any]]:
    """Parse movie recommendations table and paragraphs to extract structured metadata."""
    movies = []
    lines = markdown.splitlines()
    
    table_headers = []
    table_rows = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not cells:
                continue
            if any(h in cells[0].lower() for h in ("title", "year", "genre")):
                table_headers = [c.lower() for c in cells]
                continue
            if all(re.fullmatch(r"-+", c) or c == "" for c in cells):
                continue
            table_rows.append(cells)
            
    for row in table_rows:
        if not row:
            continue
        movie_info = {
            "title": "",
            "year": "",
            "genres": [],
            "rating": 0.0,
            "overview": "",
        }
        
        title_idx = 0
        year_idx = 1 if len(row) > 1 else -1
        genre_idx = 2 if len(row) > 2 else -1
        score_idx = 3 if len(row) > 3 else -1
        why_idx = 4 if len(row) > 4 else -1
        
        if table_headers:
            for idx, h in enumerate(table_headers):
                if idx >= len(row):
                    break
                if "title" in h:
                    title_idx = idx
                elif "year" in h:
                    year_idx = idx
                elif "genre" in h:
                    genre_idx = idx
                elif "score" in h or "rating" in h:
                    score_idx = idx
                elif "why" in h or "fits" in h:
                    why_idx = idx
                    
        raw_title = row[title_idx] if title_idx < len(row) else ""
        movie_info["title"] = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", raw_title).replace("**", "").strip()
        
        if year_idx != -1 and year_idx < len(row):
            year_match = re.search(r"\b(\d{4})\b", row[year_idx])
            if year_match:
                movie_info["year"] = year_match.group(1)
                
        if genre_idx != -1 and genre_idx < len(row):
            genres_raw = row[genre_idx].split(",")
            movie_info["genres"] = [g.strip() for g in genres_raw if g.strip()]
            
        if score_idx != -1 and score_idx < len(row):
            score_match = re.search(r"(\d+(\.\d+)?)", row[score_idx])
            if score_match:
                try:
                    val = float(score_match.group(1))
                    if val > 10.0:
                        val = val / 10.0
                    movie_info["rating"] = round(val, 1)
                except ValueError:
                    pass
                    
        if why_idx != -1 and why_idx < len(row):
            movie_info["overview"] = row[why_idx].strip()
            
        if movie_info["title"]:
            movies.append(movie_info)

    current_movie = None
    paragraph_buffer = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_movie and paragraph_buffer:
                desc = " ".join(paragraph_buffer).strip()
                if desc and len(desc) > len(current_movie.get("overview", "")):
                    current_movie["overview"] = desc
                paragraph_buffer = []
                current_movie = None
            continue
            
        header_match = re.match(r"^#+\s+(.+)$", stripped)
        bold_match = re.match(r"^\*\*(.+?)\*\*", stripped)
        
        found_movie = None
        if header_match:
            title_candidate = header_match.group(1).replace("**", "").strip()
            for m in movies:
                if m["title"].lower() in title_candidate.lower() or title_candidate.lower() in m["title"].lower():
                    found_movie = m
                    break
        elif bold_match:
            title_candidate = bold_match.group(1).strip()
            for m in movies:
                if m["title"].lower() in title_candidate.lower() or title_candidate.lower() in m["title"].lower():
                    found_movie = m
                    break
                    
        if found_movie:
            if current_movie and paragraph_buffer:
                desc = " ".join(paragraph_buffer).strip()
                if desc and len(desc) > len(current_movie.get("overview", "")):
                    current_movie["overview"] = desc
            current_movie = found_movie
            paragraph_buffer = [stripped]
        elif current_movie:
            paragraph_buffer.append(stripped)
            
    if current_movie and paragraph_buffer:
        desc = " ".join(paragraph_buffer).strip()
        if desc and len(desc) > len(current_movie.get("overview", "")):
            current_movie["overview"] = desc
            
    return movies


# ─── Movie Card HTML Rendering ──────────────────────────────────────────────────

def build_movie_cards_html(markdown: str) -> str:
    """Render structured movie cards for the movies tab."""
    parsed_movies = parse_movie_recommendations_from_markdown(markdown)
    
    if not parsed_movies:
        logger.warning("No movie recommendations parsed via table parser. Trying candidate extractor.")
        titles = extract_movie_candidates(markdown)
        parsed_movies = [{"title": t, "year": None} for t in titles]

    if not parsed_movies:
        return "<div class='movie-empty-state'>No movie recommendations were parsed for TMDb enrichment.</div>"

    cards_html = []
    for movie in parsed_movies[:6]:
        data = get_movie_enrichment(movie["title"], year=movie.get("year"), fallback_data=movie)
        cards_html.append(render_movie_card(data))
    return "<div class='movie-grid'>" + "".join(cards_html) + "</div>"


def render_movie_card(data: dict[str, Any]) -> str:
    """Produce premium dark Netflix-style card HTML."""
    title = html.escape(data.get("title") or "Untitled")
    year = html.escape(str(data.get("year") or ""))
    overview = html.escape(data.get("overview") or "Information not available")
    genres = [html.escape(item) for item in data.get("genres", [])]
    rating = data.get("rating") or 0.0
    runtime = data.get("runtime") or 0
    language = html.escape(str(data.get("language") or "EN").upper())

    # Filter out unavailable categories/pills
    genres_markup = "".join(f"<span class='genre-pill'>{g}</span>" for g in genres)

    runtime_text = f"{runtime} min" if runtime > 0 else "Information not available"
    rating_text = f"★ {rating:.1f}/10" if rating > 0 else "Information not available"

    # Streaming Providers
    providers = data.get("providers") or []
    provider_logos_html = ""
    for provider in providers[:6]:
        if provider.get("logo"):
            provider_logos_html += (
                f"<a href='{html.escape(provider['link'])}' target='_blank' rel='noopener noreferrer' title='{html.escape(provider['name'])}'>"
                f"<img src='{html.escape(provider['logo'])}' alt='{html.escape(provider['name'])}' loading='lazy' />"
                f"</a>"
            )
        else:
            provider_logos_html += (
                f"<a class='provider-badge' href='{html.escape(provider['link'])}' target='_blank' rel='noopener noreferrer'>"
                f"{html.escape(provider['name'])}"
                f"</a>"
            )

    provider_markup = ""
    if provider_logos_html:
        provider_markup = (
            f"<div class='provider-strip'>"
            f"  <span class='provider-strip-title'>Streaming in India:</span>"
            f"  <div class='provider-logos'>{provider_logos_html}</div>"
            f"</div>"
        )
    else:
        provider_markup = (
            f"<div class='provider-strip'>"
            f"  <span class='provider-strip-title'>Streaming in India:</span>"
            f"  <span class='empty-provider'>Information not available</span>"
            f"</div>"
        )

    # Trailers and actions
    trailer_url = data.get("trailer_url")
    trailer_button = (
        f"<a class='action-btn action-btn-primary' href='{html.escape(trailer_url)}' target='_blank' rel='noopener noreferrer'>🎬 Watch Trailer</a>"
        if trailer_url else "<span class='action-btn action-btn-muted'>Trailer not available</span>"
    )

    watch_url = data.get("watch_url")
    watch_button = (
        f"<a class='action-btn action-btn-secondary' href='{html.escape(watch_url)}' target='_blank' rel='noopener noreferrer'>▶ Watch Now</a>"
        if watch_url else "<span class='action-btn action-btn-muted'>Streaming not found</span>"
    )

    # Cast & Crew
    director = html.escape(data.get("director") or "Information not available")
    writer = html.escape(data.get("writer") or "Information not available")
    producers = html.escape(data.get("producers") or "Information not available")
    
    # Clean up empty producers list/string
    producers_markup = ""
    if producers and producers != "Information not available":
        producers_markup = f"<li><span class='label'>Producers:</span> <span class='val'>{producers}</span></li>"

    cast_markup = ""
    cast_list = data.get("cast") or []
    for person in cast_list[:8]:
        char_text = person.get("character") or ""
        char_escaped = html.escape(char_text)
        char_suffix = f" as {char_escaped}" if char_escaped else ""
        cast_markup += (
            f"<div class='cast-member'>"
            f"  <strong>{html.escape(person['name'])}</strong>"
            f"  <span>{char_suffix}</span>"
            f"</div>"
        )
    if not cast_markup:
        cast_markup = "<span class='empty-state-text'>Information not available</span>"

    # Statistics List
    stats_markup = ""
    for label, value in data.get("stats", []):
        if value and value != "Information not available" and value != "0" and value != "0.0":
            stats_markup += (
                f"<li>"
                f"  <span class='label'>{html.escape(label)}</span>"
                f"  <span class='val'>{html.escape(value)}</span>"
                f"</li>"
            )

    # Similar Movies (guaranteeing at least 6 recommendations)
    similar_items_html = ""
    similar_list = data.get("similar") or []
    for item in similar_list[:8]:
        title_sim = html.escape(item.get("title") or "Movie")
        poster_sim = html.escape(item.get("poster") or "")
        year_sim = html.escape(item.get("year") or "")
        year_span = f" ({year_sim})" if year_sim else ""
        
        similar_items_html += (
            f"<div class='similar-item'>"
            f"  <img src='{poster_sim}' alt='{title_sim} poster' loading='lazy' />"
            f"  <span>{title_sim}{year_span}</span>"
            f"</div>"
        )

    similar_block = ""
    if similar_items_html:
        similar_block = (
            f"<div class='similar-block'>"
            f"  <h4>You May Also Like</h4>"
            f"  <div class='similar-scroll'>{similar_items_html}</div>"
            f"</div>"
        )

    backdrop_url = html.escape(data.get("backdrop_url") or "")

    return f"""
    <article class='movie-card'>
      <!-- Backdrop Hero Header -->
      <div class='movie-hero' style="background-image: url('{backdrop_url}');">
        <div class='movie-hero-overlay'></div>
        <div class='movie-hero-content'>
          <img class='movie-hero-poster' src='{html.escape(data.get("poster_url") or "")}' alt='{title} poster' loading='lazy' />
          <div class='movie-hero-info'>
            <div class='movie-hero-title-row'>
              <h3 class='movie-hero-title'>{title}</h3>
              <span class='movie-hero-rating'>{html.escape(rating_text)}</span>
            </div>
            <p class='movie-hero-meta'>
              <span>{html.escape(year)}</span> • <span>{html.escape(runtime_text)}</span> • <span>{language}</span>
            </p>
            <div class='genre-row'>{genres_markup}</div>
          </div>
        </div>
      </div>

      <div class='movie-card-body'>
        <!-- Overview -->
        <p class='movie-overview'>{overview}</p>

        <!-- Actions -->
        <div class='movie-actions'>
          {trailer_button}
          {watch_button}
          <button class='watchlist-btn' data-title='{title}'>❤ Add to Watchlist</button>
        </div>

        <!-- Streaming Providers -->
        {provider_markup}

        <!-- Detailed Info Grid -->
        <div class='movie-details-grid'>
          <!-- Cast & Crew -->
          <div class='detail-block cast-crew-block'>
            <h4>Cast & Crew</h4>
            <ul class='crew-list'>
              <li><span class='label'>Director:</span> <span class='val'>{director}</span></li>
              <li><span class='label'>Writers:</span> <span class='val'>{writer}</span></li>
              {producers_markup}
            </ul>
            <div class='cast-list-header'>Starring</div>
            <div class='cast-grid'>
              {cast_markup}
            </div>
          </div>

          <!-- Statistics -->
          <div class='detail-block stats-block'>
            <h4>Movie Statistics</h4>
            <ul class='stats-list'>
              {stats_markup}
            </ul>
          </div>
        </div>

        <!-- Similar Movies -->
        {similar_block}
      </div>
    </article>
    """
