#!/usr/bin/env python3
"""Repair exactly one divergent, auto-generated Pi publisher commit safely.

No hard reset, force push, production TV/Google modification, or unbacked
history loss. Refuse unexpected worktree/commit/files, back up local commit,
rebase onto current GitHub main and invoke the ORIGINAL publisher.
Results are written only to private "Entwicklung & Diagnose" Google Drive.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path("/home/kuhfi/tusberne-github-sync")
BACKUP=Path("/home/kuhfi/infoboard-app/backups/github-public-sync-recovery")
LOCK=Path.home()/".cache/tusberne-github-public-sync.lock"
KEY=Path.home()/".ssh/tusberne_github_deploy"
REMOTE="git@github.com:kuhfi/tusberne-infoboard.git"
FOLDER="17nIUUe6LAJYWsbe-hH4cKrruXSBp0SBI"
NOW=datetime.now(ZoneInfo("Europe/Berlin"))
REPORT_NAME="tusberne-github-publisher-reparatur-"+NOW.strftime("%Y%m%d-%H%M%S")+".txt"
EXPECTED="Sync public infoboard content from Raspberry Pi"
ALLOWED={"data/content.json","data/fussball_live_data.json",
         "data/kabinen_live_data.json","data/kabinen_auto_data.json",
         "data/training-berne.json","data/training-farmsen.json",
         "data/teams.json"}
LOG=["tus BERNE – vorsichtige GitHub-Publisher-Reparatur", NOW.isoformat(),
     "Keine Änderungen an Google-Daten, automatischem TV-Plan oder TV-Overlay."]

class Stop(RuntimeError): pass

def note(s):
    LOG.append(str(s))

def cmd(args,timeout=45,env=None,fail=False):
    try:
        result=subprocess.run(args,cwd=str(ROOT),text=True,errors="replace",
                              capture_output=True,timeout=timeout,env=env)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise Stop("Befehl "+str(args[:2])+" nicht ausführbar: "+type(e).__name__) from e
    if result.returncode and not fail:
        raise Stop("Befehl "+str(args[:2])+" fehlgeschlagen: rc="+str(result.returncode))
    return result

def git(*args,env=None,timeout=45,fail=False):
    return cmd(["git",*args],env=env,timeout=timeout,fail=fail)

def one(*args):
    return git(*args).stdout.strip()

def env_git():
    e=dict(os.environ)
    e["GIT_TERMINAL_PROMPT"]="0"
    e["GIT_SSH_COMMAND"]="ssh -i "+shlex.quote(str(KEY))+" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes"
    e["GIT_EDITOR"]="true"
    e["GIT_SEQUENCE_EDITOR"]="true"
    return e

def checkout_clean():
    if one("branch","--show-current")!="main":
        raise Stop("Nicht Branch main")
    if one("remote","get-url","origin")!=REMOTE:
        raise Stop("Git remote ist nicht das erwartete Projekt")
    if one("status","--porcelain","--untracked-files=normal"):
        raise Stop("Git-Arbeitskopie ist nicht sauber; STOPP ohne Datenänderung")
    for marker in ("rebase-apply","rebase-merge","MERGE_HEAD","CHERRY_PICK_HEAD"):
        if (ROOT/".git"/marker).exists():
            raise Stop("Git-Vorgang bereits offen: "+marker)

def google_current():
    store=Path("/var/lib/tusberne-kabinen/overrides.json")
    if not store.is_file() or store.is_symlink():
        raise Stop("Google-Override-Speicher fehlt")
    obj=json.loads(store.read_text(encoding="utf-8"))
    rev=int(obj.get("google_cabins_sync",{}).get("revisions",{}).get("2026-11-09",0))
    note("Private Google-Importrevision: "+str(rev))
    if rev<8: raise Stop("Google-Revision 8 auf dem Pi nicht vorhanden")

def reconcile():
    if ROOT.is_symlink() or not ROOT.is_dir(): raise Stop("Git-Repo fehlt")
    if not KEY.is_file(): raise Stop("Bisheriger GitHub-Deploy-Key fehlt")
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open("a+") as fh:
        try: fcntl.flock(fh, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise Stop("GitHub-Publisher ist bereits beschäftigt; nichts verändert") from e
        google_current()
        checkout_clean()
        old=one("rev-parse","HEAD")
        note("Git HEAD vor Reparatur: "+old)
        env=env_git()
        git("fetch","--quiet","origin","main",timeout=90,env=env)
        remote=one("rev-parse","refs/remotes/origin/main")
        note("Git origin/main nach Fetch: "+remote)
        if git("merge-base","--is-ancestor","origin/main","HEAD",fail=True).returncode==0:
            note("Git bereits kompatibel; kein Rebase notwendig")
            return
        if git("merge-base","--is-ancestor","HEAD","origin/main",fail=True).returncode==0:
            git("merge","--ff-only","origin/main",env=env,timeout=70)
            note("Fast-Forward von main erfolgreich")
            return
        count=int(one("rev-list","--count","origin/main..HEAD"))
        note("Lokale nicht publizierte Commits: "+str(count))
        if count!=1: raise Stop("Mehr als ein lokaler Commit; nur manuelle Prüfung möglich")
        subject=one("show","-s","--format=%s","HEAD")
        note("Letzter lokaler Commit: "+subject[:120])
        if subject!=EXPECTED: raise Stop("Unbekannter lokaler Commit-Typ; keine automatische Reparatur")
        parents=one("rev-list","--parents","-n","1","HEAD").split()
        if len(parents)!=2: raise Stop("Lokaler Commit ist kein normaler Einzelcommit")
        changed=[x for x in one("diff-tree","--no-commit-id","--name-only","-r","HEAD").splitlines() if x]
        forbidden=[x for x in changed if x not in ALLOWED and not x.startswith("files/")]
        note("Vom Pi-Commit berührte Dateien: "+", ".join(changed)[:1200])
        if not changed or forbidden:
            raise Stop("Lokaler Commit enthält fremde Dateien; NICHT automatisch ändern")
        BACKUP.mkdir(parents=True,exist_ok=True,mode=0o700)
        BACKUP.chmod(0o700)
        backup_ref="backup/tusberne-publisher-"+NOW.strftime("%Y%m%d-%H%M%S")
        git("branch",backup_ref,"HEAD")
        if one("rev-parse",backup_ref)!=old:
            raise Stop("Backup-Branch konnte nicht verifiziert werden")
        manifest=BACKUP/(NOW.strftime("%Y%m%d-%H%M%S")+"-original-commit.txt")
        manifest.write_text("Original commit: "+old+"\nBackup branch: "+backup_ref+
                            "\nRemote: "+remote+"\n\n"+"\n".join(changed)+"\n",
                            encoding="utf-8")
        manifest.chmod(0o600)
        note("UNVERÄNDERTE Sicherung des lokalen Originalcommits: "+backup_ref)
        note("Backup-Manifest: "+str(manifest))
        reb=git("-c","rebase.autoStash=false","rebase","origin/main",
                env=env,timeout=120,fail=True)
        if reb.returncode:
            aborted=git("rebase","--abort",env=env,fail=True)
            note("Rebase nicht konfliktfrei; Abbruchstatus: "+str(aborted.returncode))
            raise Stop("Rebase-Konflikt; lokale Commit-Sicherung erhalten, kein Push")
        checkout_clean()
        if one("rev-parse",backup_ref)!=old:
            raise Stop("Originalbackup wurde verändert; Publisher nicht gestartet")
        if git("merge-base","--is-ancestor","origin/main","HEAD",fail=True).returncode:
            raise Stop("Git-Historie nach Rebase ungültig")
        note("Git-Verlauf erfolgreich zusammengeführt.")
        note("Neuer HEAD: "+one("rev-parse","HEAD"))

def publish():
    note("Starte unveränderten bestehenden Publisher exakt einmal.")
    p=cmd(["bash","scripts/pi_public_publish.sh","--publish"],
          timeout=320,env=env_git(),fail=True)
    note("Publisher Rückgabecode: "+str(p.returncode))
    useful=re.compile(r"(?i)(KABINENPLAN|Kabinenplan|Änderung|Aenderung|Commit|commit|Synchronisierung|GitHub|push|WARNUNG|STOPP|Arbeitskopie|fatal:)")
    private=re.compile(r"(?i)(password|bearer|secret|token|credential|private.key)")
    lines=[x[:250] for x in (p.stdout+"\n"+p.stderr).splitlines() if useful.search(x) and not private.search(x)]
    for x in lines[-28:]: note("  "+x)
    try:
        doc=json.loads((ROOT/"data/kabinen_live_data.json").read_text(encoding="utf-8"))
        meta=doc.get("manual_weeks",{}).get("2026-11-09",{})
        games=[g for g in doc.get("games",[]) if
               g.get("date")=="2026-11-15" and g.get("time")=="13:00" and
               g.get("home")=="tus BERNE 7.D (J4)" and g.get("away")=="Concordia 3.D (J2)"]
        observed=games[0].get("sr_cabin") if len(games)==1 else "nicht eindeutig"
        note("Lokale GitHub-Arbeitskopie Revision: "+str(meta.get("revision"))+
             ", Modus "+str(meta.get("mode"))+", Testspiel-SR "+str(observed))
        valid=meta.get("revision")==8 and meta.get("mode")=="partial" and observed=="SR2"
    except (OSError,ValueError,TypeError) as e:
        note("Lokale Exportprüfung fehlgeschlagen: "+type(e).__name__)
        valid=False
    if p.returncode:
        raise Stop("Publisher hat Fehler gemeldet; regelmäßiger Timer bleibt aktiv")
    if not valid:
        raise Stop("Export Revision 8, SR2 noch nicht bestätigt")
    note("Lokaler Export erfolgreich: Revision 8 / SR2. GitHub-Webdarstellung noch separat zu prüfen.")

def report():
    path=Path(tempfile.gettempdir())/REPORT_NAME
    path.write_text("\n".join(LOG)+"\n",encoding="utf-8")
    try:
        p=subprocess.run(["rclone","copyto",str(path),"gdrive:"+REPORT_NAME,
                          "--drive-root-folder-id",FOLDER],
                         capture_output=True,timeout=120)
        print("Bericht privat hochgeladen: "+REPORT_NAME if p.returncode==0
              else "Bericht nur lokal: "+str(path))
    except (OSError,subprocess.TimeoutExpired):
        print("Bericht nur lokal: "+str(path))

def main():
    result=0
    try:
        reconcile()
        publish()
        note("ERGEBNIS: Automatische GitHub-Publikation ausgeführt; lokaler Revision-8-Export bestätigt.")
        print("Reparaturlauf abgeschlossen. Bitte privaten Bericht prüfen.")
    except Stop as e:
        note("ERGEBNIS: Sichere Unterbrechung: "+str(e))
        print("STOPP: "+str(e),file=sys.stderr)
        result=1
    except Exception as e:
        note("ERGEBNIS: Unerwarteter Fehler: "+type(e).__name__)
        print("STOPP: "+type(e).__name__,file=sys.stderr)
        result=1
    report()
    return result

if __name__=="__main__":
    raise SystemExit(main())
