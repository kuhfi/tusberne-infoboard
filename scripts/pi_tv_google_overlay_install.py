#!/usr/bin/env python3
"""tus BERNE TV cabin overlay: separate read-only source + reversible TV routing.

--check (default): offline validation only, private Drive report.
--install (sudo): install independent one-minute timer, display JSON, and two
    narrowly pinned HTML URL adjustments. Back up every changed file first.
--generate (service user): atomic refresh of effective TV JSON; last good survives errors.
--rollback (sudo): undo this install using its exact recorded backup.
No change to the Google Web App, original JSON, producer, its timer, or PDF export.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

APP = Path("/home/kuhfi/infoboard-app")
REPO = Path("/home/kuhfi/tusberne-github-sync")
SRC = APP / "public/kabinen-live/kabinenplan_data.json"
OUT = APP / "public/kabinen-live/kabinenplan_tv_effective.json"
STORE = Path("/var/lib/tusberne-kabinen/overrides.json")
IMPL = APP / "scripts/tv_google_cabins_overlay.py"
UNIT = Path("/etc/systemd/system/berne-tv-cabins-overlay.service")
TIMER = Path("/etc/systemd/system/berne-tv-cabins-overlay.timer")
BACKUPS = APP / "backups/tv-google-cabins"
DRIVE_FOLDER = "17nIUUe6LAJYWsbe-hH4cKrruXSBp0SBI"
NOW = datetime.now(ZoneInfo("Europe/Berlin"))
NAME = "tusberne-tv-google-overlay-" + NOW.strftime("%Y%m%d-%H%M%S") + ".txt"
OLD_URL = "/kabinen-live/kabinenplan_data.json"
NEW_URL = "/kabinen-live/kabinenplan_tv_effective.json"
HTMLS = (
    (APP / "public/portrait/kabinen.html",
     "8c8ee467a806f7f0c01ec3750669141609bc67053301adcb791e24ec581f1e20"),
    (APP / "public/kabinen-live/01_kabinen_live.html",
     "ceb282c4e1b6325952489cdf9aae62b7985870b34304023ff522bbd0b944253c"),
)
SERVICE_TEXT = """[Unit]
Description=tus BERNE - private Google cabin corrections on local TV
After=local-fs.target

[Service]
Type=oneshot
User=kuhfi
WorkingDirectory=/home/kuhfi/tusberne-github-sync
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 /home/kuhfi/infoboard-app/scripts/tv_google_cabins_overlay.py --generate
"""
TIMER_TEXT = """[Unit]
Description=tus BERNE - local TV Google cabin overlay (every minute)

[Timer]
OnCalendar=*-*-* *:*:00
AccuracySec=10s
Persistent=true
Unit=berne-tv-cabins-overlay.service

