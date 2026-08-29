# Briefing: Rack auf Unraid integrieren

Auftraggeber: Marvin. Ziel ist ein selbst gehosteter Kleiderschrank mit KI-Outfitvorschlägen, der einen bestehenden Artefakt-Prototypen ablöst.

Referenzimplementierung: `rack.jsx` (React-Einzeldatei, liegt bei). Sie enthält die vollständige Regel-Engine und ist die fachliche Vorlage. Die Datei ist Spezifikation, nicht Codebasis: Die Engine wird nach Python portiert, die Oberfläche wird übernommen und an eine echte API angebunden.

---

## 0. Arbeitsweise, verbindlich

**Phase 1, Bestandsaufnahme. Nichts ändern, nur lesen.**

Erhebe und protokolliere:

- `docker ps -a`, laufende Container, Namen, Netzwerke, Portbelegung
- Struktur von `/mnt/user/appdata`, Namenskonventionen der Unterordner
- Wie die vorhandenen Container definiert sind: Unraid-Templates unter `/boot/config/plugins/dockerMan/templates-user/` und, falls vorhanden, Compose-Dateien
- PUID, PGID, UMASK und Zeitzone, die die bestehenden Container nutzen
- SWAG: Konfiguration unter `appdata/swag`, welche Subdomains aktiv sind, welches Proxy-Muster verwendet wird, DNS-01-Setup
- Tailscale: `tailscale status`, wie andere Dienste erreichbar gemacht werden, ob als Container, Plugin oder auf dem Host
- Ob das Appdata-Backup-Plugin läuft und welche Ordner es einschließt
- Freie Ports, damit nichts kollidiert
- Verfügbarer Speicherplatz auf dem Cache-Pool

**Phase 2, Plan.** Lege einen kurzen Plan vor: gewählte Ports, Pfade, Abweichungen von diesem Briefing samt Begründung, offene Fragen. Rückfragen stellen statt raten.

**Phase 3, Bauen.** Erst nach Freigabe. Danach Selbsttest gegen die Abnahmekriterien in Abschnitt 9 und ein kurzes Übergabeprotokoll.

---

## 1. Zielbild

Ein Container namens `rack` auf dem Unraid-Server. Web-App, als PWA auf dem iPhone-Home-Bildschirm installierbar. Erreichbar ausschließlich über Tailscale, **nicht** öffentlich über SWAG. Das entspricht der bestehenden Regel: öffentlich sind nur `tv.`, `vault.` und `seer.`, alles Weitere bleibt im Tailnet.

Alle Daten bleiben lokal. Nach außen geht ausschließlich der Aufruf der Anthropic-API und optional ein Wetterabruf.

---

## 2. Technikentscheidungen

| Bereich | Wahl | Begründung |
|---|---|---|
| Backend | Python 3.12, FastAPI, uvicorn | rembg und Pillow sind Python, ein Prozess weniger |
| Datenbank | SQLite mit WAL | Einzelnutzer, kein Serverprozess, trivial zu sichern |
| Bilder | Dateien im Volume, DB speichert nur Pfade | vermeidet aufgeblähte Datenbank |
| Freistellung | rembg mit u2net, serverseitig | ersetzt die Flutfüllung des Prototypen |
| Frontend | React über Vite, statisch von FastAPI ausgeliefert | ein Container, kein separater Webserver |
| KI | Anthropic Messages API, Schlüssel serverseitig | Schlüssel darf nie im Client landen |
| Wetter | Open-Meteo, kein Schlüssel nötig | ersetzt den Temperaturregler |

Der Container soll **ein** Image sein, das Frontend wird im Build-Schritt kompiliert und im Image abgelegt.

---

## 3. Datenmodell

SQLite, Tabellen:

**items**
`id` TEXT PK, `name`, `category`, `subcategory`, `color_hex`, `color_name`, `pattern`, `pattern_scale`, `material`, `thickness`, `texture`, `fit`, `length`, `rise`, `sleeve`, `shoe_weight`, `warmth` REAL, `formality` REAL, `warmth_manual` INT, `formality_manual` INT, `image_path`, `cutout` INT, `paused` INT, `last_worn` TEXT, `wear_count` INT, `created_at`.

Wichtig: `warmth` und `formality` werden berechnet, nicht vom Modell geschätzt. Die beiden `_manual`-Flags markieren, ob der Nutzer überschrieben hat. Nur ohne Flag darf neu berechnet werden.

**profile**
Einzelzeile: `gender`, `height` INT, `build`, `torso`, `glasses` INT, `silhouette`, `notes`.

**feedback**
`pair_key` TEXT PK, `verdict` TEXT (`liked` oder `disliked`), `updated_at`.

**outfit_log**
`id`, `worn_at`, `item_ids` JSON, `occasion`, `temp`, `score` REAL. Im Prototyp fehlt das, hier bitte mitschreiben: Grundlage für spätere Auswertungen und Cost-per-Wear.

