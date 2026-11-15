import unittest

from uk_context import uk_activity_evidence, extract_blocks, fetch_article_evidence

NOW = "2026-11-15T15:00:00Z"
SRC = "https://www.examplelighting.co.uk/en/news/a-case-study"


def sample(title, article, footer="Our London office. Contact us."):
    return (
        "<html><body><header>UK Head Office London</header>"
        "<nav>Find a showroom in London</nav>"
        f"<main><article><h1>{title}</h1><p>{article}</p></article></main>"
        f"<footer>{footer}</footer></body></html>"
    )


class UKContextTests(unittest.TestCase):
    def test_london_event_body_qualifies_without_uk_headline(self):
        page = sample("A new lighting showcase",
                      "The launch takes place at the Business Design Centre in London. "
                      "Architects and designers will meet to experience the collection.")
        result = uk_activity_evidence(page, "A new lighting showcase", SRC, NOW)
        self.assertIsNotNone(result)
        self.assertEqual(result["place"], "Business Design Centre")
        self.assertIn("London", result["quote"])
        self.assertEqual(result["source_url"], SRC)

    def test_uk_project_in_article_qualifies(self):
        page = sample("An illuminated cultural destination",
                      "The heritage lighting project at the museum in Manchester "
                      "uses precision optics to bring the exhibition to life.")
        result = uk_activity_evidence(page,"An illuminated cultural destination",SRC,NOW)
        self.assertEqual(result["place"], "Manchester")

    def test_uk_footer_and_navigation_do_not_count(self):
        page = sample("Lighting experience in Germany",
                      "The architecture exhibition took place in Berlin and "
                      "attracted lighting designers from across Europe.")
        self.assertIsNone(uk_activity_evidence(page,"Lighting experience in Germany",SRC,NOW))

    def test_foreign_event_not_reassigned_by_general_london_mention(self):
        page = sample("Milan Design Week 2026",
                      "A new lighting collection was launched in Milan. "
                      "The company operates studios in London and Copenhagen.")
        self.assertIsNone(uk_activity_evidence(page,"Milan Design Week 2026",SRC,NOW))

    def test_generic_uk_contact_paragraph_does_not_count(self):
        page = sample("Lighting collection now available",
                      "A new luminaire technology has been launched for the global market. "
                      "Our products serve many offices around the world. "
                      "<strong>Contact us at our London head office</strong> for more details.")
        self.assertIsNone(uk_activity_evidence(page,"Lighting collection now available",SRC,NOW))

    def test_article_preferred_to_main_page_sidebar(self):
        page = ("<main><article><p>New lighting product with "
                "high-performance optical technology for professional designers.</p></article>"
                "<p>Register for the upcoming design week workshop in London now.</p></main>")
        self.assertIsNone(uk_activity_evidence(page,"New lighting product",SRC,NOW))

    def test_nonsemantic_article_text_can_show_uk_event(self):
        page = ('<html><body><nav>Global website</nav>'
                '<div class="story"><h2>iGuzzini at LiGHT26</h2>'
                '<div>On 18-19 November, we will be at LiGHT26 at the '
                'Business Design Centre in London, where we will showcase '
                'the latest architectural lighting solutions.</div>'
                '</div><footer>Our worldwide locations</footer></body></html>')
        result=uk_activity_evidence(page,"iGuzzini at LiGHT26",SRC,NOW)
        self.assertIsNotNone(result)
        self.assertIn("London", result["quote"])

    def test_markup_outside_main_is_ignored(self):
        page = "<body><p>UK showroom in London for lighting designers.</p></body>"
        self.assertIsNone(uk_activity_evidence(page,"New collection",SRC,NOW))


if __name__ == "__main__":
    unittest.main()
