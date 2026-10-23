# tus BERNE – Digitales Fußball-Infoboard und QR-Code-Homepage

**EINMAL BERNE IMMER BERNE**

Öffentliche, mobilfreundliche Ergänzung zum digitalen Infoboard der Fußballabteilung **tus BERNE**.

- **Homepage:** https://kuhfi.github.io/tusberne-infoboard/
- **Mannschaften:** https://kuhfi.github.io/tusberne-infoboard/files/mannschaften.html
- **Repository:** https://github.com/kuhfi/tusberne-infoboard
- **Produktivzweig:** `main`
- **Dokumentationsstand:** 23.10.2026

> **Wichtig:** Die öffentliche GitHub-Pages-Homepage und die Anzeige auf dem Raspberry-Pi-Fernseher sind getrennte Systeme. Dieses Repository enthält ausschließlich die öffentliche Website und ihre Exportprogramme. Es ist **kein vollständiges Abbild der Pi-Konfiguration**.

## Aktueller Projektstand

Die Website läuft produktiv und wird vom Raspberry Pi automatisch mit freigegebenen Informationen versorgt. Die Gestaltung ist blau-weiß (Vereinsblau `#0055A5`), nutzt das originale Vereinslogo und den Vereinsslogan. Die Startseite besitzt **vier Bereiche**, aber **keine Suchfunktion**. Für den Zugang vor Ort wurde ein separater QR-Code-Aushang gestaltet; ob und wo er bereits montiert ist, wird hier nicht vorausgesetzt.

Die Anzahl und Auswahl der Inhalte verändern sich durch die Synchronisierung. Maßgeblich ist stets [`data/content.json`](data/content.json), **nicht** eine fest eingetragene Anzahl in dieser README.

| Bereich | Öffentlich sichtbare Inhalte und Quellen |
| --- | --- |
| **1 – Training** | Trainingspläne Berner Allee und „3 für FARBE“ (Farmsen) aus den bestehenden Pi-HTML-Dateien; freigegebene Trainingsgrafiken. |
| **2 – Belegung** | Kabinenbelegungsplan für Heimspiele, verlinkte Fußballraumbelegung und Kabinenzuordnung für das Training. Der Kabinenplan startet immer auf **Seite/Woche 1**, auch wenn keine Spiele eingetragen sind. |
| **3 – Tabellen / News** | Interaktive Fußballtabellen sowie freigegebene Bilder und optional PDF-Dokumente. Die festgelegte Reihenfolge wird mit `order` in `data/content.json` gesteuert. **Keine Wetterseite auf der Homepage.** |
| **4 – Mannschaften / Ansprechpartner** | Foto der Abteilungsleitung und eigene mobilfreundliche Mannschaftsübersicht mit freigegebenen Kontakten und Trainingszeiten. Quelle: https://tusberne-fussball.de/teams/; im Praxistest wurden 23 Mannschaften übernommen. |

Die Reihenfolge in **Tabellen / News** beginnt mit Fußballtabellen, gefolgt von Schiedsrichterkosten, Notfallfortbildung (09.01.2027), Jahresauftaktessen (22.01.2027), Dachwarnung, mobiler Sitzbank und Sternenbrücke. Die tatsächlich noch veröffentlichten Einträge stehen im Inhaltsverzeichnis; abgelaufene Termine/Grafiken müssen an der Quelle gepflegt bzw. entfernt werden.

## Datenfluss und automatische Aktualisierung

```text
Google Drive (vier öffentliche Kachelordner) ──┐
                                               ├──> Raspberry Pi
Öffentliche Vereins-/Spieldaten ───────────────┘       │
                                                       │ geprüfte Exporte
                                                       v
                                    Git-Arbeitskopie -> GitHub main
                                                          │
                                                          v
                                                    GitHub Pages
                                                          │
                                                          v
                                                QR-Code-Homepage
```

Die bestehenden Datenquellen und die lokale Pi-Anzeige werden durch den GitHub-Export nicht umgebaut.

### Google Drive → Pi

- Quellstruktur: Drive-Ordner `tus-BERNE-Infoboard-Hochkant` mit `Kachel1` bis `Kachel4`. Bei gleichnamigen alten Drive-Ordnern muss die **tatsächlich produktive Quelle** geprüft werden.
- Zuständig: `berne-portrait-sync.timer` / `berne-portrait-sync.service` (Solltakt ca. **2 Minuten**).
- Das bestehende Pi-Skript `portrait-drive-sync.sh` synchronisiert die Kacheln und schreibt `portrait-content/manifest.json`.
- Danach prüft `scripts/pi_drive_attest.py` bei vollständigem Abgleich die Bilder/PDFs gegen Drive und erzeugt die Bestätigung `drive-publication-verified.json`.

