from crewai import Task
from agents import movie_agent, music_agent, planner_agent

def create_tasks(user_input: str):

    # Task 1 - Movie Research
    movie_task = Task(
        description=f"""
        The user has requested: "{user_input}"
        
        Your job:
        1. Understand what kind of movies the user is looking for
        2. Use the Movie Search Tool to find relevant movies
        3. If the user mentions a specific movie, use Movie Details Tool to get more info
        4. Provide a list of at least 3 movie recommendations with reasons why each is a good fit
        
        Be specific, helpful and friendly in your response.
        """,
        expected_output="""
        A well formatted list of movie recommendations including:
        - Movie title and year
        - Rating
        - Why it matches the user's request
        - Any extra details if available
        """,
        agent=movie_agent
    )

    # Task 2 - Music Curation
    music_task = Task(
        description=f"""
        The user has requested: "{user_input}"
        
        Based on the movies recommended, your job is to:
        1. Identify the mood and genre from the user's request
        2. Use the Music Search Tool to find matching songs
        3. Suggest at least 3 songs that complement the movie-watching experience
        4. Explain why each song fits the mood
        
        Make your suggestions feel personal and curated.
        """,
        expected_output="""
        A curated music list including:
        - Song name and artist
        - Mood/vibe of the song
        - Why it pairs well with the recommended movies
        """,
        agent=music_agent,
        context=[movie_task]  # Music agent waits for movie task to finish first
    )

    # Task 3 - Final Entertainment Plan
    plan_task = Task(
        description=f"""
        The user has requested: "{user_input}"
        
        You have received movie recommendations and music suggestions from the experts.
        Your job is to:
        1. Combine both into one clean, exciting entertainment plan
        2. Structure it nicely with sections for Movies and Music
        3. Add a short intro and a closing note to make it feel complete
        4. Make the user feel excited about their entertainment experience
        
        Keep the tone friendly, fun and engaging.
        """,
        expected_output="""
        A complete Entertainment Plan containing:
        - A short welcome intro
        - Movie Recommendations section
        - Music Playlist section
        - A fun closing note
        """,
        agent=planner_agent,
        context=[movie_task, music_task]  # Waits for both tasks to finish
    )

    return [movie_task, music_task, plan_task]