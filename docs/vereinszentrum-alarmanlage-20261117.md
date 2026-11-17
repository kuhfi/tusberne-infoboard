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

## Überarbeitung nach Nutzerfeedback – 17.11.2026
Ziel: Anleitung kürzer, übersichtlicher und ohne Quell-/Historienverweise in der Nutzeransicht. Die mobile Seite `files/vereinszentrum-alarmanlage.html` wurde auf Basis Blob `de689260e7314921daf361968670d5734dddbed2` gezielt geändert: kompaktere Abstände; doppelte „Auf einen Blick“-Sektion entfernt; Buchungs- und FAQ-Link im Hauptwarnblock; Zugangstexte gekürzt; Quell-, Stand- und „alte Anleitung“-Verweise aus dem sichtbaren Inhalt entfernt. Die eigentlichen Öffnen-/Schließen-Schritte, Schließkontrolle, Alarmkontakt und Öffnungszeiten bleiben erhalten. Commit `3dd91135d3ea4d85b72094cf0fece9feaf44f214`, neuer Blob `d92426945355a80b5605859cfc963217b397192e`. Original-GitHub-Blob ist Rückrollreferenz.

**Verbindlich gewünschtes UI der eigenständigen Buchungs-App, NOCH NICHT UMGESETZT:**
1. Buchungsseite zeigt dauerhaft einen klaren Link auf `https://kuhfi.github.io/tusberne-infoboard/files/vereinszentrum-alarmanlage.html`, vor/bei dem Buchungsformular.
2. Benutzer füllt bisherige Buchungsangaben wie gewohnt aus. Erst beim absichtlichen finalen „Buchen“ (sowohl Mausklick als auch Enter/Form-Submit) werden die bestehenden Validierungen ausgeführt und vor Speicherung ein barrierearm nutzbares, mobiles Bestätigungs-Pop-up geöffnet.
3. Pop-up: kurze Hinweise „Wer als Letzter geht, schließt das Vereinszentrum ab und schaltet die Alarmanlage scharf. Bedienung nur mit Transponder UND persönlicher Einweisung. Vor Termin Schließzuständigkeit klären. Transponder in Geschäftszeiten organisieren.“ und ein Link zur vollständigen Anleitung. Keine einzelnen Schaltsequenzen im Pop-up.
4. Zwei Pflichtcheckboxen, standardmäßig AUS: „Ich habe die Anleitung gelesen.“ und „Ich übernehme die Verantwortung, vor der Nutzung eine berechtigte Person für Abschließen und Alarmanlage zu organisieren bzw. die Zuständigkeit zu klären.“
5. Statusauswahl zwingend: „Bereits geklärt“ oder „Noch offen“. Bei „Noch offen“ deutliche zusätzliche Warnung, aber kein Buchungsverbot. Erst mit beiden Checkboxes und Status darf eine Aktion „Jetzt verbindlich buchen“ möglich sein; „Zurück“ beendet ohne Speichern. Jede neue Buchung erfordert erneute Bestätigung.
6. Vor Buchung Eingabevalidierung beibehalten, nie doppelt buchen, den serverseitigen Buchungs-/Kalenderablauf nicht verändern; im Idealfall Bestätigungs- und Statuswert zusammen mit der Buchung protokollieren, aber nur nach Prüfung der echten Speicherstruktur.
7. Editor-/Apps-Script-Quellprojekt und aktuelle Version/Backup, Berechtigungen und Deployment der produktiven Raum-Buchungs-Web-App sind nicht verfügbar. Die gleichnamig erscheinende GitHub-Unterstruktur `apps_script/` gehört zur **Google-Kabinenverwaltung**, nicht zum Buchungsformular. Kein Code im echten Buchungsformular geändert; kein Pop-up dort aktiviert. Zur Umsetzung ist der echte Apps-Script-Editorlink (Projekt, nicht `/exec`-Link) oder das zugehörige vollständige Codepaket erforderlich.
8. Tests vor Deploy: vorhandene freie/belegte Slots; Doppelbuchung; ungültige Eingaben; Pop-up abbrechen; Checkboxen fehlen; Status „noch offen“; erfolgreich verbindlich buchen; Mobilansicht und Tastatur; bestehende Buchungsbenachrichtigung/Belegung weiter funktionsfähig.

