# IPTV / Live TV — Deutsches Fernsehen in Jellyfin

Anleitung zur Einrichtung von deutschem Live-TV (inkl. Sportkanäle) über **Threadfin**
als IPTV-Proxy und Jellyfin als Abspieler — erreichbar von überall über Tailscale.

---

## Inhaltsverzeichnis

1. [Wie funktioniert das?](#1-wie-funktioniert-das)
2. [Threadfin starten](#2-threadfin-starten)
3. [M3U-Playlist hinzufügen](#3-m3u-playlist-hinzufügen)
4. [EPG einrichten (Programmzeitschrift)](#4-epg-einrichten-programmzeitschrift)
5. [Kanäle filtern & aktivieren](#5-kanäle-filtern--aktivieren)
6. [Jellyfin Live TV konfigurieren](#6-jellyfin-live-tv-konfigurieren)
7. [Verfügbare deutsche Sender](#7-verfügbare-deutsche-sender)
8. [Sport — Was geht, was nicht](#8-sport--was-geht-was-nicht)
9. [DVR / Aufnahmen](#9-dvr--aufnahmen)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Wie funktioniert das?

```
  M3U Playlist            XMLTV EPG
  (Senderliste)           (Programmzeitschrift)
       │                        │
       └──────────┬─────────────┘
                  ▼
         ┌────────────────┐
         │   Threadfin    │  ← IPTV-Proxy
         │   Port 34400   │    verwaltet Sender + EPG
         └───────┬────────┘    emuliert HDHomeRun-Tuner
                 │ HDHomeRun-Protokoll
                 ▼
         ┌────────────────┐
         │    Jellyfin    │  ← Media-Server
         │   Live TV Tab  │    zeigt Kanäle + Programm
         └────────────────┘
                 │
    ─────────────┴──────────────────────
    Smartphone   PC   Fire TV   Browser
    (via Tailscale von überall)
```

**Threadfin** fungiert als Mittler zwischen deinen IPTV-Quellen und Jellyfin:
- Nimmt M3U-Playlisten entgegen (Senderliste mit Stream-URLs)
- Verknüpft Sender mit EPG-Daten (Programmzeitschrift via XMLTV)
- Stellt sich gegenüber Jellyfin als **HDHomeRun-Tuner** vor
- Jellyfin nutzt Threadfin genau wie einen echten TV-Empfänger

---

## 2. Threadfin starten

Threadfin startet automatisch mit dem Stack:

```bash
docker compose up -d
```

Webinterface aufrufen:
```
http://<unraid-ip>:34400/web
```
oder via Tailscale:
```
http://<tailscale-ip>:34400/web
```

Beim ersten Start erscheint der **Setup-Wizard** von Threadfin → durchklicken.

---

## 3. M3U-Playlist hinzufügen

### Was ist eine M3U-Playlist?

Eine M3U-Datei ist eine Textdatei, die Sender-Namen, Stream-URLs und Metadaten
(Logos, EPG-IDs) enthält. Threadfin lädt diese URL automatisch und aktualisiert sie.

### Im Threadfin-Webinterface

```
Einstellungen → M3U → Neuen Playlist hinzufügen
→ URL eintragen → Speichern → Update Now
```

### Empfohlene kostenlose Quellen (legal, öffentlich-rechtlich + FTA)

#### Option A — Kodinerds IPTV (empfohlen, vollständig)

```
https://raw.githubusercontent.com/jnk22/kodinerds-iptv/master/iptv/kodi/kodi_tv.m3u
```

Enthält: ARD (alle Dritten), ZDF, ZDFneo, ZDFinfo, arte, 3sat, Phoenix, KiKa,
RTL, Sat.1, ProSieben, VOX, RTL2, Kabel Eins, n-tv, ntv, Sport1, Eurosport 1,
ServusTV, ORF 1/2, SRF 1/2, und viele regionale Sender.

#### Option B — Bereinigte deutsche Liste

```
https://raw.githubusercontent.com/josxha/german-tv-m3u/main/german-tv.m3u
```

Weniger Sender, dafür ohne Teleshopping und Duplikate — gut für einen sauberen Start.

#### Option C — Internationales Projekt (iptv-org)

```
https://iptv-org.github.io/iptv/countries/de.m3u
```

Größte Sammlung, enthält auch deutschsprachige Sender aus Österreich und der Schweiz.

> **Hinweis**: Die Streams basieren auf öffentlichen HLS-Endpunkten der Sender selbst
> (ARD Mediathek-Infrastruktur, etc.). Sie sind legal und kostenlos, können aber
> gelegentlich ihre URL ändern. Die o. g. Projekte werden community-gepflegt und
> aktualisiert.

### Abo-Dienste (kostenpflichtig)

| Dienst | Preis | Sender | M3U-Export |
|---|---|---|---|
| **Zattoo** | ab 6,99 €/Mo | ~100 DE-Sender inkl. Sky Bundesliga | Inoffiziell via Dritttools möglich |
| **waipu.tv** | ab 7,49 €/Mo | ~310 Sender, DAZN zubuchbar | API vorhanden, Dritttools verfügbar |
| **Xtream-Anbieter** | variiert | sehr unterschiedlich | Xtream-API nativ in Threadfin unterstützt |

> **Xtream-API in Threadfin**: Falls dein Anbieter Xtream Codes unterstützt, kannst du
> unter `Einstellungen → Xtream` direkt Zugangsdaten eintragen — kein M3U-Link nötig.

---

## 4. EPG einrichten (Programmzeitschrift)

EPG (Electronic Program Guide) liefert die Programmdaten: Sendetitel, Beschreibungen,
Start- und Endzeiten. Ohne EPG siehst du nur den Kanalnamen, aber kein Programm.

### Im Threadfin-Webinterface

```
Einstellungen → XMLTV → Neue EPG-Quelle hinzufügen
→ URL eintragen → Speichern → Update Now
```

### Empfohlene EPG-Quellen

#### Option A — iptv-org EPG (beste Channel-ID-Übereinstimmung mit iptv-org M3U)

```
https://epg.112114.xyz/epg.xml.gz
```
oder für Deutschland gefiltert:
```
https://raw.githubusercontent.com/iptv-org/epg/gh-pages/guides/de/all.xml.gz
```

Enthält Programmdaten für die meisten deutschen Free-TV-Sender (7 Tage).

#### Option B — XMLTV-Guide (deutschlandspezifisch)

```
https://xmltv.ch/xmltv/xmltv-epg.xml.gz
```

Gute Abdeckung für ARD, ZDF, RTL-Gruppe, ProSiebenSat.1 (7 Tage).

#### Option C — epg.best

```
https://epg.best/epg.xml.gz
```

Breite internationale Abdeckung inkl. Deutschland.

### EPG-Aktualisierungsintervall

In Threadfin unter `Einstellungen → EPG`:
- **Update interval**: `12` Stunden empfohlen (EPG-Quellen aktualisieren täglich)

### Channel-Mapping (falls EPG nicht automatisch matched)

Wenn Kanäle kein Programm anzeigen:
```
Threadfin → Kanäle → [Kanal auswählen] → EPG-ID manuell zuordnen
```

Die EPG-IDs aus dem XMLTV-File müssen den `tvg-id`-Werten in der M3U entsprechen.
Bei Mismatch: einfach per Dropdown in Threadfin den richtigen Kanal zuordnen.

---

## 5. Kanäle filtern & aktivieren

Nicht alle Sender aus der M3U werden benötigt. In Threadfin:

```
Kanäle → Alle Kanäle
→ Unerwünschte Sender deaktivieren (Schalter)
→ Reihenfolge per Drag & Drop anpassen
→ Sendernamen und Logos können überschrieben werden
```

**Empfohlene Vorgehen:**
1. Alle deaktivieren: oben „Deselect All"
2. Gewünschte Sender einzeln aktivieren
3. Kanalnummern vergeben (werden in Jellyfin angezeigt)
4. Speichern

**Anzahl gleichzeitiger Streams (Tuner):**
```
Einstellungen → General → Tuner (Buffer) → z. B. 4
```
Jeder Tuner ermöglicht einen parallelen Live-Stream. 2–4 ist für den Heimgebrauch ausreichend.

---

## 6. Jellyfin Live TV konfigurieren

### Tuner hinzufügen

```
Jellyfin → Admin-Panel (⚙️) → Live TV → Tuner-Geräte → +
→ Tuner-Typ: HD HomeRun
→ URL: http://threadfin:34400
→ Speichern
```

> Jellyfin sucht automatisch nach HDHomeRun-Geräten im Netzwerk — Threadfin erscheint
> dabei möglicherweise nicht. In diesem Fall manuell die URL eintragen.

### Programmdaten hinzufügen

```
Jellyfin → Admin-Panel → Live TV → TV Guide-Datenanbieter → +
→ XMLTV
→ URL: [gleiche EPG-URL wie in Threadfin]
→ Speichern
```

### Kanal-Scan

```
Jellyfin → Admin-Panel → Live TV → [Kanal-Scan-Symbol]
→ warten bis alle Kanäle geladen sind (kann 1–2 Minuten dauern)
```

### Live TV nutzen

In der Jellyfin-App:
```
Startseite → Live TV
oder
Bibliothek → Live TV → Kanäle
```

**In der Jellyfin-App (Mobile/TV):** Live TV Tab ist direkt auf der Startseite verfügbar.

---

## 7. Verfügbare deutsche Sender

### Öffentlich-Rechtlich (kostenlos, immer verfügbar)

| Sender | Inhalt |
|---|---|
| **ARD / Das Erste** | Vollprogramm, Tagesschau, Sport |
| **ZDF** | Vollprogramm, ZDF Sportstudio |
| **ZDFneo** | Serien, Dokumentationen |
| **ZDFinfo** | Dokumentationen, Nachrichten |
| **3sat** | Kultur, Wissenschaft, Dokumentationen |
| **arte** | Kultur (DE/FR) |
| **Phoenix** | Politik, Nachrichten, Bundestagsdebatten live |
| **KiKa** | Kinderprogramm |
| **ARD-Dritte** | BR, hr, MDR, NDR, rbb, SR, SWR, WDR |
| **funk** | Digitales Jugendangebot |

### Privat (frei empfangbar, FTA)

| Sender | Inhalt |
|---|---|
| **RTL** | Vollprogramm, RTL Aktuell |
| **Sat.1** | Vollprogramm, Sat.1 Nachrichten |
| **ProSieben** | Unterhaltung, US-Serien |
| **VOX** | Kochshows, Doku-Soaps |
| **RTL2** | Reality TV |
| **Kabel Eins** | Spielfilme, Doku-Soaps |
| **n-tv** | Nachrichten (RTL-Gruppe) |
| **ServusTV** | Sport, Dokumentationen (AT/DE) |

### Sport (frei empfangbar)

| Sender | Sport-Inhalt |
|---|---|
| **Sport1** | Handball, Darts, eSports, 3. Liga-Highlights, Motor Sport |
| **Eurosport 1** | Radsport, Tennis, Wintersport, Olympia |
| **ARD/ZDF** | Champions League (Konferenz), DFB-Pokal, Olympia |

---

## 8. Sport — Was geht, was nicht

### Was kostenlos via Threadfin läuft ✓

| Sport | Sender | Verfügbarkeit |
|---|---|---|
| Bundesliga Highlights | Sport1 (Fantalk), ARD Sportschau | ✓ kostenlos |
| Champions League Konferenz | ZDF (Saison-abhängig) | ✓ kostenlos |
| DFB-Pokal | ARD/ZDF | ✓ kostenlos |
| Formel 1 (Highlights) | RTL (einige Rennen live) | ✓ kostenlos |
| Handball Bundesliga | Sport1 | ✓ kostenlos |
| Darts WM / Premier League | Sport1 | ✓ kostenlos |
| Olympische Spiele | ARD/ZDF | ✓ kostenlos |
| Wintersport | ARD/ZDF, Eurosport 1 | ✓ kostenlos |
| Tennis (Roland Garros, etc.) | Eurosport 1 | ✓ kostenlos |

### Was ein separates Abo benötigt ✗

| Dienst | Inhalt | Preis | Via Threadfin? |
|---|---|---|---|
| **Sky Sport** | Bundesliga (Sa), F1 live, Golf, NFL | ab 25 €/Mo | ✗ — kein legaler M3U-Export |
| **DAZN** | Bundesliga (Fr/So), Champions League, NFL, Boxen | ab 14,99 €/Mo | ✗ — kein legaler M3U-Export |
| **Eurosport 2** | Mehr Tennis, Radsport | Discovery+-Abo nötig | ✗ — DRM-geschützt |
| **MagentaSport** | DEL, Basketball, 3. Liga live | 10 €/Mo | ✗ — kein legaler M3U-Export |

> **Wichtiger Hinweis**: Sky, DAZN und MagentaSport sind **DRM-geschützt** (Widevine/PlayReady).
> Es gibt zwar M3U-Listen im Internet, die diese Sender versprechen — diese verstoßen jedoch
> gegen deutsches Urheberrecht (§ 95a UrhG) und die Nutzungsbedingungen der Anbieter.
> Nutze für diese Dienste die offiziellen Apps (Sky Go, DAZN-App, MagentaSport-App),
> die alle auf Geräten mit Tailscale-Zugang verfügbar sind.

### Empfehlung für Sports-Fans

```
Kostenlos via Threadfin:    Sport1 + Eurosport 1 + ARD/ZDF
DAZN-App auf Fire TV:       Bundesliga Fr/So + Champions League + NFL
Sky Go / WOW:               Bundesliga Sa + Formel 1 + Golf
```

Die Apps laufen parallel zu Jellyfin auf demselben Fire TV Stick — kein weiteres Gerät nötig.

---

## 9. DVR / Aufnahmen

Jellyfin unterstützt **Live TV-Aufnahmen** wenn ein Tuner konfiguriert ist.

### Aufnahme einrichten

```
Jellyfin → Live TV → [Kanal wählen] → [Sendung auswählen]
→ Aufnehmen (⏺)
→ Einmalig oder Serie
```

### Speicherort konfigurieren

```
Jellyfin → Admin → Live TV → Aufnahmen → Pfad: /data/media/recordings
```

Den Ordner vorher anlegen:
```bash
mkdir -p /mnt/user/data/media/recordings
chown 99:100 /mnt/user/data/media/recordings
```

Und in `docker-compose.yml` unter Jellyfin volumes hinzufügen (einmalig):
```yaml
- ${DATA}/media:/data/media  # recordings werden unter /data/media/recordings abgelegt
```

> **Hinweis**: Aufnahmen benötigen Speicherplatz. Plane entsprechende Kapazität ein
> (~2–8 GB/Stunde je nach Qualität).

---

## 10. Troubleshooting

**Keine Kanäle in Jellyfin**
→ Threadfin läuft? `docker logs threadfin`
→ M3U in Threadfin geladen? Threadfin UI → Kanäle → Liste leer?
→ Tuner-URL in Jellyfin korrekt? `http://threadfin:34400` (nicht `localhost`)
→ Kanal-Scan in Jellyfin neu starten: Admin → Live TV → Kanal-Scan

**EPG zeigt kein Programm**
→ XMLTV-URL in Threadfin korrekt und erreichbar?
→ Threadfin → EPG → Letzter Update-Zeitstempel prüfen
→ Channel-ID-Mapping manuell durchführen (Threadfin → Kanäle → EPG-Zuordnung)
→ In Jellyfin: Admin → Live TV → Guide-Provider → Programm aktualisieren

**Streams brechen ab / Buffering**
→ Tuner-Anzahl in Threadfin zu niedrig? → Einstellungen → Tuner erhöhen (z. B. auf 4)
→ Netzwerkbandbreite prüfen — HD-Streams benötigen 5–15 Mbit/s
→ Transkodierung in Jellyfin ausschalten (Direct Play bevorzugen)

**Bestimmte Sender nicht verfügbar**
→ M3U-URL aktualisiert? Manche Sender ändern ihre Stream-URLs
→ In Threadfin: M3U → Update Now
→ Anderen M3U-Anbieter versuchen (kodinerds ↔ iptv-org)

**Threadfin startet nicht**
→ Verzeichnis-Berechtigungen prüfen:
  ```bash
  chown -R 99:100 /mnt/user/appdata/threadfin/
  ```
→ Logs: `docker logs threadfin`

**M3U-Playlist leer nach Update**
→ Prüfen ob die GitHub-URL erreichbar ist (Unraid benötigt DNS → AdGuard aktiv?)
→ Alternativ: M3U-Datei lokal herunterladen und als Datei in Threadfin einbinden

---

## Schnellübersicht — Adressen

| Dienst | URL |
|---|---|
| Threadfin Web UI | `http://<unraid-ip>:34400/web` |
| Jellyfin Live TV | `http://<unraid-ip>:8096` → Live TV Tab |

## Empfohlene M3U + EPG Kombination

| | URL |
|---|---|
| **M3U** | `https://raw.githubusercontent.com/jnk22/kodinerds-iptv/master/iptv/kodi/kodi_tv.m3u` |
| **EPG** | `https://raw.githubusercontent.com/iptv-org/epg/gh-pages/guides/de/all.xml.gz` |

---

*Threadfin GitHub: [github.com/Threadfin/Threadfin](https://github.com/Threadfin/Threadfin)*
*Docker Image: [fyb3roptik/threadfin](https://hub.docker.com/r/fyb3roptik/threadfin)*
*kodinerds-iptv: [github.com/jnk22/kodinerds-iptv](https://github.com/jnk22/kodinerds-iptv)*
