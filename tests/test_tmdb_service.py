import unittest

from tmdb_service import build_placeholder_image, build_watch_url, extract_movie_candidates, pick_best_trailer


class TMDbServiceTests(unittest.TestCase):
    def test_extract_movie_candidates_from_markdown(self):
        markdown = """
        | Title | Year | Genre | Audience Score | Why It Fits |
        | --- | --- | --- | --- | --- |
        | Inception | 2010 | Sci-Fi | 94 | Smart and thrilling |
        | Interstellar | 2014 | Sci-Fi | 92 | Emotional and ambitious |
        """

        titles = extract_movie_candidates(markdown)
        self.assertEqual(titles, ["Inception", "Interstellar"])

    def test_pick_best_trailer_prefers_official(self):
        videos = [
            {"type": "Teaser", "official": False, "key": "teaser"},
            {"type": "Trailer", "official": False, "key": "trailer"},
            {"type": "Trailer", "official": True, "key": "official"},
        ]
        self.assertEqual(pick_best_trailer(videos), "https://www.youtube.com/watch?v=official")

    def test_pick_best_trailer_returns_none_when_missing(self):
        self.assertIsNone(pick_best_trailer([]))

    def test_placeholder_image_is_valid_svg_data_uri(self):
        image = build_placeholder_image()
        self.assertTrue(image.startswith("data:image/svg+xml"))

    def test_watch_url_falls_back_to_search_when_provider_link_missing(self):
        self.assertEqual(build_watch_url("https://example.com/watch", "Inception"), "https://example.com/watch")
        self.assertIn("google.com/search", build_watch_url(None, "Inception"))
        self.assertIn("Inception", build_watch_url(None, "Inception"))

    def test_parse_movie_recommendations_from_markdown(self):
        from tmdb_service import parse_movie_recommendations_from_markdown
        markdown = """
        Here is a recommendation:
        | Title | Year | Genre | Audience Score | Why It Fits |
        | --- | --- | --- | --- | --- |
        | The Others | 2001 | Horror, Mystery | 7.6 | Atmospherically spooky and matches perfectly |
        | The Conjuring | 2013 | Horror | 7.5 | Relentless tension |

        And some details:
        ### The Others
        This is a brilliant ghost story starring Nicole Kidman.
        """
        movies = parse_movie_recommendations_from_markdown(markdown)
        self.assertEqual(len(movies), 2)
        self.assertEqual(movies[0]["title"], "The Others")
        self.assertEqual(movies[0]["year"], "2001")
        self.assertEqual(movies[0]["genres"], ["Horror", "Mystery"])
        self.assertEqual(movies[0]["rating"], 7.6)
        # Verify it fetched description from paragraph rather than table cell because paragraph is longer
        self.assertIn("Nicole Kidman", movies[0]["overview"])

        self.assertEqual(movies[1]["title"], "The Conjuring")
        self.assertEqual(movies[1]["year"], "2013")
        self.assertEqual(movies[1]["rating"], 7.5)

    def test_api_keys_sanitization(self):
        from tmdb_service import _get_tmdb_api_key, _omdb_api_key
        import os
        
        # Test TMDB Key sanitization
        os.environ["TMDB_API_KEY"] = "  api_key=12345abc  "
        self.assertEqual(_get_tmdb_api_key(), "12345abc")
        
        # Test OMDb Key sanitization
        os.environ["OMDB_API_KEY"] = " https://www.omdbapi.com/?i=tt3896198&apikey=d8a03d60  "
        self.assertEqual(_omdb_api_key(), "d8a03d60")
        
        # Clean up
        os.environ["TMDB_API_KEY"] = ""
        os.environ["OMDB_API_KEY"] = " https://www.omdbapi.com/?i=tt3896198&apikey=d8a03d60 "

    def test_get_movie_enrichment_mock_fallback(self):
        from tmdb_service import get_movie_enrichment
        
        # Inception is in POPULAR_MOVIES_DB
        data = get_movie_enrichment("Inception")
        self.assertEqual(data["title"], "Inception")
        self.assertEqual(data["year"], "2010")
        self.assertEqual(data["director"], "Christopher Nolan")
        self.assertEqual(data["writer"], "Christopher Nolan")
        self.assertTrue(len(data["similar"]) >= 6)
        self.assertTrue(len(data["cast"]) >= 8)
        self.assertNotEqual(data["backdrop_url"], "")
        self.assertNotEqual(data["poster_url"], "")

    def test_get_movie_enrichment_unpopular_fallback(self):
        from tmdb_service import get_movie_enrichment
        
        # Test a movie not in database, it should generate mock data or call OMDb
        data = get_movie_enrichment("A Brand New Sci-Fi Movie 2026")
        self.assertEqual(data["title"], "A Brand New Sci-Fi Movie 2026")
        self.assertTrue(len(data["similar"]) >= 6)
        self.assertNotEqual(data["director"], "Unknown")
        self.assertNotEqual(data["writer"], "Unknown")


if __name__ == "__main__":
    unittest.main()
