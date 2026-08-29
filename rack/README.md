# Rack

Selbst gehosteter Kleiderschrank mit Regel-Engine und Outfitvorschlägen. Läuft als
einzelner Container auf dem Unraid-Server, erreichbar ausschließlich über Tailscale.

Der Prototyp `rack.jsx` bleibt als fachliche Vorlage im Repository liegen. Die Engine
daraus ist nach Python portiert und gegen das Original gegengeprüft, die Oberfläche ist
übernommen und an die eigene API angebunden.

---

## Kurz und knapp

| | |
|---|---|
| Adresse | **https://arr-stack.tailbb5c95.ts.net/** (nur im Tailnet) |
| Container | `rack`, Projektverzeichnis `/mnt/user/rack` |
| Daten | `/mnt/user/appdata/rack/` mit `db/`, `images/`, `models/` |
| Schlüssel und Konfiguration | `/mnt/user/rack/.env`, Rechte 600 |
| Port | 8099, gebunden an `127.0.0.1` — im LAN ist nichts offen |
| Nutzer | PUID 99, PGID 100, UMASK 022, TZ Europe/Berlin |
| Modelle | `claude-sonnet-5` für beides, umstellbar über die `.env` |

---

## Bedienen

```bash
cd /mnt/user/rack

docker compose up -d           # starten, und nach jeder Änderung an der .env
docker compose stop rack       # anhalten
docker compose logs -f rack    # zusehen
docker ps --filter name=rack   # Zustand, inklusive Healthcheck
```

`docker compose restart rack` startet nur den Prozess im bestehenden Container neu und
behält dessen alte Umgebung. Nach einer Änderung an der `.env` ist deshalb immer
`docker compose up -d` das Richtige.

Der Container startet nach einem Neustart des Servers von allein wieder
(`restart: unless-stopped`).

### Auf dem iPhone einrichten

1. Tailscale auf dem iPhone öffnen und verbunden lassen.
2. In Safari **https://arr-stack.tailbb5c95.ts.net/** aufrufen.
3. Teilen-Symbol, „Zum Home-Bildschirm". Symbol und Startbildschirm sind hinterlegt,
   die App startet danach im Vollbild ohne Safari-Leisten.

Safari, nicht Chrome: nur Safari darf auf iOS zum Home-Bildschirm hinzufügen.

---

## Der API-Schlüssel

Der Schlüssel steht **ausschließlich** in `/mnt/user/rack/.env` unter
`ANTHROPIC_API_KEY`. Er liegt nicht im Image, nicht in der Compose-Datei, nicht im
Git-Repository und taucht in keinem Log auf. Ausgegeben wird er nur maskiert,
etwa `sk-ant-…4f2a`.

Eintragen oder wechseln:

```bash
bash /mnt/user/rack/scripts/schluessel-setzen.sh
```

Das Skript liest die Eingabe verdeckt ein, schreibt sie mit Rechten 600 in die `.env`,
erzeugt den Container neu und macht einen minimalen Testaufruf gegen die API. Ein
Wechsel braucht **keinen Neubau des Images**.

Wichtig, falls du es von Hand machst: `docker compose restart` genügt **nicht**. Der
Befehl startet nur den Prozess im bestehenden Container neu und übernimmt dessen alte
Umgebung, die `.env` wird dabei gar nicht gelesen. Richtig ist `docker compose up -d`,
das den Container neu erzeugt, ohne das Image neu zu bauen.

Schlägt der Testaufruf fehl, unterscheidet die Ausgabe die Gründe: falscher Schlüssel,
fehlendes Guthaben, fehlende Berechtigung, Anfragelimit oder Netzwerkproblem.

**Ohne Schlüssel läuft die App weiter.** Aus sind dann nur das automatische Auslesen der
Fotos, die Kuratierung mit Styling-Schritten, die Körperanalyse und die Trendrecherche.
Erfassen von Hand, die komplette Regel-Engine, die Bewertung, die Freistellung, die
Lückenanalyse als reine Rechnung sowie Import und Export funktionieren unverändert. Die
Oberfläche weist oben darauf hin.

Hintergrund: Ein Claude-Pro-Abo enthält keinen API-Zugang. Der Schlüssel kommt aus der
Anthropic Console unter Settings und API Keys, Guthaben wird vorab unter Settings und
Billing gekauft. Ein Ausgabenlimit ist empfohlen.

