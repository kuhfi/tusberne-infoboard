#!/usr/bin/env python3
"""Offline tests: public Pi teams cache, full contact fields, safe live activation."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi_teams_export.py"
spec = importlib.util.spec_from_file_location("pi_teams_export", SCRIPT)
teams = importlib.util.module_from_spec(spec)
spec.loader.exec_module(teams)


def make_cache(count=23):
    data = {
        "source": "https://tusberne-fussball.de/teams/",
        "checkedAt": "2026-10-23T08:00:00Z",
        "hash": "unused",
        "rows": [],
    }
    for i in range(count):
        data["rows"].append([
            f"{i+1}. Mannschaft", "2013" if i else "–",
            f"Ansprechperson {i+1}", "0176/12345678",
            f"team{i+1}@example.org", "Di.+Do. 18:15–19:45 in Berne"
        ])
    return data


def make_index():
    return {"schema_version": 1, "mode": "published", "items": [
        {"public": True, "category": "mannschaften-ansprechpartner",
         "title": "Mannschaften", "kind": "link",
         "url": "https://tusberne-fussball.de/teams/"},
        {"public": True, "category": "mannschaften-ansprechpartner",
         "title": "Abteilungsleitung", "kind": "image",
         "url": "./files/abteilungsleitung.png"}
    ]}


class TeamsExporterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "repo"
        (self.repo / "data").mkdir(parents=True)
        self.cache = self.root / "teams.json"
        self.save(make_cache())
        (self.repo / "data/content.json").write_text(
            json.dumps(make_index()), encoding="utf-8"
        )

    def save(self, cache):
        self.cache.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    def test_23_teams_six_columns_and_unicode(self):
        raw = make_cache()
        raw["rows"][0] = [
            "1. Herren", "–", "Jürgen Evers",
            "0172/9935247", "m5moritz@gmx.de", "Di.+Do. 20:00–21:30 in Berne"
        ]
        raw["rows"][1] = [
            "1. A (U18/U17)", "2009/\n2010", "André von Behrens\nFelix Achilles",
            "0176/61413644\n0176/42058548",
            "vonbehrens@gmx.net\nfe.achilles@gmail.com",
            "Mo. in Farmsen\nMi. in Berne"
        ]
        result = teams.parse_rows(raw)
        self.assertEqual(len(result["teams"]), 23)
        self.assertEqual(result["teams"][0]["contact"], "Jürgen Evers")
        self.assertEqual(result["teams"][1]["year"], "2009/\n2010")
        self.assertEqual(result["teams"][1]["contact"], "André von Behrens\nFelix Achilles")
        self.assertEqual(result["teams"][1]["training"], "Mo. in Farmsen\nMi. in Berne")

    def test_writes_nothing_in_preview(self):
        data, changed = teams.export(self.cache, self.repo)
        self.assertEqual(len(data["teams"]), 23)
        self.assertEqual(len(changed), 2)
        self.assertFalse((self.repo / "data/teams.json").exists())
        saved = json.loads((self.repo / "data/content.json").read_text())
        self.assertEqual(saved["items"][0]["url"], teams.SOURCE_URL)

    def test_link_changes_only_after_successful_export(self):
        data, changed = teams.export(self.cache, self.repo)
        for path, contents in changed:
            path.write_bytes(contents)
        index = json.loads((self.repo / "data/content.json").read_text())
        self.assertEqual(index["items"][0]["url"], teams.TARGET_URL)
        self.assertEqual(index["items"][1]["url"], "./files/abteilungsleitung.png")
        result, none = teams.export(self.cache, self.repo)
        self.assertEqual(none, [])

    def test_timestamps_do_not_cause_extra_commits(self):
        _, changed = teams.export(self.cache, self.repo)
        for path, contents in changed:
            path.write_bytes(contents)
        cache = make_cache()
        cache["checkedAt"] = "2026-11-02T12:00:00Z"
        cache["hash"] = "different"
        self.save(cache)
        _, unchanged = teams.export(self.cache, self.repo)
        self.assertEqual(unchanged, [])

    def test_incomplete_cache_rejected(self):
        with self.assertRaisesRegex(ValueError, "unvollstaendige Anzahl"):
            teams.parse_rows(make_cache(2))

    def test_unexpected_source_rejected(self):
        raw = make_cache()
        raw["source"] = "https://example.org/private"
        with self.assertRaisesRegex(ValueError, "unbekannte Datenquelle"):
            teams.parse_rows(raw)

    def test_wrong_row_length_rejected(self):
        raw = make_cache()
        raw["rows"][0] = ["Team", "2013"]
        with self.assertRaisesRegex(ValueError, "sechs Spalten"):
            teams.parse_rows(raw)

    def test_duplicate_team_rejected(self):
        raw = make_cache()
        raw["rows"][1][0] = raw["rows"][0][0]
        with self.assertRaisesRegex(ValueError, "Doppelte Mannschaft"):
            teams.parse_rows(raw)

    def test_missing_contact_rejected(self):
        raw = make_cache()
        raw["rows"][1][2] = ""
        with self.assertRaisesRegex(ValueError, "Ansprechperson fehlt"):
            teams.parse_rows(raw)

    def test_unexpected_link_rejected(self):
        index = make_index()
        index["items"][0]["url"] = "https://example.org/unexpected"
        with self.assertRaisesRegex(ValueError, "manuell geaendert"):
            teams.updated_index(index)

    def test_control_character_rejected(self):
        raw = make_cache()
        raw["rows"][2][0] = "Team\x00secret"
        with self.assertRaisesRegex(ValueError, "ungueltig"):
            teams.parse_rows(raw)


if __name__ == "__main__":
    unittest.main()