**trends_cache**
`id`, `payload` JSON, `fetched_at`.

---

## 4. API

- `GET /api/health`
- `GET /api/profile`, `PUT /api/profile`
- `POST /api/body-analysis` — Ganzkörperfoto als Multipart, gibt `build` und `torso` als Vorschlag zurück. **Das Bild wird nicht gespeichert, nicht geloggt und nicht zwischengespeichert.** Nach dem Modellaufruf sofort verwerfen. Das ist eine ausdrückliche Zusage an den Nutzer und in der Oberfläche so beschrieben.
- `POST /api/ingest` — ein oder mehrere Fotos als Multipart. Ablauf je Bild: skalieren, rembg, Vision-Aufruf, abgeleitete Werte berechnen. Rückgabe ist ein **Vorschlag zur Bestätigung**, noch kein gespeichertes Objekt, inklusive Liste unsicherer Felder.
- `POST /api/items` — bestätigtes Teil speichern
- `PATCH /api/items/{id}`, `DELETE /api/items/{id}`, `GET /api/items`
- `GET /api/images/{id}` — ausliefern mit Cache-Header
- `POST /api/outfits` — Eingabe Anlass, Temperatur, optional Ankerteil. Ablauf: Kombinationen erzeugen, harte Ausschlüsse, Bewertung, die besten acht ans Modell, drei kuratierte Vorschläge mit Styling-Schritten zurück.
- `POST /api/feedback`, `POST /api/worn`
- `POST /api/gaps` — Lückenanalyse
- `GET /api/trends` — mit serverseitigem Cache, Erneuerung nach 30 Tagen
- `GET /api/weather?lat=&lon=` — Open-Meteo, serverseitig gecacht
- `GET /api/export`, `POST /api/import`

Lange Vorgänge, also Ingest mit mehreren Bildern, per Server-Sent-Events oder Polling melden, damit die Oberfläche den Fortschritt anzeigen kann wie im Prototypen.

---

## 5. Fachlogik, die exakt zu übernehmen ist

Aus `rack.jsx` nach Python portieren, **ohne inhaltliche Änderungen**:

- `derive()`: Ableitung von Wärme und Formalität aus Kategorie, Dicke, Material, Ärmellänge, inklusive der Wortlisten `WARM_WORDS` und `FORMAL_HINTS`
- Farbmathematik: `hsl()`, `neutral()`, `hueGap()`, `colorDetail()`
- Einzelbewertungen: `sSilhouette`, `sProportion` inklusive Körpermodifikatoren, `sPattern`, `sTexture`, `sShoes`, `sFormality`, `sWarmth`, `sFresh`
- Gewichtungen `W` und `W_OPEN`, Feedbackfaktor
- Harte Ausschlüsse in `violates()` samt gestufter Lockerung in `topPicks()`
- Lückenanalyse `analyseGaps()` mit virtuellem Test und dem Kandidatenkatalog `catalogFor()`

Diese Werte sind über mehrere Iterationen entstanden. Sie sind bewusst so gewählt und dürfen nicht ohne Rücksprache angepasst werden.

**Pflicht: Unit-Tests**, die die Schwellwerte festhalten. Mindestens: oversize-Oberteil mit slim-Unterteil wird im Modus `oversize` ausgeschlossen; zwei große Muster werden ausgeschlossen; Wärmesumme außerhalb der Toleranz wird ausgeschlossen; ein Wollpullover mit langen Ärmeln ergibt reproduzierbar denselben Wärmewert.

Die Prompts aus `rack.jsx` unverändert übernehmen: `READ_PROMPT`, `BODY_PROMPT`, der Kurations-Prompt und der Lücken-Prompt. Sie sind auf die JSON-Schemata abgestimmt.

---

## 6. Migration

`POST /api/import` muss die Exportdatei des Prototypen lesen: `{version, items, images, profile, fb}`. Die Bilder liegen dort als Data-URLs und müssen in Dateien geschrieben werden. Idempotent gestalten, ein zweiter Import darf nichts duplizieren.

---

## 7. Betrieb

- `docker-compose.yml` und `Dockerfile`, dazu ein Unraid-Template als XML, damit der Container in der Docker-Oberfläche auftaucht und die WebUI-Verknüpfung funktioniert
- Volumes unter `/mnt/user/appdata/rack/`: `db/`, `images/`, `models/`
- Das rembg-Modell im Build-Schritt herunterladen und ins Image legen, sonst zieht der erste Start rund 180 MB nach
- `restart: unless-stopped`, Healthcheck gegen `/api/health`
- PUID, PGID, UMASK und Zeitzone an die vorhandenen Container angleichen, Werte aus Phase 1 verwenden
- Logs nach stdout, kein eigenes Logfile
- Der Anthropic-Schlüssel kommt aus einer `.env` neben der Compose-Datei, Rechte 600, niemals ins Image, niemals ins Repository
- Hinweis für die Übergabe: rembg ist CPU-lastig. Die erste Erfassung von zwanzig Teilen belastet den Server spürbar, das ist normal.

