#!/usr/bin/env python3
"""Stufe 1: oeffentliche Pi-Bilder und Fussballtabellen lokal fuer GitHub vorbereiten.

Standard: rein lesender Probelauf. --apply schreibt nur in die Git-Arbeitskopie.
Dieses Programm fuehrt weder git commit noch git push aus.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PI_PUBLIC = Path("/home/kuhfi/infoboard-app/public")
TILE_DIR = PI_PUBLIC / "portrait-content"
CATEGORIES = {
    "1": "training", "2": "belegung",
    "3": "tabellen-news", "4": "mannschaften-ansprechpartner",
}
# Bereits kuratierte Homepage-Bilder: deren URLs und Beschreibungen beibehalten.
EXISTING = {
    ("1", "03 Lageplan Tore.png"): "files/lageplan-tore.png",
    ("1", "04 Advance Football.png"): "files/advance-football.png",
    ("1", "05 DFB Akademie.png"): "files/dfb-akademie.png",
    ("2", "01 Kabinen Training.png"): "files/kabinen-training.png",
    ("3", "02 Schiedsrichter Kosten.png"): "files/schiedsrichterkosten-hfv-2026.png",
    ("3", "03 Fussballschule.png"): "files/fussballschule-herbstferien-2026.png",
    ("3", "04 Sitzbank.png"): "files/mobile-sitzbank.png",
    ("3", "05 Warnung.png"): "files/dach-betreten-verboten.png",
    ("3", "06 Jahresauftaktessen 2027.png"): "files/jahresauftaktessen-2027.png",
    ("3", "07 Notfallfortbildung.png"): "files/notfallfortbildung-2027.png",
    ("3", "08 Sternbrücke.png"): "files/sternenbruecke.png",
    ("4", "01 Abteilungsleitung.png"): "files/abteilungsleitung.png",
}
ALLOWED_IMAGES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024
GAME_FIELDS = ("date", "time", "competition", "home", "away",
               "home_score", "away_score", "status")
TABLE_FIELDS = ("place", "team", "games", "won", "draw",
                "lost", "goals", "points")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def slug(name):
    value = re.sub(r"^\d{1,3}[\s_-]+", "", Path(name).stem)
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")[:65] or "bild"


def public_title(name):
    return re.sub(r"^\d{1,3}[\s_-]+", "", Path(name).stem).replace("_", " ").strip()


def clean_scalar_dict(value, fields):
    if not isinstance(value, dict):
        return None
    return {field: value[field] for field in fields
            if field in value and
            (value[field] is None or isinstance(value[field], (str, int, float, bool)))}


def football_export():
    source = PI_PUBLIC / "fussball-live/fussball_live_data.json"
    original = load_json(source)
    teams = original.get("teams")
    if not isinstance(teams, list) or len(teams) < 10 or len(teams) > 40:
        raise ValueError("Fussballdaten: unerwartete Mannschaftsanzahl")
    result = []
    for team in teams:
        if not isinstance(team, dict) or not isinstance(team.get("table"), list):
            raise ValueError("Fussballdaten: Tabellenstruktur ungueltig")
        rows = []
        for raw in team["table"]:
            row = clean_scalar_dict(raw, TABLE_FIELDS)
            if row is not None:
                rows.append(row)
        result.append({
            "display_name": str(team.get("display_name", "")),
            "league_line": str(team.get("league_line", "")),
            "last_game": clean_scalar_dict(team.get("last_game"), GAME_FIELDS),
            "next_game": clean_scalar_dict(team.get("next_game"), GAME_FIELDS),
            "table": rows,
        })
    if sum(len(team["table"]) for team in result) < 80:
        raise ValueError("Fussballdaten unvollstaendig: weniger als 80 Tabellenzeilen")
    new = {"generated_at": original.get("generated_at"), "teams": result}
    target = REPO / "data/fussball_live_data.json"
    if target.is_file():
        old = load_json(target)
        if old.get("teams") == new["teams"]:
            # Keine Commits allein wegen eines neuen Abruf-Zeitstempels.
            new["generated_at"] = old.get("generated_at") or new["generated_at"]
    return target, encoded(new), len(teams)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="gepruefte Dateien in die Git-Arbeitskopie schreiben; kein Push")
    args = parser.parse_args()

    if not (REPO / ".git").exists():
        raise RuntimeError("Git-Arbeitskopie fehlt")
    remote = subprocess.check_output(
        ["git", "-C", str(REPO), "remote", "get-url", "origin"], text=True
    ).strip()
    if remote != "git@github.com:kuhfi/tusberne-infoboard.git":
        raise RuntimeError("Unerwartetes GitHub-Repository: Vorgang abgebrochen")
    manifest = load_json(TILE_DIR / "manifest.json")
    tiles = manifest.get("tiles")
    if not isinstance(tiles, dict) or set(tiles) != set(CATEGORIES):
        raise ValueError("Unvollstaendiges Kachel-Manifest: Vorgang abgebrochen")
    if any(not isinstance(tiles[key], list) or not tiles[key] for key in CATEGORIES):
        raise ValueError("Eine Kachel fehlt oder ist leer: Vorgang abgebrochen")

    index_file = REPO / "data/content.json"
    index = load_json(index_file)
    if index.get("schema_version") != 1 or not isinstance(index.get("items"), list):
        raise ValueError("GitHub-Inhaltsverzeichnis ungueltig")
    items = index["items"]

    staged = {}
    counts = {"pictures": 0, "new": 0, "excluded_html": 0}
    for tile_id, entries in tiles.items():
        folder = TILE_DIR / ("kachel" + tile_id)
        for entry in entries:
            name = entry.get("name")
            if not isinstance(name, str) or not name or name != Path(name).name:
                raise ValueError("Ungueltiger Dateiname im Manifest")
            if entry.get("type") != "image":
                counts["excluded_html"] += 1
                continue  # HTML gesondert behandeln; Wetter niemals uebertragen.
            if Path(name).suffix.lower() not in ALLOWED_IMAGES:
                raise ValueError("Nicht freigegebener Bild-Dateityp: " + name)
            source = folder / name
            if source.is_symlink() or not source.is_file():
                raise FileNotFoundError("Quelldatei fehlt: " + str(source))
            if source.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError("Bild zu gross: " + name)

            source_id = "kachel" + tile_id + "/" + name
            relative = EXISTING.get((tile_id, name))
            if relative is None:
                fingerprint = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
                relative = ("files/drive/kachel" + tile_id + "/" + slug(name)
                            + "-" + fingerprint + Path(name).suffix.lower())
            url = "./" + relative
            matching = next((item for item in items
                             if item.get("source_path") == source_id), None)
            if matching is None:
                matching = next((item for item in items
                                 if item.get("url") == url), None)
            if matching is None:
                matching = {"public": True, "category": CATEGORIES[tile_id],
                            "title": public_title(name), "kind": "image",
                            "url": url}
                items.append(matching)
                counts["new"] += 1
            # Bereits vorhandene kuratierte Titel/Beschreibungen erhalten.
            matching["source_path"] = source_id
            matching["managed_by"] = "pi-public-sync"
            target = REPO / relative
            staged[target] = source.read_bytes()
            counts["pictures"] += 1

    football_path, football_bytes, team_count = football_export()
    staged[football_path] = football_bytes
    staged[index_file] = encoded(index)

    changed = []
    for path, contents in staged.items():
        if not path.is_file() or path.read_bytes() != contents:
            changed.append((path, contents))
    mode = "ANWENDEN" if args.apply else "PROBELAUF (keine Aenderungen)"
    print("=== " + mode + " ===")
    print("Bilder aus 4 Kacheln:", counts["pictures"])
    print("Neue Bildeintraege:", counts["new"])
    print("Ausgeschlossene HTML-Dateien:", counts["excluded_html"])
    print("Fussballmannschaften:", team_count)
    print("Dateien mit Aenderungen:", len(changed))
    for path, contents in changed:
        print("  ", path.relative_to(REPO), "(" + str(len(contents)) + " Bytes)")
        if args.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
    if args.apply:
        print("Lokale Dateien aktualisiert. Noch KEIN Git-Commit/Push.")
    else:
        print("Nichts veraendert. Fuer die lokale Vorbereitung: --apply")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("STOPP:", exc, file=sys.stderr)
        sys.exit(1)
