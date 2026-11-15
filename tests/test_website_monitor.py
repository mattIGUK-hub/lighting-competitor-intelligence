import unittest

from website_monitor import normalized_text


class WebsiteMonitorTests(unittest.TestCase):
    def test_readable_html_ignores_navigation_and_scripts(self):
        html = """<html><body><nav>IRRELEVANT</nav><main><h1>LIGHT THAT MOVES</h1>
        <p>Architectural lighting for people and places.</p>
        <script>secret token</script></main></body></html>"""
        cleaned = normalized_text(html)
        self.assertIn("LIGHT THAT MOVES", cleaned)
        self.assertNotIn("IRRELEVANT", cleaned)
        self.assertNotIn("secret token", cleaned)

    def test_whitespace_is_normalized(self):
        html = "<html><body><main><p>one   two</p><p>three</p></main></body></html>"
        self.assertEqual(normalized_text(html), "one two three")


if __name__ == "__main__":
    unittest.main()