---

## 8. Sicherheit und Netz

- Keine Portfreigabe nach außen, keine SWAG-Subdomain, kein Eintrag in bestehende Proxy-Konfigurationen
- Erreichbarkeit über Tailscale, so wie die anderen Admin-Oberflächen im Bestand. Wenn dort bereits ein Muster existiert, dieses übernehmen statt ein neues zu erfinden
- Für den Fall, dass der Dienst im LAN erreichbar ist: einfacher Token-Schutz vor der API, Token in der `.env`
- Keine Telemetrie, keine externen Skripte oder Schriftarten im Frontend. Die im Prototypen per Google Fonts eingebundenen Schriften lokal ins Image legen

---

## 9. Abnahmekriterien

1. Container startet, Healthcheck grün, überlebt einen Neustart des Servers
2. Aufruf über den Tailscale-Namen funktioniert vom iPhone, Installation als PWA klappt, App-Symbol und Startbildschirm vorhanden
3. Erfassung: fünf Fotos in einem Durchgang, Freistellung sichtbar besser als beim Prototypen, Prüfkarte mit markierten unsicheren Feldern, Speichern funktioniert
4. Outfitvorschläge liefern drei Ergebnisse mit Styling-Schritten, harte Ausschlüsse greifen nachweislich
5. Lückenanalyse liefert Empfehlungen mit gemessenem Zugewinn und Beispielprodukten
6. Import der Prototyp-Exportdatei stellt Teile samt Bildern wieder her
7. Ganzkörperfoto wird nachweislich nicht gespeichert, Prüfung per Dateisystem und Logs
8. Unit-Tests der Engine laufen durch
9. Der API-Schlüssel steht nur in der `.env`, taucht in keinem Log auf, und ein Wechsel wirkt nach einem Neustart ohne Neubau
10. Ohne Schlüssel startet der Container und die Engine-Funktionen bleiben bedienbar
11. Nach einem Containerneustart sind alle Daten vollständig vorhanden

---

## 10. Ausdrücklich nicht tun

- Keine bestehenden Container, Templates oder SWAG-Konfigurationen ändern
- Nichts in `appdata` außerhalb von `rack/` anfassen
- Den Dienst nicht öffentlich erreichbar machen
- Die Bewertungsgewichte und Schwellwerte nicht eigenmächtig anpassen
- Das Ganzkörperfoto unter keinen Umständen speichern oder loggen
- Keine zusätzlichen Cloud-Dienste einbinden

---

## 11. API-Schlüssel

Der Schlüssel wird **nicht** in diesem Briefing mitgeliefert und darf nirgends fest verdrahtet werden.

Vorgehen:

- Im Bau-Schritt den Nutzer **interaktiv nach dem Anthropic-API-Schlüssel fragen**. Er beginnt mit `sk-ant-`.
- Den Schlüssel ausschließlich in eine `.env` neben der Compose-Datei schreiben, Dateirechte 600, Eigentümer passend zum Container-Nutzer. Die `.env` gehört in `.gitignore`.
- Er darf nicht im Image landen, nicht in der Template-XML stehen, nicht in Logs auftauchen und nicht im Terminal wiederholt werden. In Ausgaben nur maskiert anzeigen, etwa `sk-ant-…4f2a`.
- Nach dem Eintragen einen minimalen Testaufruf gegen die API machen und das Ergebnis melden. Schlägt er fehl, den Grund unterscheiden: falscher Schlüssel, fehlendes Guthaben oder Netzwerkproblem.
- Fehlt der Schlüssel, muss der Container trotzdem starten. Die Oberfläche zeigt dann einen Hinweis, dass die KI-Funktionen deaktiviert sind. Erfassen von Hand, Bewertung durch die Regel-Engine und alle Ansichten müssen ohne API funktionieren, weil die Engine rein rechnerisch arbeitet.
- Den Schlüssel austauschbar halten: eine Änderung in der `.env` plus Neustart des Containers muss genügen, kein Neubau.

Hintergrund für den Nutzer, falls er danach fragt: Ein Claude-Pro-Abo enthält keinen API-Zugang. Der Schlüssel kommt aus der Anthropic Console unter Settings und API Keys, Guthaben wird vorab unter Settings und Billing gekauft. Ein Ausgabenlimit ist empfohlen.

---

## 12. Übergabe

Am Ende: Kurzanleitung mit Start, Stopp, Backup und Wiederherstellung, dazu die Angabe, wo Schlüssel und Konfiguration liegen und wie ein Update eingespielt wird.
