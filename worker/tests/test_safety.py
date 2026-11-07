import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["CURSOR_SECRET"] = "test-secret-that-is-long-enough-for-unit-tests"

from app import config
config.CURSOR_SECRET = "test-secret-that-is-long-enough-for-unit-tests"
from app.cursors import encode_cursor, decode_cursor, InvalidCursor
from app.security import validate_tiktok_url, UnsafeSource
from app.media import _make_progress_hook
from yt_dlp.utils import DownloadError
from app.config import MAX_MEDIA_BYTES


class CursorTests(unittest.TestCase):
    def test_round_trip(self):
        token = encode_cursor("https://www.tiktok.com/@user/video/123", 90.0)
        url, offset = decode_cursor(token)
        self.assertEqual(url, "https://www.tiktok.com/@user/video/123")
        self.assertEqual(offset, 90.0)

    def test_tampered_cursor_rejected(self):
        token = encode_cursor("https://www.tiktok.com/@user/video/123", 90.0)
        with self.assertRaises(InvalidCursor):
            decode_cursor(token + "x")


class UrlValidationTests(unittest.TestCase):
    def test_non_tiktok_host_rejected(self):
        with self.assertRaises(UnsafeSource):
            validate_tiktok_url("https://example.com/video")

    def test_http_rejected(self):
        with self.assertRaises(UnsafeSource):
            validate_tiktok_url("http://www.tiktok.com/@user/video/123")

    @patch("app.security.socket.getaddrinfo")
    def test_private_dns_result_rejected(self, mocked_dns):
        mocked_dns.return_value = [(None, None, None, None, ("127.0.0.1", 443))]
        with self.assertRaises(UnsafeSource):
            validate_tiktok_url("https://www.tiktok.com/@user/video/123")


class DownloadLimitTests(unittest.TestCase):
    def test_progress_hook_rejects_over_limit(self):
        hook = _make_progress_hook()
        with self.assertRaises(DownloadError):
            hook({"filename": "segment.mp4", "downloaded_bytes": MAX_MEDIA_BYTES + 1})

    def test_progress_hook_allows_within_limit(self):
        hook = _make_progress_hook()
        hook({"filename": "segment.mp4", "downloaded_bytes": MAX_MEDIA_BYTES})


if __name__ == "__main__":
    unittest.main()
