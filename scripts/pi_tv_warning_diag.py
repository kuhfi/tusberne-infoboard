#!/usr/bin/env python3
"""Read-only Pi TV-warning diagnostic; uploads selected display-code snippets to a private Drive folder."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile

ROOT = Path("/home/kuhfi/infoboard-app")
DRIVE_FOLDER_ID = "17nIUUe6LAJYWsbe-hH4cKrruXSBp0SBI"
OUT_NAME = "tusberne-tv-warntexte-diagnose-20261111.txt"
MATCH = re.compile(
    r"warn|konflikt|conflict|gastgruppen|conflictfree|notice|hint|critical|"
    r"issue|problem|warning|problem|note|reason|status|error|cabin",
    re.IGNORECASE,
)


def formatted_lines(lines: list[str], indexes: set[int], limit: int = 18000) -> str:
    result = []
    for i in sorted(indexes):
        if 0 <= i < len(lines):
            text = lines[i]
            if len(text) > limit:
                text = text[:limit] + " [...] (Zeile gekürzt)"
            result.append(f"{i + 1:4}: {text}")
    return "\n".join(result)


def selected_file(relative: str, mandatory: tuple[int, int] | None = None, radius: int = 7) -> str:
    path = ROOT / relative
    if not path.is_file() or path.is_symlink():
        return f"=== {relative}: fehlt/kein reguläres File ===\n"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    interesting = set()
    if mandatory:
        a, b = mandatory
        interesting.update(range(a - 1, min(b, len(lines))))
    matching = []
    for i, line in enumerate(lines):
        if MATCH.search(line):
            matching.append(i)
            interesting.update(range(max(0, i - radius), min(len(lines), i + radius + 1)))
    return (
        f"=== {relative} ({len(lines)} Zeilen, "
        f"{len(matching)} relevante Zeilen) ===\n"
        + formatted_lines(lines, interesting) + "\n"
    )


def sample_games() -> str:
    path = ROOT / "public/kabinen-live/kabinenplan_data.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    result = ["=== Datenstruktur (nur Feldnamen/Warnungen) ==="]
    result.append("Top-Level-Felder: " + ", ".join(sorted(data)))
    for game in data.get("games", []):
        if game.get("date") == "2026-11-15" and game.get("time") in ("13:00", "13:22", "13:44"):
            result.append(f"Spiel: {game.get('date')} {game.get('time')} {game.get('home')} – {game.get('away')}")
            result.append("Felder: " + ", ".join(sorted(game)))
            for key, val in game.items():
                if MATCH.search(key) and key not in ("home_cabin", "guest_cabin", "sr_cabin"):
                    result.append(f"  {key}: {str(val)[:2500]}")
    return "\n".join(result) + "\n"


def main() -> int:
    parts = [
        "TV-Warntext Diagnose - tus BERNE",
        "Zeitpunkt: " + datetime.now().astimezone().isoformat(),
        "Nur Anzeige-Code und ausgewählte Warnfelder; keine Token/Passwörter.",
        "",
        selected_file("public/app.js", (470, 640)),
        selected_file("public/portrait/kabinen.html", (435, 545)),
        selected_file("public/kabinen-live/01_kabinen_live.html", (1, 220)),
        selected_file("public/portrait/portrait.js", (1, 50)),
        sample_games(),
    ]
    body = "\n".join(parts)
    if len(body.encode("utf-8")) > 380_000:
        raise ValueError("Diagnosedaten zu umfangreich")
    with tempfile.TemporaryDirectory(prefix="tusberne-tvdiag-") as temporary:
        source = Path(temporary) / OUT_NAME
        source.write_text(body, encoding="utf-8")
        command = [
            "rclone", "copyto", str(source), "gdrive:" + OUT_NAME,
            "--drive-root-folder-id", DRIVE_FOLDER_ID,
        ]
        subprocess.run(command, check=True, timeout=120)
        print("OK: Diagnose in Google Drive / Entwicklung & Diagnose hochgeladen.")
        print("Dateiname:", OUT_NAME)
        print("Größe:", len(body.encode("utf-8")), "Bytes")
    print("Keine TV-Dateien, Dienste oder Kabinenzuweisungen verändert.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("STOPP: Diagnose-Upload fehlgeschlagen:", type(exc).__name__, str(exc)[:350], file=sys.stderr)
        sys.exit(1)
