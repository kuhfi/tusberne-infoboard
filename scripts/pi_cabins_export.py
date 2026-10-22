#!/usr/bin/env python3
"""Prueft den berechneten Kabinenplan fuer die oeffentliche GitHub-Homepage.

Standard: rein lesender Probelauf. --apply schreibt NUR in die Git-Arbeitskopie,
ohne Commit oder Push. Der produktive Pi wird nie veraendert.
Private Felder (Quellen, Tabellen-IDs, Berechnungsregeln, Warnungstexte,
Diagnosedaten) werden nicht in den oeffentlichen Export uebernommen.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path("/home/kuhfi/infoboard-app/public/kabinen-live/kabinenplan_data.json")
TARGET = REPO / "data/kabinen_live_data.json"
INDEX = REPO / "data/content.json"
CABIN_URL = "./files/kabinen-belegungsplan.html"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME = re.compile(r"^\d{1,2}:\d{2}$")
FIELDS = ("date", "time", "kind", "league", "home", "away",
          "home_cabin", "guest_cabin", "sr_cabin", "festival")


def short_text(value, max_length=160):
    if value is None:
        return ""
    if not isinstance(value, (str, int, float, bool)):
        raise ValueError("Unerwarteter Wert in einem oeffentlichen Feld")
    text = str(value).strip()
    if len(text) > max_length or any(ord(char) < 32 for char in text):
        raise ValueError("Ungueltiger Wert in einem oeffentlichen Feld")
    return text


def build_export():
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("games"), list):
        raise ValueError("Kabinenplan hat kein gueltiges JSON-Format")
    period = raw.get("period")
    if not isinstance(period, dict):
        raise ValueError("Der Zeitraum fehlt")
    weeks = period.get("weeks")
    if not isinstance(weeks, list) or not 1 <= len(weeks) <= 4:
        raise ValueError("Unerwartete Anzahl der Wochen")
    clean_weeks = []
    for week in weeks:
        if not isinstance(week, dict):
            raise ValueError("Ungueltiger Wocheneintrag")
        start, end = week.get("start"), week.get("end")
        if not isinstance(start, str) or not DATE.fullmatch(start):
            raise ValueError("Ungueltiger Wochenbeginn")
        if not isinstance(end, str) or not DATE.fullmatch(end) or end < start:
            raise ValueError("Ungueltiges Wochenende")
        clean_weeks.append({"start": start, "end": end})

    games = raw["games"]
    if len(games) > 200:
        raise ValueError("Unerwartet viele Spiele")
    clean_games = []
    for game in games:
        if not isinstance(game, dict):
            raise ValueError("Ungueltiges Spiel")
        day, time = game.get("date"), game.get("time")
        if not isinstance(day, str) or not DATE.fullmatch(day):
            raise ValueError("Ungueltiges Spiel-Datum")
        if not isinstance(time, str) or not TIME.fullmatch(time):
            raise ValueError("Ungueltige Anstosszeit")
        if not any(week["start"] <= day <= week["end"] for week in clean_weeks):
            continue
        selected = {field: short_text(game.get(field)) for field in FIELDS
                    if field != "festival"}
        selected["festival"] = bool(game.get("festival"))
        if not selected["home"] or not selected["away"]:
            raise ValueError("Mannschaftsname fehlt")
        clean_games.append(selected)

    generated_at = raw.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at:
        raise ValueError("Erstellungszeit fehlt")
    result = {
        "schema_version": 1,
        "generated_at": generated_at,
        "period": {"weeks": clean_weeks},
        "games": clean_games,
    }

    if TARGET.is_file():
        previous = json.loads(TARGET.read_text(encoding="utf-8"))
        if (previous.get("games") == result["games"] and
                previous.get("period") == result["period"]):
            # Nur inhaltliche Änderungen committen; Zeitstempel nicht künstlich auffrischen.
            result["generated_at"] = previous.get("generated_at", generated_at)
    return result, len(games)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Git-Arbeitskopie aktualisieren; kein Upload")
    args = parser.parse_args()

    export, number_source = build_export()
    data = (json.dumps(export, ensure_ascii=False, indent=2) + "\n").encode()
    changed = not TARGET.is_file() or TARGET.read_bytes() != data
    print("=== KABINENPLAN:", "LOKAL SCHREIBEN" if args.apply else "PROBELAUF", "===")
    print("Wochen:", len(export["period"]["weeks"]))
    print("Spiele in Pi-Datei:", number_source)
    print("Spiele im oeffentlichen Export:", len(export["games"]))
    print("Freigegebene Spielfelder:", ", ".join(FIELDS))
    print("Interne Quellen/Berechnungsdetails: NICHT enthalten")
    print("Vorgesehene GitHub-Datei:", TARGET.relative_to(REPO))
    print("Aenderung:", "JA" if changed else "NEIN")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    if index.get("schema_version") != 1 or not isinstance(index.get("items"), list):
        raise ValueError("GitHub-Inhaltsverzeichnis ungueltig")
    items = index["items"]
    existing = [item for item in items if item.get("url") == CABIN_URL]
    if existing and (len(existing) != 1 or existing[0].get("category") != "belegung"
                     or existing[0].get("kind") != "link"):
        raise ValueError("Kabinenplan-Link mit falscher Zuordnung vorhanden")
    entry_missing = not existing
    print("Kachel-2-Eintrag:", "NEU" if entry_missing else "vorhanden")
    if args.apply:
        if changed:
            TARGET.parent.mkdir(parents=True, exist_ok=True)
            TARGET.write_bytes(data)
            print("Lokale Exportdatei geschrieben")
        if entry_missing:
            insert_pos = next(
                (i + 1 for i, item in enumerate(items)
                 if item.get("category") == "belegung"),
                len(items)
            )
            items.insert(insert_pos, {
                "public": True,
                "category": "belegung",
                "title": "Kabinenbelegungsplan – Heimspiele",
                "kind": "link",
                "url": CABIN_URL,
                "description": "Automatisch vom Raspberry Pi berechnete Spiel- und Kabinenzuordnung der nächsten zwei Wochen.",
                "managed_by": "pi-cabins-export",
            })
            INDEX.write_text(
                json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8"
            )
            print("Kachel-2-Link lokal ergaenzt")
        print("KEIN Commit/Push; nur lokale Git-Arbeitskopie")
    else:
        print("Keinerlei Dateien veraendert")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("STOPP:", error, file=sys.stderr)
        sys.exit(1)
