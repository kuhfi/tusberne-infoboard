#!/usr/bin/env python3
"""Offline tests for Pi training HTML to public JSON exporter."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi_training_export.py"
spec = importlib.util.spec_from_file_location("pi_training_export", SCRIPT)
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)


def html_for(location, season="Saison 2026/27"):
    header = ('<main><header><div class="brandtext"><h1>' + location +
              '</h1><div class="sub"><span>' + season +
              '</span><time id="date"></time></div></div></header><div class="week">')
    for day in exp.WEEKDAYS:
        header += f'<section class="day" aria-label="{day}"><div class="dayhead">Tag</div>'
        for n in range(1, 4):
            t = '<span class="hours">18:00–19:30</span>'
            if n == 3:
                t = '<span class="hours">19:30/20:00<br>–21:00</span>'
            header += (
                '<div class="row"><div class="time compact">'
                f'<span>Block {n}</span>{t}</div>'
                '<div class="half front"><div class="cell">2013<small>(14-täglich)</small></div></div>'
                '<div class="half back"><div class="cell free">frei</div></div></div>'
            )
        header += '</section>'
    return header + "</div><footer>Ende</footer></main>"


class TrainingTests(unittest.TestCase):
    def test_parse_berne_schedule(self):
        result = exp.parse_schedule(html_for("Sportplatz „Berner Allee“"), "berne")
        self.assertEqual(len(result["days"]), 5)
        self.assertEqual(len(result["days"][0]["blocks"]), 3)
        self.assertEqual(result["days"][0]["blocks"][0]["front"], ["2013 (14-täglich)"])
        self.assertEqual(result["days"][0]["blocks"][2]["time"], "19:30/20:00 –21:00")

    def test_parse_farmsen_schedule(self):
        result = exp.parse_schedule(html_for("Sportplatz „3 für FARBE“"), "farmsen")
        self.assertEqual(result["location_id"], "farmsen")

    def test_reject_wrong_location(self):
        with self.assertRaisesRegex(ValueError, "Platz oder Saison"):
            exp.parse_schedule(html_for("Sportplatz „3 für FARBE“"), "berne")

    def test_reject_missing_day(self):
        src = html_for("Sportplatz „Berner Allee“")
        src = src.replace('aria-label="Freitag"', 'aria-label="Sonntag"')
        with self.assertRaisesRegex(ValueError, "Trainingstage"):
            exp.parse_schedule(src, "berne")

    def test_reject_missing_block(self):
        src = html_for("Sportplatz „Berner Allee“")
        # Last block of each day is removed; these rows have unique times.
        src = src.replace(
            '<div class="row"><div class="time compact"><span>Block 3</span>',
            '<div class="row"><div class="time compact"><span>Block 9</span>'
        )
        with self.assertRaisesRegex(ValueError, "Trainingsblock"):
            exp.parse_schedule(src, "berne")

    def test_reject_missing_week(self):
        with self.assertRaisesRegex(ValueError, "Wochenbereich"):
            exp.parse_schedule(html_for("Sportplatz „Berner Allee“").replace('<div class="week">', '<div class="not-week">'), "berne")

    def test_preview_does_not_change_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "portrait-content/kachel1"
            local.mkdir(parents=True)
            (local / "01 Trainingsplan Berne.html").write_text(
                html_for("Sportplatz „Berner Allee“"), encoding="utf-8"
            )
            target = root / "data/training-berne.json"
            target.parent.mkdir()
            target.write_text('{"old": true}', encoding="utf-8")
            with patch.object(exp, "REPO", root):
                new_path, new_bytes, changed = exp.export_one(local.parent, "berne")
            self.assertTrue(changed)
            self.assertEqual(new_path, target)
            self.assertEqual(json.loads(target.read_text()), {"old": True})
            self.assertEqual(json.loads(new_bytes)["days"][0]["name"], "Montag")

    def test_unchanged_schedule_preserves_source_timestamp(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "portrait-content/kachel1"
            local.mkdir(parents=True)
            (local / "01 Trainingsplan Berne.html").write_text(
                html_for("Sportplatz „Berner Allee“"), encoding="utf-8"
            )
            target = root / "data/training-berne.json"
            target.parent.mkdir()
            with patch.object(exp, "REPO", root):
                _, encoded, _ = exp.export_one(local.parent, "berne")
                previous = json.loads(encoded)
                previous["source_modified_at"] = "2026-09-30T17:53:54.459Z"
                target.write_text(json.dumps(previous), encoding="utf-8")
                _, encoded_again, changed = exp.export_one(local.parent, "berne")
            self.assertFalse(changed)
            self.assertEqual(
                json.loads(encoded_again)["source_modified_at"],
                "2026-09-30T17:53:54.459Z"
            )


if __name__ == "__main__":
    unittest.main()