### Pi → GitHub → Homepage

- Zuständig: `berne-github-public-sync.timer` / `berne-github-public-sync.service` (Solltakt ca. **10 Minuten**).
- Einstiegspunkt: `scripts/pi_public_publish.sh`. Im Standardmodus `--dry-run` werden nur Exporte geprüft; `--publish` ist der produktive Veröffentlichungsmodus.
- Das Skript prüft Git-Arbeitskopie und `main`, holt den GitHub-Stand per Fast-Forward, erstellt die freigegebenen Inhalte und führt **nur bei Änderungen** Commit/Push aus.
- Nach einem fehlgeschlagenen Push werden **lokal ausstehende Commits** beim nächsten geeigneten Lauf erneut hochgeladen, auch ohne neue Inhaltsänderung.
- Veröffentlichte Homepage: **GitHub Pages** aus `main` / Repository-Wurzel.

| Exportskript | Aufgabe |
| --- | --- |
| `scripts/pi_public_sync.py` | Freigegebene Bilder/PDFs aus den Kacheln und bereinigte Fußballtabellen |
| `scripts/pi_drive_attest.py` | Vollständigkeitsnachweis für den Drive-Abgleich |
| `scripts/pi_training_export.py` | Trainingspläne Berne/Farmsen als JSON |
| `scripts/pi_cabins_export.py` | Öffentlicher Kabinenplan ohne interne Berechnungs-/Quelldetails |
| `scripts/pi_teams_export.py` | Mannschaften, Ansprechpartner und Trainingszeiten aus dem Pi-Cache |
| `scripts/pi_public_publish.sh` | Plausibilitätsprüfung, Git-Abgleich, Commit und Push |

### Sicherheits- und Fehlergrenzen

- **Nur freigegebene, ausdrücklich öffentliche Inhalte** dürfen exportiert werden. Kein Export von Zugangsdaten, internen Raumkalendern oder privaten Konfigurationsdateien.
- Eine bereits veränderte Git-Arbeitskopie oder ein unerwarteter Branch führt zum **Abbruch statt Überschreiben**; bei Blockaden zuerst Ursache anhand des Git-Status prüfen.
- JSON-, Tabellen-, Trainingsplan- und Mannschaftsdaten werden vor der Veröffentlichung plausibilisiert. Bei bestimmten fehlerhaften Einzelquellen bleiben die zuletzt veröffentlichten Daten erhalten.
- **Löschschutz:** Automatisches Entfernen aus dem öffentlichen Index erfordert einen vollständigen, zur Manifest-Prüfsumme passenden Google-Drive-Nachweis (maximal **45 Minuten** alt). Mehr als **3 Löschungen** pro Dateityp/Abgleich werden blockiert. Bei fehlendem Nachweis bleiben frühere öffentliche Einträge erhalten.
- Unterstützte Uploadformate: `png`, `jpg`, `jpeg`, `webp` (max. **15 MiB**) und `pdf` (max. **20 MiB**). Allgemeine HTML-Dateien aus den Kacheln werden **nicht** pauschal öffentlich kopiert; Trainingspläne werden gesondert exportiert.
- Wenn GitHub nicht erreichbar ist, bleibt die bereits veröffentlichte Homepage auf ihrem vorherigen Stand; der Pi-Exporter verändert die laufende TV-Anzeige nicht. Das **vollständige** Verhalten bei längeren Netzwerk-/Google-Drive-Ausfällen ist noch nicht kontrolliert getestet.

## Projektdateien

| Pfad im Repository | Bedeutung |
| --- | --- |
| `index.html` | Startseite mit vier auswählbaren Bereichen (ohne Suche) |
| `assets/styles.css`, `assets/app.js` | Design, Filter, sichere Linkbehandlung |
| `assets/tus-berne-logo.svg` | Originales Vereinslogo für die Homepage |
| `data/content.json` | Öffentliches Inhaltsverzeichnis, Reihenfolge und Links |
| `data/training-berne.json`, `data/training-farmsen.json` | Exportierte Trainingspläne |
| `data/fussball_live_data.json` | Bereinigte Fußball-Livedaten |
| `data/kabinen_live_data.json` | Öffentliche Kabinenbelegung |
| `data/teams.json` | Freigegebene Mannschafts- und Kontaktdaten |
| `files/trainingsplan.html`, `files/kabinen-belegungsplan.html`, `files/fussball-tabellen.html`, `files/mannschaften.html` | Mobilfreundliche Unterseiten |
| `files/` | Öffentliche Grafiken, PDFs und weitere veröffentlichte Dateien |
| `scripts/pi_system_status.sh`, `scripts/pi_status_ampel.py` | Rein lesende Diagnose auf dem Raspberry Pi |
| `tests/` | Automatisierte Offline-/Regressionstests |