Verifikation: GitHub-Repo-Quelländerungen per Dateirücklesung prüfbar, Live-HTTP-Zugriffe auf Google Apps Script und GitHub Pages über die verfügbaren Browserquellen nicht bestätigt. Keine Google-Script-, Raspberry-Pi-, systemd-, Drive-Ordner- oder Kalenderänderung.

## Vereinfachung nach Screenshot-Markierungen – 17.11.2026, nachmittags
Die vom Nutzer grün gestrichenen Bereiche der mobilen Anleitung wurden **gezielt entfernt**:
- Im ersten Hinweisblock den zweiten und dritten Satz nach „Vor dem Termin klären, wer das übernimmt.“ entfernt. Die eigentliche Schließpflicht und der knappe Aufruf zur Klärung bleiben.
- Im ersten Hinweisblock die beiden Navigationsschaltflächen „Fußballraum buchen“ und „FAQ“ entfernt.
- Unter „Tür & Alarmanlage bedienen“ den doppelten erklärenden Absatz entfernt; die Kennzeichnung „Nur für eingewiesene Personen“ bleibt.

Änderung nur an `files/vereinszentrum-alarmanlage.html`, öffentlicher GitHub-Branch main, Commit `4eb4857b27e78cd360afddee803728ea26ff0799`; vorheriger Blob `d92426945355a80b5605859cfc963217b397192e`, neuer Blob `587d650da19c7aa7ec4eb55260e15abd0fa88bdb`. Rücknahme durch gezielten Git-Revert bzw. Wiederherstellen der Vorgängerblobfassung; keine Änderungen an Apps Script, Buchungs-/Kalenderdaten, Raspberry Pi oder anderen Webseiten.

**Kontrolle:** komplette HTML-Quelldatei aus GitHub zurückgelesen, alle drei vorgesehenen Löschstellen nicht mehr enthalten, HTML-Tag-Verschachtelung geprüft (kein Fehlpaar, kein offenes Tag). Wichtige Bestandsinhalte vorhanden: Schließpflicht, Kurzaufforderung zur vorherigen Klärung, persönliche Einweisung beim Zugang, zwei ausklappbare Bedienabläufe, Alarmkontakt, Geschäftsstellenzeiten, echtes Logo und „EINMAL BERNE IMMER BERNE“. Kein eigenständiger Smartphone-/GitHub-Pages-Sichttest dieser Änderung erfolgt; GitHub-Commit bestätigt den Repository-Stand, nicht die Auslieferungszeit.

## Kontakt bei Schließproblemen ohne Alarm – 17.11.2026
Auf ausdrückliche Nutzerangabe wurde der bislang offene Kontakt bei gewöhnlichen Schließproblemen **ohne ausgelösten Alarm** konkretisiert: Brigitte Steckel kann unter +49 176 48187978 kontaktiert werden. Der separate Alarmfall-Kontakt Holger Maiwald bleibt unverändert. Es wird keine garantierte Erreichbarkeit außerhalb der Bürozeiten behauptet.

Änderung: GitHub `files/vereinszentrum-alarmanlage.html`, Branch main, vorheriger Blob `587d650da19c7aa7ec4eb55260e15abd0fa88bdb`, neuer Blob `6b7c5ff5e8ebafc5e1ea3b9215c1964c53178537`, Commit `c140e941401005ab3d637adbe7e33c663f2f77c0`. Genau ein Absatz im Abschnitt „Wenn etwas nicht funktioniert“ ersetzt, klickbarer Telefon-Link `tel:+4917648187978`, kein Eingriff in Apps Script, Google-Kalender oder Raspberry Pi.

Prüfung: die geänderte GitHub-Datei zurückgelesen; beide Kontakte dem korrekten Anlass zugeordnet, alte Nicht-benannt-Aussage entfernt, Telefonnummer und Anruflink abgeglichen, HTML-Tags ohne Verschachtelungsfehler, Schließabläufe und Öffnungszeiten weiterhin vorhanden. Keine Live-Browser-/GitHub-Pages-Abnahme. Rollback: ursprünglichen Git-Blob gezielt wiederherstellen bzw. Änderung per Revert rückgängig machen. Hinweis: Die Telefonnummer wird auf der öffentlich abrufbaren GitHub-Pages-Seite sichtbar sein, wie vom Nutzer gewünscht.

