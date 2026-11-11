"""Manual, week-scoped cabin assignments. No network calls or public secrets.

The source calculation stays untouched. Only the effective public export is merged.
"""
import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
DEFAULT_PATH = Path("/var/lib/tusberne-kabinen/overrides.json")
CABIN_FIELDS = ("home_cabin", "guest_cabin", "sr_cabin")
GAME_FIELDS = ("date", "time", "kind", "league", "home", "away", *CABIN_FIELDS, "festival")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")
CABIN_RE = re.compile(r"^[\w /.+-]{0,16}$", re.UNICODE)


def override_path():
    return Path(os.environ.get("TUSBERNE_CABINS_OVERRIDES", str(DEFAULT_PATH)))


def now_berlin():
    return datetime.now(TZ)


def week_start(now=None):
    now = now or now_berlin()
    return (now.date() - timedelta(days=now.weekday())).isoformat()


def game_key(game):
    """Conservative identity: never transfer a change to a changed fixture silently."""
    fields = ("date", "time", "kind", "league", "home", "away")
    payload = json.dumps([game.get(k, "") for k in fields], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def file_revision(path=None):
    path = path or override_path()
    data = path.read_bytes() if path.is_file() else b""
    return hashlib.sha256(data).hexdigest()


def load_store(path=None):
    path = path or override_path()
    if not path.is_file():
        return {"schema_version": 1, "weeks": {}}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema_version") != 1 or not isinstance(doc.get("weeks"), dict):
        raise ValueError("Ungültige manuelle Kabinendaten; Export abgebrochen")
    return doc


def clean_game(raw, start, end):
    if not isinstance(raw, dict) or set(raw) - set(GAME_FIELDS):
        raise ValueError("Unzulässige Felder im manuellen Spiel")
    game = {}
    for field in GAME_FIELDS:
        if field == "festival":
            if not isinstance(raw.get(field, False), bool):
                raise ValueError("Ungültiger Turnierstatus")
            game[field] = raw.get(field, False)
            continue
        value = raw.get(field, "")
        if not isinstance(value, str) or len(value) > 160 or any(ord(c) < 32 for c in value):
            raise ValueError("Ungültiger Spieltext")
        game[field] = value.strip()
    if not DATE_RE.fullmatch(game["date"]) or not start <= game["date"] <= end:
        raise ValueError("Spiel liegt nicht in der ausgewählten Woche")
    if not TIME_RE.fullmatch(game["time"]):
        raise ValueError("Ungültige Anstoßzeit")
    if not game["home"] or not game["away"]:
        raise ValueError("Mannschaftsname fehlt")
    for field in CABIN_FIELDS:
        if not CABIN_RE.fullmatch(game[field]):
            raise ValueError("Ungültige Kabinennummer")
    return game


def current_period(raw, now=None):
    start = week_start(now)
    for week in raw.get("period", {}).get("weeks", []):
        if week.get("start") == start and week.get("end") >= start:
            return week
    return None


def effective_plan(raw, store, now=None):
    """Return compatible exported data. Expired/future overrides never apply."""
    now = now or now_berlin()
    result = copy.deepcopy(raw)
    weeks = raw.get("period", {}).get("weeks", [])
    current = current_period(raw, now)
    active_start = current["start"] if current else None
    records = store.get("weeks", {})
    summary = {}
    games = []
    for period in weeks:
        start, end = period["start"], period["end"]
        base = [copy.deepcopy(g) for g in raw.get("games", []) if start <= g.get("date", "") <= end]
        mode = "automatic"
        missing = 0
        if start == active_start and start in records:
            record = records[start]
            mode = record.get("mode", "automatic")
            if mode == "locked":
                base = [clean_game(g, start, end) for g in record["games"]]
                for g in base:
                    g["manual_override"] = True
            elif mode == "partial":
                changes = record.get("changes", {})
                keys = [game_key(g) for g in base]
                # Never apply an ambiguous match.
                for g, key in zip(base, keys):
                    if key in changes and keys.count(key) == 1:
                        g.update(changes[key])
                        g["manual_override"] = True
                missing = len(set(changes) - {k for k in keys if keys.count(k) == 1})
            else:
                raise ValueError("Unbekannter manueller Wochenmodus")
        summary[start] = {"mode": mode, "unmatched": missing}
        games.extend(base)
    result["games"] = games
    result["manual_weeks"] = summary
    return result


def _validate_changes(changes, auto_games):
    if not isinstance(changes, dict) or len(changes) > 200:
        raise ValueError("Ungültige Einzelkorrekturen")
    keys = [game_key(g) for g in auto_games]
    allowed = {k for k in keys if keys.count(k) == 1}
    cleaned = {}
    for key, fields in changes.items():
        if key not in allowed or not isinstance(fields, dict) or not fields or set(fields) - set(CABIN_FIELDS):
            raise ValueError("Spiel nicht eindeutig gefunden; bitte neu laden")
        values = {}
        for field, value in fields.items():
            if not isinstance(value, str) or not CABIN_RE.fullmatch(value):
                raise ValueError("Ungültiger Kabinenwert")
            values[field] = value
        cleaned[key] = values
    return cleaned


def make_record(raw, mode, payload, now=None):
    now = now or now_berlin()
    period = current_period(raw, now)
    if not period:
        raise ValueError("Die aktuelle Kalenderwoche ist nicht in den Quelldaten")
    start, end = period["start"], period["end"]
    current_games = [g for g in raw["games"] if start <= g["date"] <= end]
    if mode == "automatic":
        return start, None
    if mode == "partial":
        changes = _validate_changes(payload.get("changes"), current_games)
        return start, ({"mode": "partial", "changes": changes, "updated_at": now.isoformat()} if changes else None)
    if mode == "locked":
        submitted = payload.get("games")
        if not isinstance(submitted, list) or len(submitted) > 200:
            raise ValueError("Ungültiger vollständiger Wochenplan")
        games = [clean_game(g, start, end) for g in submitted]
        return start, {"mode": "locked", "games": games, "updated_at": now.isoformat()}
    raise ValueError("Unbekannter Bearbeitungsmodus")


def save_store(doc, path=None):
    """Atomic replace, restrictive permissions, one previous-state backup."""
    path = path or override_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("Symlink als Korrekturdatei unzulässig")
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(data) > 200_000:
        raise ValueError("Zu viele gespeicherte Änderungen")
    if path.exists():
        backup = path.with_suffix(".bak")
        old = path.read_bytes()
        fd, name = tempfile.mkstemp(prefix=".kabinen-prev-", dir=path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(old)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, backup)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    fd, name = tempfile.mkstemp(prefix=".kabinen-new-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)