---

## Sichern und Wiederherstellen

Auf diesem Server läuft **kein** Appdata-Backup-Plugin. Die Sicherung ist deshalb ein
eigenes Skript:

```bash
bash /mnt/user/rack/scripts/backup.sh
# legt /mnt/user/appdata/rack/backups/rack-JJJJ-MM-TT-HHMM.tar.gz an
# und behält die letzten vierzehn
```

Die Datenbank wird über die SQLite-Sicherungs-API kopiert, nicht mit `cp`. Nur so ist der
Stand bei laufendem Container in sich stimmig, weil die WAL-Datei sonst mitten im
Schreibvorgang erwischt werden kann.

Wiederherstellen:

```bash
cd /mnt/user/rack
docker compose stop rack
tar xzf /mnt/user/appdata/rack/backups/rack-2026-08-27-2313.tar.gz -C /mnt/user/appdata/rack
docker compose start rack
```

Zusätzlich gibt es in der App unter Profil einen **Export** als einzelne JSON-Datei.
Seit Fassung 3 (29.08.2026) ist er **vollständig**: Teile mit allen Feldern, Bilder,
Etikettfotos, Outfitfotos, Profil, Rückmeldungen, Trageprotokoll, gemerkte Outfits und
Planung. Vorher fehlte davon einiges, und das Trageprotokoll stand zwar in der Datei,
wurde vom Import aber nie gelesen — eine Wiederherstellung verlor damit die gesamte
Historie samt Zählung und Bilanz.

Ein Export gehört immer **genau einer Person**; der Import legt ihn in die dann aktive.
Die Personennummer aus der Datei wird dabei verworfen, sonst landeten die Teile bei einer
fremden oder längst gelöschten Person und wären unsichtbar.

Der Import ist idempotent: dieselbe Datei zweimal eingelesen legt nichts doppelt an. Beim
Protokoll wird bewusst direkt geschrieben statt über den normalen Weg — sonst gingen die
Tragezähler hoch und die Wäschefrist würde neu gestartet, was beim Wiederherstellen einer
Sicherung falsch wäre. Er liest weiterhin auch einen Export aus dem alten
Artefakt-Prototypen.

Als Nachtsicherung eingerichtet werden kann das Skript über die Unraid-Oberfläche unter
Settings, User Scripts — bewusst nicht automatisch eingetragen, das ist deine
Entscheidung.

Seit dem 29.08.2026 erfasst zusätzlich das zentrale `scripts/backup-appdata.sh` des
arr-stack den Ordner `rack` mit. Es stoppt dafür auch das rack-Compose-Projekt und macht
vorher einen `wal_checkpoint(TRUNCATE)`. Hintergrund: SQLite hält im WAL-Modus frische
Daten in `rack.sqlite3-wal`, die Hauptdatei kann dabei fast leer sein — hier waren es
4 KB gegen 770 KB WAL. Ein `tar` über beide Dateien ist vollständig, aber wer sich später
nur `rack.sqlite3` herauskopiert, hätte eine leere Datenbank in der Hand.

---

## Aktualisieren

```bash
cd /mnt/user/rack
git pull                       # oder die geänderten Dateien hochladen
docker compose up -d --build
```

Der Neubau dauert wenige Minuten. Das rembg-Modell und der vorkompilierte
numba-Zwischenspeicher liegen im Image, beim Start wird nichts nachgeladen. Der
numba-Zwischenspeicher liegt zur Laufzeit im Container unter `/data/cache` und wird bei
jedem Start aus dem Image befüllt; er muss nicht gesichert werden.

Versionen sind fest gepinnt, in `backend/requirements.txt` und `frontend/package.json`.
Aktualisieren heißt: Version dort hochsetzen, neu bauen, committen.

---

## Wie es gebaut ist

