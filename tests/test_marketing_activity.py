import unittest
from datetime import date
from marketing_activity_collector import extract, categories, good_link

ERCO = {
  "brand": "ERCO",
  "name": "ERCO press",
  "domain": "press.erco.com",
  "paths": ["/press-release/"],
  "scope": "Global",
  "url": "https://press.erco.com/en",
}

class MarketingActivityTests(unittest.TestCase):
  def test_extract_official_named_links_and_reject_untrusted_or_generic(self):
    page = """<body><a href="/en/press-release/events-9/erco-lighting-partnership">
    ERCO becomes official lighting partner of an international design event</a>
    <a href="/en/press-release/events-9/erco-lighting-partnership">Read more</a>
    <a href="https://fake-erco.example/en/press-release/something">Fake story about ERCO</a>
    <a href="https://press.erco.com/en/privacy">Privacy policy for visitors</a></body>"""
    records = extract(page, ERCO, "2026-11-15")
    self.assertEqual(len(records), 1)
    self.assertEqual(records[0]["brand"], "ERCO")
    self.assertEqual(records[0]["published_at"], None)
    self.assertEqual(records[0]["first_seen"], "2026-11-15")
    self.assertEqual(records[0]["source_type"], "official_website")

  def test_source_paths_constrain_discoveries(self):
    self.assertFalse(good_link("https://press.erco.com/en/products/anything", ERCO))
    self.assertFalse(good_link("https://malicious-press.erco.com.evil.com/en/press-release/a", ERCO))
    self.assertTrue(good_link("https://press.erco.com/en/press-release/products/new-range", ERCO))

  def test_multiple_marketing_categories(self):
    values = categories("A new UK showroom event for lighting designers", "https://press.erco.com/en/press-release/events-9/a")
    self.assertIn("Events", values)
    self.assertIn("Messaging", values)

if __name__ == "__main__":
  unittest.main()
