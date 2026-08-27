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

Zusätzlich gibt es in der App unter Profil einen **Export**, der eine einzelne
JSON-Datei mit Teilen, Bildern, Profil und Rückmeldungen herunterlädt — dasselbe Format
wie im Prototypen. Der **Import** liest sowohl diese Datei als auch einen Export aus dem
alten Artefakt-Prototypen. Der Import ist idempotent: dieselbe Datei zweimal eingelesen
legt nichts doppelt an.

Als Nachtsicherung eingerichtet werden kann das Skript über die Unraid-Oberfläche unter
Settings, User Scripts — bewusst nicht automatisch eingetragen, das ist deine
Entscheidung.

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
  Dockerfile              dreistufig: Frontend bauen, Abhängigkeiten und Modell, Laufzeit
  docker-compose.yml      eigenes Projekt, bewusst getrennt vom arr-stack
  docker-entrypoint.sh    Umask, Verzeichnisse, Modell spiegeln, auf PUID:PGID wechseln
  .env                    Schlüssel und Konfiguration, Rechte 600, nicht im Git
  backend/
    app/engine.py         die Regel-Engine, 1:1 aus rack.jsx portiert
    app/gaps.py           Lückenanalyse mit virtuellem Test
    app/prompts.py        die Prompts, wortgleich übernommen
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

Die Fachlogik ist aus `rack.jsx` übernommen, ohne inhaltliche Änderungen: `derive()`, die
Farbmathematik, alle Einzelbewertungen, die Gewichtungen `W` und `W_OPEN`, der
Feedbackfaktor, die harten Ausschlüsse in `violates()` samt gestufter Lockerung und die
Lückenanalyse mit dem Kandidatenkatalog.

An drei Stellen musste die JavaScript-Semantik ausdrücklich nachgebaut werden, weil
Python sich sonst anders verhält — jede Stelle ist im Quelltext kommentiert:

- `Math.round` rundet halbe Werte immer nach oben, Pythons `round` zur geraden Zahl.
- `Math.max` färbt bei einem `NaN` im Eingang das ganze Ergebnis auf `NaN`, Pythons `max`
  liefert je nach Reihenfolge irgendetwas.
- `parseInt("zz", 16)` ergibt `NaN` statt eines Fehlers, was bei kaputten Farbwerten zu
  anderen Bewertungen führt.

Geprüft wird das zweifach:

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
durch beide Fassungen und vergleicht jeden Zahlenwert. Ergebnis zuletzt: keine Abweichung.

---

## Wenn etwas klemmt

| Beobachtung | Ursache und Abhilfe |
|---|---|
| Seite lädt gar nicht | Tailscale auf dem Gerät verbunden? `docker exec tailscale tailscale serve status` muss den Proxy auf `127.0.0.1:8099` zeigen. |
| „Der Server ist nicht erreichbar" in der App | `docker ps --filter name=rack` — Healthcheck rot? Dann `docker compose logs rack`. |
| Fotos werden nicht freigestellt | Im Log steht die Ursache mit Meldung. Der Hintergrund bleibt dann stehen, das Teil wird trotzdem gespeichert. |
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
