#!/usr/bin/env python3
"""Offline tests for Drive-to-Pi image completeness proof."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi_drive_attest.py"
spec = importlib.util.spec_from_file_location("pi_drive_attest", SCRIPT)
attest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(attest)


class VerifyDriveSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.local = Path(self.tmp.name)
        self.images = {str(n): f"0{n} Abbildung.png" for n in range(1, 5)}
        self.manifest = {"updated": 123, "tiles": {}}
        for tile_id, name in self.images.items():
            folder = self.local / f"kachel{tile_id}"
            folder.mkdir()
            (folder / name).write_bytes(b"valid-image")
            self.manifest["tiles"][tile_id] = [{"name": name, "type": "image"}]
        (self.local / "manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )

    def fake_drive(self, remote_root, tile_id):
        return [self.images[tile_id]], []

    def test_matches_all_four_drive_folders(self):
        with patch.object(attest, "read_drive_files", side_effect=self.fake_drive):
            proof = attest.create_proof("drive:tus-BERNE-Infoboard-Hochkant", self.local)
            self.assertEqual(set(proof["image_names"]), set(self.images))
            attest.atomic_write(self.local, proof)
        saved = json.loads(
            (self.local / attest.PROOF_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(saved, proof)

    def test_missing_drive_image_blocks_proof(self):
        with patch.object(attest, "read_drive_files", return_value=(["different.png"], [])):
            with self.assertRaisesRegex(ValueError, "stimmen nicht"):
                attest.create_proof("drive:folder", self.local)
        self.assertFalse((self.local / attest.PROOF_NAME).exists())

    def test_empty_drive_folder_blocks_proof(self):
        with patch.object(attest, "read_drive_files", return_value=([], [])):
            with self.assertRaisesRegex(ValueError, "stimmen nicht"):
                attest.create_proof("drive:folder", self.local)

    def test_missing_pi_file_blocks_proof(self):
        (self.local / "kachel1" / self.images["1"]).unlink()
        with patch.object(attest, "read_drive_files", side_effect=self.fake_drive):
            with self.assertRaisesRegex(ValueError, "lokale Bilddatei"):
                attest.create_proof("drive:folder", self.local)

    def test_half_complete_manifest_blocks_proof(self):
        self.manifest["tiles"].pop("4")
        (self.local / "manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "unvollstaendig"):
            attest.create_proof("drive:folder", self.local)

    def test_remote_failure_blocks_proof(self):
        with patch.object(
            attest, "read_drive_files", side_effect=ValueError("Drive nicht erreichbar")
        ):
            with self.assertRaisesRegex(ValueError, "Drive nicht erreichbar"):
                attest.create_proof("drive:folder", self.local)

    def test_proof_contains_empty_pdf_lists(self):
        with patch.object(attest, "read_drive_files", side_effect=self.fake_drive):
            proof = attest.create_proof("drive:folder", self.local)
        self.assertEqual(proof["pdf_names"], {tile: [] for tile in self.images})

    def test_matching_pdf_can_be_verified(self):
        pdf = "03 Turnierinformationen.pdf"
        tile = "3"
        (self.local / "kachel3" / pdf).write_bytes(b"%PDF-1.7\n")
        self.manifest["tiles"][tile].append({"name": pdf, "type": "pdf"})
        (self.local / "manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )
        def drive(remote_root, tile_id):
            return [self.images[tile_id]], ([pdf] if tile_id == tile else [])
        with patch.object(attest, "read_drive_files", side_effect=drive):
            proof = attest.create_proof("drive:folder", self.local)
        self.assertEqual(proof["pdf_names"][tile], [pdf])

    def test_missing_drive_pdf_blocks_proof(self):
        pdf = "03 Turnierinformationen.pdf"
        (self.local / "kachel3" / pdf).write_bytes(b"%PDF-1.7\n")
        self.manifest["tiles"]["3"].append({"name": pdf, "type": "pdf"})
        (self.local / "manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )
        with patch.object(attest, "read_drive_files", side_effect=self.fake_drive):
            with self.assertRaisesRegex(ValueError, "Drive-PDFs"):
                attest.create_proof("drive:folder", self.local)

    def test_remote_lists_pdf_and_image_in_one_call(self):
        class Proc:
            returncode = 0
            stdout = json.dumps([
                {"Name": "A.png", "IsDir": False},
                {"Name": "B.PDF", "IsDir": False},
                {"Name": "C.html", "IsDir": False},
            ])
        with patch.object(attest.subprocess, "run", return_value=Proc()):
            images, pdfs = attest.read_drive_files("drive:folder", "1")
        self.assertEqual(images, ["A.png"])
        self.assertEqual(pdfs, ["B.PDF"])

    def test_duplicate_names_block_proof(self):
        with self.assertRaisesRegex(ValueError, "doppelte"):
            attest.image_names([{"name": "same.png"}, {"name": "same.png"}])

    def test_remote_json_list_and_errors(self):
        class Proc:
            def __init__(self, returncode=0, stdout="[]"):
                self.returncode = returncode
                self.stdout = stdout

        with patch.object(attest.subprocess, "run", return_value=Proc(
            stdout=json.dumps([
                {"Name": "hello.png", "IsDir": False},
                {"Name": "other.html", "IsDir": False},
            ])
        )):
            self.assertEqual(attest.read_drive_files("drive:base", "1"), (["hello.png"], []))
        with patch.object(attest.subprocess, "run", return_value=Proc(returncode=1)):
            with self.assertRaisesRegex(ValueError, "fehlgeschlagen"):
                attest.read_drive_files("drive:base", "1")


if __name__ == "__main__":
    unittest.main()