## Betrieb und Diagnose auf dem Raspberry Pi

Beim Systemcheck vom **23.10.2026, 11:55 Uhr (CEST)** waren **12/12 erwartete Timer aktiv**, die überprüften Dienste erfolgreich, der Drive-Abgleich frisch, die lokale Git-Arbeitskopie sauber und die SD-Karte zu **28 %** belegt. Das ist eine **Momentaufnahme**, keine permanente Überwachung.

Die Pi-Anzeige wird über `berne-infoboard.service` betrieben; am 23.10. war sie aktiv, für den Autostart aktiviert und mit `Restart=always` konfiguriert. Der ältere `berne-drive-sync.timer` war **deaktiviert** und wird nicht zusätzlich aktiviert.

### Kompakte Ampel (nur lokal, nicht auf TV oder Homepage)

```bash
python3 -B /home/kuhfi/tusberne-github-sync/scripts/pi_status_ampel.py
```

Ausgabe in **GRUEN**, **GELB** oder **ROT** für TV-Dienst, Timer, Synchronisierung, Datenaktualität, Git-Arbeitskopie, Backups und SD-Speicher. Am 23.10. bestanden **11/11 zugehörige Offline-Tests**; der lokale Praxislauf lieferte **10/10 GRUEN**. Die Ampel fragt GitHub nicht live ab und kontrolliert nicht das tatsächliche TV-Bild.

### Ausführliche, ebenfalls rein lesende Diagnose

```bash
bash /home/kuhfi/tusberne-github-sync/scripts/pi_system_status.sh
```

Weitere gezielte, lesende Befehle:

```bash
systemctl list-timers --all --no-pager
systemctl status berne-infoboard.service --no-pager
systemctl status berne-portrait-sync.service --no-pager
systemctl status berne-github-public-sync.service --no-pager
journalctl -u berne-portrait-sync.service --since "today" --no-pager -n 50
journalctl -u berne-github-public-sync.service --since "today" --no-pager -n 50
git -C /home/kuhfi/tusberne-github-sync status --short
```

Ein `inactive` bei erfolgreich abgeschlossenen **One-Shot-Services** ist für sich genommen kein Fehler; Resultat, Exit-Code und Timerstatus sind mitzubewerten.

### Wiederkehrende Störungen

| Beobachtung | Erste Prüfung | Verhalten / Einschränkung |
| --- | --- | --- |
| Drive-Manifest veraltet | Portrait-Timer und `journalctl`; DNS-/Netzverbindung prüfen | Ohne gültigen Drive-Nachweis werden Löschungen der Homepage-Einträge blockiert. Am 23.10. traten morgens DNS-Timeouts auf; spätere Synchronisierungen waren wieder erfolgreich. |
| GitHub-Homepage bleibt alt | GitHub-Sync-Service, lokalen Branch und `git status --short` prüfen | Push wird bei Netzfehlern erneut versucht. **Nicht** unbesehen `git reset --hard` einsetzen: eine unsaubere Arbeitskopie kann schützenswerte lokale Änderungen enthalten. |
| Einzelne Tabellen/Pläne fehlen oder sind alt | Quelldaten und zugehörigen Exportdienst prüfen | Fehlerhafte/fehlende Daten können von der Exportlogik zurückgewiesen werden. |
| Systemampel gelb/rot | Ausführliche Diagnose und letzten Service-Lauf ansehen | Es werden **keine automatischen Reparaturen** oder Neustarts durch die Ampel ausgeführt. |

## Backups und Wiederherstellung

Auf dem Pi ist `berne-backup-daily.timer` aktiv (täglicher Lauf gegen **07:00 Uhr**). Die Sicherung vom **23.10.2026** wurde laut `backup-status.txt` lokal auf Extrahierbarkeit/Metadaten geprüft sowie nach Google Drive hochgeladen und durch Rücklesen verifiziert.

