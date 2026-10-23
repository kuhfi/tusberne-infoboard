#!/usr/bin/env python3
"""Oeffentliche Pi-Bilder, PDFs und Fussballtabellen lokal fuer GitHub vorbereiten.

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
ALLOWED_PDFS = {".pdf"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024
# Must be written by the upstream Drive downloader *after* a complete successful
# listing of ALL four Drive folders and a matching local manifest was saved.
DRIVE_VERIFICATION = TILE_DIR / "drive-publication-verified.json"
MAX_PROOF_AGE_SECONDS = 45 * 60
MAX_REMOVALS = 3
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



def verified_drive_manifest(manifest_bytes, tiles):
    """Only trust deletions with a fresh, complete, Drive-origin verification.

    Absence/error/staleness of the proof leaves existing public images intact.
    A hash alone is not proof of Drive success: the upstream Drive fetcher MUST
    emit this file only after successful folder listings and local downloads.
    """
    if not DRIVE_VERIFICATION.is_file() or DRIVE_VERIFICATION.is_symlink():
        return False
    try:
        proof = load_json(DRIVE_VERIFICATION)
        if (not isinstance(proof, dict)
                or proof.get("schema_version") != 1
                or proof.get("source") != "google-drive"
                or proof.get("status") != "complete"
                or proof.get("manifest_sha256") != hashlib.sha256(manifest_bytes).hexdigest()):
            return False
        checked = datetime.fromisoformat(str(proof["completed_at"]).replace("Z", "+00:00"))
        if checked.tzinfo is None:
            return False
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        if age < 0 or age > MAX_PROOF_AGE_SECONDS:
            return False
        names_by_tile = proof["image_names"]
        if not isinstance(names_by_tile, dict) or set(names_by_tile) != set(CATEGORIES):
            return False
        for tile_id in CATEGORIES:
            expected = names_by_tile[tile_id]
            current = [entry.get("name") for entry in tiles[tile_id]
                       if isinstance(entry, dict) and entry.get("type") == "image"]
            if (not isinstance(expected, list)
                    or not all(isinstance(x, str) and x for x in expected)
                    or len(set(expected)) != len(expected)
                    or len(set(current)) != len(current)
                    or set(expected) != set(current)):
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def verified_drive_pdf_manifest(manifest_bytes, tiles):
    """PDF removals need an explicit per-tile PDF list in the Drive proof.

    Older image-only proofs remain sufficient for image removal but never
    authorize removing a PDF from the public index.
    """
    if not verified_drive_manifest(manifest_bytes, tiles):
        return False
    try:
        proof = load_json(DRIVE_VERIFICATION)
        names_by_tile = proof.get("pdf_names")
        if not isinstance(names_by_tile, dict) or set(names_by_tile) != set(CATEGORIES):
            return False
        for tile_id in CATEGORIES:
            expected = names_by_tile[tile_id]
            current = [entry.get("name") for entry in tiles[tile_id]
                       if isinstance(entry, dict) and entry.get("type") == "pdf"]
            if (not isinstance(expected, list)
                    or not all(isinstance(x, str) and x
                               and x == Path(x).name and Path(x).suffix.lower() in ALLOWED_PDFS
                               for x in expected)
                    or len(set(expected)) != len(expected)
                    or len(set(current)) != len(current)
                    or set(expected) != set(current)):
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def remove_stale_pdfs(items, active_sources, verified):
    """Remove only our generated public PDF entries on verified Drive deletion.

    Return removed GitHub blob paths separately; callers delete them only
    after all other exports and safety checks have succeeded.
    """
    if not verified:
        return items, 0, []
    stale = [
        item for item in items
        if item.get("managed_by") == "pi-public-sync"
        and item.get("kind") == "pdf"
        and isinstance(item.get("source_path"), str)
        and re.fullmatch(r"kachel[1-4]/[^/]+", item["source_path"])
        and item["source_path"] not in active_sources
    ]
    if len(stale) > MAX_REMOVALS:
        raise ValueError("Zu viele geloeschte PDFs auf einmal; manuelle Pruefung erforderlich")
    stale_ids = {id(item) for item in stale}
    other_urls = {item.get("url") for item in items if id(item) not in stale_ids}
    blobs = []
    for item in stale:
        url = item.get("url")
        if (isinstance(url, str)
                and re.fullmatch(r"\./files/drive/kachel[1-4]/[a-z0-9-]+-[0-9a-f]{8}\.pdf", url)
                and url not in other_urls):
            blobs.append(REPO / url.removeprefix("./"))
    return [item for item in items if id(item) not in stale_ids], len(stale), blobs


def remove_stale_images(items, active_sources, verified):
    """Remove only entries previously managed by this sync; never manual links.

    Published blobs are intentionally NOT deleted in this first stage.
    """
    if not verified:
        return items, 0
    stale = [
        item for item in items
        if item.get("managed_by") == "pi-public-sync"
        and item.get("kind") == "image"
        and isinstance(item.get("source_path"), str)
        and re.fullmatch(r"kachel[1-4]/[^/]+", item["source_path"])
        and item["source_path"] not in active_sources
    ]
    if len(stale) > MAX_REMOVALS:
        raise ValueError("Zu viele geloeschte Bilder auf einmal; manuelle Pruefung erforderlich")
    stale_ids = {id(item) for item in stale}
    return [item for item in items if id(item) not in stale_ids], len(stale)

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
    manifest_bytes = (TILE_DIR / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
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
    counts = {"pictures": 0, "pdfs": 0, "new": 0, "new_pdfs": 0,
              "removed": 0, "removed_pdfs": 0, "excluded_html": 0}
    active_sources = set()
    for tile_id, entries in tiles.items():
        folder = TILE_DIR / ("kachel" + tile_id)
        for entry in entries:
            name = entry.get("name")
            if not isinstance(name, str) or not name or name != Path(name).name:
                raise ValueError("Ungueltiger Dateiname im Manifest")
            kind = entry.get("type")
            if kind not in ("image", "pdf"):
                counts["excluded_html"] += 1
                continue  # HTML gesondert behandeln; Wetter niemals uebertragen.
            permitted = ALLOWED_IMAGES if kind == "image" else ALLOWED_PDFS
            if Path(name).suffix.lower() not in permitted:
                raise ValueError("Nicht freigegebener Datei-Typ: " + name)
            source = folder / name
            if source.is_symlink() or not source.is_file():
                raise FileNotFoundError("Quelldatei fehlt: " + str(source))
            limit = MAX_IMAGE_BYTES if kind == "image" else MAX_PDF_BYTES
            if not 0 < source.stat().st_size <= limit:
                raise ValueError("Datei ist leer oder zu gross: " + name)
            if kind == "pdf":
                with source.open("rb") as pdf:
                    if not pdf.read(5).startswith(b"%PDF-"):
                        raise ValueError("Ungueltige PDF-Datei: " + name)

            source_id = "kachel" + tile_id + "/" + name
            if source_id in active_sources:
                raise ValueError("Doppelter Dateieintrag im Kachel-Manifest: " + source_id)
            active_sources.add(source_id)
            relative = EXISTING.get((tile_id, name)) if kind == "image" else None
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
                            "title": public_title(name), "kind": kind,
                            "url": url}
                items.append(matching)
                counts["new_pdfs" if kind == "pdf" else "new"] += 1
            # Bereits vorhandene kuratierte Titel/Beschreibungen erhalten.
            matching["source_path"] = source_id
            matching["managed_by"] = "pi-public-sync"
            target = REPO / relative
            staged[target] = source.read_bytes()
            counts["pdfs" if kind == "pdf" else "pictures"] += 1

    safe_to_remove = verified_drive_manifest(manifest_bytes, tiles)
    safe_pdf_remove = verified_drive_pdf_manifest(manifest_bytes, tiles)
    items, counts["removed"] = remove_stale_images(items, active_sources, safe_to_remove)
    items, counts["removed_pdfs"], obsolete_pdf_blobs = remove_stale_pdfs(
        items, active_sources, safe_pdf_remove
    )
    index["items"] = items

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
    print("PDFs aus 4 Kacheln:", counts["pdfs"])
    print("Neue Bildeintraege:", counts["new"])
    print("Neue PDF-Eintraege:", counts["new_pdfs"])
    print("Entfernte Bildeintraege:", counts["removed"])
    print("Entfernte PDF-Eintraege:", counts["removed_pdfs"])
    print("Geloeschte Dateien nur nach Drive-Vollpruefung:", "JA" if safe_to_remove else "NEIN")
    print("PDF-Loeschung durch Drive belegt:", "JA" if safe_pdf_remove else "NEIN")
    print("Ausgeschlossene HTML-Dateien:", counts["excluded_html"])
    print("Fussballmannschaften:", team_count)
    print("Dateien mit Aenderungen:", len(changed))
    for path, contents in changed:
        print("  ", path.relative_to(REPO), "(" + str(len(contents)) + " Bytes)")
        if args.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
    if args.apply:
        for blob in obsolete_pdf_blobs:
            if blob.is_symlink():
                raise ValueError("Zu loeschendes PDF ist ein symbolischer Link")
            if blob.is_file():
                blob.unlink()
        print("Lokale Dateien aktualisiert. Noch KEIN Git-Commit/Push.")
    else:
        print("Nichts veraendert. Fuer die lokale Vorbereitung: --apply")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("STOPP:", exc, file=sys.stderr)
        sys.exit(1)
