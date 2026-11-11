# tus BERNE – Mobile Kabinenverwaltung über Google Sheets

Stand: 11.11.2026 – **Google-Web-App bereitgestellt und Speicher-/Sperrtests erfolgreich**, Raspberry-Pi-Google-Synchronisierung noch NICHT aktiviert. Testdaten in Google sind auf Automatik, Revision 6, zurückgesetzt.

## Was wurde bereits angelegt?

- Private native Google-Tabelle **tus BERNE – Kabinenverwaltung (Daten)**:
  https://docs.google.com/spreadsheets/d/1U8PoGl6_vGeLxFBryIL0JVBZPw9RAtFnHbQeoov_spc/edit
- Tabellenblätter: `Wochen`, `Einzelkorrekturen`, `Fixierte_Spiele`, `Protokoll`, `Hinweise`.
- Eigentümer ist das verbundene Google-Konto; bei Prüfung am 11.11. war die Tabelle **nicht geteilt**.
- Öffentliche, bereinigte Automatik-Anzeige als Lesemodell:
  https://kuhfi.github.io/tusberne-infoboard/data/kabinen_auto_data.json
- Quellcode im GitHub-Repository `kuhfi/tusberne-infoboard`.
- Kein Login-Schlüssel oder Service-Account im Repository, keine Zugangsdaten in der Tabelle.

## Teil 1: Google-Web-App über den PC veröffentlichen (ohne Raspberry Pi)

1. Obige Google-Tabelle mit dem passenden Google-Konto öffnen.
2. **Erweiterungen → Apps Script** öffnen. In `Code.gs` den gesamten Inhalt von
   `apps_script/Code.gs` aus dem GitHub-Projekt einfügen und speichern.
3. Im Apps-Script-Editor über **Dateien → + → HTML** die Datei **Index** (genau so, ohne `.html` bei der Namenseingabe) anlegen.
   Den Inhalt von `apps_script/Index.html` einfügen und speichern.
4. Unter den Projekteinstellungen die Manifestdatei `appsscript.json` einblenden und nach Sichtprüfung die bereitgestellte
   Fassung aus `apps_script/appsscript.json` übernehmen. Sie enthält die Google-Sheets- und UrlFetch-Rechte sowie
   `MYSELF` und `USER_DEPLOYING`.
5. Über **Bereitstellen → Neue Bereitstellung → Web-App** auswählen.
   - **Ausführen als:** Ich.
   - **Zugriff:** Nur ich / Only myself.
   - Autorisierung durch dasselbe Google-Konto durchführen.
6. Die Web-App wurde am 11.11.2026 bereits bereitgestellt. Die private `/exec`-Adresse liegt dem Betreiber vor; sie wird nicht in diesem öffentlichen Repository dokumentiert.
7. Bereits durchgeführt: Einzelkorrektur, kompletter Wochen-Lock und Rückkehr zur Automatik. Letzte Google-Revision 6, Modus automatic. Die Pi-Übernahme folgt in Teil 2.

**Bei späteren Codeänderungen**: Unter Bereitstellen → Bereitstellungen verwalten dieselbe Bereitstellung mit einer neuen Version aktualisieren,
damit der Link stabil bleibt. Nie "Jeder mit dem Link" für diese Bearbeitungsseite aktivieren.

## Teil 2: Raspberry Pi – nur nach Fernzugriff und Bestandsaufnahme

Zuerst unverändernde Diagnose, aktuellen Git-Stand und produktive Dienste prüfen:

```bash
cd /home/kuhfi/tusberne-github-sync || exit 1
hostname
python3 --version
git status --short
git log -1 --oneline
systemctl is-active berne-infoboard.service berne-github-public-sync.timer
ls -l /home/kuhfi/infoboard-app/public/kabinen-live/kabinenplan_data.json
```

**Vor dem Update:** Sicherung der Git-Arbeitskopie und der privaten bestehenden Konfiguration anlegen.
Bei vorhandenen unveröffentlichten Änderungen **nicht** `git reset --hard` verwenden.
Erst bei sauberem Arbeitsverzeichnis:

```bash
cd /home/kuhfi/tusberne-github-sync
# nur nach Sicherung und Prüfung:
git fetch origin main
git merge --ff-only origin/main
python3 -m unittest discover -s tests -p 'test_google_cabins_sync.py' -v
python3 scripts/pi_cabins_export.py   # DRY RUN
```

### Empfohlener Pi-Zugang: vorhandenes rclone (bereits festgestellt)

**Stand 11.11.2026:** Auf dem Pi sind `rclone v1.60.1-DEV`, Remote `gdrive:`
und `openpyxl 3.1.5` vorhanden. Der private Sheet-Export ist sichtbar unter
`gdrive:ChatGPT/tus BERNE – Kabinenverwaltung (Daten).xlsx`.
Ein neues Servicekonto und `google-auth` sind für diesen Pfad **nicht erforderlich**.

Das folgende Kommando ist ein **reiner Probelauf**, der aus Google liest,
Tabellenblätter und Spalten prüft und **keine lokale Datei verändert**:

```bash
cd /home/kuhfi/tusberne-github-sync || exit 1
git status --short
# Nur bei sauberem Arbeitsverzeichnis nach vorheriger Sicherung:
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_google_cabins_sync.py' -v
python3 scripts/pi_google_cabins_sync.py \
  --rclone-path "gdrive:ChatGPT/tus BERNE – Kabinenverwaltung (Daten).xlsx"
```

Erst wenn der Probeabruf die erwartete **Google-Version 6 und Automatik**
meldet und die local store / Export-Umgebung geprüft wurde,
den systemd-Dienst mit `deploy/systemd/cabins-google-sync.env.example`
vorbereiten. Der Dienst nutzt jetzt `/usr/bin/python3` und die
private `~/.config/rclone`-Anmeldung. Die Unit darf allein
`/var/lib/tusberne-kabinen` und `~/.config/rclone` verändern,
weil rclone bei Bedarf ein OAuth-Refresh-Token aktualisiert.
Vollständigen Betrieb/TV-Anzeige vor dem Aktivieren kontrollieren.

```bash
sudo install -d -o root -g kuhfi -m 0750 /etc/tusberne
sudo install -o root -g kuhfi -m 0640 deploy/systemd/cabins-google-sync.env.example /etc/tusberne/cabins-google-sync.env
sudo install -o root -g root -m 0644 deploy/systemd/berne-cabins-google-sync.service /etc/systemd/system/
sudo install -o root -g root -m 0644 deploy/systemd/berne-cabins-google-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start berne-cabins-google-sync.service
systemctl status berne-cabins-google-sync.service --no-pager
# Timer erst nach erfolgreichem Lese- und Publikationstest einschalten:
# sudo systemctl enable --now berne-cabins-google-sync.timer
```

### Alternativer Google-Lesezugang – nur falls rclone nicht funktioniert



Die Python-Synchronisierung verwendet `https://www.googleapis.com/auth/spreadsheets.readonly`.
Sie benötigt auf dem Pi eine **private JSON-Credentialdatei**, die nicht nach GitHub gehört.

**Bevorzugt:** Falls die bisherige Google-Anbindung des Pi bereits passende OAuth-Zugangsdaten für
Sheets bereitstellt, diese nach Prüfung wiederverwenden. **Alternativ:** Im eigenen Google-Cloud-Projekt
Sheets API aktivieren, ein dediziertes Servicekonto erstellen, ein JSON-Credential ausgeben,
und **nur dieser** Google-Tabelle für die Servicekonto-E-Mail **Leser**-Zugriff geben.
Dieser Cloud-Schritt ist noch offen. Den geheimen JSON-Schlüssel ausschließlich über den
bereits sicheren Fernzugriff auf den Pi übertragen, nicht in ChatGPT oder GitHub hochladen.