```
rack/
  Dockerfile              vierstufig: Frontend, Abhängigkeiten und Modell, Tests, Laufzeit
  docker-compose.yml      eigenes Projekt, bewusst getrennt vom arr-stack
  docker-entrypoint.sh    Umask, Verzeichnisse, Modell spiegeln, auf PUID:PGID wechseln
  .env                    Schlüssel und Konfiguration, Rechte 600, nicht im Git
  backend/
    app/engine.py         die Regel-Engine, 1:1 aus rack.jsx portiert
    app/gaps.py           Lückenanalyse mit virtuellem Test
    app/prompts.py        die Prompts aus rack.jsx (Kuration bewusst geschärft)
    app/api.py            die HTTP-Schnittstelle
    app/db.py             SQLite mit WAL, einzige Stelle mit snake_case
    app/images.py         skalieren, freistellen, ablegen
    app/ai.py             Anthropic Messages API
    tests/                Unit-Tests der Engine plus Gegenprobe gegen rack.jsx
  frontend/               React über Vite, wird ins Image kompiliert
  scripts/                Schlüssel setzen, Sicherung, Funktionstests
```

**Ein Container, ein Prozess.** FastAPI liefert die API und das kompilierte Frontend aus,
Logs gehen nach stdout.

**Zwei Bildgrößen, zwei Zwecke.** `RACK_MAX_IMAGE_DIM` (1400) ist die Fassung, die im
Volume liegt und in der App erscheint. `RACK_MODEL_IMAGE_DIM` (2000) geht an die
Vision-API. Die Trennung kostet einen zweiten Encode und spart die schlechtere
Alternative: entweder ein grobes Bild für die Erkennung oder ein unnötig großes in der
Ablage. Freigestellt wird nur einmal, auf der größeren Fassung — rembg ist der teure
Teil, und auf dem N150 will man ihn nicht doppelt.

Warum nicht einfach unkomprimiert? Weil die Grenze nicht vom Speicherplatz kommt, sondern
von der API: **Claude Sonnet 5 verarbeitet 2576 Pixel auf der langen Kante.** Alles
darüber skaliert die API selbst herunter — das wäre nur Upload und CPU ohne Gegenwert.
Umgekehrt waren die vorherigen 1000 Pixel zu wenig: Cordrippen, Grobstrick und
Leinenstruktur sind genau die Merkmale, an denen die Materialerkennung hängt, und die
verschwinden als erstes beim Verkleinern.

**Wärme und Formalität werden gerechnet, nie vom Modell geschätzt.** Wer einen Wert im
Detail von Hand verschiebt, setzt damit ein Merkzeichen; ab dann wird dieser Wert nicht
mehr überschrieben. In der App steht dann „(von Hand)" daneben, und ein Knopf gibt ihn
wieder für die Berechnung frei.

**Das Ganzkörperfoto wird nicht gespeichert.** Es lebt nur als lokale Variable bis zum
Ende des Aufrufs, wird nicht auf Platte geschrieben, nicht zwischengespeichert und auch
der Dateiname landet in keinem Log.

### Netz und Sicherheit

- Der Port ist an `127.0.0.1` gebunden. Aus dem LAN ist der Dienst nicht erreichbar.
- `tailscale serve` nimmt die Anfragen im Tailnet auf HTTPS entgegen und reicht sie
  intern weiter. Das Zertifikat kommt von Let's Encrypt über Tailscale.
- Keine SWAG-Subdomain, kein Eintrag in bestehende Proxy-Konfigurationen, keine
  Portfreigabe im Router.
- Nach außen gehen nur zwei Dinge: der Aufruf der Anthropic-API und der Wetterabruf bei
  Open-Meteo. Keine Telemetrie.
- Im Frontend sind keine externen Skripte oder Schriften eingebunden. Bodoni Moda und
  Archivo liegen als WOFF2 im Image.
- Für den Fall, dass der Port doch einmal im LAN geöffnet wird, gibt es einen
  Token-Schutz: `RACK_TOKEN` in der `.env` setzen, dann fragt die App beim ersten Aufruf
  danach. Über Tailscale nicht nötig und deshalb leer.

### Die Engine

Die Fachlogik ist aus `rack.jsx` übernommen: `derive()`, die Farbmathematik, alle
Einzelbewertungen, die Gewichtungen `W` und `W_OPEN`, der Feedbackfaktor, die harten
Ausschlüsse in `violates()` samt gestufter Lockerung und die Lückenanalyse mit dem
Kandidatenkatalog.

Eine inhaltliche Erweiterung gibt es seit dem 29.08.2026, auf ausdrückliche Freigabe:
das Material zählt jetzt mit (siehe nächster Abschnitt). Alles andere ist unverändert.

