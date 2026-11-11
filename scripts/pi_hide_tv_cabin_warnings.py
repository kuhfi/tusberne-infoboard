#!/usr/bin/env python3
"""Remove only TV per-game warning text, keep diagnostic JSON and conflict checking.

The patch is explicitly pinned to the HTML observed on 2026-11-11.
Backup first, atomic write, idempotent, attempt a kiosk browser refresh, log to private Drive.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

TARGET = Path("/home/kuhfi/infoboard-app/public/portrait/kabinen.html")
FRAGMENT = """${g.warnings?.length?`<br>⚠ ${esc(g.warnings.join(' · '))}`:''}"""
CUE = """${esc([...new Set([g.kind,g.league].filter(Boolean).map(x=>String(x).trim()))].join(' · '))}"""
DRIVE_FOLDER = "17nIUUe6LAJYWsbe-hH4cKrruXSBp0SBI"
REPORT_NAME = "tusberne-tv-warntext-entfernung-20261111.txt"


def refresh_kiosk():
    """Best-effort keyboard refresh only when local graphical kiosk is detected."""
    try:
        procs = subprocess.run(
            ["pgrep", "-a", "-u", str(os.getuid()), "-f", "chromium|chrome"],
            capture_output=True, text=True, timeout=5)
        if procs.returncode != 0:
            return "Kein Chromium-Prozess unter diesem Benutzer erkannt; Browser-Reload nicht gesendet."
    except (OSError, subprocess.TimeoutExpired):
        return "Chromium-Status konnte nicht geprüft werden."

    uid = os.getuid()
    runtime = Path(f"/run/user/{uid}")
    if shutil.which("wtype") and runtime.exists():
        for socket in sorted(runtime.glob("wayland-*")):
            if not socket.is_socket():
                continue
            env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY=socket.name)
            try:
                r = subprocess.run(
                    ["wtype", "-M", "ctrl", "-k", "r", "-m", "ctrl"],
                    env=env, capture_output=True, text=True, timeout=8)
                if r.returncode == 0:
                    return f"Ctrl+R an Wayland-Kiosk gesendet ({socket.name}); sichtbares Ergebnis nicht ferngeprüft."
            except (OSError, subprocess.TimeoutExpired):
                pass

    if shutil.which("xdotool") and Path("/tmp/.X11-unix/X0").exists():
        env = dict(os.environ, DISPLAY=":0")
        xauth = Path.home() / ".Xauthority"
        if xauth.is_file():
            env["XAUTHORITY"] = str(xauth)
        try:
            r = subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "ctrl+r"],
                env=env, capture_output=True, text=True, timeout=8)
            if r.returncode == 0:
                return "Ctrl+R an X11-Kiosk gesendet; sichtbares Ergebnis nicht ferngeprüft."
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "Browser-Neuladen nicht automatisch möglich; HTML-Korrektur wird bei nächstem Reload sichtbar."


def upload_report(body):
    if not shutil.which("rclone"):
        return "rclone nicht verfügbar: kein Drive-Bericht"
    with tempfile.TemporaryDirectory(prefix="tusberne-tv-patch-log-") as temp:
        report = Path(temp) / REPORT_NAME
        report.write_text(body, encoding="utf-8")
        try:
            p = subprocess.run(
                ["rclone", "copyto", str(report), "gdrive:" + REPORT_NAME,
                 "--drive-root-folder-id", DRIVE_FOLDER],
                capture_output=True, timeout=90)
            return "Drive-Bericht hochgeladen" if p.returncode == 0 else f"Drive-Upload fehlgeschlagen (Code {p.returncode})"
        except (OSError, subprocess.TimeoutExpired):
            return "Drive-Upload konnte nicht ausgeführt werden"


def main():
    if not TARGET.is_file() or TARGET.is_symlink():
        raise RuntimeError("Ziel-HTML fehlt oder ist ein symbolischer Link")
    raw = TARGET.read_text(encoding="utf-8")
    if len(raw) > 500_000:
        raise RuntimeError("Unerwartet große HTML-Datei")
    if CUE not in raw:
        raise RuntimeError("Spielinfo-Renderer weicht von geprüfter Version ab")
    matches = raw.count(FRAGMENT)
    if matches == 0:
        if "g.warnings?.length" in raw:
            raise RuntimeError("Warntext-Renderer wurde geändert; kein unsicherer Patch")
        status = "Warntext bereits aus dem Spielrenderer entfernt (keine neue Dateiänderung)."
        backup = "Keine neue Sicherung erforderlich"
    elif matches != 1:
        raise RuntimeError(f"Warntext-Muster {matches} Mal gefunden statt genau einmal")
    else:
        revised = raw.replace(FRAGMENT, "")
        if revised.count(CUE) != raw.count(CUE) or FRAGMENT in revised or len(revised) >= len(raw):
            raise RuntimeError("Sicherheitsprüfung des HTML-Patches fehlgeschlagen")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = TARGET.with_name(TARGET.name + ".bak-hide-warning-" + stamp)
        shutil.copy2(TARGET, backup_path)
        backup = str(backup_path)
        fd, tmp = tempfile.mkstemp(prefix=".kabinen-warning-", dir=TARGET.parent)
        try:
            os.fchmod(fd, TARGET.stat().st_mode & 0o777)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(revised)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, TARGET)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        if FRAGMENT in TARGET.read_text(encoding="utf-8"):
            raise RuntimeError("Nachprüfung fehlgeschlagen")
        status = "OK: Nur Warnzeile im Spielrenderer entfernt; JSON und Konfliktdaten unverändert."

    reload_result = refresh_kiosk()
    report = "\n".join([
        "tus BERNE - TV-Kabinen-Warntexte",
        datetime.datetime.now().astimezone().isoformat(),
        "Datei: " + str(TARGET),
        "Status: " + status,
        "Sicherung: " + backup,
        "Neuladen: " + reload_result,
        "Google-Kabinenverwaltung: unverändert",
        "Konfliktberechnung und JSON: unverändert",
        "",
    ])
    print(report)
    print(upload_report(report))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("STOPP: TV-Korrektur nicht vollständig: " + str(exc), file=sys.stderr)
        sys.exit(1)
