"""Portable checks for offline packaging and public-safe source."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Sources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("src", "href") and value:
                self.urls.append(value)


class PackageTests(unittest.TestCase):
    def test_entry_point_uses_existing_local_assets(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        sources = Sources()
        sources.feed(html)
        self.assertTrue(html.lower().startswith("<!doctype html>"))
        self.assertIn('name="viewport"', html)
        self.assertIn('src="vendor/lucide.js"', html)
        for url in sources.urls:
            if url.startswith("data:"):
                continue
            self.assertFalse(re.match(r"^[a-z]+:|^//", url, re.I), url)
            self.assertTrue((ROOT / url).is_file(), url)

    def test_no_host_api_or_private_machine_path(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for forbidden in ("window.openai", "globalThis.openai", "document.currentScript",
                          "C:/Users/", "C:\\Users\\", "file:///", "fetch(", "XMLHttpRequest",
                          "new WebSocket", "localStorage", "indexedDB"):
            self.assertNotIn(forbidden, html)
        self.assertIn("Images stay in this prototype session.", html)

    def test_third_party_license_is_present(self):
        license_text = (ROOT / "vendor/LICENSE-lucide").read_text(encoding="utf-8")
        self.assertIn("ISC License", license_text)
        self.assertIn("The MIT License (MIT)", license_text)
        self.assertIn("Copyright", license_text)
        self.assertGreater((ROOT / "vendor/lucide.js").stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
