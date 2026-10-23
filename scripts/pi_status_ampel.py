#!/usr/bin/env python3
"""Rein lesende Ampel fuer das tus-BERNE-Infoboard auf dem Raspberry Pi.

Aufruf: python3 /home/kuhfi/tusberne-github-sync/scripts/pi_status_ampel.py
Keine Netzabfragen, Dateiaenderungen, Neustarts oder Uploads.
Alle Altersgrenzen sind Diagnosehinweise, keine Dienstkonfiguration.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path("/home/kuhfi/infoboard-app/public")
REPO = Path("/home/kuhfi/tusberne-github-sync")
BACKUPS = Path("/home/kuhfi/berne-infoboard-backups")
TIMERS = (
    "berne-portrait-sync", "berne-github-public-sync",
    "berne-fussball-live", "berne-fussballraum-live",
    "berne-kabinen-live", "berne-tv-schedule",
    "berne-radar-prefetch", "berne-backup-daily",
    "berne-padlet-export", "berne-wissensbasis",
    "berne-wissensbasis-erweiterung", "berne-shutdown",
)
# Der deaktivierte Alt-Timer berne-drive-sync ist bewusst NICHT enthalten.
SERVICES = (
    "berne-portrait-sync", "berne-github-public-sync",
    "berne-fussball-live", "berne-fussballraum-live",
    "berne-kabinen-live", "berne-backup-daily",
)
RANK = {"GRUEN": 0, "GELB": 1, "ROT": 2}


def cmd(*args):
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=12, check=False,
        )
        return result.returncode, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 99, ""


def age_minutes(path, now):
    return (now.timestamp() - path.stat().st_mtime) / 60


def drive_check(root, now):
    manifest = root / "manifest.json"
    proof_path = root / "drive-publication-verified.json"
    if not manifest.is_file() or not proof_path.is_file():
        return "ROT", "Manifest oder Drive-Bestaetigung fehlt"
    try:
        raw = manifest.read_bytes()
        tiles = json.loads(raw)["tiles"]
        if set(tiles) != set("1234") or any(
            not isinstance(tiles[k], list) or not tiles[k] for k in "1234"
        ):
            raise ValueError("vier vollstaendige Kacheln fehlen")
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        completed = datetime.fromisoformat(
            proof["completed_at"].replace("Z", "+00:00")
        )
        age = (now - completed).total_seconds() / 60
        if (proof.get("schema_version") != 1
            or proof.get("source") != "google-drive"
            or proof.get("status") != "complete"
            or proof.get("manifest_sha256") != hashlib.sha256(raw).hexdigest()):
            return "ROT", "Drive-Bestaetigung passt nicht zum Manifest"
        if age < -2:
            return "GELB", "Drive-Zeitstempel liegt in der Zukunft"
        if age > 45:
            return "ROT", f"Letzte bestaetigte Drive-Synchronisierung vor {age:.0f} min"
        if age > 15:
            return "GELB", f"Drive-Daten {age:.0f} min alt (Soll ca. 2 min)"
        return "GRUEN", f"Drive bestaetigt vor {age:.0f} min, vier Kacheln"
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return "ROT", "Manifest/Drive-Bestaetigung nicht lesbar"


def backup_check(folder, now):
    statuses = sorted(folder.glob("*/backup-status.txt"), reverse=True)
    if not statuses:
        return "ROT", "Kein Backup-Status gefunden"
    try:
        path = statuses[0]
        info = json.loads(path.read_text(encoding="utf-8"))
        when = datetime.fromisoformat(info["created_at"].replace("Z", "+00:00"))
        hours = (now - when).total_seconds() / 3600
        archive = path.parent / info["archive_name"]
        size = archive.stat().st_size
        if size != info.get("archive_bytes") or size == 0:
            return "ROT", "Backup-Archiv fehlt oder Groesse stimmt nicht"
        if (info.get("local_extract_and_metadata_verified") is not True
            or info.get("drive_readback_verified") is not True):
            return "ROT", "Lokale Pruefung oder Drive-Ruecklesung nicht bestaetigt"
        if hours < -1:
            return "GELB", "Backup-Zeitstempel liegt in der Zukunft"
        if hours > 48:
            return "ROT", f"Letztes verifiziertes Backup {hours:.0f} h alt"
        if hours > 30:
            return "GELB", f"Letztes verifiziertes Backup {hours:.0f} h alt"
        return "GRUEN", f"Backup {hours:.0f} h alt; lokale Pruefung und Drive-Ruecklesung OK"
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return "ROT", "Backup-Status nicht auswertbar"


def file_check(path, warn_after, now):
    try:
        age = age_minutes(path, now)
        if age < -5:
            return "GELB", "Dateizeit liegt in der Zukunft"
        if age > warn_after:
            return "GELB", f"Quelldaten {age:.0f} min alt"
        return "GRUEN", f"Quelldaten {age:.0f} min alt"
    except OSError:
        return "ROT", "Quelldatei fehlt"


def check_units():
    code, enabled = cmd("systemctl", "is-enabled", "berne-infoboard.service")
    code2, active = cmd("systemctl", "is-active", "berne-infoboard.service")
    _, show = cmd("systemctl", "show", "berne-infoboard.service", "-p", "Restart")
    display_ok = code == 0 and code2 == 0 and enabled == "enabled" and active == "active"
    display = ("GRUEN" if display_ok else "ROT",
               f"Autostart={enabled or '?'}, aktiv={active or '?'}, {show or 'Restart=?'}")
    missing = []
    for timer in TIMERS:
        t = timer + ".timer"
        _, en = cmd("systemctl", "is-enabled", t)
        _, ac = cmd("systemctl", "is-active", t)
        if en != "enabled" or ac != "active":
            missing.append(f"{t} ({en or '?'}/{ac or '?'})")
    timer_level = "GRUEN" if not missing else "ROT"
    timers = (timer_level,
              f"{len(TIMERS)-len(missing)}/{len(TIMERS)} erwarteten Timern aktiviert und aktiv"
              + (": " + "; ".join(missing) if missing else ""))
    failures = []
    for unit in SERVICES:
        _, out = cmd("systemctl", "show", unit + ".service", "-p", "Result", "-p", "ExecMainStatus")
        data = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        if data.get("Result") != "success" or data.get("ExecMainStatus") != "0":
            failures.append(unit + " (" + data.get("Result", "?") + "/"
                            + data.get("ExecMainStatus", "?") + ")")
    services = ("ROT" if failures else "GRUEN",
                "Letzte kritische Service-Laeufe: " +
                ("; ".join(failures) if failures else "alle erfolgreich"))
    return display, timers, services


def git_check(repo):
    if not (repo / ".git").is_dir():
        return "ROT", "Lokale Git-Arbeitskopie fehlt"
    status, branch = cmd("git", "-C", str(repo), "branch", "--show-current")
    code, dirty = cmd("git", "-C", str(repo), "status", "--porcelain")
    if status != 0 or code != 0 or branch != "main":
        return "ROT", "Git-Checkout/Branch ungueltig"
    if dirty:
        return "ROT", "Git-Arbeitskopie enthaelt Aenderungen; Sync stoppt aus Sicherheitsgruenden"
    code, counts = cmd("git", "-C", str(repo), "rev-list",
                       "--left-right", "--count", "origin/main...HEAD")
    if code != 0:
        return "GELB", "Kein lokaler Vergleich mit origin/main moeglich"
    try:
        behind, ahead = (int(value) for value in counts.split())
    except ValueError:
        return "GELB", "Git-Referenzvergleich unklar"
    if behind or ahead:
        return "GELB", f"Git-Referenz: {behind} zurueck, {ahead} voraus (nur lokaler Vergleich)"
    return "GRUEN", "Git-Arbeitskopie sauber, 0/0 gegen lokales origin/main"


def disk_check(path):
    try:
        du = shutil.disk_usage(path)
        used = 100 * (du.total - du.free) / du.total
        if used >= 95:
            return "ROT", f"Speicherbelegung {used:.0f} %"
        if used >= 85:
            return "GELB", f"Speicherbelegung {used:.0f} %"
        return "GRUEN", f"Speicherbelegung {used:.0f} %"
    except (OSError, ZeroDivisionError):
        return "GELB", "Speicherbelegung nicht ermittelbar"


def main():
    now = datetime.now(timezone.utc)
    print("tus BERNE | INFOBOARD-SYSTEMAMPEL")
    print(now.astimezone().strftime("%d.%m.%Y %H:%M:%S %Z"))
    print("-" * 55)
    display, timers, services = check_units()
    checks = [
        ("TV-Anzeige", display),
        ("Timer/Autostart", timers),
        ("Sync-Dienste", services),
        ("Google Drive", drive_check(APP / "portrait-content", now)),
        ("Mannschaften", file_check(APP / "cache/teams.json", 120, now)),
        ("Fussballtabellen", file_check(APP / "fussball-live/fussball_live_data.json", 35, now)),
        ("Kabinenbelegung", file_check(APP / "kabinen-live/kabinenplan_data.json", 35, now)),
        ("GitHub-Export", git_check(REPO)),
        ("Backups", backup_check(BACKUPS, now)),
        ("SD-Karte", disk_check("/")),
    ]
    worst = max((RANK[level] for _, (level, _) in checks), default=0)
    for label, (level, detail) in checks:
        print(f"[{level:5}] {label:19} {detail}")
    summary = ("Alles im geprueften Bereich OK" if worst == 0 else
               "Mindestens ein Punkt braucht Beachtung" if worst == 1 else
               "Mindestens ein Fehler erkannt")
    print("-" * 55)
    print(f"GESAMT: {('GRUEN', 'GELB', 'ROT')[worst]} - {summary}")
    print("Hinweis: GitHub-Remote und TV-Bild werden NICHT live geprueft.")
    print("Hinweis: Backup-Integritaet laut Backupstatus; kein Hardware-Restore-Test.")
    print("Rein lesende Diagnose abgeschlossen.")
    return worst


if __name__ == "__main__":
    sys.exit(main())
