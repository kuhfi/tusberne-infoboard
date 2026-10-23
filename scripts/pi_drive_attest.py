#!/usr/bin/env python3
"""Certify a complete Google-Drive-to-Pi public image/PDF synchronization.

Run only after portrait-drive-sync.sh has successfully completed all four
rclone sync calls and atomically written portrait-content/manifest.json.
Without --apply, this script only validates and prints results.

This helper never changes displayed Pi content or manifest entries.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_IMAGES = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_PDFS = {".pdf"}
PROOF_NAME = "drive-publication-verified.json"
TILES = ("1", "2", "3", "4")


def image_names(entries):
    """Extract unique flat image filenames from remote or local listings."""
    if not isinstance(entries, list):
        raise ValueError("Unvollstaendige Dateiliste")
    names = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Ungueltiger Dateieintrag")
        name = entry.get("name")
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("Ungueltiger Dateiname")
        if Path(name).suffix.lower() in ALLOWED_IMAGES:
            names.append(name)
    if not names or len(names) != len(set(names)):
        raise ValueError("Leere oder doppelte Bilddateiliste")
    return sorted(names)


def pdf_names(entries):
    """Return unique PDF filenames; a tile with no PDFs is valid."""
    if not isinstance(entries, list):
        raise ValueError("Unvollstaendige PDF-Dateiliste")
    names = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Ungueltiger PDF-Dateieintrag")
        name = entry.get("name")
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("Ungueltiger PDF-Dateiname")
        if Path(name).suffix.lower() in ALLOWED_PDFS:
            names.append(name)
    if len(names) != len(set(names)):
        raise ValueError("Doppelte PDF-Dateiliste")
    return sorted(names)


def read_drive_files(remote_root, tile_id):
    """rclone must list all pages. Any error disables certification."""
    folder = f"{remote_root.rstrip('/')}/Kachel{tile_id}"
    try:
        proc = subprocess.run(
            ["rclone", "lsjson", folder, "--files-only", "--max-depth", "1"],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Drive-Abfrage Kachel {tile_id} fehlgeschlagen") from exc
    if proc.returncode != 0:
        # Never print rclone stderr, which could include private config data.
        raise ValueError(f"Drive-Abfrage Kachel {tile_id} fehlgeschlagen")
    try:
        records = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Drive-Dateiliste Kachel {tile_id} ungueltig") from exc
    if not isinstance(records, list):
        raise ValueError(f"Drive-Dateiliste Kachel {tile_id} unvollstaendig")
    if any(not isinstance(row, dict) for row in records):
        raise ValueError(f"Drive-Dateiliste Kachel {tile_id} fehlerhaft")
    files = [{"name": row.get("Name")}
             for row in records if row.get("IsDir") is not True]
    return image_names(files), pdf_names(files)


def create_proof(remote_root, local_root):
    manifest_path = local_root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Pi-Manifest fehlt oder ist kein regulaerer Inhalt")
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError("Pi-Manifest ist ungueltig") from exc
    tiles = manifest.get("tiles") if isinstance(manifest, dict) else None
    if not isinstance(tiles, dict) or set(tiles) != set(TILES):
        raise ValueError("Pi-Manifest ist unvollstaendig")

    verified = {}
    verified_pdfs = {}
    for tile_id in TILES:
        entries = tiles[tile_id]
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"Pi-Manifest Kachel {tile_id} leer")
        # HTML and other content are not published by this image exporter.
        local = image_names([
            entry for entry in entries
            if isinstance(entry, dict) and entry.get("type") == "image"
        ])
        local_pdfs = pdf_names([
            entry for entry in entries
            if isinstance(entry, dict) and entry.get("type") == "pdf"
        ])
        drive, drive_pdfs = read_drive_files(remote_root, tile_id)
        if local != drive:
            raise ValueError(
                f"Kachel {tile_id}: Drive-Bilder stimmen nicht mit dem Pi-Manifest ueberein"
            )
        if local_pdfs != drive_pdfs:
            raise ValueError(
                f"Kachel {tile_id}: Drive-PDFs stimmen nicht mit dem Pi-Manifest ueberein"
            )
        for name in local + local_pdfs:
            item = local_root / f"kachel{tile_id}" / name
            if item.is_symlink() or not item.is_file() or item.stat().st_size <= 0:
                raise ValueError(f"Kachel {tile_id}: lokale Bilddatei fehlt")
        verified[tile_id] = drive
        verified_pdfs[tile_id] = drive_pdfs

    # Block a proof if another portrait-sync replaced the manifest meanwhile.
    if manifest_path.read_bytes() != manifest_bytes:
        raise ValueError("Pi-Manifest wurde waehrend der Pruefung veraendert")

    return {
        "schema_version": 1,
        "source": "google-drive",
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "image_names": verified,
        "pdf_names": verified_pdfs,
    }


def atomic_write(local_root, payload):
    target = local_root / PROOF_NAME
    if target.is_symlink():
        raise ValueError("Bestaetigungsdatei ist ein symbolischer Link")
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=local_root,
            prefix=".drive-proof-", delete=False
        ) as tmp:
            temp_name = tmp.name
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote-root", required=True)
    parser.add_argument("--local-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true",
                        help="Write the proof only after successful checks")
    args = parser.parse_args()
    try:
        proof = create_proof(args.remote_root, args.local_root)
        count = sum(len(names) for names in proof["image_names"].values())
        pdf_count = sum(len(names) for names in proof["pdf_names"].values())
        if args.apply:
            atomic_write(args.local_root, proof)
        print(
            "f"Drive-Dateiabgleich: {count} Bilder und {pdf_count} PDFs "
            f"in 4 Kacheln bestaetigt; "
            + ("Bestaetigung geschrieben" if args.apply else "nur Probelauf")
        )
    except (ValueError, OSError) as exc:
        print("WARNUNG: Kein Drive-Nachweis: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