Beispielhafte Pi-Zielpfade (vor Ort prüfen):

- Credentials: `/etc/tusberne/cabins-google-reader.json` (root:kuhfi, 0640)
- Umgebungsdatei: `/etc/tusberne/cabins-google-sync.env`
- Lokaler Korrekturspeicher: `/var/lib/tusberne-kabinen/overrides.json`
- Virtualenv: `/home/kuhfi/.venvs/tusberne-cabins-google`

Nach der Sichtprüfung:

```bash
python3 -m venv /home/kuhfi/.venvs/tusberne-cabins-google
/home/kuhfi/.venvs/tusberne-cabins-google/bin/pip install google-auth requests
# Credentials über sicheren Weg ablegen; Zugriffsrechte manuell kontrollieren.
# Umgebungsdatei nach Beispiel deploy/systemd/cabins-google-sync.env.example erstellen.
/home/kuhfi/.venvs/tusberne-cabins-google/bin/python scripts/pi_google_cabins_sync.py
# Erst NACH erfolgreichem Probelauf: --apply
```

Erst nach erfolgreichem Probelauf und Kontrolle der bestehenden lokalen Änderungen:

```bash
sudo cp deploy/systemd/berne-cabins-google-sync.service /etc/systemd/system/
sudo cp deploy/systemd/berne-cabins-google-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now berne-cabins-google-sync.timer
systemctl list-timers berne-cabins-google-sync.timer --no-pager
```

**Wichtig:** Die alte, noch nicht produktiv eingerichtete lokale Kabinen-Admin-Anwendung
`berne-cabins-admin.service` nicht aktivieren. Sie soll durch Google ersetzt werden.
Die lokale Pi-Infoboard-Anwendung könnte bereits Port 8765 verwenden.

## Teil 3: Abnahme nach der Aktivierung

1. In der Google-Web-App eine Gastkabine ändern, speichern und die neue Google-Version prüfen.
2. Prüfen, ob der Pi nach dem Abruf `overrides.json` mit genau dieser Version befüllt.
3. Prüfen, dass der reguläre GitHub-Abgleich weiterhin funktioniert.
4. Öffentliche Kabinenanzeige kontrollieren:
   https://kuhfi.github.io/tusberne-infoboard/files/kabinen-belegungsplan.html
5. Die Web-App meldet `Auf Infoboard veröffentlicht` erst, wenn die öffentliche JSON die Google-Version bestätigt.
6. Ganze Woche sperren, eine zusätzliche Ansetzung simulieren, Sperre aufheben und die Automatik kontrollieren.
7. Wochenwechsel prüfen (Korrekturen der Vorwoche dürfen nicht auf die neue Woche übergehen).
8. Prüfen, ob die **separate Anzeige auf dem TV** dieselben wirksamen Zuordnungen verwendet. Dieser Datenfluss ist noch offen.

## Sicherheit und Fehlerbehandlung

- Web-App ausschließlich als Eigentümer und mit Zugriff **Nur ich** bereitstellen.
- Die private Tabelle bleibt privat; Servicekonto erhält nur **Leser**-Zugriff.
- Schreibvorgänge erfolgen mit `LockService`; neue Revision wird erst nach allen Detailzeilen geschrieben.
- Pi übernimmt nur vollständige Revisionen mit passender Zeilenanzahl.
- Bei Google-Ausfall, ungültigen Daten oder unbekanntem lokalen Altstand wird der lokale Korrekturstand NICHT überschrieben.
- Jede lokale Änderung schreibt zuvor ein `.bak`-Backup; in Google bleiben frühere Revisionen erhalten.
- Originalautomatik wird durch die neue Google-Verwaltung nicht verändert.
- Automatischer Pi-Abgleich ist auf 3 Minuten, öffentlicher GitHub-Abgleich auf ca. 10 Minuten ausgelegt; das ist kein garantierter Echtzeitwert.
- Die bestehende Raumbelegung über Google Kalender bleibt unberührt.