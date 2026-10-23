#!/usr/bin/env python3
"""Offline end-to-end PDF publication and verified deletion tests."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi_public_sync.py"
spec = importlib.util.spec_from_file_location("pi_public_sync_pdf_integration", SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class PdfPublicationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.source = self.root / "portrait-content"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "data").mkdir()
        (self.repo / "data/content.json").write_text(
            json.dumps({"schema_version": 1, "mode": "published", "items": []}),
            encoding="utf-8"
        )
        self.tiles = {}
        for tile in range(1, 5):
            dest = self.source / f"kachel{tile}"
            dest.mkdir(parents=True)
            (dest / "01 Aushang.png").write_bytes(b"PNG-bytes")
            self.tiles[str(tile)] = [{"name": "01 Aushang.png", "type": "image"}]
        self.pdf = self.source / "kachel3" / "02 Turnierinformationen.pdf"
        self.pdf.write_bytes(b"%PDF-1.7\n1 0 obj\n")
        self.tiles["3"].append({"name": self.pdf.name, "type": "pdf"})
        self.write_manifest_proof()
        self.overrides = [
            patch.object(sync, "REPO", self.repo),
            patch.object(sync, "TILE_DIR", self.source),
            patch.object(sync, "DRIVE_VERIFICATION", self.source / "drive-publication-verified.json"),
            patch.object(sync, "football_export", side_effect=self.football_stub),
            patch.object(sync.subprocess, "check_output", return_value="git@github.com:kuhfi/tusberne-infoboard.git\n"),
        ]
        for override in self.overrides:
            override.start()
            self.addCleanup(override.stop)

    def football_stub(self):
        return self.repo / "data/fussball_live_data.json", b'{"teams":[]}\n', 20

    def write_manifest_proof(self):
        manifest = json.dumps({"tiles": self.tiles}).encode("utf-8")
        (self.source / "manifest.json").write_bytes(manifest)
        proof = {
            "schema_version": 1,
            "source": "google-drive",
            "status": "complete",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "image_names": {str(i): ["01 Aushang.png"] for i in range(1, 5)},
            "pdf_names": {str(i): ([self.pdf.name] if i == 3 and self.pdf.is_file() else [])
                          for i in range(1, 5)},
        }
        (self.source / "drive-publication-verified.json").write_text(
            json.dumps(proof), encoding="utf-8"
        )

    def run_sync(self, apply=True):
        import io
        from contextlib import redirect_stdout
        with patch.object(sync.sys, "argv", ["pi_public_sync.py"] + (["--apply"] if apply else [])):
            stream = io.StringIO()
            with redirect_stdout(stream):
                sync.main()
        return stream.getvalue()

    def test_pdf_upload_and_verified_deletion_removes_index_and_blob(self):
        out = self.run_sync(apply=True)
        self.assertIn("Neue PDF-Eintraege: 1", out)
        index = json.loads((self.repo / "data/content.json").read_text())
        pdfs = [item for item in index["items"] if item["kind"] == "pdf"]
        self.assertEqual(len(pdfs), 1)
        self.assertEqual(pdfs[0]["category"], "tabellen-news")
        self.assertEqual(pdfs[0]["title"], "Turnierinformationen")
        binary = self.repo / pdfs[0]["url"].removeprefix("./")
        self.assertTrue(binary.is_file())
        self.assertEqual(binary.read_bytes(), self.pdf.read_bytes())

        self.pdf.unlink()
        self.tiles["3"] = [i for i in self.tiles["3"] if i["type"] != "pdf"]
        self.write_manifest_proof()
        out = self.run_sync(apply=True)
        self.assertIn("Entfernte PDF-Eintraege: 1", out)
        index = json.loads((self.repo / "data/content.json").read_text())
        self.assertFalse(any(item["kind"] == "pdf" for item in index["items"]))
        self.assertFalse(binary.exists())

    def test_dry_run_never_publishes_pdf(self):
        out = self.run_sync(apply=False)
        self.assertIn("Neue PDF-Eintraege: 1", out)
        index = json.loads((self.repo / "data/content.json").read_text())
        self.assertEqual(index["items"], [])
        self.assertFalse((self.repo / "files").exists())

    def test_not_a_pdf_is_rejected(self):
        self.pdf.write_bytes(b"<html>danger</html>")
        with self.assertRaisesRegex(ValueError, "Ungueltige PDF-Datei"):
            self.run_sync()

    def test_old_proof_does_not_delete_published_pdf(self):
        self.run_sync(apply=True)
        self.pdf.unlink()
        self.tiles["3"] = [i for i in self.tiles["3"] if i["type"] != "pdf"]
        self.write_manifest_proof()
        proof_path = self.source / "drive-publication-verified.json"
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        proof.pop("pdf_names")
        proof_path.write_text(json.dumps(proof), encoding="utf-8")
        out = self.run_sync(apply=True)
        self.assertIn("Entfernte PDF-Eintraege: 0", out)
        index = json.loads((self.repo / "data/content.json").read_text())
        self.assertTrue(any(item["kind"] == "pdf" for item in index["items"]))


if __name__ == "__main__":
    unittest.main()
