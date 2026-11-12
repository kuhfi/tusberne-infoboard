#!/usr/bin/env python3
"""tus BERNE: read-only discovery of the LOCAL TV cabin-data producer.

No application files, services, timers, Google sheets, or cabin assignments are
modified. A carefully limited report is uploaded only to the known PRIVATE
Google Drive folder "Entwicklung & Diagnose" using the Pi's existing rclone.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

TV_ROOT = Path("/home/kuhfi/infoboard-app")
GH_ROOT = Path("/home/kuhfi/tusberne-github-sync")
TV_SOURCE = TV_ROOT / "public/kabinen-live/kabinenplan_data.json"
OVERRIDES = Path("/var/lib/tusberne-kabinen/overrides.json")
DRIVE_FOLDER_ID = "17nIUUe6LAJYWsbe-hH4cKrruXSBp0SBI"
NOW = datetime.now(ZoneInfo("Europe/Berlin"))
REPORT_NAME = "tusberne-tv-datenproduzent-diagnose-" + NOW.strftime("%Y%m%d-%H%M%S") + ".txt"

SIGNATURE = re.compile(
    r"kabinenplan_data\.json|kabinen-live|cabins?_.*export|"
    r"cabins?_.*sync|anzeigezeiten|kabinenplan|kabinen.*live|"
    r"cabins.*override|effective_plan",
    re.IGNORECASE,
)
WRITER = re.compile(
    r"write_text|write_bytes|json\.dump|os\.replace|\.replace\(|"
    r"\brename\(|mkstemp|NamedTemporaryFile|atomic|\.write\(|copyfile|copy2|"
    r"shutil\.move|install\s+.*json",
    re.IGNORECASE,
)
RELEVANT_UNIT = re.compile(
    r"berne|infoboard|kabinen|cabins|fussball|anzeigezeiten|github",
    re.IGNORECASE,
)
SENSITIVE = re.compile(
    r"password|passwd|secret|oauth|authorization|bearer|"
    r"access.token|refresh.token|private.key|client.secret|"
    r"credential|api.key|api_key|(^|[^a-z])token([^a-z]|$)",
    re.IGNORECASE,
)
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", "backups", "backup", "archive", "archives", "logs",
}
SCAN_EXTS = {".py", ".sh", ".service", ".timer", ".path", ".js", ".html",
             ".conf", ".ini", ".bash", ".desktop", ".yml", ".yaml"}
MAX_REPORT = 180_000
sections: list[str] = []


def add(title: str, body: str) -> None:
    sections.append("\n=== " + title + " ===\n" + body.rstrip() + "\n")


def safe_line(value: str, limit: int = 280) -> str:
    value = str(value).replace("\0", " ").strip()
    if SENSITIVE.search(value):
        return "[Zeile mit möglichen Zugangsdaten ausgelassen]"
    value = re.sub(r"https?://[^\s'\"]+", "[URL entfernt]", value)
    value = re.sub(r"(?:[A-Za-z0-9_+/-]{40,}={0,2})", "[lange Zeichenfolge entfernt]", value)
    value = re.sub(r"(?i)(?:--?(?:password|token|secret|key))(?:=|\s+)\S+",
                   "[Zugangsdaten entfernt]", value)
    return value[:limit] + (" [gekürzt]" if len(value) > limit else "")


def command(args: list[str], timeout: int = 12) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, errors="replace",
            timeout=timeout, check=False)
        return proc.returncode, proc.stdout[:150_000]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, type(exc).__name__


def json_info(path: Path, *, is_private: bool = False) -> str:
    if not path.exists() or path.is_symlink():
        return "Datei fehlt oder ist Symlink (nicht gelesen)"
    try:
        data_bytes = path.read_bytes()
        obj = json.loads(data_bytes)
        st = path.stat()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return "Lesefehler: " + type(exc).__name__
    if not isinstance(obj, dict):
        return "JSON-Wurzel nicht Objekt"
    lines = [
        "Pfad: " + str(path),
        "Größe: " + str(len(data_bytes)) + " Bytes",
        "Datei-mtime: " + datetime.fromtimestamp(st.st_mtime, ZoneInfo("Europe/Berlin")).isoformat(),
        "SHA256 (nur verkürzter Fingerabdruck): " + hashlib.sha256(data_bytes).hexdigest()[:16],
        "Top-Level-Schlüssel: " + ", ".join(sorted(obj)),
    ]
    if is_private:
        weeks = obj.get("weeks", {})
        revs = obj.get("google_cabins_sync", {}).get("revisions", {})
        if isinstance(weeks, dict):
            lines.append("Wochenmodi: " + repr({
                k: (v.get("mode") if isinstance(v, dict) else "ungueltig")
                for k, v in weeks.items()
            }))
        if isinstance(revs, dict):
            lines.append("Import-Revisionen: " + repr({
                k: v for k, v in revs.items() if isinstance(v, (str, int))
            }))
        lines.append("KEINE privaten Korrekturwerte / Spiele-IDs ausgegeben")
    else:
        games = obj.get("games", [])
        period = obj.get("period", {})
        extras = obj.get("extra_source", {})
        lines.extend([
            "Spieleanzahl: " + str(len(games) if isinstance(games, list) else "ungueltig"),
            "Spiele-Feldnamen (erstes Spiel): " +
            (", ".join(sorted(games[0])) if isinstance(games, list) and games and isinstance(games[0], dict) else "-"),
            "Zeitraum: " + repr(period.get("weeks", []) if isinstance(period, dict) else "ungueltig")[:350],
            "generated_at: " + str(obj.get("generated_at")),
            "extra_source.mode: " + str(extras.get("mode") if isinstance(extras, dict) else None),
            "extra_source Feldnamen: " + (", ".join(sorted(extras)) if isinstance(extras, dict) else "-"),
            "extra_source relevante Zeitangaben: " + repr({
                k: v for k, v in extras.items()
                if isinstance(v, str) and re.search(r"at$|time|date|stamp|updated|fetch|sync", k, re.I)
                and len(v) < 90
            })[:400] if isinstance(extras, dict) else "extra_source nicht lesbar",
            "Quellstatistik-Feldnamen: " +
            (", ".join(sorted(obj["source_stats"])) if isinstance(obj.get("source_stats"), dict) else "-"),
            "Warnungen (Anzahl): " + str(len(obj["warnings"]) if isinstance(obj.get("warnings"), list) else "?"),
            "Kritische Konflikte: " + str(obj.get("critical_conflicts", "?")),
        ])
    return "\n".join(lines)


def units() -> None:
    rows = []
    for cmd in (
        ["systemctl", "list-units", "--all", "--type=service", "--type=timer",
         "--type=path", "--no-legend", "--no-pager"],
        ["systemctl", "list-unit-files", "--no-legend", "--no-pager"],
        ["systemctl", "list-timers", "--all", "--no-legend", "--no-pager"],
    ):
        code, output = command(cmd)
        relevant = [safe_line(line) for line in output.splitlines()
                    if RELEVANT_UNIT.search(line)]
        rows.append("$ " + " ".join(cmd) + " (rc=" + str(code) + ")")
        rows.extend(relevant[:75])
    add("systemd Liste/Timer (nur passende Zeilen)", "\n".join(rows))
    candidates = set()
    for line in "\n".join(rows).splitlines():
        candidates.update(re.findall(
            r"\b[\w@.-]+\.(?:service|timer|path)\b", line))
    candidates.update({
        "berne-infoboard.service", "berne-cabins-google-sync.service",
        "berne-cabins-google-sync.timer", "berne-github-public-sync.service",
        "berne-github-public-sync.timer",
    })
    details = []
    for name in sorted(candidates)[:55]:
        if not RELEVANT_UNIT.search(name):
            continue
        code, output = command([
            "systemctl", "show", name, "--no-pager",
            "--property=ActiveState,SubState,FragmentPath,WorkingDirectory,ExecStart,MainPID,NextElapseUSecRealtime"
        ], timeout=8)
        details.append(name + " (rc=" + str(code) + ")")
        details.extend(safe_line(line, 450) for line in output.splitlines()
                       if not line.startswith("ExecStartEx="))
    add("systemd Unit Details (ohne Environment/Secrets)", "\n".join(details))


def scripts() -> None:
    matches = []
    processed = 0
    skips = 0
    for root in (TV_ROOT, GH_ROOT):
        if not root.is_dir():
            matches.append("FEHLT: " + str(root))
            continue
        for base, dirs, filenames in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                if processed >= 3500:
                    break
                path = Path(base) / name
                if path.suffix.lower() not in SCAN_EXTS or path.is_symlink():
                    continue
                try:
                    if path.stat().st_size > 360_000:
                        skips += 1
                        continue
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    skips += 1
                    continue
                processed += 1
                signal = [i for i, l in enumerate(lines) if SIGNATURE.search(l)]
                if not signal:
                    continue
                writer = [i for i, l in enumerate(lines) if WRITER.search(l)]
                key_lines = sorted(set(signal + [
                    j for j in writer if any(abs(j-i) <= 36 for i in signal)
                ]))[:55]
                matches.append("DATEI: " + str(path) +
                               " | Signatur-Treffer=" + str(len(signal)) +
                               " | Schreib-Treffer=" + str(len(writer)))
                for idx in key_lines:
                    marks = ("PRODUZENT?" if idx in writer else "VERWEIS")
                    matches.append("  " + str(idx+1) + " " + marks + " " +
                                   safe_line(lines[idx], 300))
                if len(matches) > 1100:
                    matches.append("HINWEIS: Maximalumfang erreicht")
                    break
            if len(matches) > 1100 or processed >= 3500:
                break
    add("Quellcode-Fundstellen / möglicher Schreiber", "\n".join(
        ["Untersuchte Quelldateien: " + str(processed),
         "Übersprungene Dateien: " + str(skips)] + matches)[:110_000])


def service_files_and_cron() -> None:
    lines = []
    for root in (Path("/etc/systemd/system"), Path("/lib/systemd/system"),
                 Path("/usr/lib/systemd/system"), Path("/etc/cron.d"),
                 Path("/etc/cron.hourly"), Path("/etc/cron.daily")):
        if not root.is_dir():
            continue
        checked = 0
        for path in root.rglob("*"):
            if checked > 2000:
                break
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 150_000:
                continue
            checked += 1
            try:
                content = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            hits = [(i, v) for i, v in enumerate(content)
                    if SIGNATURE.search(v) or
                    (RELEVANT_UNIT.search(path.name) and re.search(
                        r"^(ExecStart|ExecStartPre|OnCalendar|OnUnitActiveSec|"
                        r"OnUnitInactiveSec|PathChanged|PathModified|"
                        r"WorkingDirectory)=", v))]
            if hits:
                lines.append("DATEI: " + str(path))
                lines.extend("  " + str(i+1) + ": " + safe_line(v)
                             for i, v in hits[:35])
    rc, out = command(["crontab", "-l"])
    lines.append("Benutzer-crontab (rc=" + str(rc) +
                 ", nur relevante Zeilen; keine Umgebungswerte)")
    lines.extend(safe_line(s) for s in out.splitlines()
                 if RELEVANT_UNIT.search(s) or SIGNATURE.search(s))
    add("systemd-Dateien / Cron (selektiv)", "\n".join(lines)[:45_000])


def tv_viewer_and_renderers() -> None:
    findings = []
    rc, output = command(["ps", "-eo", "pid=,comm=,args="])
    findings.append("Prozessliste (rc=" + str(rc) + "; nur plausible TV/Produzent-Prozesse):")
    for line in output.splitlines():
        if re.search(r"chromium|chrome|wayfire|cage|wpe|weston|"
                     r"infoboard|kabinen|anzeigezeiten|pi_.*sync|"
                     r"fussball.*live", line, re.I):
            findings.append(safe_line(line, 450))
            if len(findings) > 48:
                break
    files = (
        "server.py", "public/app.js", "public/portrait/portrait.js",
        "public/portrait/kabinen.html",
        "public/kabinen-live/01_kabinen_live.html",
        "scripts/anzeigezeiten/core.py",
        "public/portrait/cycle.js",
    )
    for filename in files:
        path = TV_ROOT / filename
        if not path.is_file() or path.is_symlink():
            findings.append(filename + ": fehlt")
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        selected = [(i+1, line) for i, line in enumerate(content.splitlines())
                    if re.search(r"kabinenplan_data\.json|cabinsLiveSource|"
                                 r"KABINEN_LIVE_V|berneCycle\(|"
                                 r"g\.warnings\?\.length|Zusatztermine: älterer Stand|"
                                 r"Planung prüfen", line, re.I)]
        findings.append(filename + ": " + str(len(selected)) + " relevante Stellen")
        findings.extend("  " + str(i) + ": " + safe_line(line, 350)
                        for i, line in selected[:22])
    path = TV_ROOT / "public/portrait/kabinen.html"
    if path.is_file():
        code = path.read_text(encoding="utf-8", errors="replace")
        findings.append("Portrait: alte Spiel-Warnzeile vorhanden = " +
                        str("g.warnings?.length" in code))
        findings.append("Portrait: alter Wochenbalken-Hinweis vorhanden = " +
                        str("Zusatztermine: älterer Stand" in code or
                            "Planung prüfen" in code))
    add("Tatsächlicher Kiosk / lokale JSON-Verbraucher", "\n".join(findings))


def journal_sample() -> None:
    names = (
        "berne-infoboard.service", "berne-cabins-google-sync.service",
        "berne-github-public-sync.service",
    )
    result = []
    for name in names:
        rc, output = command(["journalctl", "-u", name, "-n", "35",
                              "--no-pager", "-o", "short-iso"], timeout=8)
        result.append(name + " (rc=" + str(rc) + ")")
        filtered = [safe_line(s, 400) for s in output.splitlines()
                    if re.search(r"kabinen|cabins|json|anzeige|fussball|"
                                 r"sync|error|warn|failed|start|finish",
                                 s, re.I)]
        result.extend(filtered[-18:])
    add("Journal-Auszug (selektiv, geschwärzt)", "\n".join(result))


def main() -> int:
    add("Überblick", "\n".join([
        "tus BERNE - lokale TV-Datenproduzent-Diagnose",
        "Zeitpunkt: " + NOW.isoformat(),
        "Modus: AUSSCHLIESSLICH LESEND am Pi",
        "Kein Restart, kein Patch, keine Timeränderung",
        "Rohdaten und Zugangsdaten NICHT nach GitHub übertragen",
    ]))
    add("TV-Rohdaten (nur Metadaten)", json_info(TV_SOURCE))
    add("Private Overrides (nur Modus/Revision)", json_info(OVERRIDES, is_private=True))
    add("Öffentlicher Export (nur Metadaten)",
        json_info(GH_ROOT / "data/kabinen_live_data.json"))
    units()
    scripts()
    service_files_and_cron()
    tv_viewer_and_renderers()
    journal_sample()
    report = "\n".join(sections)
    if len(report.encode("utf-8")) > MAX_REPORT:
        report = report[:MAX_REPORT // 3] + "\n[Bericht auf Sicherheitsmaximum gekürzt]\n"
    local = Path(tempfile.gettempdir()) / REPORT_NAME
    local.write_text(report, encoding="utf-8")
    print("tus BERNE TV-Produzent-Diagnose: " + REPORT_NAME)
    # Only write outside the Pi's original application to a private report.
    try:
        cmd = ["rclone", "copyto", str(local), "gdrive:" + REPORT_NAME,
               "--drive-root-folder-id", DRIVE_FOLDER_ID]
        proc = subprocess.run(cmd, text=True, capture_output=True,
                              errors="replace", timeout=120, check=False)
        if proc.returncode:
            print("UPLOAD FEHLGESCHLAGEN. Report lokal: " + str(local))
            print("rclone-Rückgabecode: " + str(proc.returncode))
            return 2
    except (OSError, subprocess.TimeoutExpired) as exc:
        print("UPLOAD FEHLGESCHLAGEN: " + type(exc).__name__)
        print("Report lokal: " + str(local))
        return 2
    print("OK: Bericht in privatem Google Drive / Entwicklung & Diagnose.")
    print("TV-Anzeige, Dienste, Quelldaten und Google-Overrides unverändert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
