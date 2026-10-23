# Öffentliche PDF-Dateien auf der QR-Code-Homepage

## Bedienung

Eine PDF in Google Drive in `tus-BERNE-Infoboard-Hochkant/Kachel1`,
`Kachel2`, `Kachel3` oder `Kachel4` ablegen.
Dateinamen können zur Sortierung mit `01 `, `02 `, ... beginnen.
Beispiel: `09 Turnierinformationen.pdf` in Kachel 3.

Die vorhandene Pi-Synchronisierung überträgt PDFs ins lokale
`portrait-content/kachelN` und führt sie im Manifest mit
`"type": "pdf"`. Der öffentliche Publisher erstellt daraus einen
eigenen Eintrag mit `"kind": "pdf"`, überträgt die geprüfte Datei
nach `files/drive/kachelN/` und zeigt auf der Homepage „PDF öffnen“ an.

Neue und geänderte PDFs werden im normalen etwa zehnminütigen
GitHub-Abgleich übernommen. Vorher muss die bestehende
Google-Drive-zu-Pi-Synchronisierung abgeschlossen sein.

## Sicherheits- und Löschregeln

- **Nur PDFs in den vier ausdrücklich öffentlichen Kachel-Ordnern**
  werden veröffentlicht. Andere Drive-Ordner bleiben unberührt.
- **Öffentlich bedeutet ohne Anmeldung weltweit abrufbar.**
  Keine personenbezogenen, internen oder vertraulichen Unterlagen einstellen.
- Die erlaubte Größe beträgt maximal **20 MiB pro PDF**. Dateien müssen
  nicht leer sein und mit `%PDF-` beginnen.
- PDFs werden als Dateien verlinkt, nicht als HTML eingebettet oder serverseitig ausgeführt.
- Entfernen eines öffentlichen PDF-Eintrags **und der zugehörigen generierten
  PDF-Datei aus GitHub** erfolgt erst mit einer frischen, vollständigen
  Drive-Bestätigung, die die Bild- und PDF-Dateilisten aller vier Kacheln
  mit dem lokalen Pi-Manifest abgleicht.
- Ältere Bestätigungen ohne `pdf_names` dürfen weiterhin nur Bilder
  löschen, niemals PDFs. Stimmt eine Liste nicht überein oder fällt der
  Drive-Abgleich aus, erfolgt keine automatische Löschung.
- Höchstens drei von diesem Sync verwaltete PDF-Einträge dürfen pro
  Durchlauf entfernt werden. Manuelle Links werden nicht entfernt.
- Eine GitHub Pages-Veröffentlichung kann auch nach Löschung noch kurz
  über Caches verfügbar sein. Man darf **nicht** auf sofortigen
  Widerruf bereits heruntergeladener PDF-Dateien vertrauen.

Der Raspberry-Pi-Fernsehbildschirm, sein Zeitplan und sein
`portrait-drive-sync.sh` bleiben unverändert. Das bereits
installierte Pi-Skript ruft die neue Version des Prüfbausteins
`scripts/pi_drive_attest.py` auf, sobald GitHub-Updates automatisch
im lokalen Clone ankommen.

## Funktionsprüfung

```bash
cd /home/kuhfi/tusberne-github-sync
python3 scripts/pi_public_sync.py
```

Das ist ein **rein lesender** Probelauf. Die Ausgabe enthält die
Anzahl der übernommenen PDFs, neue PDF-Einträge, entfernte PDF-Einträge
und `PDF-Loeschung durch Drive belegt: JA/NEIN`.

Automatische Tests auf GitHub: `python3 -m unittest discover -s tests -v`.