#### Material

Bis August 2026 war `material` ein freies Textfeld. Es wirkte an genau einer Stelle: einer
Substring-Suche in `WARM_WORDS` für die Wärme. Das ging in beide Richtungen schief —
„Bio-Baumwolle" traf das Teilwort „wolle" und bekam den Wollbonus, „Kunstleder" erbte den
Wert von echtem Leder, und Cord stand gar nicht in der Liste und zählte damit wie ein
T-Shirt. In der Oberfläche war das Feld überhaupt nicht zu sehen.

Jetzt gilt:

| | |
|---|---|
| Vokabular | `engine.MATERIALS`, achtzehn Werte von Baumwolle bis Mesh. Das Frontend spiegelt die Liste in `constants.js`. |
| Normalisierung | `normalize_material()` bildet Schreibweisen, Fremdwörter und Handelsnamen ab (`corduroy`, `KORD`, `merino`, `polyester` …). Geprüft wird vom längsten Begriff zum kürzesten — sonst gewinnt „wolle" gegen „baumwolle". |
| Mehrfachangaben | `split_materials()` zerlegt „Wildleder/Mesh" in Haupt- und Zweitmaterial (`material_secondary`). |
| Unbekanntes | wird zu `null` statt geraten, und landet auf der Prüfkarte unter „unsicher". |
| Wärme | jedes Material im Vokabular hat einen Eintrag in `WARM_WORDS`; ein Test stellt sicher, dass keines fehlt. |
| Bewertung | `s_material()` mit Gewicht 0.05 — prüft Saison (Leinen im Winter, Wolle im Hochsommer) und Materialdopplung (Cord auf Cord, zwei glänzende). |

`s_material` ist bewusst **nur ein weiches Kriterium**. `violates()` blieb unberührt: ein
Outfit verschwindet nie, weil ein Material unbekannt oder grenzwertig ist — es rutscht
höchstens nach hinten. Ohne erkanntes Material gibt es 0.85, denselben neutralen Wert,
den `s_texture` bei dünner Datenlage liefert.

Die fünf Gewichtspunkte für `material` kamen von den größten Posten: silhouette
0.23→0.22, proportion 0.15→0.14, color 0.16→0.15, warmth 0.15→0.14, formality 0.12→0.11.
Shoes, pattern und texture blieben unangetastet, beide Sätze summieren sich weiter auf 1.0.

#### Wäsche

Was getragen wurde, geht von selbst in die Wäsche und kommt von selbst zurück. Beim
Vermerken als getragen setzt `log_outfit()` eine Frist (`RACK_LAUNDRY_DAYS`, Vorgabe drei
Tage); bis dahin schlägt die Engine das Teil nicht mehr vor. Umgesetzt **ohne
Hintergrundjob**: gespeichert wird ein Zeitpunkt, „verfügbar" rechnet `is_available()` bei
jeder Abfrage neu aus. Das überlebt Neustarts, kann nicht auseinanderlaufen und braucht
keinen Cron im Container.

Nicht jedes Teil gehört nach einmal Tragen in die Maschine: betroffen sind nur
**Oberteile, Unterteile und Kleider** (`LAUNDRY_CATEGORIES`). Jacken, Schuhe, Gürtel und
Uhren bleiben verfügbar.

Ein unlesbares Datum sperrt nie ein Teil — im Zweifel ist es verfügbar. Vorzeitig
freigeben geht im Detail des Teils oder per `POST /api/items/{id}/verfuegbar`.

Das ergänzt `s_fresh`, ersetzt es aber nicht: die Wäsche ist ein harter Ausschluss für
drei Tage, danach wertet `s_fresh` das Teil noch bis Tag zehn weich ab.

#### Bilanz

`GET /api/stats` wertet das Trageprotokoll aus, das von Anfang an mitgeschrieben, aber
nirgends sichtbar war: meistgetragene Teile, Ladenhüter (mindestens einen Monat da und nie
getragen), was gerade in der Wäsche liegt, und — sofern am Teil ein **Preis** hinterlegt
ist — der Preis pro Tragen. Preis und Kaufdatum sind freiwillig; ohne sie funktioniert
alles wie zuvor, es fehlt nur diese eine Auswertung.

#### Ein Vokabular für beide Seiten

