> **Stand 11.11.2026:** Die hier beschriebene lokale Admin-Bedienoberfläche ist eine ältere,
> noch nicht produktiv aktivierte Variante. Für die gewünschte Handy-Bedienung über Google
> siehe `docs/kabinen-google-mobile.md`. Den Dienst `berne-cabins-admin.service`
> **nicht aktivieren**, insbesondere wegen eines möglichen Portkonflikts mit dem Pi-Infoboard.

# tus BERNE – Kabinenbelegung: manuelle Wochenkorrekturen

## Zweck und Sicherheit

Die vorhandene automatische Pi-Berechnung bleibt unverändert. Der veröffentlichte
Kabinenplan wird beim Export mit einer **privaten** Korrekturdatei zusammengeführt.
Diese Datei darf **nicht** im öffentlichen GitHub-Repository liegen.

- **Automatik:** keine manuellen Änderungen.
- **Einzelkorrekturen:** nur die ausdrücklich geänderten Kabinenfelder je Spiel
  überschreiben die automatische Zuordnung. Die Zuordnung nutzt einen
  konservativen Spielschlüssel (Datum, Zeit, Art, Staffel, Heim- und Gastteam).
  Bei Spielverlegung oder doppelten Schlüsseln wird **nicht** stillschweigend
  korrigiert; die Verwaltung und der öffentliche Plan warnen.
- **Wochensperre:** alle Spiele der laufenden Woche werden als kompletter Plan
  gespeichert; Spiele dürfen ergänzt, gelöscht, zeitlich und in der
  Kabinenzuordnung geändert werden. Neue automatisch berechnete Spiele gelten
  erst nach Entsperren oder Wochenwechsel. Daher bei Sperre neue Ansetzungen
  zusätzlich selbst prüfen.
- **Neue Kalenderwoche:** nur die laufende Woche wird gemischt; ältere
  Korrekturen sind nicht mehr wirksam. Die letzten 16 Einträge verbleiben zur
  begrenzten Nachvollziehbarkeit lokal.
- **Backup:** jede neue Speicherung bewahrt die vorherige Datei als `.bak` auf.
  Eine vollständige Historie für jede Einzeländerung besteht noch nicht.

## Vor der Installation auf dem Raspberry Pi

1. Lauffähigkeit des Pi, Datenquelle, Konfiguration und Anzeige prüfen.
   Besonders feststellen, ob die TV-Kabinenansicht dieselbe JSON-Datei verwendet.
   Dieser Code ändert **nur den GitHub-Export**; ein abweichender lokaler
   TV-Datenfluss muss gesondert auf denselben wirksamen Plan umgestellt werden.
2. Von der vorhandenen Pi-Installation und Git-Arbeitskopie eine Sicherung machen.
3. Raspberry Pi Python-Version >=3.9 prüfen (für `zoneinfo`).
4. Neue Dateien durch die bestehende GitHub-Synchronisierung auf den Pi bringen;
   die laufenden Pi-Dienste werden **nicht automatisch** umgestellt.

## Systemdienst einrichten (erst nach Prüfung direkt auf dem Pi)

Die Beispieldateien liegen unter `deploy/systemd/`:

- `berne-cabins-admin.service`
- `kabinen-admin.env.example`

Der Dienst ist auf `127.0.0.1:8765` begrenzt und besitzt **keinen**
öffentlichen Port. Ein eigenständiges mindestens 16-stelliges Kennwort
muss in `/etc/tusberne/kabinen-admin-password` hinterlegt werden; die
Kennwortdatei muss für den Dienstbenutzer `kuhfi` lesbar sein, aber nicht
für alle. Die Einstellungen in `/etc/tusberne/kabinen-admin.env` sind aus der
Beispieldatei zu erstellen und zu prüfen. Keine Kennwörter in GitHub eintragen.

Der Dienst schreibt manuelle Vorgaben in
`/var/lib/tusberne-kabinen/overrides.json`. Das systemd-`StateDirectory`
stellt das benötigte Verzeichnis bereit. Der Pi-Public-Sync verwendet dieselbe
Datei nur zum Lesen. Für Fehlertests kann `TUSBERNE_CABINS_OVERRIDES` auf
Testpfade umgestellt werden.

```bash
# Nur nach Sichtprüfung von Pfaden und Service-Umgebung:
sudo cp deploy/systemd/berne-cabins-admin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now berne-cabins-admin.service
systemctl status berne-cabins-admin.service --no-pager
```

Am PC lässt sich die lokale Verwaltung zunächst über einen **SSH-Tunnel**
öffnen, ohne einen weiteren Internetdienst freizuschalten:

```bash
ssh -L 8765:127.0.0.1:8765 kuhfi@berne-infoboard
```

Danach `http://127.0.0.1:8765/` im PC-Browser öffnen. Die geschützte Verwaltung
für das Handy sollte erst nach einer **separaten Zugriffskonfiguration**
(z. B. Tailscale Serve mit passenden ACLs und TLS) freigegeben werden. Bei
Zugriff über einen HTTPS-Reverse-Proxy muss
`TUSBERNE_CABINS_ADMIN_ORIGIN=https://<exakter-hostname>` gesetzt werden.
Keine direkte Internetfreigabe des Admin-Dienstes und keine ungesicherte
HTTP-Weiterleitung einrichten.

## Abnahme-/Regressionstests

```bash
python3 -m unittest discover -s tests -p 'test_cabins_manual.py' -v
python3 scripts/pi_cabins_export.py  # Ohne --apply: nur Probeexport
```

Abnahmefälle:

1. Automatik ohne Korrektur → identische Zuweisungen.
2. Einzelne Gastkabine ändern → automatisches Heim/SR bleibt unverändert.
3. Gleiche Quelle ändert die Kabine erneut → manuelle Vorgabe bleibt.
4. Spiel wird zeitlich verschoben → alte Einzelkorrektur nicht unbemerkt übernehmen.
5. Wochensperre → zusätzliche Quellen-Spiele gelangen nicht in den gesperrten Plan.
6. Sperre aufheben → automatische Berechnung ist wieder maßgeblich.
7. Wochenwechsel → alte manuelle Änderungen sind nicht mehr wirksam.
8. Gleichzeitige Bearbeitung → veraltete Version wird mit HTTP 409 abgewiesen.
9. Fehlende Anmeldung oder unpassender Browser-Ursprung → HTTP 401/403.
10. Export- und Liveanzeige prüfen. Optional danach kontrolliert auf dem Pi
    `python3 scripts/pi_cabins_export.py --apply` und regulären Sync testen.

**Offen:** Die private Berechnung auf dem Pi und eine möglicherweise separate
TV-Kabinenansicht sind nicht Bestandteil des öffentlichen Repositorys. Diese
Quellen müssen vor endgültiger Produktivfreigabe vor Ort geprüft werden.