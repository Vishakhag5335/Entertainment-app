"""
Agent pipeline.
Three sequential agents: Movie Expert → Music Expert → Planner.
Only agents relevant to the user's selected intent are run.
"""

import logging
import os
from typing import Optional

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from tools import search_movies, search_music

try:
    from groq import Groq
except ImportError:  # pragma: no cover - runtime fallback
    Groq = None

logger = logging.getLogger(__name__)

_client = None
_client_error = None


def _initialize_client():
    global _client, _client_error
    if Groq is None:
        _client_error = RuntimeError("groq package is not installed")
        logger.error("Groq SDK is unavailable; groq package is not installed.")
        return None

    load_dotenv(find_dotenv())
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        _client_error = RuntimeError("GROQ_API_KEY is not configured in .env file")
        logger.error("GROQ_API_KEY environment variable is not configured.")
        return None

    try:
        client_inst = Groq(api_key=os.getenv("GROQ_API_KEY"))
        _client_error = None
        return client_inst
    except Exception as exc:  # pragma: no cover - defensive fallback
        _client_error = exc
        logger.error("Groq client initialization failed: %s", exc, exc_info=True)
        return None


def _get_client():
    global _client
    if _client is None:
        _client = _initialize_client()
    return _client


# Use supported Groq models starting with llama-3.3-70b-versatile
MODELS = [
    "llama-3.3-70b-versatile",
    "groq/compound",
    "groq/compound-mini",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant",
]


# ── LLM helper ─────────────────────────────────────────────────────────────────

def _call(system: str, user: str) -> str:
    client = _get_client()
    if client is None:
        if _client_error is not None:
            logger.error("Groq call skipped due to initialization error: %s", _client_error)
        return "AI generation is currently unavailable. Please check your GROQ_API_KEY and SDK compatibility."

    last_error: Optional[Exception] = None
    for model in MODELS:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=2048,
                temperature=0.7,
            )
            content = getattr(resp.choices[0].message, "content", None)
            if content:
                logger.info("Successfully generated AI response using model '%s'", model)
                return str(content).strip()
            logger.warning("Groq model '%s' returned an empty response.", model)
        except Exception as exc:  # pragma: no cover - defensive fallback
            last_error = exc
            logger.error("Groq API request failed for model '%s': %s", model, exc, exc_info=True)

    if last_error is not None:
        logger.error("Groq request failed after trying all models. Last error: %s", last_error)
    return "AI generation failed. Please try again shortly."


# ── Individual agents ──────────────────────────────────────────────────────────

MOVIE_SYSTEM = """
You are a knowledgeable movie recommendation expert.

Always respond in clean GitHub-flavored Markdown:
1. One sentence framing why these films fit the request.
2. A Markdown table with columns: Title | Year | Genre | Audience Score | Why It Fits
3. A short paragraph (2-3 sentences) for each recommended film.
4. A final "Suggested Viewing Order" list if you recommend multiple films.

Rules:
- Use proper Markdown syntax (## headings, **bold**, | tables |, - lists).
- Do NOT output raw asterisks as bullet substitutes.
- Keep each film description tight and useful, not padded.
""".strip()

MUSIC_SYSTEM = """
You are a music curator with deep knowledge across genres and moods.

Always respond in clean GitHub-flavored Markdown:
1. One sentence setting the vibe for the playlist.
2. A Markdown table with columns: Song | Artist | Genre | Mood | Why It Fits
3. A short note (1-2 sentences) for each recommended track.
4. A "Playlist Order" numbered list at the end.

Rules:
- Use proper Markdown syntax.
- Do NOT output raw asterisks.
- Be specific: mention tempo, key themes, feel — not just "great song".
""".strip()

PLANNER_SYSTEM = """
You are an entertainment planner who pairs films and music into a cohesive experience.

Always respond in clean GitHub-flavored Markdown with these sections:
## The Experience
A 2-3 sentence narrative about the overall vibe.

## Schedule
A Markdown table: Time Slot | Activity | What to Play/Watch | Notes

## Why This Pairing Works
2-3 sentences explaining how the movies and music complement each other.

Rules:
- Use proper Markdown syntax.
- Be concrete and practical — actual time slots (e.g. "7:00 PM"), not vague references.
- Keep it brief: quality over quantity.
""".strip()


def _movie_agent(query: str) -> str:
    raw_data = search_movies(query)
    return _call(
        MOVIE_SYSTEM,
        f'User request: "{query}"\n\nSearch results to draw from:\n{raw_data}',
    )


def _music_agent(query: str) -> str:
    raw_data = search_music(query)
    return _call(
        MUSIC_SYSTEM,
        f'User request: "{query}"\n\nSearch results to draw from:\n{raw_data}',
    )


def _planner_agent(query: str, movies_md: str, music_md: str) -> str:
    return _call(
        PLANNER_SYSTEM,
        f'User request: "{query}"\n\nMovie recommendations:\n{movies_md}\n\nMusic recommendations:\n{music_md}',
    )


# ── Public entrypoint ──────────────────────────────────────────────────────────

def run_plan(query: str, intent: str = "both") -> dict:
    """
    Run the relevant agents for the given intent.
    Returns a dict with keys: intent, and optionally movies, music, plan.
    """
    result: dict = {"intent": intent}

    if intent in ("movies", "both"):
        result["movies"] = _movie_agent(query)

    if intent in ("music", "both"):
        result["music"] = _music_agent(query)

    if intent == "both":
        result["plan"] = _planner_agent(
            query,
            result.get("movies", ""),
            result.get("music", ""),
        )

    return result