#!/usr/bin/env python3
"""Remove the TV weekbar's cache/planning hint only, with a private backup and report.

Never changes fixture JSON, conflict detection, cabin assignments or Google integration.
Pinned to the actual renderer inspected from the private 2026-11-11 diagnostic.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile

TARGET = Path("/home/kuhfi/infoboard-app/public/portrait/kabinen.html")
DATA = Path("/home/kuhfi/infoboard-app/public/kabinen-live/kabinenplan_data.json")
BACKUP_DIR = Path("/home/kuhfi/infoboard-app/backups/tv-cabins-status")
DRIVE_FOLDER = "17nIUUe6LAJYWsbe-hH4cKrruXSBp0SBI"
REPORT_NAME = "tusberne-tv-zusatztermine-hinweis-entfernung-20261111.txt"

# The exact JS interpolation in BOTH weekbar variants (empty / nonempty).
STATUS = "${data.extra_source?.mode==='cache'?' · ⚠ Zusatztermine: älterer Stand':(data.warnings?.length?' · ⚠ Planung prüfen':'')}"
WEEKBAR = "WOCHE ${page+1}/${weeks.length}"


def refresh_kiosk():
    # Previous 2026-11-11 patch successfully sent Ctrl+R via Wayland wtype.
    try:
        procs = subprocess.run(
            ["pgrep", "-a", "-u", str(os.getuid()), "-f", "chromium|chrome"],
            capture_output=True, text=True, timeout=5)
        if procs.returncode != 0:
            return "Kein lokaler Chromium-Prozess gefunden; Reload nicht gesendet."
    except (OSError, subprocess.TimeoutExpired):
        return "Chromium-Status nicht prüfbar."
    uid = os.getuid()
    runtime = Path(f"/run/user/{uid}")
    if shutil.which("wtype") and runtime.exists():
        for wayland in sorted(runtime.glob("wayland-*")):
            if not wayland.is_socket():
                continue
            env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY=wayland.name)
            try:
                cmd = ["wtype", "-M", "ctrl", "-k", "r", "-m", "ctrl"]
                r = subprocess.run(cmd, env=env, capture_output=True, timeout=8)
                if r.returncode == 0:
                    return f"Ctrl+R an Wayland-Kiosk gesendet ({wayland.name}); Bildschirm nicht visuell verifiziert."
            except (OSError, subprocess.TimeoutExpired):
                pass
    return "HTML geändert, aber automatisches Browser-Neuladen nicht möglich."


def report_to_drive(message):
    with tempfile.TemporaryDirectory(prefix="tusberne-tv-hint-") as temp:
        local = Path(temp) / REPORT_NAME
        local.write_text(message, encoding="utf-8")
        try:
            result = subprocess.run(
                ["rclone", "copyto", str(local), "gdrive:" + REPORT_NAME,
                 "--drive-root-folder-id", DRIVE_FOLDER],
                capture_output=True, timeout=90)
            if result.returncode != 0:
                return f"Bericht nicht hochgeladen (rclone Code {result.returncode})"
            return "Bericht in Drive: Entwicklung & Diagnose gespeichert."
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"Bericht-Upload fehlgeschlagen ({type(exc).__name__})"


def main():
    if not TARGET.is_file() or TARGET.is_symlink():
        raise RuntimeError("TV-HTML ist nicht als reguläre Datei vorhanden")
    original = TARGET.read_text(encoding="utf-8")
    if len(original) > 500_000:
        raise RuntimeError("HTML ungewöhnlich groß")
    count = original.count(STATUS)
    if count == 0 and "Zusatztermine: älterer Stand" not in original and "Planung prüfen" not in original:
        update = "Bereits entfernt; keine Dateiänderung."
        backup = "Nicht erforderlich."
    elif count != 2 or original.count(WEEKBAR + STATUS) != 2:
        raise RuntimeError(f"Unbekannte Woche-Anzeige: Textmuster {count} Mal statt exakt zweimal")
    else:
        updated = original.replace(WEEKBAR + STATUS, WEEKBAR)
        if (updated.count(WEEKBAR) != original.count(WEEKBAR)
                or "Zusatztermine: älterer Stand" in updated
                or "Planung prüfen" in updated):
            raise RuntimeError("Nachprüfung der geplanten Änderung fehlgeschlagen")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        BACKUP_DIR.chmod(0o700)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_file = BACKUP_DIR / f"kabinen.html.before-hint-{stamp}.bak"
        shutil.copy2(TARGET, backup_file)
        backup_file.chmod(0o600)
        backup = str(backup_file)
        fd, tmp = tempfile.mkstemp(prefix=".tv-hint-", dir=TARGET.parent)
        try:
            os.fchmod(fd, TARGET.stat().st_mode & 0o777)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(updated)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, TARGET)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        if TARGET.read_text(encoding="utf-8") != updated:
            raise RuntimeError("Geschriebene HTML-Datei stimmt nicht mit Zielzustand überein")
        update = "OK: Nur die Statuswarnung in beiden Wochenbalken entfernt."

    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
        extra = data.get("extra_source", {})
        mode = extra.get("mode", "unbekannt") if isinstance(extra, dict) else "unbekannt"
        generated = str(data.get("generated_at", "unbekannt"))
    except (OSError, ValueError, TypeError):
        mode, generated = "nicht prüfbar", "nicht prüfbar"
    reload_result = refresh_kiosk()
    output = "\n".join([
        "tus BERNE – TV-Zusatztermine-Hinweis entfernen",
        "Zeitpunkt: " + datetime.now().astimezone().isoformat(),
        "Status: " + update,
        "Datei: " + str(TARGET),
        "Sicherung: " + backup,
        "Neuladen: " + reload_result,
        "TV-Zusatzquelle Modus: " + str(mode),
        "TV-Quelldaten erstellt: " + generated,
        "Konfliktberechnung/TV-JSON/Google-Sync: unverändert.",
        "Prüfung der Aktualität der Zusatztermine: noch offen.",
        "",
    ])
    print(output)
    print(report_to_drive(output))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("STOPP: " + str(exc), file=sys.stderr)
        sys.exit(1)
