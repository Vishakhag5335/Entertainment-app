import logging
import os

from dotenv import find_dotenv, load_dotenv

from tools import search_movies, search_music

try:
    from groq import Groq
except ImportError:  # pragma: no cover - runtime fallback
    Groq = None

load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)

MODELS = [
    "llama-3.3-70b-versatile",
    "groq/compound",
    "groq/compound-mini",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant",
]


def _build_client():
    if Groq is None:
        logger.error("Groq SDK is unavailable; groq package is not installed.")
        return None

    load_dotenv(find_dotenv())
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        logger.error("GROQ_API_KEY environment variable is not configured.")
        return None

    try:
        return Groq(api_key=os.getenv("GROQ_API_KEY"))
    except Exception as exc:  # pragma: no cover - runtime fallback
        logger.error("Groq client initialization failed: %s", exc, exc_info=True)
        return None


def call_llm(prompt: str) -> str:
    client = _build_client()
    if client is None:
        return "AI generation is currently unavailable. Please check your GROQ_API_KEY and SDK compatibility."

    last_error = None
    for model in MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = getattr(response.choices[0].message, "content", None)
            if content:
                logger.info("Successfully generated AI response using model '%s'", model)
                return str(content).strip()
            logger.warning("Groq model '%s' returned an empty response.", model)
        except Exception as exc:  # pragma: no cover - runtime fallback
            last_error = exc
            logger.error("Groq API request failed for model '%s': %s", model, exc, exc_info=True)

    if last_error is not None:
        logger.error("Groq request failed after trying all models. Last error: %s", last_error)
    return "AI generation failed. Please try again shortly."

def run_entertainment_agent(user_input: str):
    print("\n" + "="*50)
    print("🎬 Entertainment Planning Agent 🎵")
    print("="*50)
    print(f"\n📝 Your Request: {user_input}\n")

    # --- Agent 1: Movie Expert ---
    print("🎬 Movie Agent is working...")
    movie_data = search_movies(user_input)
    movie_prompt = f"""
    You are a Movie Expert. The user asked: "{user_input}"
    Here is the movie data: {movie_data}
    Give a short friendly recommendation with reasons why each movie fits.
    Be brief and to the point.
    """
    movie_result = call_llm(movie_prompt)
    print("✅ Movie Agent done!\n")

    # --- Agent 2: Music Expert ---
    print("🎵 Music Agent is working...")
    music_data = search_music(user_input)
    music_prompt = f"""
    You are a Music Expert. The user asked: "{user_input}"
    Here is the music data: {music_data}
    Suggest these songs briefly and explain why each fits the mood.
    Be brief and to the point.
    """
    music_result = call_llm(music_prompt)
    print("✅ Music Agent done!\n")

    # --- Agent 3: Entertainment Planner ---
    print("📋 Planner Agent is working...")
    plan_prompt = f"""
    You are an Entertainment Planner. Combine the following into one clean fun entertainment plan.

    Movies: {movie_result}
    Music: {music_result}

    Format it with:
    - A short welcome line
    - 🎬 Movie Recommendations section
    - 🎵 Music Playlist section
    - A fun closing line
    """
    final_plan = call_llm(plan_prompt)
    print("✅ Planner Agent done!\n")

    print("\n" + "="*50)
    print("✅ Your Entertainment Plan is Ready!")
    print("="*50)
    print(final_plan)

if __name__ == "__main__":
    print("\n🎬 Welcome to the Entertainment Planning Agent! 🎵")
    print("------------------------------------------------")
    user_input = input("What kind of entertainment are you looking for today?\n> ")
    run_entertainment_agent(user_input)