## Einheitliche Darstellung der beiden Ansprechpartner – 17.11.2026
Anlass: Nutzer zeigte einen Screenshot der beiden unterschiedlich dargestellten Kontakte unter „Wenn etwas nicht funktioniert“ und wünschte einen einheitlichen, übersichtlichen Bereich. Vorher stand der versehentliche Alarm in einer roten Fließtextbox; das Schließproblem war ein regulärer unstrukturierter Absatz mit unglücklichem Zeilenumbruch bei der Telefonnummer.

Umsetzung: Im bestehenden `files/vereinszentrum-alarmanlage.html` sind jetzt **zwei gleichartig aufgebaute Kontaktkarten** innerhalb derselben Gruppe vorhanden, jeweils mit kurzem Anlass, fettem Kontaktnamen, separatem anklickbarem Telefonlink und einem knappen Handlungs-Hinweis. Beide Karten haben identische Abstände, Hintergrund, Typografie und Umrandung; nur beim Alarmfall bleibt eine schmale rot-orange Akzentlinie zur Unterscheidung von einem gewöhnlichen Schließproblem. Die Telefonnummern werden mit `white-space:nowrap` zusammengehalten und die Kontaktzeile darf mobil umbrechen. Der Alarmtext nennt weiterhin Holger Maiwald, sofortigen Anruf und Information durch die Alarmfirma; beim Schließproblem bleibt Brigitte Steckel Ansprechpartnerin und das Gebäude darf nicht unverschlossen bleiben. Nicht behauptet wird, dass Brigitte jederzeit erreichbar ist.

Produktive Änderung: Nur `files/vereinszentrum-alarmanlage.html` in GitHub `kuhfi/tusberne-infoboard`, Branch `main`, Commit `87758ad08d2791afb1e5309f4b5dcca7c568a66d`. Vorgängerblob `6b7c5ff5e8ebafc5e1ea3b9215c1964c53178537`, neuer Blob `6c31d12808926921c9f7dd1be3c02a37500c10b9`. Revert durch gezieltes Rückspielen des Vorgängerblobs/Commit-Revert, kein destruktiver Reset. Kein Google-Apps-Script-, Kalender-, Raspberry-Pi-, Timer- oder Drive-Ordner-Eingriff.

Prüfung: vollständige HTML-Datei über GitHub erneut gelesen, Tag-Balance: 0 Fehler und 0 offene Tags, genau zwei gleichartig strukturierte Karten, beide korrekten `tel:`-Links einmal vorhanden, beide Überschriften korrekt, übrige Schließanleitung, Bürozeiten und Slogan unverändert vorhanden. Echte mobile Darstellung und GitHub-Pages-HTTP-Auslieferung wurden noch nicht separat nachgewiesen.

## Einheitliches Format der Handynummern – 17.11.2026
Auf ausdrücklichen Nutzerwunsch wurden die beiden öffentlich angezeigten Mobilnummern im gleichen deutschen Schema (führende Null, Gruppen 4–3–2–Rest) formatiert. Holger Maiwald bleibt „0171 261 23 75“. Brigitte Steckel wird statt „+49 176 48187978“ als „0176 481 87 978“ angezeigt. Die technische Anruf-URL von Brigitte `tel:+4917648187978` und Holgers `tel:+491712612375` bleiben unverändert und somit korrekt.

Geändert wurde genau eine Anzeigezeichenfolge in `files/vereinszentrum-alarmanlage.html`, Branch `main`, Commit `a623127dc40add2a2887e60f859bf1f4bb6d8c39`, Original-Blob `6c31d12808926921c9f7dd1be3c02a37500c10b9`, Ergebnis-Blob `23863d837d960015626ea3a060c34afa686c4777`. Rollback durch gezieltes Zurücksetzen dieses Blobs bzw. Revert-Commit möglich; weder Apps Script noch Kalender, Raspberry Pi, Systemdienste oder andere Dateien angetastet. Rücklesen von GitHub bestätigt beide Anzeigen, beide unveränderten tel:-Links und fehlerfreie HTML-Tag-Balance. Kein mobiler Browser-/GitHub-Pages-Renderingtest.
