"""
Agent pipeline.
Three sequential agents: Movie Expert → Music Expert → Planner.
Only agents relevant to the user's selected intent are run.
"""

import os
from groq import Groq
from tools import search_movies, search_music
from dotenv import load_dotenv

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Use the best available Groq model for quality formatting
MODEL = "llama-3.3-70b-versatile"


# ── LLM helper ─────────────────────────────────────────────────────────────────

def _call(system: str, user: str) -> str:
    resp = _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=2048,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


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