Die Auswahllisten kommen aus `GET /api/vocab`, das Frontend zieht sie beim Start. Vorher
standen dieselben Listen doppelt — in `engine.py` und in `constants.js`. Laufen sie
auseinander, zeigt die Oberfläche stumm „nicht gesetzt" für einen Wert, den das Backend
kennt: ein Fehler, bei dem nichts kaputtgeht und deshalb niemand etwas merkt. Die
Konstanten in `constants.js` bleiben als Rückfallebene, wenn der Aufruf scheitert.

Dieselben Listen prüfen beim Speichern die Eingaben (`_pruefe_vokabular`). Unbekannte
Werte werden **verworfen, nicht abgelehnt** — ein einzelnes schiefes Feld soll nicht das
ganze Teil unspeicherbar machen. Es bleibt dann leer und fällt in der Oberfläche auf.

#### Planen, Merken, Packen

| | |
|---|---|
| **Gemerkte Outfits** | Ein Vorschlag, der funktioniert hat, unter einem Namen (`saved_outfits`). Die Teile stehen als JSON-Liste drin, nicht als Fremdschlüssel — ein gelöschtes Teil soll das Outfit nicht mitreißen, es fehlt dann eben eines und das sieht man. |
| **Kalender** | Ein Tag, ein Outfit (`planned_outfits`, `plan_date` als Primärschlüssel). Die Ansicht zeigt sieben Tage. |
| **Wäsche kennt die Planung** | Was in den nächsten Tagen eingeplant ist, wandert nach dem Tragen **nicht** in die Wäsche. Sonst nimmt die Automatik einem das Hemd weg, das man für Freitag vorgemerkt hat. |
| **Packliste** | `POST /api/packliste` — die kleinste Teilemenge, aus der sich für *n* Tage genug Outfits bauen lassen. |

Die Packliste rechnet **gierig, nicht vollständig**: alle Kombinationen über alle Teilmengen
durchzugehen wäre exponentiell. Stattdessen wird Runde für Runde das beste noch nicht
gepackte Outfit genommen, gewichtet nach `score / (1 + neue Teile)`. Ein Outfit, das nur
aus bereits gepackten Teilen besteht, gewinnt damit gegen ein besseres, das zwei neue
braucht — genau so packt man auch von Hand. Reicht der Schrank nicht für die gewünschten
Tage, sagt die Antwort das (`genug: false`), statt eine zu kurze Liste als vollständig
auszugeben.

#### Einmotten statt löschen

