import os
from dotenv import load_dotenv
from groq import Groq
from tools import search_movies, search_music

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def call_llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

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