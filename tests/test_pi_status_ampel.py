"""Offline tests for the read-only status script (no Pi services required)."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi_status_ampel.py"
spec = importlib.util.spec_from_file_location("pi_status_ampel", SCRIPT)
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)


class DriveTrafficLightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime.now(timezone.utc)
        self.raw = json.dumps({"tiles": {i: [{"name": "test.png"}] for i in "1234"}}).encode()
        (self.root / "manifest.json").write_bytes(self.raw)
        self.proof = {
            "schema_version": 1,
            "source": "google-drive",
            "status": "complete",
            "manifest_sha256": hashlib.sha256(self.raw).hexdigest(),
            "completed_at": self.now.isoformat()
        }
        self.write_proof()

    def write_proof(self):
        (self.root / "drive-publication-verified.json").write_text(json.dumps(self.proof))

    def test_fresh_complete_proof_green(self):
        self.assertEqual(status.drive_check(self.root, self.now)[0], "GRUEN")

    def test_old_proof_yellow_then_red(self):
        self.proof["completed_at"] = (self.now - timedelta(minutes=20)).isoformat()
        self.write_proof()
        self.assertEqual(status.drive_check(self.root, self.now)[0], "GELB")
        self.proof["completed_at"] = (self.now - timedelta(minutes=50)).isoformat()
        self.write_proof()
        self.assertEqual(status.drive_check(self.root, self.now)[0], "ROT")

    def test_wrong_digest_red(self):
        self.proof["manifest_sha256"] = "not-a-match"
        self.write_proof()
        self.assertEqual(status.drive_check(self.root, self.now)[0], "ROT")

    def test_missing_tile_red(self):
        (self.root / "manifest.json").write_text(json.dumps({"tiles": {"1": [1]}}))
        self.assertEqual(status.drive_check(self.root, self.now)[0], "ROT")


class BackupTrafficLightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.dir = self.base / "2026-10-23_07-00-00_berne-infoboard"
        self.dir.mkdir()
        self.archive = self.dir / "test.tar.gz"
        self.archive.write_bytes(b"not-an-actual-backup")
        self.now = datetime.now(timezone.utc)
        self.info = {
            "created_at": (self.now - timedelta(hours=2)).isoformat(),
            "archive_name": "test.tar.gz",
            "archive_bytes": len(self.archive.read_bytes()),
            "local_extract_and_metadata_verified": True,
            "drive_readback_verified": True
        }
        self.save()

    def save(self):
        (self.dir / "backup-status.txt").write_text(json.dumps(self.info))

    def test_recent_verified_backup_green(self):
        self.assertEqual(status.backup_check(self.base, self.now)[0], "GRUEN")

    def test_old_backup_yellow_and_red(self):
        self.info["created_at"] = (self.now - timedelta(hours=32)).isoformat()
        self.save()
        self.assertEqual(status.backup_check(self.base, self.now)[0], "GELB")
        self.info["created_at"] = (self.now - timedelta(hours=50)).isoformat()
        self.save()
        self.assertEqual(status.backup_check(self.base, self.now)[0], "ROT")

    def test_missing_drive_verification_red(self):
        self.info["drive_readback_verified"] = False
        self.save()
        self.assertEqual(status.backup_check(self.base, self.now)[0], "ROT")

    def test_missing_archive_red(self):
        self.archive.unlink()
        self.assertEqual(status.backup_check(self.base, self.now)[0], "ROT")


class GitTrafficLightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / ".git").mkdir()

    def test_clean_tracking_branch_green(self):
        with patch.object(status, "cmd", side_effect=[
            (0, "main"), (0, ""), (0, "0\t0")
        ]):
            self.assertEqual(status.git_check(self.repo)[0], "GRUEN")

    def test_pending_commit_yellow(self):
        with patch.object(status, "cmd", side_effect=[
            (0, "main"), (0, ""), (0, "0\t1")
        ]):
            self.assertEqual(status.git_check(self.repo)[0], "GELB")

    def test_dirty_checkout_red(self):
        with patch.object(status, "cmd", side_effect=[
            (0, "main"), (0, " M data/content.json")
        ]):
            self.assertEqual(status.git_check(self.repo)[0], "ROT")


if __name__ == "__main__":
    unittest.main()
