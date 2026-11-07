import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import music

class MusicRecognitionTests(unittest.TestCase):
    @patch.object(music, "AUDD_API_TOKEN", "")
    def test_missing_token_returns_not_configured(self):
        result = music.identify_songs(Path("unused.mp4"), 90)
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["matches"], [])

    @patch.object(music, "_extract_sample", return_value=b"sample-audio-data" * 100)
    @patch.object(music.requests, "post")
    def test_deduplicates_repeated_matches_and_preserves_timestamps(self, post, extract):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "status": "success",
            "result": {"artist": "Example Artist", "title": "Example Song", "song_link": "https://example.com/song"}
        }
        post.return_value = response
        with patch.object(music, "AUDD_API_TOKEN", "test-token"):
            result = music.identify_songs(Path("unused.mp4"), 90, 90)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["matched_at_seconds"], 90)
        self.assertEqual(result["matches"][0]["provider"], "AudD")
        self.assertEqual(post.call_count, 3)

    @patch.object(music, "_extract_sample", return_value=b"sample-audio-data" * 100)
    @patch.object(music.requests, "post")
    def test_no_match_is_not_reported_as_identified(self, post, extract):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"status": "success", "result": None}
        post.return_value = response
        with patch.object(music, "AUDD_API_TOKEN", "test-token"):
            result = music.identify_songs(Path("unused.mp4"), 15)
        self.assertEqual(result["status"], "no_match")
        self.assertEqual(result["matches"], [])
        self.assertEqual(post.call_count, 1)

if __name__ == "__main__":
    unittest.main()
