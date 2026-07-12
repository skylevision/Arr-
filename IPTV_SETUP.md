# IPTV / Live TV — Fernsehen in Jellyfin (über VPN)

Anleitung zur Einrichtung von Live-TV über **Threadfin** als IPTV-Proxy und Jellyfin
als Abspieler — erreichbar von überall über Tailscale. Der gesamte Live-TV-Traffic
läuft dabei durch ein **Premiumize-VPN** (nur Threadfin, nicht der restliche Stack).

---

## Inhaltsverzeichnis

1. [Wie funktioniert das?](#1-wie-funktioniert-das)
2. [VPN einrichten (Premiumize) + starten](#2-vpn-einrichten-premiumize--starten)
3. [M3U-Playlist / Anbieter hinzufügen](#3-m3u-playlist--anbieter-hinzufügen)
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
  M3U / Xtream            XMLTV EPG
  (Senderliste)           (Programmzeitschrift)
       │                        │
       └──────────┬─────────────┘
                  ▼
      ┌───────────────────────────┐
      │  gluetun (VPN-Gateway)    │  ← Premiumize OpenVPN
      │  ┌─────────────────────┐  │    NUR Threadfin-Traffic
      │  │     Threadfin       │  │    Killswitch bei VPN-Ausfall
      │  │     Port 34400      │  │    emuliert HDHomeRun-Tuner
      │  └─────────────────────┘  │
      └────────────┬──────────────┘
                   │ HDHomeRun-Protokoll  (http://gluetun:34400)
                   ▼
          ┌────────────────┐
          │    Jellyfin    │  ← Media-Server (direkte Leitung)
          │   Live TV Tab  │    zeigt Kanäle + Programm
          └────────────────┘
                   │
     ──────────────┴──────────────────────
     Smartphone   PC   Fire TV   Browser
     (via Tailscale von überall)
```

**Threadfin** fungiert als Mittler zwischen deinen IPTV-Quellen und Jellyfin:
- Nimmt M3U-Playlisten oder Xtream-Codes-Zugänge entgegen (Senderliste mit Stream-URLs)
- Verknüpft Sender mit EPG-Daten (Programmzeitschrift via XMLTV)
- Stellt sich gegenüber Jellyfin als **HDHomeRun-Tuner** vor
- Jellyfin nutzt Threadfin genau wie einen echten TV-Empfänger

**Split-Tunnel:** Threadfin teilt sich den Netzwerk-Stack des VPN-Containers **gluetun**
(`network_mode: service:gluetun`). Dadurch läuft *jeder* Live-TV-Request durch Premiumize,
während Radarr/Sonarr/Jellyfin/Downloads auf der normalen Leitung bleiben. gluetun bringt
einen **Killswitch** mit: Fällt das VPN aus, verliert Threadfin die Verbindung — es leakt
nie über deine echte IP.

> **Rechtlicher Hinweis:** Threadfin und der VPN-Split-Tunnel sind neutrale Technik. Für
> welche IPTV-Quelle du sie nutzt, bist du selbst verantwortlich — nur Anbieter/Inhalte
> verwenden, zu denen du berechtigt bist.

---

## 2. VPN einrichten (Premiumize) + starten

Live TV liegt hinter dem Compose-Profil **`iptv`** und startet **nicht** mit dem
normalen `docker compose up -d`, sondern gezielt.

### Schritt 1 — OpenVPN-Config von Premiumize holen

1. Bei [premiumize.me](https://www.premiumize.me) einloggen → **Plugins** (bzw.
   *premiumize.me/plugins*) → Protokoll **OpenVPN** wählen.
   > Von den angebotenen Protokollen (SoftEther, OpenVPN, PPTP, SSTP, L2TP) ist **OpenVPN**
   > das einzige, das mit gluetun funktioniert — und für Live-TV-Bitraten schnell genug.
2. Die `.ovpn`-Datei herunterladen und auf dem Server ablegen als:
   ```
   /mnt/user/appdata/gluetun/premiumize.ovpn
   ```
3. **`remote`-Zeile auf eine IP setzen** — gluetun akzeptiert bei Custom-Configs nur
   IP-Adressen, keine Hostnamen. Server-Hostnamen auflösen und ersetzen:
   ```bash
   getent hosts vpn-nl.premiumize.me            # z. B. → 185.107.94.249
   sed -i 's|^remote .*|remote 185.107.94.249 1194|' /mnt/user/appdata/gluetun/premiumize.ovpn
   ```
   > Ändert Premiumize später die Server-IP (VPN wird plötzlich nicht mehr healthy),
   > einfach neu auflösen und die `remote`-Zeile aktualisieren.
4. Deine Premiumize-VPN-Zugangsdaten (Customer ID + PIN/Passwort) in die `.env` eintragen:
   ```
   PREMIUMIZE_VPN_USER=...
   PREMIUMIZE_VPN_PASSWORD=...
   ```

### Schritt 2 — Live TV starten

```bash
docker compose --profile iptv up -d
bash bootstrap/11-threadfin.sh   # Threadfin an alle Interfaces binden (0.0.0.0)
```

Der zweite Befehl ist **wichtig**: Threadfin bindet im VPN-Netz-Stack sonst nur an die
Tunnel-IP und ist weder über den Host-Port noch aus Jellyfin erreichbar. Das Skript ist
idempotent — bei bereits korrekter Einstellung macht es nichts.

Prüfen, ob das VPN steht:

```bash
docker logs gluetun 2>&1 | grep -i "public ip"   # zeigt die VPN-IP (nicht deine echte)
docker inspect -f '{{.State.Health.Status}}' gluetun   # sollte "healthy" sein
```

Threadfin-Webinterface aufrufen (Port wird über gluetun veröffentlicht):
```
http://<unraid-ip>:34400/web
```
oder via Tailscale / DNS-Name:
```
http://<tailscale-ip>:34400/web     bzw.     http://threadfin.fritz.box:34400/web
```

Beim ersten Start erscheint der **Setup-Wizard** von Threadfin → durchklicken.

> **Stoppen:** `docker compose --profile iptv stop threadfin gluetun`

---

## 3. M3U-Playlist / Anbieter hinzufügen

### Anbieter mit Zugangsdaten (Xtream Codes oder M3U-Link)

Kommerzielle IPTV-Anbieter liefern meist eines von beidem:

- **Xtream Codes** (Server-URL + Benutzername + Passwort) — in Threadfin unter
  `Einstellungen → Xtream` direkt eintragen, kein M3U-Link nötig. Threadfin holt
  Senderliste **und** EPG in einem Rutsch.
- **M3U-Link** (fertige URL, oft mit `?username=…&password=…`) — wie unten unter
  „Im Threadfin-Webinterface" einbinden; die EPG-URL bekommst du meist separat vom Anbieter.

> Beide Wege laufen bei diesem Setup automatisch durch das Premiumize-VPN, weil Threadfin
> im gluetun-Netz-Stack läuft — du musst dafür nichts Zusätzliches tun.

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
→ URL: http://gluetun:34400
→ Speichern
```

> **Wichtig:** Die URL ist `http://gluetun:34400`, **nicht** `http://threadfin:34400`.
> Threadfin läuft im Netz-Stack von gluetun und hat keinen eigenen Docker-Namen mehr —
> im arr_net ist der Threadfin-Port über den Namen `gluetun` erreichbar.

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
→ Tuner-URL in Jellyfin korrekt? `http://gluetun:34400` (nicht `threadfin`, nicht `localhost`)
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
→ Threadfin startet erst, wenn **gluetun healthy** ist (`depends_on`). Hängt gluetun,
  startet auch Threadfin nicht — zuerst das VPN prüfen (nächster Punkt).

**VPN (gluetun) wird nicht healthy / Threadfin ohne Verbindung**
→ Logs: `docker logs gluetun` — nach `AUTH_FAILED`, `TLS`, oder `public ip` suchen
→ Liegt die Config unter `/mnt/user/appdata/gluetun/premiumize.ovpn`?
→ `PREMIUMIZE_VPN_USER` / `PREMIUMIZE_VPN_PASSWORD` in `.env` korrekt?
→ VPN-IP testen: `docker exec gluetun wget -qO- https://ipinfo.io/ip` (muss die
  Premiumize-IP zeigen, nicht deine echte)
→ Nach `.env`- oder `.ovpn`-Änderung neu aufbauen:
  `docker compose --profile iptv up -d --force-recreate gluetun threadfin`

**Kein Tuner in Jellyfin gefunden**
→ URL ist `http://gluetun:34400` (nicht `threadfin`) — siehe Abschnitt 6
→ Läuft der iptv-Stack? `docker ps | grep -E 'gluetun|threadfin'`

**M3U-Playlist leer nach Update**
→ Prüfen ob die Anbieter-/GitHub-URL erreichbar ist. Achtung: Threadfin löst DNS
  **durch das VPN** auf (gluetun) — bei DNS-Problemen zuerst `docker logs gluetun` prüfen
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
