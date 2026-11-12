#!/usr/bin/env python3
"""tus BERNE – read-only post-installation acceptance of TV Google overlay.

Reads the current original/effective cabin JSON, private override *metadata*,
units, producer status and local loopback HTTP routes. Reports only limited
diagnostics to the existing PRIVATE "Entwicklung & Diagnose" Drive folder.
Never edits the production files, Google sheet, timer, or service.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from zoneinfo import ZoneInfo

APP=Path("/home/kuhfi/infoboard-app")
ORIG=APP/"public/kabinen-live/kabinenplan_data.json"
EFFECTIVE=APP/"public/kabinen-live/kabinenplan_tv_effective.json"
IMPL=APP/"scripts/tv_google_cabins_overlay.py"
STORE=Path("/var/lib/tusberne-kabinen/overrides.json")
FOLDER="17nIUUe6LAJYWsbe-hH4cKrruXSBp0SBI"
NOW=datetime.now(ZoneInfo("Europe/Berlin"))
NAME="tusberne-tv-google-overlay-abnahme-"+NOW.strftime("%Y%m%d-%H%M%S")+".txt"
BASE="http://127.0.0.1:8765"
checks=[]

def add(name, status, reason):
    checks.append((name,status,str(reason)[:330]))

def read_json(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>1_000_000:
        raise RuntimeError("Fehlende, verlinkte oder übergroße Datei: "+str(path))
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict):
        raise ValueError("JSON ohne Objektwurzel: "+str(path))
    return data

def cmd(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,errors="replace",timeout=12,check=False)
        return p.returncode,p.stdout
    except (OSError,subprocess.TimeoutExpired) as e:
        return -1,type(e).__name__

def digest(payload):
    return hashlib.sha256(payload).hexdigest()[:16]

def check_unit(name, expected):
    code, output=cmd(["systemctl","is-active",name])
    actual=output.strip() or "nicht verfügbar"
    add("Unit "+name, "OK" if code==0 and actual==expected else "WARNUNG",
        "Status: "+actual+"; erwartet: "+expected)
    code,output=cmd(["systemctl","show",name,"--no-pager",
                     "--property=Result,ExecMainStatus,ExecMainStartTimestamp,ActiveEnterTimestamp"])
    lines=[l for l in output.splitlines() if not re.search("Environment|ExecStart",l,re.I)]
    add("Unit Details "+name,"INFO","; ".join(lines)[:300])

def fetch_local(path, *, as_json=False):
    url=BASE+path
    try:
        with urlopen(url,timeout=7) as response:
            raw=response.read(950_000)
            status=response.status
            if len(raw)>=950_000:
                raise ValueError("HTTP-Inhalt zu groß")
            if not as_json:
                text=raw.decode("utf-8")
                return status,text
            document=json.loads(raw)
            return status,document
    except (HTTPError,URLError,OSError,ValueError,json.JSONDecodeError) as e:
        return -1,type(e).__name__

def main():
    try:
        original=read_json(ORIG)
        output=read_json(EFFECTIVE)
        store=read_json(STORE)
        add("Dateien gelesen","OK","Quell-JSON und neue TV-JSON sind lesbar")
        add("Zeitraum","OK" if output.get("period")==original.get("period") else "FEHLER",
            str(output.get("period",{}).get("weeks",[])))
        source_count=len(original.get("games",[]))
        result_count=len(output.get("games",[]))
        add("Spielzahlen","INFO",f"Original: {source_count}, Anzeige: {result_count}")
        add("Revision","INFO",repr(output.get("manual_weeks",{}))[:320])
        add("Originalfingerabdruck","INFO",digest(ORIG.read_bytes()))
        add("Overlayfingerabdruck","INFO",digest(EFFECTIVE.read_bytes()))
        for k in ("critical_conflicts","warnings","rules","source_stats","extra_source","source","venue_filter"):
            add("Hintergrundfeld "+k,"OK" if output.get(k)==original.get(k) else "FEHLER",
                "identisch" if output.get(k)==original.get(k) else "abweichend")
        add("Zusatztermine-Modus","INFO",str((original.get("extra_source") or {}).get("mode")))
        if IMPL.is_file():
            spec=importlib.util.spec_from_file_location("tusberne_tv_effective_check",str(IMPL))
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            expected=module.render_data(original,store)
            add("Overlay stimmt mit aktuellem Google-Speicher überein",
                "OK" if output==expected else "WARNUNG",
                "Vollständiger JSON-Datenvergleich" if output==expected
                else "Noch unterschiedliche Stände (Timerlauf erneut abwarten)")
        else:
            add("Overlay-Code","FEHLER","Installierte Overlay-Datei fehlt")
    except (OSError,ValueError,RuntimeError,ImportError,AttributeError) as e:
        add("Aktuelle Dateien prüfen","FEHLER",type(e).__name__+": "+str(e)[:160])
    check_unit("berne-infoboard.service","active")
    check_unit("berne-tv-cabins-overlay.timer","active")
    check_unit("berne-kabinen-live.timer","active")
    check_unit("berne-cabins-google-sync.timer","active")
    for name in ("berne-tv-cabins-overlay.service", "berne-kabinen-live.service"):
        code,stdout=cmd(["systemctl","show",name,
                         "--property=Result,ExecMainStatus,ExecMainExitTimestamp,ExecMainStartTimestamp"])
        add("Letzter Lauf "+name,"INFO","; ".join(stdout.strip().splitlines())[:300])
    for label,path in (
        ("Portrait HTML",APP/"public/portrait/kabinen.html"),
        ("Live V17 HTML",APP/"public/kabinen-live/01_kabinen_live.html"),
    ):
        try:
            text=path.read_text(encoding="utf-8")
            new=text.count("/kabinen-live/kabinenplan_tv_effective.json")
            old=text.count("/kabinen-live/kabinenplan_data.json")
            success=new==1 and old==0
            if "Portrait" in label:
                success=success and ("g.warnings?.length" not in text
                          and "Zusatztermine: älterer Stand" not in text
                          and "Planung prüfen" not in text)
            add(label,"OK" if success else "FEHLER",
                f"Neuer Pfad: {new}; alter Pfad: {old}; Warntexte aus: "+
                str("g.warnings?.length" not in text))
        except OSError as e:
            add(label,"FEHLER",type(e).__name__)
    for label,route in (
        ("TV-JSON über Server","/kabinen-live/kabinenplan_tv_effective.json"),
        ("Portrait über Server","/portrait/kabinen.html"),
        ("Live V17 über Server","/kabinen-live/01_kabinen_live.html"),
    ):
        code,content=fetch_local(route,as_json=route.endswith(".json"))
        if code!=200:
            add(label,"WARNUNG","Loopback 127.0.0.1:8765 HTTP "+str(code)+", "+str(content)[:50])
        elif route.endswith(".json"):
            try:
                on_disk=read_json(EFFECTIVE)
                add(label,"OK" if content==on_disk else "FEHLER",
                    "HTTP-Inhalt ist identisch mit TV-Datei" if content==on_disk
                    else "Abweichung zwischen ausgelieferter und lokaler JSON")
            except (OSError,ValueError) as e:
                add(label,"FEHLER",type(e).__name__)
        else:
            success="kabinenplan_tv_effective.json" in content
            add(label,"OK" if success else "FEHLER",
                "Neue Datenquelle wird ausgeliefert" if success else "Neuer Pfad im HTTP-HTML nicht gefunden")
    return 0

if __name__=="__main__":
    result=main()
    lines=["tus BERNE – Post-Installationsprüfung TV-Google-Kabinen",
           "Zeitpunkt: "+NOW.isoformat(),
           "Modus: vollständig lesend",
           "Funktionen: lokale Dateien, Dienste, sichere HTTP-Loopback-Prüfung",
           "TV-Bildschirm kann damit NICHT visuell bestätigt werden",
           ""]
    lines += [f"{status}: {name}: {detail}" for name,status,detail in checks]
    failures=sum(1 for _,status,_ in checks if status=="FEHLER")
    warnings=sum(1 for _,status,_ in checks if status=="WARNUNG")
    lines += ["",f"Fehler: {failures}; Warnungen: {warnings}",
              "Keine produktive Datei oder Dienst verändert"]
    text="\n".join(lines)+"\n"
    print(text[:1800])
    destination=Path(tempfile.gettempdir())/NAME
    destination.write_text(text,encoding="utf-8")
    try:
        p=subprocess.run(["rclone","copyto",str(destination),"gdrive:"+NAME,
                          "--drive-root-folder-id",FOLDER],
                         capture_output=True,timeout=120,check=False)
        if p.returncode:
            print("Drive-Upload fehlgeschlagen; lokaler Bericht:",destination)
            raise SystemExit(2)
        print("Bericht im privaten Google Drive / Entwicklung & Diagnose:",NAME)
    except (OSError,subprocess.TimeoutExpired):
        print("Drive-Upload fehlgeschlagen; lokaler Bericht:",destination)
        raise SystemExit(2)
    raise SystemExit(result if not failures else 1)
