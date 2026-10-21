# tus BERNE – Digitales Fußball-Infoboard

Öffentliche, mobilfreundliche Informationsseite zum digitalen Infoboard der Fußballabteilung **tus BERNE**.

**EINMAL BERNE IMMER BERNE**

## Projektstand (21.10.2026)

Die mobile öffentliche Homepage nutzt die vier Bereiche des digitalen Infoboards. Derzeit sind **15 öffentliche Einträge** in `data/content.json` hinterlegt:

- **Kachel 1 / Training:** 5 Inhalte (zwei Trainingspläne und drei Grafiken).
- **Kachel 2 / Belegung:** 2 Inhalte (Kabinen-Grafik und externer Link zur Fußballraumbelegung über Google Apps Script).
- **Kachel 3 / Tabellen / News:** 8 Inhalte (sieben Informations-/Termingrafiken und Wetter-/Radar-HTML).
- **Kachel 4 / Mannschaften und Ansprechpartner:** noch keine öffentlichen Einträge.

Die Originalgrafiken liegen statisch im Verzeichnis `files/`. Wetterdaten werden auf der Wetterseite im Browser über Open-Meteo und die Regenradar-Karten über DWD geladen; die tatsächliche Verfügbarkeit dieser externen Dienste wurde nicht bestätigt. Die öffentlichen Einträge sind **noch nicht automatisch mit Google Drive oder Raspberry Pi synchronisiert**.

**Hinweis zur Aktualität:** Das Herbstferien-Camp wird mit dem Datum 26.–30.10.2026 als statische Grafik angezeigt. Veranstaltungshinweise müssen nach Ablauf kontrolliert und bei Bedarf entfernt werden. Persönliche Buchungsdaten bleiben aus dem statischen Export ausgeschlossen.

Dateistruktur:
- `index.html` – Startseite mit Suche und vier Kacheln
- `assets/styles.css` – Darstellung
- `assets/app.js` – Darstellung, Suche, Filter und sichere URL-Auswahl
- `data/content.json` – ausschließlich freigegebene öffentliche Einträge
- `data/training-berne.json`, `data/training-farmsen.json` – veröffentlichte Trainingsplan-Daten
- `files/` – veröffentlichte HTML-Seiten und Grafiken

## GitHub Pages

Unter **Settings → Pages → Build and deployment** die Quelle **Deploy from a branch**, Branch **main**, Verzeichnis **/(root)** wählen und speichern. Die GitHub-Pages-Adresse wird in den Projekteinstellungen angezeigt, sobald die Veröffentlichung eingerichtet ist.

Dieses Repository ist bewusst **öffentlich**. Keine Anmeldedaten, Pi-Konfigurationen, internen Kontakte, Buchungsdaten oder privaten Diagnoseberichte hochladen. Neue Daten werden erst nach Prüfung und Freigabe übernommen.

Die vorhandene FAQ bleibt als eigenständige Netlify-Website bestehen.

## Vier Kacheln (seit dem 21.10.2026)

Die Startseite entspricht den vier Bereichen des Infoboards:

1. **Training** (Export-Kategorien: \`trainingsplaene\`, \`training\`)
2. **Belegung** (\`kabinen\`, \`lageplan\`, \`belegung\`)
3. **Tabellen / News** (\`fussball\`, \`news\`, \`tabellen-news\`)
4. **Mannschaften / Ansprechpartner** (\`mannschaften\`, \`ansprechpartner\`, \`mannschaften-ansprechpartner\`)

Die bisherigen Kategorien der Datenstruktur bleiben lesbar. Einträge werden weiterhin nur gezeigt, wenn sie ausdrücklich als \`public: true\` freigegeben sind und eine sichere URL haben. Die Beispiel-Datendatei bleibt leer.
