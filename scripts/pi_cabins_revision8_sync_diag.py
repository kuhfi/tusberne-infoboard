#!/usr/bin/env python3
"""tus BERNE – Diagnose: Google Revision 8 erreicht GitHub nicht.

READ-ONLY on Raspberry Pi. Prints only status, version and the specifically
requested 15 Nov 2026 fixture/cabin. The report is uploaded ONLY to the private
Google Drive "Entwicklung & Diagnose" folder, never committed to GitHub.

Checks 4 stages: Google import file, local effective TV, local publisher
worktree, and journal/systemd. No git fetch, service restart, sync or patch.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

APP=Path("/home/kuhfi/infoboard-app")
REPO=Path("/home/kuhfi/tusberne-github-sync")
PRIVATE=Path("/var/lib/tusberne-kabinen/overrides.json")
RAW=APP/"public/kabinen-live/kabinenplan_data.json"
TV=APP/"public/kabinen-live/kabinenplan_tv_effective.json"
GITHUB_LOCAL=REPO/"data/kabinen_live_data.json"
DRIVE_ID="17nIUUe6LAJYWsbe-hH4cKrruXSBp0SBI"
NOW=datetime.now(ZoneInfo("Europe/Berlin"))
REPORT="tusberne-kabinen-revision8-sync-diagnose-"+NOW.strftime("%Y%m%d-%H%M%S")+".txt"
WEEK="2026-11-09"
FIXTURE_DATE="2026-11-15"
FIXTURE_TIME="13:00"
FIXTURE_HOME="tus BERNE 7.D (J4)"
FIXTURE_AWAY="Concordia 3.D (J2)"
EXPECTED_REV=8
EXPECTED_CABIN="SR2"
BODY=[]

def line(text):
    BODY.append(str(text))

def sec(label):
    line("\n=== "+label+" ===")

def redact(text):
    val=str(text).strip()
    if re.search(r"(?i)(password|passwd|secret|bearer |authorization|oauth|private.key|client.secret|token=|credential|api.key)",val):
        return "[Zeile mit möglichen Zugangsdaten ausgelassen]"
    val=re.sub(r"https?://\S+","[URL verborgen]",val)
    return val[:260]

def run(args, cwd=None,timeout=15):
    try:
        return subprocess.run(args,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,errors="replace",timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as e:
        line("Befehl nicht lesbar: "+redact(" ".join(args[:3]))+" ("+type(e).__name__+")")
        return None

def read_json(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>2_000_000:
        raise RuntimeError("Datei fehlt oder unzulässiger Dateityp: "+str(path))
    return json.loads(path.read_text(encoding="utf-8"))

def iso_mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime,ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")

def only_fixture(games):
    if not isinstance(games,list):
        raise ValueError("Spieleliste fehlt")
    selected=[g for g in games if isinstance(g,dict) and
        g.get("date")==FIXTURE_DATE and g.get("time")==FIXTURE_TIME and
        g.get("home")==FIXTURE_HOME and g.get("away")==FIXTURE_AWAY]
    if len(selected)!=1:
        return "Anzahl passender Spiele: "+str(len(selected))+" (erwartet: 1)"
    g=selected[0]
    return ("Gefunden: Heim "+str(g.get("home_cabin"))+", Gast "+
            str(g.get("guest_cabin"))+", SR "+str(g.get("sr_cabin")))

def check_private():
    sec("1. Google-Import: privater Pi-Speicher (KEINE Änderungen/IDs exportieren)")
    try:
        p=read_json(PRIVATE)
        track=(p.get("google_cabins_sync") or {}).get("revisions") or {}
        revision=int(track.get(WEEK,0))
        mode=(p.get("weeks") or {}).get(WEEK,{}).get("mode","automatic")
        line("Gespeicherte Google-Revision: "+str(revision)+" (Google hat: 8)")
        line("Gespeicherter Modus: "+str(mode))
        line("Datei geändert: "+iso_mtime(PRIVATE))
        changes=(p.get("weeks") or {}).get(WEEK,{}).get("changes",{})
        line("Korrektur-Felder/Anzahl: "+", ".join(sorted({
            k for v in changes.values() if isinstance(v,dict) for k in v
            }))+" / "+str(len(changes))+" Spiel(e)")
        line("Befund: "+"GOOGLE-IMPORT VERALTET" if revision<EXPECTED_REV else
              "Befund: Google-Revision 8 oder höher auf Pi angekommen")
    except Exception as e:
        line("FEHLER: "+type(e).__name__+": "+redact(e))

def check_json(label,path):
    sec(label)
    try:
        d=read_json(path)
        line("Dateistand: "+iso_mtime(path))
        line("Spiele: "+str(len(d.get("games",[]))))
        line("Version / erzeugt: "+str(d.get("version","–"))+" / "+str(d.get("generated_at","–")))
        meta=(d.get("manual_weeks") or {}).get(WEEK,{})
        line("Manuelle Woche: Revision "+str(meta.get("revision","–"))+
             ", Modus "+str(meta.get("mode","–"))+", unmatched "+
             str(meta.get("unmatched","–")))
        line(only_fixture(d.get("games",[])))
    except Exception as e:
        line("FEHLER: "+type(e).__name__+": "+redact(e))

def check_git():
    sec("4. Git-Publisher: nur lokale Repo-Metadaten")
    for label,args in (
        ("Branch",["git","branch","--show-current"]),
        ("Lokaler HEAD",["git","rev-parse","--short","HEAD"]),
        ("Lokaler origin/main",["git","rev-parse","--short","refs/remotes/origin/main"]),
        ("Arbeitskopie (Status - Pfade)",["git","status","--short","--untracked-files=normal"]),
        ("Lokale unveröffentlichte Commits",["git","rev-list","--count","origin/main..HEAD"]),
    ):
        proc=run(args,cwd=REPO)
        if proc is None:
            continue
        line(label+": rc="+str(proc.returncode))
        if proc.returncode:
            for v in proc.stderr.splitlines()[:4]:
                line("  "+redact(v))
        else:
            output=proc.stdout.splitlines()
            line("  "+(" | ".join(redact(v) for v in output[:16]) if output else "(leer)"))
            if len(output)>16:
                line("  + "+str(len(output)-16)+" weitere Statuszeilen")
    sec("5. Öffentlicher Kabinenexport – NUR Trockenlauf")
    proc=run(["python3","scripts/pi_cabins_export.py"],cwd=REPO,timeout=18)
    if proc is not None:
        line("Rückgabecode: "+str(proc.returncode))
        for v in (proc.stdout+proc.stderr).splitlines()[:30]:
            line("  "+redact(v))

def check_systemd():
    sec("6. Dienste / letzte Laufstatus")
    for name in ("berne-cabins-google-sync","berne-github-public-sync",
                 "berne-tv-cabins-overlay","berne-kabinen-live"):
        for suffix in ("service","timer"):
            unit=name+"."+suffix
            proc=run(["systemctl","show",unit,
                "--property=LoadState,ActiveState,Result,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp,NextElapseUSecRealtime"],
                timeout=8)
            if proc is None:
                continue
            vals=dict(row.split("=",1) for row in proc.stdout.splitlines() if "=" in row)
            line(unit+": "+", ".join(k+"="+redact(v) for k,v in vals.items()
                    if v and k in ("LoadState","ActiveState","Result","ExecMainStatus",
                                   "ExecMainStartTimestamp","ExecMainExitTimestamp",
                                   "NextElapseUSecRealtime"))[:400])
    sec("7. Journal Google-Importer seit 09:25 Uhr (selektive Zeilen)")
    journal("berne-cabins-google-sync.service")
    sec("8. Journal GitHub-Publisher seit 09:25 Uhr (selektive Zeilen)")
    journal("berne-github-public-sync.service")
    sec("9. Journal TV-Overlay seit 09:25 Uhr (selektive Zeilen)")
    journal("berne-tv-cabins-overlay.service")

def journal(unit):
    proc=run(["journalctl","-u",unit,"--since","2026-11-12 09:25:00",
              "--no-pager","-n","100","-o","short-iso"],timeout=14)
    if proc is None:
        return
    line("Journal-Rückgabecode: "+str(proc.returncode))
    # No raw log blobs; select only safe operational outcomes
    keep=re.compile(r"(?i)(starting |started |finished |failed |stopp|kabinen:|revision|version|änderung|aenderung|git|fetch|merge|push|commit|dirty|working tree|arbeitskopie|source|sync|export|fehler|error|warnung|fatal|unchanged|update|dateien|sperre|output|exit-code)")
    matches=[redact(v) for v in proc.stdout.splitlines() if keep.search(v)]
    for v in matches[-45:]:
        line("  "+v)
    if not matches:
        line("Keine passenden Journalzeilen (oder fehlende Leseberechtigung).")
    if proc.returncode and proc.stderr:
        line("Journal stderr-Kategorie: "+redact(proc.stderr.splitlines()[0]))

def main():
    line("tus BERNE – gezielte Revision-8-Synchronisationsdiagnose")
    line("Zeitpunkt: "+NOW.isoformat())
    line("Modus: L E S E N D – keine Änderungen am Pi/Google/GitHub")
    line("Ausgangslage: Google-Revision 8 (09:28:51 CET), SR2; öffentliche Revision 7, SR1")
    check_private()
    check_json("2. TV-Automatikquelle",RAW)
    check_json("2b. Effektive lokale TV-JSON",TV)
    check_json("3. GitHub-Arbeitskopie des öffentlichen Plans",GITHUB_LOCAL)
    check_git()
    check_systemd()
    result="\n".join(BODY)+"\n"
    result=result[:60_000]
    dest=Path(tempfile.gettempdir())/REPORT
    dest.write_text(result,encoding="utf-8")
    print("Lokaler lesender Bericht:",str(dest))
    print("Google-Stand: Version 8, öffentlich zuletzt Revision 7")
    try:
        proc=run(["rclone","copyto",str(dest),"gdrive:"+REPORT,
                  "--drive-root-folder-id",DRIVE_ID],timeout=120)
        if proc is None or proc.returncode:
            print("WARNUNG: Privater Drive-Upload nicht erfolgreich. Bericht bleibt lokal.")
            return 1
        print("OK: Bericht privat nach Google Drive / Entwicklung & Diagnose übertragen:")
        print(REPORT)
        print("Keine Änderung am System vorgenommen.")
        return 0
    except Exception as e:
        print("WARNUNG: Drive-Upload nicht bestätigt:",type(e).__name__)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
