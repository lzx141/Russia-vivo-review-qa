from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "src" / "dashboard"


class TestDashboardFrontend(unittest.TestCase):
    def setUp(self):
        self.html = (DASHBOARD / "index.html").read_text(encoding="utf-8")

    def test_external_design_system_and_eight_pages(self):
        self.assertIn('href="styles.css"', self.html)
        self.assertNotIn("<style>", self.html)
        for route in (
            "overview",
            "sentiment",
            "products",
            "geography",
            "timeline",
            "qa",
            "diagnosis",
            "governance",
        ):
            self.assertIn(f'id="page-{route}"', self.html)
            self.assertIn(f'data-page="{route}"', self.html)

    def test_existing_chart_contract_is_preserved(self):
        for chart_id in (
            "ovTrend",
            "ovRating",
            "ovProductRank",
            "ovWordcloud",
            "ovPlatform",
            "sentPie",
            "sentRadar",
            "sentPosCloud",
            "sentNegCloud",
            "sentAspectBar",
            "prodMonthly",
            "prodRatingCompare",
            "geoChart",
            "geoCompetitors",
            "geoFeatures",
            "tlHeatmap",
            "tlTrend",
            "tlLength",
            "qaIntent",
            "qaWordcloud",
            "qaScatter",
            "qaAuthors",
            "diagRootCause",
            "diagSeverity",
            "diagReviews",
        ):
            self.assertIn(f'id="{chart_id}"', self.html)

    def test_accessible_shell_and_governance_nodes_exist(self):
        for token in (
            'id="mobileMenu"',
            'id="navBackdrop"',
            'id="mainContent"',
            'aria-label="主导航"',
            'id="governanceContent"',
            'class="skip-link"',
        ):
            self.assertIn(token, self.html)


if __name__ == "__main__":
    unittest.main()
