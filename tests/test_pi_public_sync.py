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

    def test_mass_removal_is_blocked(self):
        items = [{"kind": "image", "managed_by": "pi-public-sync",
                  "source_path": f"kachel1/old{i}.png"} for i in range(4)]
        with self.assertRaises(ValueError):
            sync.remove_stale_images(items, set(), True)


if __name__ == "__main__":
    unittest.main()
