from crewai.tools import tool

@tool("Movie Search Tool")
def movie_search_tool(query: str) -> str:
    """Searches for movies based on user query like genre, mood, or title."""
    
    mock_movies = {
        "thriller": [
            {"title": "Gone Girl", "rating": 8.1, "year": 2014},
            {"title": "Prisoners", "rating": 8.1, "year": 2013},
            {"title": "Se7en", "rating": 8.6, "year": 1995},
        ],
        "romance": [
            {"title": "The Notebook", "rating": 7.8, "year": 2004},
            {"title": "La La Land", "rating": 8.0, "year": 2016},
            {"title": "Titanic", "rating": 7.9, "year": 1997},
        ],
        "action": [
            {"title": "John Wick", "rating": 7.4, "year": 2014},
            {"title": "Mad Max: Fury Road", "rating": 8.1, "year": 2015},
            {"title": "The Dark Knight", "rating": 9.0, "year": 2008},
        ],
        "comedy": [
            {"title": "The Grand Budapest Hotel", "rating": 8.1, "year": 2014},
            {"title": "Superbad", "rating": 7.6, "year": 2007},
            {"title": "Home Alone", "rating": 7.7, "year": 1990},
        ],
    }
    
    query_lower = query.lower()
    for genre, movies in mock_movies.items():
        if genre in query_lower:
            result = f"Top {genre} movies:\n"
            for m in movies:
                result += f"- {m['title']} ({m['year']}) — Rating: {m['rating']}\n"
            return result
    
    return "No movies found for your query. Try genres like thriller, romance, action, or comedy."


@tool("Music Search Tool")
def music_search_tool(query: str) -> str:
    """Searches for music/songs based on mood, genre, or movie name."""
    
    mock_music = {
        "thriller": [
            {"song": "Stressed Out", "artist": "Twenty One Pilots", "mood": "intense"},
            {"song": "Psycho", "artist": "Post Malone", "mood": "dark"},
            {"song": "Believer", "artist": "Imagine Dragons", "mood": "powerful"},
        ],
        "romance": [
            {"song": "Perfect", "artist": "Ed Sheeran", "mood": "romantic"},
            {"song": "All of Me", "artist": "John Legend", "mood": "emotional"},
            {"song": "Thinking Out Loud", "artist": "Ed Sheeran", "mood": "warm"},
        ],
        "action": [
            {"song": "Thunder", "artist": "Imagine Dragons", "mood": "energetic"},
            {"song": "Till I Collapse", "artist": "Eminem", "mood": "intense"},
            {"song": "Eye of the Tiger", "artist": "Survivor", "mood": "pump-up"},
        ],
        "comedy": [
            {"song": "Happy", "artist": "Pharrell Williams", "mood": "cheerful"},
            {"song": "Can't Stop the Feeling", "artist": "Justin Timberlake", "mood": "fun"},
            {"song": "Uptown Funk", "artist": "Bruno Mars", "mood": "groovy"},
        ],
    }
    
    query_lower = query.lower()
    for genre, songs in mock_music.items():
        if genre in query_lower:
            result = f"Top {genre} songs:\n"
            for s in songs:
                result += f"- {s['song']} by {s['artist']} (Mood: {s['mood']})\n"
            return result
    
    return "No music found for your query. Try moods like thriller, romance, action, or comedy."


@tool("Movie Details Tool")
def movie_details_tool(title: str) -> str:
    """Gets detailed information about a specific movie."""
    
    mock_details = {
        "gone girl": {
            "director": "David Fincher",
            "cast": ["Ben Affleck", "Rosamund Pike"],
            "duration": "149 min",
            "description": "A thriller about a husband suspected of his wife's disappearance."
        },
        "the dark knight": {
            "director": "Christopher Nolan",
            "cast": ["Christian Bale", "Heath Ledger"],
            "duration": "152 min",
            "description": "Batman faces the Joker, a criminal mastermind in Gotham City."
        },
        "la la land": {
            "director": "Damien Chazelle",
            "cast": ["Ryan Gosling", "Emma Stone"],
            "duration": "128 min",
            "description": "A jazz musician and an actress fall in love in Los Angeles."
        },
    }
    
    title_lower = title.lower()
    if title_lower in mock_details:
        d = mock_details[title_lower]
        return (
            f"Movie: {title}\n"
            f"Director: {d['director']}\n"
            f"Cast: {', '.join(d['cast'])}\n"
            f"Duration: {d['duration']}\n"
            f"Description: {d['description']}"
        )
    
    return f"Details not found for '{title}'. Try 'Gone Girl', 'The Dark Knight', or 'La La Land'."

# Plain functions for direct use (without CrewAI wrapper)
def search_movies(query: str) -> str:
    return movie_search_tool.run(query)

def search_music(query: str) -> str:
    return music_search_tool.run(query)