#!/usr/bin/env bash
# tus BERNE - Veröffentlicht ausschließlich freigegebene Kachel-Bilder und die
# für GitHub bereinigten Fußball-/Kabinendaten. Pi-Anzeige nicht verändern.
# Ohne --publish: nur Probelauf, weder Commit noch Push.
set -Eeuo pipefail
umask 077

MODE="--dry-run"
if [[ "$#" -gt 0 ]]; then MODE="$1"; fi
if [[ "$MODE" != "--dry-run" && "$MODE" != "--publish" ]]; then
  echo "Aufruf: $0 [--dry-run|--publish]" >&2
  exit 2
fi

REPO="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$REPO"
SSH_KEY="$HOME/.ssh/tusberne_github_deploy"
EXPECTED_REPO="git@github.com:kuhfi/tusberne-infoboard.git"
if [[ "$(git remote get-url origin)" != "$EXPECTED_REPO" ]]; then
  echo "STOPP: Unbekanntes Git-Repository." >&2
  exit 1
fi
if [[ ! -r "$SSH_KEY" ]]; then
  echo "STOPP: GitHub-Deploy-Key nicht gefunden." >&2
  exit 1
fi

# Eigene Sperre, unabhängig von den produktiven Pi-Diensten.
LOCK_DIR="$HOME/.cache"
mkdir -p "$LOCK_DIR"
exec 9>"$LOCK_DIR/tusberne-github-public-sync.lock"
if ! flock -n 9; then
  echo "Ein anderer GitHub-Synchronisierungslauf ist noch aktiv."
  exit 0
fi

echo "=== tus BERNE GitHub-Synchronisierung: $MODE ==="
date '+Zeit: %Y-%m-%d %H:%M:%S %Z'
if [[ "$MODE" == "--dry-run" ]]; then
  python3 scripts/pi_public_sync.py
  python3 scripts/pi_cabins_export.py
  # Trainingsplaene getrennt pruefen: ein fehlerhaftes HTML darf die
  # Bild-, Fussball- und Kabinenaktualisierung nicht blockieren.
  if ! python3 scripts/pi_training_export.py; then
    echo "WARNUNG: Trainingsplaene voruebergehend nicht lesbar." >&2
  fi
  if ! python3 scripts/pi_teams_export.py; then
    echo "WARNUNG: Mannschaftsdaten voruebergehend nicht lesbar." >&2
  fi
  echo "Probelauf abgeschlossen. Keine lokalen Inhaltsänderungen und kein Upload."
  exit 0
fi

# Fremde oder unterbrochene Bearbeitungen niemals überschreiben/mitveröffentlichen.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "STOPP: Die Git-Arbeitskopie enthaelt bereits Aenderungen." >&2
  echo "Bitte erst git status --short pruefen; es wurden keine Dateien veraendert." >&2
  exit 1
fi
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "STOPP: Erwarteter Git-Branch 'main' nicht ausgecheckt." >&2
  exit 1
fi

export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes"
echo "=== GitHub-Stand abrufen ==="
git fetch --quiet origin main
git merge --ff-only origin/main

echo "=== Freigegebene Inhalte vorbereiten ==="
python3 scripts/pi_public_sync.py --apply
# Erst nach erfolgreicher, datensparsamer Kabinenplan-Erzeugung wird
# der neue Link in Kachel 2 freigeschaltet.
python3 scripts/pi_cabins_export.py --apply

# Die Trainingsplaene stammen aus den unveraenderten Pi-HTML-Dateien in Kachel 1.
# Beide Plaene werden zuerst gemeinsam geprueft. Bei Fehlern die alten,
# bereits veroeffentlichten Plaene behalten und andere Kacheln weiter pflegen.
if python3 scripts/pi_training_export.py --apply &&
   python3 -m json.tool data/training-berne.json >/dev/null &&
   python3 -m json.tool data/training-farmsen.json >/dev/null; then
  echo "Trainingsplaene fuer die Homepage erfolgreich geprueft."
else
  # Zu Beginn war die Git-Arbeitskopie sauber; daher darf nur diese
  # optionale Dateigruppe auf die bekannte Version zurueckgesetzt werden.
  git restore --worktree -- data/training-berne.json data/training-farmsen.json
  echo "WARNUNG: Trainingsplan-Export fehlgeschlagen; vorige Homepage-Plaene bleiben." >&2
fi

# Kachel 4: Die bereits vorhandene Pi-Zwischenspeicherung enthaelt alle
# oeffentlich freigegebenen Mannschaften, Trainer-Kontakte und Trainingszeiten.
# Nur nach vollstaendiger Plausibilitaetspruefung neue JSON-Daten publizieren
# und den Homepage-Link auf die eigene mobile Mannschaftsseite umstellen.
if python3 scripts/pi_teams_export.py --apply; then
  python3 -m json.tool data/teams.json >/dev/null
  echo "Mannschaftsuebersicht aus dem Pi-Cache vorbereitet."
else
  echo "WARNUNG: Mannschaftsdaten nicht lesbar; bestehende Ansicht bleibt." >&2
fi
python3 -m json.tool data/content.json >/dev/null
python3 -m json.tool data/fussball_live_data.json >/dev/null
python3 -m json.tool data/kabinen_live_data.json >/dev/null

# Die Arbeitskopie war vorher sauber. Es werden nur ausdruecklich
# freigegebene Homepage-Dateien uebertragen. Keine Pi-Quelle wird veraendert.
git add -A -- data/content.json data/fussball_live_data.json data/kabinen_live_data.json \
  data/training-berne.json data/training-farmsen.json files/
# Bei einem voruebergehenden Ausfall der Pi-Teams-Datei ist teams.json
# moeglicherweise noch nicht angelegt. In diesem Fall trotzdem alle anderen
# Kacheln ohne Git-Pathspec-Fehler aktualisieren.
if [[ -f data/teams.json ]]; then
  git add -- data/teams.json
fi
git diff --cached --check

if git diff --cached --quiet; then
  echo "Keine oeffentlichen Inhaltsaenderungen. Kein Commit erforderlich."
  exit 0
fi

echo "=== Freigegebene Dateien fuer den Upload ==="
git diff --cached --stat
git commit -m "Sync public infoboard content from Raspberry Pi"
echo "=== Zu GitHub uebertragen ==="
git push origin HEAD:main
echo "Synchronisierung erfolgreich: $(git log -1 --format='%h %s')"