[Install]
WantedBy=timers.target
"""


def load_logic():
    sys.path.insert(0, str(REPO / "scripts"))
    from cabins_overrides import effective_plan, game_key, load_store, week_start
    return effective_plan, game_key, load_store, week_start


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_document(path: Path, max_size: int = 700_000):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > max_size:
        raise RuntimeError("Pfad fehlt, ist Symlink oder unzulässig groß: " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def validate_raw(raw: dict) -> None:
    if not isinstance(raw, dict) or not isinstance(raw.get("games"), list):
        raise ValueError("TV-Automatikquelle ist kein gültiges Spieleobjekt")
    if not 1 <= len(raw.get("period", {}).get("weeks", [])) <= 4:
        raise ValueError("TV-Zweiwochenzeitraum ungültig")
    if len(raw["games"]) > 200:
        raise ValueError("Unplausible Spielzahl")
    for field in ("warnings", "critical_conflicts", "rules",
                  "source_stats", "extra_source", "source", "period"):
        if field not in raw:
            raise ValueError("Wichtiges Original-Diagnosefeld fehlt: " + field)
    for g in raw["games"]:
        if not isinstance(g, dict) or not all(isinstance(g.get(k), str)
                                              for k in ("date","time","home","away","kind","league")):
            raise ValueError("Fehlerhaftes automatisch berechnetes Spiel")


def render_data(raw: dict, store: dict, now=None) -> dict:
    """Retain *all* original TV metadata, overlay exact Google effective plan."""
    effective_plan, game_key, _, _ = load_logic()
    validate_raw(raw)
    effective = effective_plan(raw, store, now=now)
    if not isinstance(effective.get("games"), list) or len(effective["games"]) > 200:
        raise ValueError("Ungültige effektive Spielzahl")
    current = effective.get("manual_weeks", {})
    # A week-locked game matched to an unchanged auto fixture retains all
    # diagnostics and auxiliary fields. Changed/new locked fixtures are
    # intentionally display-only entries, with no invented source warnings.
    original = {}
    keys = Counter(game_key(g) for g in raw["games"])
    for g in raw["games"]:
        k = game_key(g)
        if keys[k] == 1:
            original[k] = g
    games = []
    for item in effective["games"]:
        g = copy.deepcopy(item)
        if g.get("manual_override") and keys[game_key(g)] == 1:
            base = copy.deepcopy(original[game_key(g)])
            base.update(g)
            g = base
        elif g.get("manual_override") and "guest_count" not in g:
            g.setdefault("guest_count", 1)
            g.setdefault("guest_cabins", [g.get("guest_cabin") or None])
            g.setdefault("warnings", [])
            g.setdefault("manual_source", True)
            g.setdefault("sr_required", bool(g.get("sr_cabin")))
        games.append(g)
    # All original top-level fields remain, including original conflict
    # diagnostics. TV renderer intentionally does not expose those warnings.
    out = copy.deepcopy(raw)
    out["games"] = games
    out["manual_weeks"] = current
    stamp_data = {
        "games": [
            {k: g.get(k) for k in ("date","time","kind","league","home",
                                  "away","home_cabin","guest_cabin","sr_cabin","festival")}
            for g in games
        ],
        "manual_weeks": current,
    }
    out["display_revision"] = digest(json.dumps(
        stamp_data, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8"))[:20]
    if not all(out.get(k) == raw[k] for k in
               ("warnings","critical_conflicts","rules","source_stats",
                "extra_source","source","period")):
        raise ValueError("Interne Rohdaten wurden verändert")
    return out


def snapshot() -> tuple[dict, dict]:
    _, _, load_store, _ = load_logic()
    raw = safe_document(SRC, 900_000)
    if not STORE.is_file() or STORE.is_symlink():
        raise RuntimeError("Privater gültiger Google-Override-Speicher nicht vorhanden")
    store = load_store(STORE)
    if store.get("schema_version") != 1:
        raise ValueError("Unbekannte Google-Kabinenversion")
    return raw, store


def atomic_bytes(path: Path, data: bytes, mode: int = 0o644) -> None:
    if path.is_symlink():
        raise ValueError("Symlink-Ziel gesperrt: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def generate(*, dry: bool = False) -> tuple[dict, bool]:
    raw, store = snapshot()
    out = render_data(raw, store)
    serialized = (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    # Never mutate the original; repeated scans skip identical results.
    changed = not OUT.is_file() or OUT.read_bytes() != serialized
    if not dry and changed:
        atomic_bytes(OUT, serialized)
        loaded = safe_document(OUT)
        if loaded != out:
            raise RuntimeError("Geschriebener TV-Plan nicht identisch mit validiertem Plan")
    return out, changed


def offline_tests() -> list[str]:
    """Prove automatic, partial, locked (including added/removed), and reset."""
    effective_plan, game_key, _, week_start = load_logic()
    raw, store = snapshot()
    auto = copy.deepcopy(store)
    auto["weeks"] = {}
    doc = render_data(raw, auto)
    if doc["games"] != raw["games"]:
        raise AssertionError("Automatik muss alle Originalspiele unverändert übernehmen")
    active = next((w for w in raw["period"]["weeks"]
                   if w["start"] == week_start()), None)
    if active is None:
        raise ValueError("Aktuelle Woche fehlt; Test abgebrochen")
    week = active["start"]
    week_games = [g for g in raw["games"]
                  if active["start"] <= g["date"] <= active["end"]]
    if not week_games:
        raise ValueError("Keine Spiele der aktuellen Woche für Probetests")
    target = week_games[0]
    test_id = game_key(target)
    if sum(game_key(g) == test_id for g in week_games) != 1:
        raise ValueError("Erstes Testspiel nicht eindeutig; Test abgebrochen")
    field = "sr_cabin"
    old = target.get(field) or ""
    new = "SR2" if old != "SR2" else "SR1"
    partial = copy.deepcopy(auto)
    partial["weeks"] = {week: {"mode":"partial","revision":90001,
                               "changes":{test_id:{field:new}}}}
    part = render_data(raw, partial)
    actual = [g for g in part["games"] if game_key(g) == test_id]
    if len(actual) != 1 or actual[0][field] != new or (target.get(field) or "") != old:
        raise AssertionError("Einzelkorrektur überschreibt Autodaten oder wird nicht angezeigt")
    # Synthetic fixture never written to either source/Google/TV file.
    new_fixture = {"date":week,"time":"23:58","kind":"Test",
                   "league":"Nur Offline-Probe","home":"TEST HEIM","away":"TEST GAST",
                   "home_cabin":"1","guest_cabin":"3","sr_cabin":"",
                   "festival":False}
    locked_games = [
        {k: g.get(k, "") for k in ("date","time","kind","league","home",
                                   "away","home_cabin","guest_cabin","sr_cabin","festival")}
        for g in week_games[:1]
    ] + [new_fixture]
    lock = copy.deepcopy(auto)
    lock["weeks"] = {week: {"mode":"locked","revision":90002,"games":locked_games}}
    locked = render_data(raw, lock)
    locked_week = [g for g in locked["games"]
                   if active["start"] <= g["date"] <= active["end"]]
    if len(locked_week) != 2 or not any(g["home"] == "TEST HEIM" for g in locked_week):
        raise AssertionError("Wochensperre, Hinzufügen oder Entfernen fehlgeschlagen")
    if locked["warnings"] != raw["warnings"] or locked["rules"] != raw["rules"]:
        raise AssertionError("Wochensperre verlor Original-Diagnosen")
    reset = render_data(raw, auto)
    if reset["games"] != raw["games"]:
        raise AssertionError("Automatik-Wiederherstellung fehlgeschlagen")
    if (raw, store) != snapshot():
        # Concurrent producer/Google update makes the test outcome uncertain.
        raise RuntimeError("Quellen wechselten während Probetests; bitte erneut prüfen")
    return ["Automatikspiel-Daten unverändert", "Einzelkorrektur in Offline-Test wirksam",
            "Wochensperre inklusive Hinzufügen/Entfernen geprüft",
            "Rücksetzung auf Automatik geprüft",
            "Diagnosefelder und Rohquelle unverändert"]


def html_patches() -> dict[Path, bytes]:
    result = {}
    for path, expected in HTMLS:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("TV-HTML fehlt: " + str(path))
        before = path.read_bytes()
        if digest(before) != expected:
            raise RuntimeError("STOPP: TV-HTML wurde seit Diagnose geändert: " + str(path))
        text = before.decode("utf-8")
        if text.count(OLD_URL) != 1:
            raise RuntimeError("Unerwartete Anzahl Datenladepfade: " + str(path))
        after = text.replace(OLD_URL, NEW_URL)
        if "portrait/kabinen.html" in str(path):
            if "g.warnings?.length" in after or "Zusatztermine: älterer Stand" in after or "Planung prüfen" in after:
                raise RuntimeError("Zuvor entfernte TV-Warntexte wieder vorhanden")
        else:
            needle = "const stampKey=next.generated_at+'|'+(next.games||[]).length+'|'+next.critical_conflicts;"
            newer = "const stampKey=next.generated_at+'|'+(next.games||[]).length+'|'+next.critical_conflicts+'|'+(next.display_revision||'');"
            if after.count(needle) != 1:
                raise RuntimeError("TV-Refreshkennung V17 verändert")
            after = after.replace(needle, newer)
        result[path] = after.encode("utf-8")
    return result


def run(args: list[str], *, check=True, timeout=25):
    p = subprocess.run(args, capture_output=True, text=True,
                       errors="replace", timeout=timeout, check=False)
    if check and p.returncode:
        raise RuntimeError("Befehl fehlgeschlagen: " + " ".join(args[:3]) +
                           " (rc=" + str(p.returncode) + ")")
    return p


def private_report(action: str, lines: list[str]) -> None:
    body = "\n".join(["tus BERNE – TV Google-Kabinen-Overlay",
                      NOW.isoformat(), "Aktion: " + action] + lines) + "\n"
    file = Path(tempfile.gettempdir()) / NAME
    file.write_text(body, encoding="utf-8")
    if os.geteuid() == 0:
        owner = pwd.getpwnam("kuhfi")
        os.chown(file, owner.pw_uid, owner.pw_gid)
        file.chmod(0o600)
    try:
        if os.geteuid() == 0:
            cmd = ["runuser", "-u", "kuhfi", "--", "rclone"]
        else:
            cmd = ["rclone"]
        p = run(cmd + ["copyto", str(file), "gdrive:" + NAME,
                       "--drive-root-folder-id", DRIVE_FOLDER],
                check=False, timeout=120)
        if p.returncode:
            print("Bericht nur lokal: " + str(file) + " (rclone rc=" + str(p.returncode) + ")")
        else:
            print("Bericht privat in Google Drive / Entwicklung & Diagnose: " + NAME)
    except (OSError, subprocess.TimeoutExpired):
        print("Bericht-Upload nicht bestätigt; lokal: " + str(file))


def reload_kiosk() -> str:
    try:
        uid = pwd.getpwnam("kuhfi").pw_uid
        runtime = Path(f"/run/user/{uid}")
        if shutil.which("wtype") is None or not runtime.exists():
            return "TV-Neuladen nicht gesendet (wtype/Wayland fehlt)"
        for sock in runtime.glob("wayland-*"):
            if sock.is_socket():
                r = run(["runuser","-u","kuhfi","--","env",
                         "XDG_RUNTIME_DIR="+str(runtime),
                         "WAYLAND_DISPLAY="+sock.name,
                         "wtype","-M","ctrl","-k","r","-m","ctrl"],
                        check=False, timeout=8)
                if r.returncode == 0:
                    return "Ctrl+R gesendet (" + sock.name + "); sichtbare Kontrolle ausstehend"
    except (OSError, KeyError, subprocess.TimeoutExpired):
        pass
    return "TV-Neuladen nicht bestätigt; HTML beim nächsten Aufruf aktiv"


def targets() -> list[Path]:
    return [IMPL, OUT, UNIT, TIMER] + [x[0] for x in HTMLS]


def backup() -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    name = NOW.strftime("%Y%m%d-%H%M%S-%f")
    dest = BACKUPS / name
    dest.mkdir(mode=0o700)
    entries = []
    for i, path in enumerate(targets()):
        if path.is_symlink():
            raise RuntimeError("Symlink-Ziel nicht erlaubt: " + str(path))
        exists = path.is_file()
        if exists:
            name = f"file-{i}"
            shutil.copy2(path, dest / name)
            (dest / name).chmod(0o600)
        else:
            name = None
        entries.append({"target":str(path),"copy":name,"existed":exists,
                        "mode":path.stat().st_mode & 0o777 if exists else None})
    (dest / "manifest.json").write_text(
        json.dumps({"version":1,"entries":entries},indent=2) + "\n",encoding="utf-8")
    shutil.copy2(Path(__file__), dest / "installer.py")
    return dest


def rollback(dest: Path) -> str:
    if os.geteuid() != 0:
        raise RuntimeError("Rollback benötigt sudo")
    if not dest.is_dir() or dest.parent.resolve() != BACKUPS.resolve():
        raise RuntimeError("Ungültiger Backup-Ordner")
    doc = safe_document(dest/"manifest.json")
    paths = [e["target"] for e in doc["entries"]]
    if doc.get("version") != 1 or paths != [str(p) for p in targets()]:
        raise RuntimeError("Manifest enthält unerwartete Pfade")
    run(["systemctl","disable","--now",TIMER.stem+".timer"],check=False)
    run(["systemctl","stop",UNIT.name],check=False)
    for entry in doc["entries"]:
        p = Path(entry["target"])
        if p.is_symlink():
            raise RuntimeError("Rollback stoppt vor Symlink: " + str(p))
        if entry["existed"]:
            old = (dest / entry["copy"]).read_bytes()
            atomic_bytes(p,old,entry["mode"])
        elif p.exists():
            p.unlink()
    run(["systemctl","daemon-reload"])
    return reload_kiosk()


def check() -> list[str]:
    _, _ = generate(dry=True)
    patches = html_patches()
    checks = offline_tests()
    data, changed = generate(dry=True)
    raw = safe_document(SRC,900_000)
    lines = checks + [
        "Quelldatei: "+str(SRC)+" (NICHT verändert)",
        "TV-Ziel: "+str(OUT),
        "Spiele: Automatik "+str(len(raw["games"]))+
        " / Anzeige "+str(len(data["games"])),
        "Google-Wochenstände: "+repr(data["manual_weeks"]),
        "TV-Extra-Modus: "+str((raw.get("extra_source") or {}).get("mode")),
        "Geplante HTML-Dateien: "+", ".join(str(p) for p in patches),
        "Separate systemd-Unit und Timer geplant (1 Minute)",
        "Keine vorhandenen Dienste/Timer/Publisher werden verändert",
        "Umstellung/Backup: Noch NICHT ausgeführt",
    ]
    if IMPL.exists() or UNIT.exists() or TIMER.exists() or OUT.exists():
        # This is the initial installer; do not reuse it silently.
        raise RuntimeError("Overlay-Zieldatei oder Unit bereits vorhanden; manuell prüfen")
    return lines


def install() -> list[str]:
    if os.geteuid() != 0:
        raise RuntimeError("Installation benötigt sudo")
    lines = check()
    dest = backup()
    try:
        atomic_bytes(IMPL,Path(__file__).read_bytes())
        data, _ = generate(dry=False)
        if safe_document(OUT) != data:
            raise RuntimeError("TV-Anzeige-Datei nach Erzeugen abweichend")
        atomic_bytes(UNIT,SERVICE_TEXT.encode("utf-8"))
        atomic_bytes(TIMER,TIMER_TEXT.encode("utf-8"))
        run(["systemctl","daemon-reload"])
        run(["systemctl","enable","--now",TIMER.name])
        run(["systemctl","start",UNIT.name],timeout=30)
        if run(["systemctl","is-active","--quiet",TIMER.name],check=False).returncode != 0:
            raise RuntimeError("Neuer Overlay-Timer nicht aktiv")
        if run(["systemctl","is-active","--quiet","berne-infoboard.service"],check=False).returncode != 0:
            raise RuntimeError("TV-Server nicht aktiv")
        for p, after in html_patches().items():
            atomic_bytes(p,after,0o644)
        for p in [x[0] for x in HTMLS]:
            if NEW_URL not in p.read_text(encoding="utf-8"):
                raise RuntimeError("Renderer nicht umgestellt")
        after = safe_document(OUT)
        if after["games"] != data["games"] or after["manual_weeks"] != data["manual_weeks"]:
            raise RuntimeError("Overlay-Ausgabe stimmte nach Timerstart nicht mehr")
        lines += ["INSTALLIERT UND VERIFIZIERT",
                  "Backup: "+str(dest),
                  "Overlay-Timer: AKTIV; bereits laufende Dienste unverändert",
                  "TV-Neuladen: "+reload_kiosk(),
                  "Rollback: sudo python3 "+str(dest/"installer.py")+" --rollback "+str(dest),
                  "Visuelle TV-Kontrolle und End-to-End-Tests stehen noch aus"]
        return lines
    except BaseException:
        print("Installationsfehler – automatischer Rollback",file=sys.stderr)
        print("Rollback: "+rollback(dest),file=sys.stderr)
        raise


def main() -> int:
    args=sys.argv[1:]
    try:
        if not args or args==["--check"]:
            lines=check()
            for s in lines: print(s)
            private_report("CHECK – keine Änderungen",lines)
        elif args==["--generate"]:
            result, changed=generate(dry=False)
            print("TV-Google-Overlay:",len(result["games"]),"Spiele;",
                  "neue Daten" if changed else "unverändert",
                  "Revision",result["display_revision"])
        elif args==["--install"]:
            lines=install()
            for s in lines: print(s)
            private_report("INSTALLIERT",lines)
        elif len(args)==2 and args[0]=="--rollback":
            result=rollback(Path(args[1]))
            lines=["ROLLBACK: bisherige Dateien wiederhergestellt",result]
            print("\n".join(lines))
            private_report("ROLLBACK",lines)
        else:
            raise ValueError("Erlaubte Aufrufe: --check, --generate, --install, --rollback <Backup>")
        return 0
    except Exception as exc:
        print("STOPP:",type(exc).__name__,str(exc)[:450],file=sys.stderr)
        if args!=["--generate"]:
            private_report("FEHLER – kein bestätigter Erfolg",
                           [type(exc).__name__,str(exc)[:400]])
        return 1


if __name__=="__main__":
    raise SystemExit(main())
