import os
import requests
from crewai.tools import tool
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SERPER_URL = "https://google.serper.dev/search"

def serper_search(query: str) -> list:
    """Run a Google search via Serper and return organic results."""
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"q": query, "num": 5}

    try:
        response = requests.post(SERPER_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("organic", [])
    except requests.exceptions.RequestException as e:
        return [{"title": "Error", "snippet": str(e)}]


@tool("Movie Search Tool")
def movie_search_tool(query: str) -> str:
    """Searches for movies based on user query like genre, mood, or title using Google Search."""

    results = serper_search(f"{query} best movies to watch site:imdb.com OR site:rottentomatoes.com")

    if not results:
        return "No movies found for your query."

    output = f"Movie search results for '{query}':\n"
    for r in results:
        title = r.get("title", "No title")
        snippet = r.get("snippet", "No description")
        link = r.get("link", "")
        output += f"- {title}\n  {snippet}\n  {link}\n"

    return output


@tool("Movie Details Tool")
def movie_details_tool(title: str) -> str:
    """Gets detailed information about a specific movie using Google Search."""

    results = serper_search(f"{title} movie details cast director rating site:imdb.com")

    if not results:
        return f"No details found for '{title}'."

    output = f"Details for '{title}':\n"
    for r in results[:2]:
        t = r.get("title", "No title")
        snippet = r.get("snippet", "No description")
        link = r.get("link", "")
        output += f"- {t}\n  {snippet}\n  {link}\n"

    return output


@tool("Music Search Tool")
def music_search_tool(query: str) -> str:
    """Searches for songs and artists based on mood, genre, or theme using Google Search."""

    results = serper_search(f"best {query} songs playlist site:last.fm OR site:spotify.com OR site:genius.com")

    if not results:
        return "No music found for your query."

    output = f"Music search results for '{query}':\n"
    for r in results:
        title = r.get("title", "No title")
        snippet = r.get("snippet", "No description")
        link = r.get("link", "")
        output += f"- {title}\n  {snippet}\n  {link}\n"

    return output


# Plain functions for direct use in main.py
def search_movies(query: str) -> str:
    return movie_search_tool.run(query)

def search_music(query: str) -> str:
    return music_search_tool.run(query)