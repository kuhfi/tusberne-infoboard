# Sichere Löschung öffentlicher Bilder – Stand 22.10.2026

## Was aktuell funktioniert

`scripts/pi_public_sync.py` übernimmt Bilder aus dem lokalen Kachel-Manifest des Raspberry Pi und publiziert sie über das bestehende `scripts/pi_public_publish.sh`. Neue und geänderte Bilder können so bereits zur Homepage gelangen.

**Noch offen:** Ein in Google Drive gelöschtes Bild wird bisher nicht aus `data/content.json` entfernt. Beispiel: In Kachel 1 des aktuellen Drive-Ordners liegt nun `03 Lageplan für Fußballtore Bauarbeiten.jpg`; der ältere Eintrag `03 Lageplan Tore.png` steht noch im GitHub-Inhaltsverzeichnis.

## Sicherheitsregel im Entwicklungszweig

Alte Einträge mit `managed_by: pi-public-sync` und `source_path: kachelN/<Name>` werden nur dann aus `data/content.json` entfernt, wenn:

1. Der Upstream-Drive-Downloader **alle vier freigegebenen Quellordner vollständig und fehlerfrei aufgelistet** hat, einschließlich aller Seiten der API-Paginierung, und die freigegebenen Bilder erfolgreich lokal bereitgestellt hat.
2. Der lokale `portrait-content/manifest.json` vollständig ist und die Bilder tatsächlich in den jeweiligen Kachelordnern vorhanden sind.
3. Derselbe Upstream-Downloader *nach diesen erfolgreichen Schritten* eine atomar geschriebene Datei `portrait-content/drive-publication-verified.json` angelegt hat.
4. Die Bestätigung höchstens 45 Minuten alt ist, exakt auf den aktuellen **Rohinhalt** des Manifests verweist und für alle vier Kacheln dieselben Bilddateinamen enthält.
5. Maximal drei verwaltete Bildeinträge pro Lauf wegfallen. Bei mehr wird abgebrochen (nicht schrittweise gelöschte Masseneinträge). Manuelle Einträge und Links bleiben unangetastet.

**Wichtig:** Die Bestätigungsdatei existiert bislang nicht nachgewiesen. Der Entwicklungszweig löscht deshalb standardmäßig **überhaupt nichts**. Die dauerhafte Automatik erfordert eine kontrollierte Ergänzung des vorhandenen Pi-Drive-Downloaders. Niemals bloß aus einem lokalen Verzeichnis-Snapshot eine Erfolgsmeldung erzeugen: Ein erfolgreiches Drive-Listing muss tatsächlich vorliegen.

## Erforderliches Bestätigungsformat

Beispiel (Platzhalterwerte ersetzen, niemals diese Beispieldatei auf den Pi kopieren):

```json
{
  "schema_version": 1,
  "source": "google-drive",
  "status": "complete",
  "completed_at": "2026-10-22T12:30:00Z",
  "manifest_sha256": "<SHA256 der Bytes von portrait-content/manifest.json>",
  "image_names": {
    "1": ["03 Lageplan für Fußballtore Bauarbeiten.jpg", "04 Advance Football.png", "05 DFB Akademie.png"],
    "2": ["<vom Pi bestätigter Dateiname>"],
    "3": ["<vom Pi bestätigte Dateinamen>"],
    "4": ["<vom Pi bestätigter Dateiname>"]
  }
}
```

Die `image_names` kommen aus den erfolgreich gelesenen Drive-Ordnern; ihre Menge muss identisch mit den Bildnamen des vollständig aufbereiteten lokalen Manifests sein. Wenn Dateien noch nicht geladen, gelöscht oder umbenannt sind, darf die Bestätigung **nicht** geschrieben werden. Schreiben per temporärer Datei und `os.replace` verhindert halbfertige Bestätigungen. Eine vor einem Fehler zurückgebliebene alte Bestätigung wird durch Ablaufzeit bzw. Manifest-Abweichung ignoriert.

## Noch zu prüfen, bevor dies produktiv wird

- Auf dem Pi den tatsächlichen **Erzeuger** von `portrait-content/manifest.json` und dessen Verhalten bei Google-Drive-Fehlern prüfen.
- Prüfen, ob der Pi beim Löschen in Drive auch die lokale Datei bzw. den Manifest-Eintrag entfernt. Falls nicht, muss **nur der Google-Drive-Import**, nicht die bestehende Anzeige, zuverlässig aktualisiert werden.
- Den Bestätigungsnachweis in den erfolgreichen Drive-Import integrieren und Fehlerfall simulieren.
- Offline-Test: `python3 -m unittest discover -s tests -v`.
- Auf dem Pi zunächst `python3 scripts/pi_public_sync.py` ohne `--apply` ausführen. Kontrollieren, dass genau der veraltete Eintrag entfernt werden soll, danach getrennt auf produktiven GitHub-Branch übernehmen.
- Die Bilddatei selbst wird in dieser Stufe **nicht** aus `files/` gelöscht, sondern nur der alte Homepage-Eintrag aus `data/content.json`. Aufräumen der verwaisten Dateien ist eine gesonderte Aufgabe.

## Produktion

Der automatische Pi-Timer holt derzeit den `main`-Branch von GitHub. Dieser Entwicklungszweig wird **nicht** automatisch übernommen und verändert die Infoboard-Anzeige nicht. Ein Merge nach `main` darf erst nach erfolgreichem Test des Pi-Quellprozesses erfolgen.