`archived` nimmt ein Teil aus allen Vorschlägen, lässt es aber im Bestand — für
Winterkleidung im Juli. Der Schrank zeigt eingemottete Teile nur, wenn man den Filter
umschaltet. Unterschied zu `paused`: das ist der kurze Fall („liegt gerade in der
Maschine"), `archived` der saisonale.

#### Aussortieren

`GET /api/aussortieren` bewertet nach Alter im Schrank, Tragehäufigkeit, wie oft ein Teil
in abgelehnten Kombinationen steckt, und — falls hinterlegt — dem Preis pro Tragen. Es
liefert **einen Vorschlag mit Begründung, keine Automatik**: was aus dem Schrank fliegt,
entscheidet niemand außer dir. Teile unter 60 Tagen im Bestand bleiben außen vor, sonst
verurteilt die Liste Neuzugänge.

#### Foto vom Outfit

`POST /api/worn/{id}/foto` hängt ein Bild an einen Protokolleintrag. Anders als das
Ganzkörperfoto wird dieses **bewusst gespeichert** — das ist der Zweck. Es geht nie an ein
Modell, sondern nur ins Volume.

#### „Warum wird das nie vorgeschlagen?"

Die häufigste Kritik an Kleiderschrank-Apps ist, dass sie einzelne Stücke stillschweigend
ignorieren. Rack rechnet mit nachvollziehbaren Regeln, also lässt sich die Frage
beantworten: `GET /api/items/{id}/diagnose` geht alle Kombinationen mit diesem Teil durch
und zählt, woran sie scheitern — plus die durchschnittlichen Einzelbewertungen für die
Fälle, in denen es zwar zulässig ist, aber nie oben landet.

Gezählt wird der **erste** greifende Ausschluss je Kombination, genau der, den
`violates()` meldet. Ein Outfit kann an mehreren Dingen kranken; für die Frage „was müsste
ich ändern" zählt das, was zuerst blockiert. Ist das Teil pausiert, eingemottet oder in
der Wäsche, steht das als eigene Antwort davor — dann liegt es nicht an den Regeln.

#### Regen und Wind

`s_material()` bekommt zusätzlich Niederschlag (mm) und Wind (km/h), beides so, wie
Open-Meteo es liefert. Bei Regen werden Wildleder, Satin, Seide und Leinen abgewertet,
bei Wind die durchlässigen Stoffe (Mesh, Leinen, Viskose). Glattes Leder bleibt bewusst
draußen — es verträgt Nieselregen.

Genommen wird jeweils der größere von Momentan- und Tageswert: ein trockener Vormittag
soll nicht kaschieren, dass es abends schüttet. **Ohne Angabe sind beide null**, dann
verhält sich alles exakt wie zuvor — und es war kein neues Gewicht nötig, weil das
Kriterium „passt der Stoff zur Lage" ohnehin schon existierte.

#### Waschgänge

`GET /api/waschgaenge` gruppiert, was gerade in der Wäsche liegt, nach Pflegehinweis und
grob nach hell/dunkel. Teile ohne Pflegeangabe stehen getrennt — raten wäre hier die
falsche Hilfe. Das Etikettfoto (`POST /api/items/{id}/etikett`) ergänzt das: die
Pflegesymbole liest man im Zweifel lieber ab, als sie aus einer Liste zu erraten.

#### Wiederholungsschutz

`POST /api/wiederholung` sagt, ob dieselbe Zusammenstellung kürzlich schon dran war.
Gewertet wird nach Überschneidung (ab 60 %), nicht nach exakter Gleichheit: zwei Outfits,
die sich nur im Gürtel unterscheiden, sind praktisch dasselbe. Ein Treffer beim **selben
Anlass** wiegt schwerer und wird in der Oberfläche deutlicher angezeigt — es geht um die
Frage, ob man dieselben Leute zweimal im selben Aufzug trifft.

#### Schlagworte

Frei wählbar statt aus einer Liste, weil feste Kategorien nie ganz passen — auch das eine
wiederkehrende Kritik an solchen Apps. Gespeichert wird eine Kommaliste, kleingeschrieben
und ohne Doppelte, damit die Suche zuverlässig trifft.

#### Mehrere Personen

Jede Person hat ihren eigenen Schrank, ihr eigenes Protokoll, ihre eigene Planung und ihr
eigenes Profil. Der Personenfilter sitzt dabei auch in `get_item()`, nicht nur in
`list_items()`: sämtliche Einzelzugriffe — ändern, löschen, klonen, Bild abrufen — laufen
über diese eine Funktion, und ohne den Filter käme jeder an fremde Teile, der ihre Kennung
kennt. Die aktive Person kommt als Kopfzeile `X-Rack-Person` oder als
`?person=`; ohne Angabe ist es Person 1 — für den Einzelnutzer ändert sich damit nichts.

Umgesetzt über eine **ContextVar**, die eine Middleware pro Anfrage setzt. Die Abfragen in
`db.py` greifen darauf zurück, wenn ihnen keine Person übergeben wird. Der Alternativweg
— `person_id` an zwanzig Aufrufstellen durchreichen — war die schlechtere Wahl: eine
vergessene Stelle hätte Daten zwischen Personen vermischt, ohne dass etwas kaputtgeht.
ContextVars sind pro Task isoliert, gleichzeitige Anfragen kommen sich nicht ins Gehege.

Zwei Migrationen bauen dafür Tabellen neu auf, weil SQLite weder Constraints noch
Primärschlüssel nachträglich ändern kann: `profile` verliert das `CHECK (id = 1)`,
`planned_outfits` bekommt `PRIMARY KEY (person_id, plan_date)` — sonst hätten zwei
Personen, die denselben Tag planen, sich gegenseitig überschrieben.

**Person 1 lässt sich nicht löschen**: sie trägt den Bestand, der vor der Umstellung
angelegt wurde. Und sie wird beim Start angelegt, falls sie fehlt — sonst bekäme die erste
*hinzugefügte* Person die 1 und ihre Sachen lägen im Altbestand.

#### Kopieren und Aufräumen

**Kopie** (`POST /api/items/{id}/klonen`) legt ein zweites Exemplar desselben Stücks an:
Schnitt, Material, Länge, Marke, Größe, Pflege und Schlagworte werden übernommen, **Foto
und Verlauf nicht**. Das Foto zeigt das andere Teil, und ein falsches Bild ist schlechter
als gar keins; getragen wurde die Kopie noch nie. Gedacht für dasselbe Shirt in einer
zweiten Farbe.

**Verwaiste Bilder** (`GET`/`POST /api/verwaiste-bilder`) findet Dateien im Volume, auf
die kein Datensatz mehr zeigt. Die Referenzen werden dabei **über alle Personen** gesammelt
— mit dem Personenfilter würde das Aufräumen die Bilder der jeweils anderen als
vermeintlich verwaist löschen. Die Liste wird direkt vor dem Löschen neu bestimmt, damit
kein Bild erwischt wird, das zwischen Anzeigen und Bestätigen entstanden ist.

Solche Reste stammen aus Löschungen von früher; seit dem 29.08.2026 räumt jede Löschung
selbst auf.

#### Was der Kurations-Prompt inzwischen leistet

Zwei Nachschärfungen gegenüber `rack.jsx`, beide auf Ansage:

1. **Keine Leerschritte.** Ein Schritt, der beschreibt, etwas *nicht* zu tun, ist keiner.
2. **Verdeckte Teile** (30.08.2026). Der Auslöser war ein Gürtel, zu dem „offen tragen"
   im Styling stand, während ein hüftlanges, nicht eingestecktes T-Shirt darüber hing —
   ein Widerspruch, der beim Anziehen auffällt und vorher nicht.

Für einen Gürtel im Outfit muss jetzt genau eine von drei Aussagen fallen: ein Handgriff,
der ihn zeigt (vorne einstecken, hinten hängen lassen); ein Halbsatz, dass er hier den
Sitz der Hose macht und nur in Bewegung aufblitzt; oder er landet unter „weglassen".
Stillschweigend übergehen zählt nicht — er ist im Outfit, also gehört ein Wort dazu.

Damit das Modell das beurteilen kann, bekommt es seit derselben Änderung auch die
**Kategorie** jedes Teils: „hüftlang" bedeutet bei einem Oberteil etwas anderes als bei
einer Hose.

Nachgemessen an drei kuratierten Outfits: vor der Schärfung sprachen zwei von drei den
Gürtel an, danach drei von drei — je einmal pro Variante.

#### Warum `max_tokens` großzügig steht

Bei den aktuellen Modellen deckt `max_tokens` **auch das Nachdenken** ab. Mit 2000 brach
die Kuration regelmäßig mitten im JSON ab, obwohl der Text selbst kaum 700 Zeichen hatte —
das Denken hatte den Platz aufgebraucht. Jetzt 8000; bezahlt wird ohnehin nur, was
tatsächlich erzeugt wird.

`ai.ask()` prüft dafür `stop_reason == "max_tokens"` und meldet es als eigenen Fall. Sonst
scheitert erst das JSON-Lesen, und die Meldung zeigt auf ein Formatproblem, obwohl schlicht
der Platz nicht reichte.

#### JavaScript-Semantik

An drei Stellen musste die JavaScript-Semantik ausdrücklich nachgebaut werden, weil
Python sich sonst anders verhält — jede Stelle ist im Quelltext kommentiert:

- `Math.round` rundet halbe Werte immer nach oben, Pythons `round` zur geraden Zahl.
- `Math.max` färbt bei einem `NaN` im Eingang das ganze Ergebnis auf `NaN`, Pythons `max`
  liefert je nach Reihenfolge irgendetwas.
- `parseInt("zz", 16)` ergibt `NaN` statt eines Fehlers, was bei kaputten Farbwerten zu
  anderen Bewertungen führt.

Geprüft wird das zweifach:

Die Tests laufen außerdem **im Docker-Build** (Stufe `tests`): ein Image mit roter Engine
kann gar nicht erst entstehen, `docker compose build` bricht dann ab. Zur Laufzeit liegen
weder pytest noch die Tests im Image.

```bash
# Unit-Tests, halten die Schwellwerte fest
cd rack/backend && python -m pytest tests -q

# Gegenprobe: dieselben Eingaben durch Python und durch das echte rack.jsx
cd rack/backend/tests/crosscheck
python extract.py    # schneidet die Engine aus rack.jsx.vorlage zu engine.mjs
python gen.py        # erzeugt cases.json und rechnet die Python-Seite
docker run --rm -v "$PWD:/w" -w /w node:22-alpine node driver.mjs cases.json theirs.json
python diff.py       # vergleicht jeden Zahlenwert
```

Die Gegenprobe füttert 400 `derive`-Fälle, 160 Schränke und knapp 300 `violates`-Fälle
durch beide Fassungen und vergleicht jeden Zahlenwert.

Seit der Material-Erweiterung weicht der Port an vier Stellen **absichtlich** ab:
`score.sub.material` gibt es in `rack.jsx` gar nicht, `score.total` und `picks.total`
folgen den neuen Gewichten, und `derive.warmth` unterscheidet sich genau dort, wo
`rack.jsx` das Material falsch zuordnete oder nicht kannte. `diff.py` weist diese Fälle
getrennt als erwartet aus und liefert Exit-Code 1 nur bei **unerwarteten** Abweichungen —
für alles Übrige (`violates()`, Farbmathematik, Silhouette, Proportion, Muster, Schuhe)
bleibt die Gegenprobe unverändert scharf.

---

## Wenn etwas klemmt

| Beobachtung | Ursache und Abhilfe |
|---|---|
| Seite lädt gar nicht | Tailscale auf dem Gerät verbunden? `docker exec tailscale tailscale serve status` muss den Proxy auf `127.0.0.1:8099` zeigen. |
| „Der Server ist nicht erreichbar" in der App | `docker ps --filter name=rack` — Healthcheck rot? Dann `docker compose logs rack`. |
| Fotos werden nicht freigestellt | Im Log steht die Ursache mit Meldung. Der Hintergrund bleibt dann stehen, das Teil wird trotzdem gespeichert. |
| Material bleibt leer / „nicht gesetzt" | Das Modell hat etwas geliefert, das sich keinem Wert aus `MATERIALS` zuordnen ließ. Auf der Prüfkarte steht es dann als unsicher markiert — von Hand auswählen. Kommt ein Material öfter vor, gehört es in `MATERIAL_SYNONYMS` (Backend) und ggf. in `MATERIALS` plus `WARM_WORDS`. |
| Material wird schlechter erkannt als erwartet | `RACK_MODEL_IMAGE_DIM` prüfen. Unter etwa 1200 Pixel verschwinden Cordrippen und Strickstruktur im Bild. Claude Sonnet 5 verarbeitet bis 2576 Pixel; darüber skaliert die API selbst herunter, das bringt nichts mehr. |
| Erste Erfassung nach einem Update ist langsam | Normal. Danach etwa ein bis zwei Sekunden pro Foto. rembg ist CPU-lastig, und der N150 hat nicht viel Luft. Zwanzig Teile am Stück belasten den Server spürbar. |
| „Ohne Schlüssel" steht oben | `ANTHROPIC_API_KEY` in der `.env` ist leer oder wurde nicht übernommen. Nach dem Eintragen `docker compose up -d` — `restart` allein reicht nicht. |
| Vorschläge ohne Styling-Schritte | Die Kuratierung war nicht erreichbar. Die App zeigt dann die Rangfolge der Engine und schreibt den Grund darunter. |
| „Mit strengen Regeln blieb zu wenig übrig" | Kein Fehler. Die Engine lockert gestuft, wenn unter drei zulässige Kombinationen herauskommen. Mehr Teile im Schrank lösen das. |

---

## Was bewusst nicht gemacht wurde

- Kein Eintrag in `arr-stack/docker-compose.yml`. Ein zusätzlicher Dienst dort würde bei
  jedem `docker compose up -d` den ganzen Medien-Stack anfassen.
- Kein Unraid-Template unter `templates-user/`. Das Verzeichnis ist auf diesem Server
  leer, alles läuft über das Plugin `compose.manager`. Ein Template würde bei einem
  „Apply" aus der Docker-Oberfläche die Compose-Definition überschreiben.
- Keine automatische Nachtsicherung eingerichtet.
- Nichts in `appdata` außerhalb von `rack/` angefasst, keine bestehende SWAG- oder
  Container-Konfiguration geändert.
