#!/usr/bin/env python3
"""Export Pi-cached public tus BERNE team contacts to the QR homepage.

The Pi already refreshes cache/teams.json from https://tusberne-fussball.de/teams/.
Read-only by default. --apply writes only this GitHub checkout's data/teams.json
and updates the published "Mannschaften" link after successful validation.
Never changes the Pi display, its caches or Google Drive files.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path("/home/kuhfi/infoboard-app/public/cache/teams.json")
SOURCE_URL = "https://tusberne-fussball.de/teams/"
TARGET_URL = "./files/mannschaften.html"
FIELDS = ("team", "year", "contact", "phone", "email", "training")
MAX_FIELD = {"team": 180, "year": 70, "contact": 400,
             "phone": 250, "email": 420, "training": 1000}
MIN_TEAMS = 18
MAX_TEAMS = 40


def normalize(value, name):
    if not isinstance(value, str):
        raise ValueError(f"Unerwarteter Datentyp in Feld {name}")
    # Preserve intentional line breaks for multiple contacts/sessions.
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = "\n".join(" ".join(line.split()) for line in value.split("\n")).strip()
    if len(value) > MAX_FIELD[name] or "\x00" in value:
        raise ValueError(f"Feld {name} ist zu lang oder ungueltig")
    return value


def parse_rows(source):
    if not isinstance(source, dict):
        raise ValueError("Mannschaftsdaten: Wurzel ist kein Objekt")
    if source.get("source") != SOURCE_URL:
        raise ValueError("Mannschaftsdaten: unbekannte Datenquelle")
    rows = source.get("rows")
    if not isinstance(rows, list) or not MIN_TEAMS <= len(rows) <= MAX_TEAMS:
        raise ValueError("Mannschaftsdaten: unvollstaendige Anzahl Mannschaften")
    items = []
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(FIELDS):
            raise ValueError(f"Mannschaft {index + 1}: erwartet sechs Spalten")
        item = {name: normalize(value, name) for name, value in zip(FIELDS, row)}
        if not item["team"] or not item["contact"]:
            raise ValueError(f"Mannschaft {index + 1}: Name/Ansprechperson fehlt")
        key = item["team"].casefold()
        if key in seen:
            raise ValueError(f"Doppelte Mannschaft: {item['team']}")
        seen.add(key)
        items.append(item)
    return {"schema_version": 1, "source": SOURCE_URL, "teams": items}


def updated_index(index):
    if not isinstance(index, dict) or index.get("schema_version") != 1:
        raise ValueError("Homepage-Inhaltsverzeichnis ungueltig")
    items = index.get("items")
    if not isinstance(items, list):
        raise ValueError("Homepage-Inhaltsverzeichnis ohne Eintraege")
    matching = [item for item in items
                if isinstance(item, dict)
                and item.get("title") == "Mannschaften"
                and item.get("category") == "mannschaften-ansprechpartner"]
    if len(matching) != 1:
        raise ValueError("Homepage-Mannschaftslink nicht eindeutig")
    entry = matching[0]
    if entry.get("kind") != "link" or entry.get("public") is not True:
        raise ValueError("Homepage-Mannschaftslink ist unerwartet")
    if entry.get("url") not in (SOURCE_URL, TARGET_URL):
        raise ValueError("Homepage-Mannschaftslink wurde manuell geaendert")
    entry["url"] = TARGET_URL
    entry["description"] = "23+ Mannschaften, Jahrgänge, Ansprechpartner, Kontaktdaten und Trainingszeiten"
    return index


def export(source_path=SOURCE, repo=REPO):
    if source_path.is_symlink() or not source_path.is_file():
        raise ValueError("Pi-Mannschaftsdatei nicht vorhanden")
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    payload = parse_rows(raw)
    index_path = repo / "data/content.json"
    index = updated_index(json.loads(index_path.read_text(encoding="utf-8")))
    target = repo / "data/teams.json"
    planned = [
        (target, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")),
        (index_path, (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")),
    ]
    changed = [(path, data) for path, data in planned
               if not path.is_file() or path.read_bytes() != data]
    return payload, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--apply", action="store_true",
                        help="Only modify this repository checkout; no commit/push")
    args = parser.parse_args()
    try:
        data, changes = export(args.source, args.repo)
        print("Mannschaften aus Pi-Cache:", len(data["teams"]))
        print("Quelldaten:", data["source"])
        print("Homepage-Dateien mit Aenderungen:", len(changes))
        for path, content in changes:
            print(" ", path.relative_to(args.repo), f"({len(content)} Bytes)")
        if args.apply:
            for path, content in changes:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            print("Homepage-Dateien vorbereitet. Noch kein Git-Commit/Push.")
        else:
            print("Probelauf: keine Dateien veraendert.")
    except (ValueError, OSError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        print("WARNUNG: Mannschafts-Export nicht moeglich: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
