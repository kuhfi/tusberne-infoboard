# tus BERNE – Vereinszentrum: mobile Anleitung und Pflicht-Hinweise
Stand: 17.11.2026 (Europe/Berlin)

## Anlass
Wiederholt blieb das Vereinszentrum nach einer Raumveranstaltung unverschlossen und die Alarmanlage unscharf. Der Nutzer entschied am 17.11.2026:
- Eine mobilfreundliche Webseite statt der bisherigen zweitseitigen PDF-Anleitung.
- Bedienung der Alarmanlage ausschließlich mit Transponder UND persönlicher Einweisung.
- Buchungsprozess soll sowohl Lesebestätigung als auch Status des Abschließens abfragen.
- Buchung soll auch möglich bleiben, wenn die Schließzuständigkeit noch ungeklärt ist; dann deutlich warnen.
- Zuständigkeit für Schließprobleme außerhalb der Geschäftszeiten bleibt offen und wird nicht erfunden.

## Quellen
- Ursprüngliche interne Anleitung vom 26.06.2026 (2 Seiten), bislang im FAQ als Google-Drive-PDF verlinkt.
- FAQ-Datei: `faq/index.html`.
- Bestehende Eintrittsseite: `files/besprechungsraum.html`.
- Eigenständige Raum-Buchungs-Web-App: https://script.google.com/macros/s/AKfycbxqi0Pqy_K-JkB2-KDikEWasK3AU9-U-Co0wOe7UQlb3z5X4lxayh7HtOFhATkNGeQ/exec
- Bürozeiten laut Vereinszeitschrift „Blickpunkt“ 1/2026, Seite 21: Montag 9–12 und 17–19 Uhr, Donnerstag 9–12 Uhr.

## Produktive Änderungen auf GitHub main
1. Neu: `files/vereinszentrum-alarmanlage.html` – responsiver Kurzleitfaden, Zusammenfassung der Original-PDF, Zugang/Nuki, Schließkontrolle, Alarmfall und Bürozeiten. Es werden keine Transponderdaten oder Zugangscodes veröffentlicht.
2. `faq/index.html` – FAQ-Hinweis zur Schließverantwortung präzisiert; direkter Link auf die alte PDF durch Link auf die mobile HTML-Anleitung ersetzt.
3. `files/besprechungsraum.html` – nicht-blockierender Warnhinweis und Link zur Anleitung vor dem bereits bestehenden Buchungslink.

Git-Commits:
- `ffb5c6d6d645d0d09062258caff7a486c2ee0b2d` – neue Anleitung
- `55a5e16e7cf1345b231416e93f599acac1ad9c53` – FAQ
- `b190a05f2a8eee3a41e39655decb635b6e08ec26` – Buchungseinstieg

## Technische Abgrenzung
- Die bestehende Google-Apps-Script-Buchungsanwendung wurde NICHT geändert. Ihr tatsächliches Codeprojekt wurde weder in diesem GitHub-Repository noch durch eine passende Drive-Datei identifiziert.
- Ein Hinweis auf der Eintrittsseite ist KEINE technische Pflichtbestätigung im Buchungsformular.
- GitHub Pages ist öffentlich; `noindex` ersetzt KEINEN Zugriffsschutz. Der Inhalt erläutert Bedienabläufe nur für berechtigte, persönlich eingewiesene Nutzer. Vor weiterem Ausbau ggf. geschützten Bereitstellungsweg beschließen.
- Keine Raspberry-Pi-Dienste, Timer, Google-Tabellen oder TV-Code geändert.

## Beabsichtigte Integration in der echten Buchungsmaske (OFFEN)
1. Deutlicher Hinweis zu Alarmanlage und Schließpflicht inklusive Verlinkung der gültigen Webseite.
2. Pflichtcheckbox: „Ich habe die Anleitung gelesen.“ (nicht vorbelegt).
3. Pflichtauswahl: „Abschließen ist organisiert“ ODER „Noch offen – ich kläre das verbindlich vor der Nutzung“.
4. Bei zweiter Auswahl nicht-blockierende, deutliche Warnung. Buchung bleibt möglich.
5. Status optional im Buchungsdatensatz persistieren; bestehende Eingaben, Kalenderbelegung, Benachrichtigungen und Validierung erhalten. Dafür erst aktuelle Codequelle/Deployment, Backup und Tests prüfen.
6. Verantwortliche Kontaktperson für Schließprobleme außerhalb der Bürozeiten nach interner Klärung ergänzen. Im Alarmfall bleibt der bisherige dokumentierte Alarmkontakt.

## Prüfung und Rollback
- GitHub-Dateirücklesung bestätigte neue HTML-Datei, Links, Logo-Quellpfad, Zeiten, Trainierten-Regel und Slogan sowie aktualisierten FAQ-Link.
- Externe GitHub-Pages-HTTP-/Rendering-Abnahme nicht belegbar (Webzugriff darauf lieferte Fehler). Ebenso kein mobiler realer Browser- oder Buchungsformular-End-to-End-Test durchgeführt.
- Rollback über die obigen Commits: neue Datei entfernen; `faq/index.html` und `files/besprechungsraum.html` gezielt auf jeweilige vorherige Git-Blob-Version rücksetzen. Keine harten Git-Resets.
