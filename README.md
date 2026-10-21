# tus BERNE – Digitales Fußball-Infoboard

Öffentliche, mobilfreundliche Informationsseite zum digitalen Infoboard der Fußballabteilung **tus BERNE**.

**EINMAL BERNE IMMER BERNE**

## Projektstand

Die Website enthält derzeit ausschließlich das getestete HTML/CSS/JavaScript-Grundgerüst. **Die Datenquelle `data/content.json` ist leer und befindet sich im Vorschaumodus.** Es werden noch keine Trainings-, Kabinen-, Mannschafts- oder Kontaktdaten veröffentlicht.

Aufbau:
- `index.html` – Startseite mit Suche und Themen
- `assets/styles.css` – Gestaltung
- `assets/app.js` – Darstellung, Suche und Filter
- `data/content.json` – ausschließlich freigegebene öffentliche Inhalte

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
