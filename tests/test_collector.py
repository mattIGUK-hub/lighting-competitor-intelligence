import unittest
from datetime import date
from collector import rss_records, classify, region, is_safe_link, matches_brand


class CollectorTests(unittest.TestCase):
    def test_parses_valid_item_and_rejects_unsafe_link(self):
        xml = b'''<rss version="2.0"><channel>
        <item><title>TRILUX opens London lighting showroom</title>
        <link>https://news.google.com/rss/articles/valid123</link>
        <description>Lighting design event in the UK</description>
        <pubDate>Thu, 12 Nov 2026 09:00:00 GMT</pubDate></item>
        <item><title>Unsafe content</title><link>http://unsafe.example/item</link>
        <pubDate>Thu, 12 Nov 2026 09:00:00 GMT</pubDate></item>
        </channel></rss>'''
        source = {"competitor": "TRILUX", "name": "Test RSS", "expected_domain": "news.google.com"}
        found = rss_records(xml, source, date(2026, 11, 14))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["competitor"], "TRILUX")
        self.assertEqual(found[0]["published_at"], "2026-11-12")
        self.assertEqual(found[0]["geography"], "UK")
        self.assertEqual(found[0]["verification"], "needs_review")
        self.assertEqual(found[0]["category"], "Events")

    def test_classification_and_brand_match(self):
        self.assertEqual(classify("New circular economy remanufacturing"), "Sustainability")
        self.assertEqual(region("Project in Manchester"), "Unconfirmed")
        self.assertTrue(matches_brand("Delta Light", "Deltalight showroom"))
        self.assertFalse(matches_brand("XAL", "Unrelated street lamp"))

    def test_https_domain_restriction(self):
        self.assertTrue(is_safe_link("https://news.google.com/rss/articles/123", "news.google.com"))
        self.assertFalse(is_safe_link("https://news.google.com.evil.example/a", "news.google.com"))
        self.assertFalse(is_safe_link("javascript:alert(1)", "news.google.com"))


if __name__ == "__main__":
    unittest.main()
