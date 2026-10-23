#!/usr/bin/env bash
# tus BERNE - rein lesender Systemstatus des Raspberry Pi.
# Keine Neustarts, keine Dateiaenderungen, kein Git-Push.
set -u
export LC_ALL=C
APP=/home/kuhfi/infoboard-app
REPO=/home/kuhfi/tusberne-github-sync
TILES="$APP/public/portrait-content"
heading() { printf '\n=== %s ===\n' "$1"; }
heading 'System'
date '+Zeit: %Y-%m-%d %H:%M:%S %Z'
uptime -p
df -h / | tail -n 1

heading 'Autostart / aktive Timer'
for t in berne-portrait-sync.timer berne-github-public-sync.timer berne-fussballraum-live.timer berne-tv-schedule.timer; do
  state=$(systemctl show "$t" -p LoadState --value 2>/dev/null || true)
  if [ "$state" = not-found ] || [ -z "$state" ]; then
    echo "$t: nicht gefunden (ggf. anderer Unit-Name)"
  else
    echo "$t: aktiviert=$(systemctl is-enabled "$t" 2>/dev/null || echo '?') aktiv=$(systemctl is-active "$t" 2>/dev/null || echo '?')"
  fi
done
echo 'Weitere berne-Timer und letzte/naechste Ausfuehrung:'
systemctl list-timers --all --no-pager 2>/dev/null | grep -E 'berne-|NEXT|LAST' || true

heading 'Letzte Service-Ergebnisse (inactive bei oneshot normal)'
systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null |
  awk '$1 ~ /^berne-/ {print $1}' |
  while read -r service; do
    result=$(systemctl show "$service" -p Result --value 2>/dev/null || true)
    code=$(systemctl show "$service" -p ExecMainStatus --value 2>/dev/null || true)
    echo "$service: Ergebnis=$result Exit=$code"
  done

heading 'Lokaler Drive-Abgleich'
python3 - "$TILES" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
root=Path(sys.argv[1])
now=datetime.now(timezone.utc)
for name in ['manifest.json','drive-publication-verified.json']:
    p=root/name
    if not p.is_file():
        print('WARNUNG:',name,'fehlt')
        continue
    age=(now-datetime.fromtimestamp(p.stat().st_mtime,timezone.utc)).total_seconds()/60
    print(f'{name}: Alter {age:.0f} Minuten')
m=root/'manifest.json'; p=root/'drive-publication-verified.json'
if m.is_file():
    try:
        obj=json.loads(m.read_bytes())
        print('Kacheln:',', '.join(f'{i}={len(obj["tiles"][i])}' for i in '1234'))
    except (ValueError,KeyError,TypeError):
        print('WARNUNG: Manifest unvollstaendig/ungueltig')
if m.is_file() and p.is_file():
    try:
        proof=json.loads(p.read_text())
        when=datetime.fromisoformat(proof['completed_at'].replace('Z','+00:00'))
        age=(now-when).total_seconds()/60
        digest=hashlib.sha256(m.read_bytes()).hexdigest()
        valid=(proof.get('schema_version')==1 and proof.get('source')=='google-drive'
               and proof.get('status')=='complete' and
               proof.get('manifest_sha256')==digest and 0<=age<=45)
        print('Drive-Loeschnachweis:', 'OK' if valid else 'NICHT AKTUELL / UNGUELTIG',
              f'({age:.0f} min)')
    except (ValueError,KeyError,TypeError,AttributeError):
        print('WARNUNG: Drive-Nachweis nicht auswertbar')
PY
for f in "$APP/public/cache/teams.json" \
         "$APP/public/fussball-live/fussball_live_data.json" \
         "$APP/public/kabinen-live/kabinenplan_data.json"; do
  if [ -f "$f" ]; then
    stat -c '%y | %n' "$f" | cut -c1-130
  else
    echo "WARNUNG: Datei fehlt: $f"
  fi
done

heading 'GitHub-Export (nur lokale Remote-Kopie)'
if [ -d "$REPO/.git" ]; then
  git -C "$REPO" log -1 --format='Letzter Commit: %h | %ci | %s'
  echo "Branch: $(git -C "$REPO" branch --show-current)"
  if [ -z "$(git -C "$REPO" status --porcelain)" ]; then
    echo 'Arbeitskopie: sauber'
  else
    echo 'WARNUNG: Arbeitskopie mit Aenderungen:'
    git -C "$REPO" status --short | head -n 8
  fi
  if git -C "$REPO" rev-parse --verify -q origin/main >/dev/null; then
    echo 'Rueckstand/Vorsprung gegen lokal gespeichertes origin/main (kein Netzabruf):'
    git -C "$REPO" rev-list --left-right --count origin/main...HEAD
  fi
else
  echo "WARNUNG: Git-Checkout fehlt: $REPO"
fi

heading 'Letzte Warnungen der beiden Sync-Dienste'
for s in berne-portrait-sync.service berne-github-public-sync.service; do
  echo "-- $s --"
  journalctl --no-pager --since '48 hours ago' -p warning -n 5 -u "$s" 2>/dev/null || true
done

heading 'Backup-Kandidaten im Home-Verzeichnis'
find "$HOME" -maxdepth 5 -type f \
  \( -iname '*.img' -o -iname '*.img.gz' -o -iname '*.img.xz' -o -iname '*.tar.gz' -o -iname '*backup*' \) \
  -printf '%TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort -r | head -n 12
echo 'HINWEIS: Externe Sicherungen und Ruecksicherbarkeit sind so nicht pruefbar.'
echo 'Systemstatus beendet: keinerlei Aenderungen ausgefuehrt.'
