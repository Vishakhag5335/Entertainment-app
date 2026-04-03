import os
from dotenv import load_dotenv
from crewai import Agent, LLM
from tools import movie_search_tool, music_search_tool, movie_details_tool

load_dotenv()

gemini_llm = LLM(
    model="gemini/gemini-2.0-flash",
    api_key=os.getenv("GEMINI_API_KEY")
)

movie_agent = Agent(
    role="Movie Expert",
    goal="Find movies based on user request",
    backstory="You are a movie expert who recommends films by genre.",
    tools=[movie_search_tool, movie_details_tool],
    llm=gemini_llm,
    verbose=False,
    max_iter=2  # Limits how many times agent loops
)

music_agent = Agent(
    role="Music Expert",
    goal="Find songs that match the user mood",
    backstory="You are a music curator who matches songs to moods.",
    tools=[music_search_tool],
    llm=gemini_llm,
    verbose=False,
    max_iter=2
)

planner_agent = Agent(
    role="Entertainment Planner",
    goal="Combine movies and music into a short entertainment plan",
    backstory="You create brief and fun entertainment plans.",
    tools=[],
    llm=gemini_llm,
    verbose=False,
    max_iter=1
)