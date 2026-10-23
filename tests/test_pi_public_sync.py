#!/usr/bin/env python3
"""Offline safety checks for the public image reconciliation helpers.

Run from the repo root:
    python3 -m unittest discover -s tests -v
"""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi_public_sync.py"
spec = importlib.util.spec_from_file_location("pi_public_sync", SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class DriveRemovalGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proof_path = Path(self.tmp.name) / "drive-publication-verified.json"
        self.override = patch.object(sync, "DRIVE_VERIFICATION", self.proof_path)
        self.override.start()
        self.addCleanup(self.override.stop)
        self.tiles = {
            str(i): [{"name": "01 current.png", "type": "image"},
                     {"name": "02 page.html", "type": "html"}]
            for i in range(1, 5)
        }
        self.manifest = json.dumps({"tiles": self.tiles}).encode("utf-8")

    def write_proof(self, **changes):
        data = {
            "schema_version": 1,
            "source": "google-drive",
            "status": "complete",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "manifest_sha256": hashlib.sha256(self.manifest).hexdigest(),
            "image_names": {str(i): ["01 current.png"] for i in range(1, 5)}
        }
        data.update(changes)
        self.proof_path.write_text(json.dumps(data), encoding="utf-8")

    def test_no_proof_means_no_deletion(self):
        self.assertFalse(sync.verified_drive_manifest(self.manifest, self.tiles))

    def test_good_proof_enables_deletion(self):
        self.write_proof()
        self.assertTrue(sync.verified_drive_manifest(self.manifest, self.tiles))

    def test_stale_proof_blocks_deletion(self):
        self.write_proof(completed_at=(datetime.now(timezone.utc) -
                          timedelta(hours=2)).isoformat())
        self.assertFalse(sync.verified_drive_manifest(self.manifest, self.tiles))

    def test_partial_proof_blocks_deletion(self):
        self.write_proof(image_names={"1": ["01 current.png"]})
        self.assertFalse(sync.verified_drive_manifest(self.manifest, self.tiles))

    def test_changed_manifest_blocks_deletion(self):
        self.write_proof()
        self.assertFalse(sync.verified_drive_manifest(self.manifest + b" ", self.tiles))

    def test_incorrect_filename_blocks_deletion(self):
        self.write_proof(image_names={str(i): ["DIFFERENT.png"] for i in range(1, 5)})
        self.assertFalse(sync.verified_drive_manifest(self.manifest, self.tiles))

    def test_remove_only_stale_sync_managed_images(self):
        active = {"kachel1/01 current.png"}
        items = [
            {"kind": "image", "managed_by": "pi-public-sync",
             "source_path": "kachel1/01 current.png"},
            {"kind": "image", "managed_by": "pi-public-sync",
             "source_path": "kachel1/old.png"},
            {"kind": "image", "source_path": "kachel1/manual.png"},
            {"kind": "link", "managed_by": "pi-public-sync",
             "source_path": "kachel1/old.html"}
        ]
        unchanged, n0 = sync.remove_stale_images(items, active, False)
        self.assertEqual(n0, 0)
        self.assertEqual(unchanged, items)
        kept, n = sync.remove_stale_images(items, active, True)
        self.assertEqual(n, 1)
        self.assertEqual(len(kept), 3)
        self.assertNotIn("kachel1/old.png", [x.get("source_path") for x in kept])

    def test_old_image_only_proof_does_not_enable_pdf_deletion(self):
        self.write_proof()
        self.assertTrue(sync.verified_drive_manifest(self.manifest, self.tiles))
        self.assertFalse(sync.verified_drive_pdf_manifest(self.manifest, self.tiles))

    def test_full_proof_enables_pdf_deletion(self):
        self.write_proof(pdf_names={str(i): [] for i in range(1, 5)})
        self.assertTrue(sync.verified_drive_pdf_manifest(self.manifest, self.tiles))

    def test_pdf_proof_with_wrong_names_blocks_deletion(self):
        self.write_proof(pdf_names={str(i): ["unexpected.pdf"] for i in range(1, 5)})
        self.assertFalse(sync.verified_drive_pdf_manifest(self.manifest, self.tiles))

    def test_pdf_proof_with_missing_tile_blocks_deletion(self):
        self.write_proof(pdf_names={"1": []})
        self.assertFalse(sync.verified_drive_pdf_manifest(self.manifest, self.tiles))

    def test_valid_pdf_file_named_in_manifest(self):
        self.tiles["3"].append({"name": "01 Turnier.PDF", "type": "pdf"})
        self.manifest = json.dumps({"tiles": self.tiles}).encode("utf-8")
        pdf_names = {str(i): [] for i in range(1, 5)}
        pdf_names["3"] = ["01 Turnier.PDF"]
        self.write_proof(pdf_names=pdf_names)
        self.assertTrue(sync.verified_drive_pdf_manifest(self.manifest, self.tiles))

    def test_only_verified_managed_pdf_is_removed(self):
        removed = {"kind": "pdf", "managed_by": "pi-public-sync",
                   "source_path": "kachel3/01 Veranstaltung.pdf",
                   "url": "./files/drive/kachel3/veranstaltung-a1b2c3d4.pdf"}
        existing = {"kind": "pdf", "managed_by": "pi-public-sync",
                    "source_path": "kachel3/02 Bestand.pdf",
                    "url": "./files/drive/kachel3/bestand-c1d2e3f4.pdf"}
        manual = {"kind": "pdf", "source_path": "kachel3/03 Dokument.pdf",
                  "url": "./files/manual.pdf"}
        items = [removed, existing, manual]
        unchanged, count, blobs = sync.remove_stale_pdfs(
            items, {"kachel3/02 Bestand.pdf"}, False
        )
        self.assertEqual(unchanged, items)
        self.assertEqual(count, 0)
        self.assertEqual(blobs, [])
        kept, count, blobs = sync.remove_stale_pdfs(
            items, {"kachel3/02 Bestand.pdf"}, True
        )
        self.assertEqual(kept, [existing, manual])
        self.assertEqual(count, 1)
        self.assertEqual(
            blobs, [sync.REPO / "files/drive/kachel3/veranstaltung-a1b2c3d4.pdf"]
        )

    def test_mass_pdf_removal_is_blocked(self):
        items = [{"kind": "pdf", "managed_by": "pi-public-sync",
                  "source_path": f"kachel3/old{i}.pdf"} for i in range(4)]
        with self.assertRaisesRegex(ValueError, "Zu viele geloeschte PDFs"):
            sync.remove_stale_pdfs(items, set(), True)

    def test_mass_removal_is_blocked(self):
        items = [{"kind": "image", "managed_by": "pi-public-sync",
                  "source_path": f"kachel1/old{i}.png"} for i in range(4)]
        with self.assertRaises(ValueError):
            sync.remove_stale_images(items, set(), True)


if __name__ == "__main__":
    unittest.main()
