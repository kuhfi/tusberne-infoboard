#!/usr/bin/env python3
"""Read ONLY private Google-Sheets cabin revisions, validate, cache atomically.

DRY-RUN by default; --apply writes the Pi's existing private overrides.json.
Run from /home/kuhfi/tusberne-github-sync/scripts. Never exports credentials.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from cabins_overrides import (CABIN_FIELDS, clean_game, game_key, load_store,
                              now_berlin, override_path, save_store, week_start)

SHEET_ID = "1U8PoGl6_vGeLxFBryIL0JVBZPw9RAtFnHbQeoov_spc"
DEFAULT_CREDS = "/etc/tusberne/cabins-google-reader.json"
SRC = Path("/home/kuhfi/infoboard-app/public/kabinen-live/kabinenplan_data.json")
SOURCE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
RANGES = ("Wochen!A2:F", "Einzelkorrekturen!A2:F", "Fixierte_Spiele!A2:M")
FIELDS = ("date", "time", "kind", "league", "home", "away", "home_cabin", "guest_cabin", "sr_cabin", "festival")
ALLOWED = {"home_cabin": {"", "1", "2", "3", "4"},
           "guest_cabin": {"", "1", "2", "3", "4"},
           "sr_cabin": {"", "SR1", "SR2"}}
HASH = re.compile(r"^[0-9a-f]{20}$")


def fetch_google_rows(sheet_id=SHEET_ID, creds_path=DEFAULT_CREDS):
    """Use a *read-only* credential; never use or request a write scope."""
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials as UserCredentials

    path = Path(creds_path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Google-Anmeldedatei fehlt oder ist kein regulärer Pfad")
    typ = json.loads(path.read_text(encoding="utf-8")).get("type")
    if typ == "service_account":
        creds = service_account.Credentials.from_service_account_file(str(path), scopes=SOURCE_SCOPES)
    elif typ == "authorized_user":
        creds = UserCredentials.from_authorized_user_file(str(path), scopes=SOURCE_SCOPES)
    else:
        raise ValueError("Unbekanntes Google-Anmeldeformat")
    session = AuthorizedSession(creds)
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values:batchGet"
    response = session.get(url, params=[("ranges", r) for r in RANGES] +
                           [("valueRenderOption", "FORMATTED_VALUE")], timeout=25)
    response.raise_for_status()
    payload = response.json()
    ranges = payload.get("valueRanges")
    if not isinstance(ranges, list) or len(ranges) != 3:
        raise ValueError("Google Sheets lieferte unvollständige Tabellenbereiche")
    return [part.get("values", []) for part in ranges]


def cells(row, n):
    if not isinstance(row, list) or len(row) > n:
        raise ValueError("Ungültiges Google-Sheets-Zeilenformat")
    padded = row + [""] * (n - len(row))
    if any(not isinstance(v, str) for v in padded):
        raise ValueError("Die Google-Daten müssen aus Textzellen bestehen")
    return padded


def current_source_week(source, now=None):
    period = source.get("period", {})
    if not isinstance(period, dict) or not isinstance(period.get("weeks"), list):
        raise ValueError("Fehlerhafte automatische Kabinenperiode")
    start = week_start(now)
    matching = [w for w in period["weeks"] if isinstance(w, dict) and w.get("start") == start]
    if len(matching) != 1:
        raise ValueError("Aktuelle Woche nicht eindeutig in der automatischen Quelle")
    week = matching[0]
    if not isinstance(week.get("end"), str) or week["end"] < start:
        raise ValueError("Ungültiges Enddatum der Woche")
    return week


def validated_revisions(meta_rows, start):
    matches = []
    seen = set()
    for row in meta_rows:
        x = cells(row, 6)
        if x[0] != start:
            continue
        if x[1] not in ("automatic", "partial", "locked"):
            raise ValueError("Ungültiger Wochenmodus in Google Sheets")
        if not x[2].isdigit() or not x[5].isdigit() or int(x[2]) < 1 or int(x[5]) > 200:
            raise ValueError("Ungültige Revision oder Zeilenanzahl")
        rev = int(x[2])
        if rev in seen:
            raise ValueError("Doppelte Wochenrevision")
        seen.add(rev)
        matches.append({"mode": x[1], "revision": rev, "updated_at": x[3],
                        "source_hash": x[4], "count": int(x[5])})
    return max(matches, key=lambda m: m["revision"]) if matches else None


def parse_revision_rows(source, rows, now=None):
    """Pure parser: use the last committed metadata revision, never staging rows."""
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("Drei Google-Datenbereiche erwartet")
    week = current_source_week(source, now)
    start, end = week["start"], week["end"]
    meta = validated_revisions(rows[0], start)
    if not meta:
        return start, None, None
    revision, mode = meta["revision"], meta["mode"]
    details = {"mode": mode, "revision": revision,
               "updated_at": meta["updated_at"], "origin": "google_sheets"}
    if mode == "automatic":
        if meta["count"] != 0:
            raise ValueError("Automatikrevision enthält fremde Detailzeilen")
        return start, None, revision
    if mode == "partial":
        selected = [cells(r, 6) for r in rows[1] if len(r) >= 2 and r[0] == start and str(r[1]) == str(revision)]
        if len(selected) != meta["count"]:
            raise ValueError("Unvollständige Einzelkorrektur. Letzten gültigen Stand beibehalten.")
        current = [g for g in source.get("games", []) if start <= g.get("date", "") <= end]
        ids = [game_key(g) for g in current]
        unique = {k for k in ids if ids.count(k) == 1}
        changes = {}
        for row in selected:
            _, _, key, field, value, _ = row
            if not HASH.fullmatch(key) or field not in CABIN_FIELDS or value not in ALLOWED[field]:
                raise ValueError("Unzulässige Kabinenkorrektur aus Google Sheets")
            # A delayed fixture may legitimately be absent. Keep it so the web UI warns;
            # never apply it to another game, and never infer a new game identity.
            if key in ids and key not in unique:
                raise ValueError("Mehrdeutiges Spiel im automatischen Quellplan")
            if field in changes.get(key, {}):
                raise ValueError("Dieselbe Kabine wurde in einer Revision mehrfach gespeichert")
            changes.setdefault(key, {})[field] = value
        details["changes"] = changes
        return start, details, revision
    selected = [cells(r, 13) for r in rows[2] if len(r) >= 2 and r[0] == start and str(r[1]) == str(revision)]
    if len(selected) != meta["count"]:
        raise ValueError("Unvollständiger gesperrter Wochenplan")
    positions = [r[2] for r in selected]
    if len(set(positions)) != len(positions) or set(positions) != {str(i+1) for i in range(len(selected))}:
        raise ValueError("Ungültige Spielreihenfolge in Google Sheets")
    games = []
    for row in sorted(selected, key=lambda r: int(r[2])):
        _, _, _, date, time, kind, league, home, away, home_cabin, guest_cabin, sr_cabin, festival = row
        if festival.lower() not in ("true", "false"):
            raise ValueError("Ungültiges Turnierkennzeichen")
        game = dict(zip(FIELDS, (date, time, kind, league, home, away,
                                 home_cabin, guest_cabin, sr_cabin, festival.lower() == "true")))
        game = clean_game(game, start, end)
        for field in CABIN_FIELDS:
            if game[field] not in ALLOWED[field]:
                raise ValueError("Unzulässige Kabine im gesperrten Plan")
        games.append(game)
    details["games"] = games
    return start, details, revision


def build_new_store(source, rows, previous, now=None, sheet_id=SHEET_ID):
    start, incoming, revision = parse_revision_rows(source, rows, now)
    result = copy.deepcopy(previous)
    if result.get("schema_version") != 1 or not isinstance(result.get("weeks"), dict):
        raise ValueError("Lokaler Korrekturspeicher beschädigt")
    tracking = result.setdefault("google_cabins_sync", {"sheet_id": sheet_id, "revisions": {}})
    if tracking.get("sheet_id") != sheet_id or not isinstance(tracking.get("revisions"), dict):
        raise ValueError("Falsche Google-Tabelle oder beschädigte Revisionstabelle")
    old_revision = int(tracking["revisions"].get(start, 0))
    local = result["weeks"].get(start)
    if local and local.get("origin") != "google_sheets":
        raise ValueError("Vorhandene lokale Wochenkorrekturen gefunden: erst bewusst migrieren")
    if revision is None:
        if old_revision or local:
            raise ValueError("Google-Revision verschwunden: lokalen Stand nicht überschreiben")
        return result, False, start, 0
    if revision < old_revision:
        raise ValueError("Google-Revision wurde zurückgesetzt; lokalen Stand behalten")
    if revision == old_revision:
        return result, False, start, revision
    if incoming is None:
        result["weeks"].pop(start, None)
    else:
        result["weeks"][start] = incoming
    tracking["revisions"][start] = revision
    # Older data is harmless but keep the local file bounded.
    for k in sorted(result["weeks"])[:-16]:
        result["weeks"].pop(k, None)
    for k in sorted(tracking["revisions"])[:-16]:
        tracking["revisions"].pop(k, None)
    return result, True, start, revision


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Nach Validierung atomar in die private Datei schreiben")
    ap.add_argument("--source", default=str(SRC), help="Pfad der bestehenden automatischen Quelle")
    ap.add_argument("--credentials", default=os.environ.get("TUSBERNE_CABINS_GOOGLE_CREDENTIALS", DEFAULT_CREDS))
    ap.add_argument("--sheet-id", default=os.environ.get("TUSBERNE_CABINS_GOOGLE_SHEET_ID", SHEET_ID))
    args = ap.parse_args(argv)
    source = json.loads(Path(args.source).read_text(encoding="utf-8"))
    if not isinstance(source.get("games"), list):
        raise ValueError("Automatische Spieldaten fehlen")
    rows = fetch_google_rows(args.sheet_id, args.credentials)
    original = load_store()
    updated, changed, start, revision = build_new_store(source, rows, original, sheet_id=args.sheet_id)
    print(f"Google-Kabinen: Woche {start}, Version {revision}, Änderungen: {'JA' if changed else 'NEIN'}")
    if changed and args.apply:
        save_store(updated)
        print("Neue manuelle Vorgaben atomar gespeichert. Keine Änderung an der automatischen Berechnung.")
    elif not args.apply:
        print("PROBELAUF: keine Dateien verändert")
    else:
        print("Bereits aktuell: keine Dateischreiboperation")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("STOPP: Google-Kabinenabgleich abgebrochen; vorhandene Belegung bleibt erhalten:",
              type(exc).__name__, file=sys.stderr)
        sys.exit(1)