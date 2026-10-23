"""Regression tests for Kachel 3 order and Kachel 2 initial week."""
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED_NEWS = [
    "Fußballtabellen",
    "Schiedsrichterkosten – HFV-Sätze ab 01.07.2026",
    "Notfallfortbildung – 09.01.2027",
    "Jahresauftaktessen – 22.01.2027",
    "Warnung – Dach der Multifunktionshalle",
    "Mobile Sitzbank – Kabine 2",
    "Unterstützung Kinder- und Jugendhospiz Sternenbrücke",
]


class HomepageRegressionTests(unittest.TestCase):
    def test_exact_seven_news_entries_have_requested_order(self):
        items = json.loads(
            (REPO / "data/content.json").read_text(encoding="utf-8")
        )["items"]
        news = [x for x in items if x.get("category") == "tabellen-news"]
        self.assertEqual(len(news), len(EXPECTED_NEWS))
        self.assertEqual(
            [x["title"] for x in sorted(news, key=lambda x: x["order"])],
            EXPECTED_NEWS,
        )
        self.assertEqual(sorted(x["order"] for x in news), list(range(1, 8)))

    def test_homepage_honours_numeric_order(self):
        script = (REPO / "assets/app.js").read_text(encoding="utf-8")
        self.assertIn("item.order", script)
        self.assertIn(".sort(function (a, b) { return a.order - b.order; })", script)

    def test_initial_cabins_week_is_one_even_when_empty(self):
        page = (REPO / "files/kabinen-belegungsplan.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("let data=null,week=0;", page)
        self.assertNotIn("nextWithGames", page)
        self.assertRegex(
            page,
            r"week=prevStart\s*\?\s*Math\.max\(0,incoming\.period\.weeks\.findIndex"
            r"\(w=>w\.start===prevStart\)\)\s*:\s*0;",
        )
        self.assertIn("Keine Heimspiele in Berne in dieser Woche.", page)

    def test_week_navigation_remains_available(self):
        page = (REPO / "files/kabinen-belegungsplan.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('next.addEventListener("click",()=>{week++;draw()})', page)
        self.assertIn('prev.addEventListener("click",()=>{week--;draw()})', page)
        self.assertIn("prev.disabled=week===0;next.disabled=week===weeks.length-1", page)


if __name__ == "__main__":
    unittest.main()