**Nicht nachgewiesen:** Wiederherstellung auf Ersatzhardware bzw. vollständiger Start des Systems **aus dieser Sicherung** (`hardware_restore_tested: false`). Die vorhandene `.tar.gz`-Datensicherung ist **nicht automatisch ein vollständiges bootfähiges SD-Kartenabbild**. Ein regulärer Raspberry-Pi-Neustart wurde am **23.10.2026** durchgeführt; anschließend meldete die Systemampel **10/10 GRUEN** (12/12 erwartete Timer aktiv, Dienste erfolgreich, Drive-Synchronisierung frisch). Die TV-Bildausgabe während der geplanten Betriebszeit wurde damit noch nicht gesondert nachgewiesen.

**Vertraulichkeit:** Backups enthalten auch Anwendungs-Zugangsdaten. Sie bleiben außerhalb dieses **öffentlichen** GitHub-Repositories; keine Archive, Backup-Statusdateien mit sensiblen Metadaten, Tokens, SSH-Schlüssel oder lokale Konfigurationsdateien hier veröffentlichen.

## Entwicklung und Regressionstests

Änderungen am Code möglichst über eigenen Branch → Pull Request → Tests → Merge in `main` durchführen; produktive Pi-Dienste und die TV-Anzeige nicht ohne Sicherung umbauen.

```bash
python3 -m unittest discover -s tests -v
```

Die exportierten Inhalte werden außerdem durch die produktiven Skripte vor einem Commit validiert. Automatische Tests ersetzen jedoch keinen Praxistest auf dem Raspberry Pi.

## PDF-Praxistest und Google-Drive-Aufräumen (23.10.2026)

### PDF-Veröffentlichung

- **Erfolgreich geprüft:** Die Datei `06 Hallentraining 2026-2027.pdf` wurde im produktiven Google-Drive-Ordner `tus-BERNE-Infoboard-Hochkant/Kachel1` erkannt, automatisch nach GitHub übertragen und auf der öffentlichen Homepage als „Hallentraining 2026-2027“ verlinkt.
- Auf der Homepage wurde die Kachel „Training“ dadurch vorübergehend von **5 auf 6 öffentliche Einträge** erweitert.
- **Öffnen auf Desktop und Smartphone wurde praktisch bestätigt.**
- Die PDF wurde anschließend wieder aus der produktiven Google-Drive-Kachel entfernt. **Die automatische Entfernung aus GitHub/der Homepage war bei der letzten Überprüfung noch nicht bestätigt**: `data/content.json` enthielt weiterhin den PDF-Eintrag. Diesen Löschschritt **nicht** als erledigt markieren, bevor Index **und** PDF-Datei auf GitHub verschwunden sind.

### Google-Drive-Struktur und sichere Aufräumarbeiten

- **Produktiv:** `tus-BERNE-Infoboard-Hochkant` mit `Kachel1` bis `Kachel4`, den Anzeigezeiten-Tabellen und ergänzenden Betriebsordnern.
- **Eigenständige Querformat-Struktur:** `tus-BERNE-Infoboard-Quer` mit eigenen Kacheln. **Nicht** als doppelte Hochkant-Kopie behandeln und ohne Prüfung nicht verschieben oder löschen.
- In `Entwicklung & Diagnose` wurde der Ordner **„Archiv – alte Entwürfe und Prüfnotizen 2026“** eingerichtet. Dorthin wurden **8** ältere Dateien verschoben (zwei frühere Padlet-Vorschau-Skripte, drei Prüfnotizen, drei historische ZIP-Pakete). Das ist eine **reversible Ablageverschiebung**, keine Löschung.
- **Nicht angefasst:** produktive Kachelordner, Querformat-Ordner, Anzeigezeiten, Padlet-Exporte, Backup-Ordner, aktuelle Entwicklungs- und Diagnosewerkzeuge. Der Google-Drive-Speicherplatz wird durch bloßes Verschieben nicht geringer.

## Noch offen (Stand 23.10.2026)

- **PDF-Löschtest fertigstellen:** Abwesenheit des Test-PDF-Eintrags in `data/content.json` **und** Entfernung des veröffentlichten PDF-Blobs nach gültigem Drive-Nachweis kontrollieren. Die Upload-/Anzeige-/Öffnungsseite ist bereits geprüft.
- **Technische Abnahme:** Tatsächliches TV-Bild nach einem planmäßigen Einschalten sowie kontrollierter längerer Netz-/Drive-Ausfall noch nicht nachgewiesen; regulärer Pi-Neustart mit 10/10 grünen Statusprüfungen bereits bestanden.
- **Wiederherstellung:** Hardware-Restore bzw. bootfähiges, getestetes Ersatzmedium weiterhin nicht nachgewiesen.

Die zuletzt bestätigten Betriebsdaten dienen als Ausgangspunkt für spätere Kontrollen, nicht als Garantie für den zukünftigen Zustand.
