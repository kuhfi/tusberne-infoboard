#!/usr/bin/env python3
"""tus BERNE: focused read-only diagnosis of the separate cabin plan producer.

Finds the real generator's output/write logic and viewer refresh behavior.
Never edits the source, viewer, services, or cabin plans. Uploads *selected*
non-secret code excerpts to the private diagnosis Drive folder only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

PRODUCER = Path("/home/kuhfi/infoboard-kabinen-live")
TV = Path("/home/kuhfi/infoboard-app")
REPO = Path("/home/kuhfi/tusberne-github-sync")
DEST_ID = "17nIUUe6LAJYWsbe-hH4cKrruXSBp0SBI"
DATE = datetime.now(ZoneInfo("Europe/Berlin"))
REPORT = "tusberne-tv-erzeuger-detail-" + DATE.strftime("%Y%m%d-%H%M%S") + ".txt"
SENSITIVE = re.compile(
    r"(?i)(password|passwd|secret|access[_ -]?token|refresh[_ -]?token|"
    r"authorization|bearer|client[_ -]?id|client[_ -]?secret|"
    r"private[_ -]?key|service[_ -]?account|credential|api[_ -]?key)"
)
URL = re.compile(r"https?://[^ \t'\"\]\)]+")
MATCH = re.compile(
    r"output|write_text|write_bytes|json\.dump|os\.replace|"
    r"os\.rename|\.replace\(|\.rename\(|mkstemp|tempfile|"
    r"atomic|destination|kabinenplan_data|generate|save|"
    r"extra_source|cache|guest_count|guest_cabin|sr_cabin|"
    r"warnings|critical_conflicts|lock|config|main\(",
    re.I,
)
STRONG = re.compile(
    r"output|write_text|write_bytes|json\.dump|os\.replace|"
    r"os\.rename|\.replace\(|\.rename\(|mkstemp|tempfile|"
    r"atomic|destination|kabinenplan_data",
    re.I,
)
parts: list[str] = []


def safe(line: str) -> str:
    line = str(line).rstrip()[:500]
    if SENSITIVE.search(line):
        return "[mögliche Zugangs-/Kontoinformationen nicht übertragen]"
    return URL.sub("[externe URL]", line)


def run(args: list[str], timeout: int = 12) -> str:
    try:
        p = subprocess.run(args, text=True, errors="replace",
                           capture_output=True, timeout=timeout, check=False)
        return "rc=" + str(p.returncode) + "\n" + p.stdout[:50000]
    except (OSError, subprocess.TimeoutExpired) as e:
        return type(e).__name__


def section(name: str, body: str) -> None:
    parts.append("\n=== " + name + " ===\n" + body.strip() + "\n")


def limited_file_code(path: Path, *, complete: bool = False) -> str:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 420_000:
            return "Nicht vorhanden / Symlink / zu groß"
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return "Lesefehler: " + type(e).__name__
    selected: set[int] = set()
    hits = [i for i, line in enumerate(content) if MATCH.search(line)]
    for i in hits:
        radius = 3 if not complete else 5
        selected.update(range(max(0, i-radius), min(len(content), i+radius+1)))
    # include complete small operational files when possible
    if complete and len(content) < 190:
        selected.update(range(len(content)))
    # Only show a maximum number of actual lines
    indices = sorted(selected)[:550 if complete else 380]
    lines = [f"{i+1:4d}: " + safe(content[i]) for i in indices]
    return (f"Zeilen: {len(content)}; Treffer: {len(hits)}; "
            f"Auszug: {len(indices)}\n" + "\n".join(lines))


def units() -> None:
    cmd = ["systemctl", "cat", "berne-kabinen-live.service"]
    output = run(cmd)
    section("Kabinen-Erzeuger-Unit (nur sichere Zeilen)", "\n".join(
        safe(line) for line in output.splitlines() if
        not line.startswith("Environment") and
        not line.startswith("SetCredential")))
    output = run(["systemctl", "show", "berne-kabinen-live.service",
                  "--property=ExecStart,ExecStartPost,WorkingDirectory,ActiveState,SubState,Result"])
    section("Erzeuger Unit Details", "\n".join(safe(line) for line in output.splitlines()))
    output = run(["systemctl", "cat", "berne-kabinen-live.timer"])
    section("Erzeuger Timer", "\n".join(safe(line) for line in output.splitlines()))
    code = run(["journalctl", "-u", "berne-kabinen-live.service",
                "-n", "20", "-o", "short-iso", "--no-pager"])
    section("Letzte Produzentenläufe (ohne sensible Zeilen)", "\n".join(
        safe(s) for s in code.splitlines() if not SENSITIVE.search(s)))


def producer_listing_and_code() -> None:
    if not PRODUCER.is_dir():
        section("Produzent", "PRODUCER-Verzeichnis fehlt")
        return
    entries = []
    for p in sorted(PRODUCER.rglob("*")):
        if any(part.startswith(".") for part in p.relative_to(PRODUCER).parts):
            continue
        if any(part in ("backups","backup","logs","__pycache__","node_modules") for part in p.parts):
            continue
        if p.is_file() and p.suffix in (".py", ".sh", ".json", ".service", ".timer"):
            if len(entries) >= 130:
                break
            entries.append(str(p.relative_to(PRODUCER)) +
                           (" [JSON nur Metadaten]" if p.suffix == ".json" else ""))
    section("Erzeuger-Verzeichnis: mögliche Programmdateien", "\n".join(entries))
    found = 0
    for p in sorted(PRODUCER.rglob("*.py")):
        if any(part.startswith(".") or part in ("backups","backup","logs","__pycache__")
               for part in p.relative_to(PRODUCER).parts):
            continue
        if found >= 18:
            break
        try:
            if p.stat().st_size > 420_000:
                continue
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not STRONG.search(content):
            continue
        found += 1
        section("Erzeuger-Quellcode " + str(p.relative_to(PRODUCER)),
                limited_file_code(p, complete=True)[:34000])
    for p in sorted(PRODUCER.rglob("*.json")):
        if any(part.startswith(".") for part in p.relative_to(PRODUCER).parts):
            continue
        if "backup" in str(p).lower():
            continue
        if len(parts) > 30:
            break
        if p.stat().st_size > 1_000_000 or p.is_symlink():
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(obj, dict):
            # Report ONLY JSON keys, never private config contents.
            section("Konfigurations-Schlüsselnamen " + str(p.relative_to(PRODUCER)),
                    ", ".join(sorted(obj))[:500])


def consumers() -> None:
    for rel in ("kiosk.sh", "public/portrait/cycle.js",
                "scripts/anzeigezeiten/core.py",
                "public/kabinen-live/01_kabinen_live.html",
                "public/portrait/kabinen.html"):
        p = TV / rel
        if not p.is_file() or p.is_symlink():
            continue
        content = p.read_text(encoding="utf-8", errors="replace").splitlines()
        if rel.endswith("cycle.js"):
            sample = [
                (i+1, s) for i,s in enumerate(content)
                if re.search("fetch|changed|stamp|hash|adopt|draw|cache|cycle|reload", s, re.I)
            ]
            selected = set()
            for i,_ in sample[:90]:
                selected.update(range(max(0,i-3), min(len(content), i+3)))
        elif rel.endswith("core.py") or rel=="kiosk.sh":
            selected = set(range(min(len(content),145)))
        else:
            selected = {i for i,s in enumerate(content) if
                        re.search(r"kabinenplan_data|async function loadData|stampKey|berneCycle|"
                                  r"guest_count|manual_override|g\.warnings|Zusatztermine",s)}
            around = set()
            for i in selected:
                around.update(range(max(0,i-3),min(len(content),i+4)))
            selected = around
        section("TV-Verbraucher " + rel, "\n".join(
            f"{i+1:4d}: {safe(content[i])}" for i in sorted(selected)[:220]))
    for p in (TV / "public/kabinen-live/kabinenplan_data.json",
              TV / "public/portrait/kabinen.html",
              TV / "public/kabinen-live/01_kabinen_live.html",
              TV / "public/app.js",TV / "public/portrait/portrait.js"):
        if p.exists() and p.is_file():
            section("Schutz-Fingerabdruck " + str(p.relative_to(TV)),
                    "bytes=" + str(p.stat().st_size) +
                    "\nsha256=" + hashlib.sha256(p.read_bytes()).hexdigest() +
                    "\nmtime="+datetime.fromtimestamp(p.stat().st_mtime,ZoneInfo("Europe/Berlin")).isoformat())


def main() -> int:
    section("Titel", "tus BERNE - Erzeuger-Detaildiagnose - LESEND\n" +
            DATE.isoformat() + "\nNur privater Ergebnisbericht im bekannten Google Drive")
    units()
    producer_listing_and_code()
    consumers()
    result = "\n".join(parts)
    if len(result.encode("utf-8")) > 170000:
        result = result[:145000] + "\n[Bericht begrenzt]\n"
    out = Path(tempfile.gettempdir()) / REPORT
    out.write_text(result, encoding="utf-8")
    print("Erzeuger-Detaildiagnose erstellt:", REPORT)
    cmd = ["rclone","copyto",str(out),"gdrive:"+REPORT,
           "--drive-root-folder-id",DEST_ID]
    try:
        p = subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           timeout=120,check=False)
        if p.returncode != 0:
            print("Drive-Upload fehlgeschlagen; Bericht lokal unter", out)
            return 1
    except (OSError,subprocess.TimeoutExpired):
        print("Drive-Upload fehlgeschlagen; Bericht lokal unter", out)
        return 1
    print("OK: privater Drive-Bericht hochgeladen.")
    print("Keine lokale Quelldatei/Service/Timer verändert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
