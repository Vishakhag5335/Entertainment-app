import os
import unittest
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from agents import _get_client, run_plan, MODELS
from main import call_llm


class GroqIntegrationTests(unittest.TestCase):
    def test_dotenv_loads_groq_api_key(self):
        key = os.getenv("GROQ_API_KEY")
        self.assertIsNotNone(key, "GROQ_API_KEY should be loaded from .env")
        self.assertTrue(len(key.strip()) > 0, "GROQ_API_KEY should not be empty")

    def test_groq_client_initialization(self):
        client = _get_client()
        self.assertIsNotNone(client, "Groq client should initialize successfully with the API key")

    def test_models_list_starts_with_llama33(self):
        self.assertEqual(MODELS[0], "llama-3.3-70b-versatile")

    def test_ai_generation_returns_non_empty_result(self):
        res = run_plan("Recommend an uplifting sci-fi movie", "movies")
        self.assertIn("movies", res)
        self.assertNotIn("AI generation is currently unavailable", res["movies"])
        self.assertNotIn("AI generation failed", res["movies"])

    def test_main_call_llm_returns_non_empty_result(self):
        res = call_llm("Suggest a song for relaxation")
        self.assertNotIn("AI generation is currently unavailable", res)
        self.assertNotIn("AI generation failed", res)


if __name__ == "__main__":
    unittest.main()
