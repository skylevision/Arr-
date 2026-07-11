# INVENTORY.md — Ist-Zustand Arr-Stack (Phase 0)

> Aufgenommen am **2026-07-11** per SSH (`root@192.168.178.5`, Host `Tower`), rein lesend.
> Alle Secrets sind hier maskiert; vollständige Werte liegen nur auf dem Server.

## 1. Host

| | |
|---|---|
| Server | `Tower`, Unraid **7.3.0**, Kernel 6.18.29-Unraid |
| CPU | Intel N150 |
| Array | 3 Daten-Disks, `shfs` gesamt **11 TB** (9,9 TB frei) |
| Cache | NVMe 1,9 TB (`/mnt/cache`, 52 GB belegt) |
| Docker Compose | v5.0.2 (Compose-Projekt `arr-stack`, Working-Dir `/mnt/user/arr-stack`) |

### Shares

| Share | Cache-Modus | Zweck |
|---|---|---|
| `appdata` | `only` (nur Cache/NVMe) | Container-Configs |
| `data` | `yes` (Cache → Mover → Array) | Medien + Downloads |
| `system` | `only` | Docker/libvirt |
| `arr-stack` | — | Git-Clone des Repos inkl. `.env` (Secrets) |

### Hardlink-Fähigkeit ✅

- `/mnt/user/data/downloads` und `/mnt/user/data/media` liegen auf **demselben Device** (shfs, dev 42), `fuse_useino="yes"` gesetzt.
- Radarr/Sonarr mounten `${DATA}` als einheitliches `/data` → Hardlinks & atomic moves **möglich**.
- Radarr `copyUsingHardlinks: true` ist aktiv.
- ⚠️ Einschränkung Unraid-typisch: `data` hat Cache-Modus `yes`. Solange Download **und** Import beide auf dem Cache liegen, greift der Hardlink; der Mover verschiebt später auf das Array. Hardlink über Cache↔Array-Grenze gibt es nicht (relevant nur, wenn Downloads lange liegen bleiben).

## 2. Container (Ist)

Alle Images auf `:latest` (nicht gepinnt), Restart-Policy überall `unless-stopped`, Netzwerk `arr_net` (bridge, extern angelegt) — außer Tailscale (`host`).

| Container | Image | Version (laufend) | Ports (Host) | Status | RestartCount |
|---|---|---|---|---|---|
| radarr | lscr.io/linuxserver/radarr | 6.1.1.10360 | 7878 | ✅ Up | 0 |
| sonarr | lscr.io/linuxserver/sonarr | 4.0.17.2952 | 8989 | ✅ Up | 0 |
| prowlarr | lscr.io/linuxserver/prowlarr | 2.3.5.5327 | 9696 | ✅ Up | 0 |
| sabnzbd | lscr.io/linuxserver/sabnzbd | — | 8090→8080 | ✅ Up | 0 |
| bazarr | lscr.io/linuxserver/bazarr | — | 6767 | ✅ Up | 0 |
| jellyfin | jellyfin/jellyfin | 10.11.8 | 8096, 8920 | ✅ Up (healthy) | 0 |
| seerr | seerr/seerr | 94a70bb | 5055 | ✅ Up | 0 |
| homepage | ghcr.io/gethomepage/homepage | — | 3000 | ✅ Up (healthy) | 0 |
| threadfin | fyb3roptik/threadfin | — | 34400 | ✅ Up | 0 |
| adguardhome | adguard/adguardhome | — | 53@LAN-IP, 8081, 3001 | ✅ Up, **unkonfiguriert** | 0 |
| tailscale | tailscale/tailscale | — | host | 🔴 **Restart-Loop** | **560** |
| vaultwarden | vaultwarden/server | 1.35.4 | 8082 | 🔴 **Restart-Loop** | **146** |
| lidarr / readarr | — | — | — | nicht angelegt (Compose-Profile aus), appdata leer | — |

- PUID/PGID: **99/100** (nobody/users) bei allen LSIO-Containern; Jellyfin läuft als `user: 99:100`; Seerr/Vaultwarden/AdGuard/Threadfin mit eigenem User-Modell. `UMASK` nirgends gesetzt (Default).
- Volumes: benannte Volumes als Bind auf `${APPDATA}/<dienst>` (`arr-stack_*`), wie im Compose definiert. Ist == Soll aus `docker-compose.yml`.

## 3. Ordnerstruktur & Daten

```
/mnt/user/data/
├── downloads/usenet/{complete,incomplete}   (leer)
└── media/{movies,tv,music,books}            (leer)
```

- **Die Mediathek ist komplett leer: 0 Dateien unter `/mnt/user/data`.** Radarr: 0 Filme, Sonarr: 0 Serien.
- → „Bestehende Daten erhalten" reduziert sich auf die **App-Konfigurationen in appdata** (Radarr 54 MB, Sonarr 55 MB, Prowlarr 9 MB, Seerr 3,5 MB, Rest < 1 MB). Keine Medien-Migration nötig.
- `movies-4k/`, `tv-4k/` (laut README/setup.sh vorgesehen) existieren auf dem Server **nicht**.
- Ownership: `data/downloads` und `data/media` gehören `root:root` (777), Unterordner `nobody:users` — funktioniert wegen 777, aber inkonsistent.

## 4. App-Konfiguration (per API / Config-Dateien verifiziert)

### SABnzbd
- Usenet-Server: **news.eweka.nl** (SSL, 45 Connections, Username `a3d***`) — Credentials vorhanden ✅
- Ordner: `/downloads/usenet/incomplete` + `/complete`; Kategorien `movies` → `movies`, `tv` → `tv` ✅
- `host_whitelist` enthält veralteten Container-Hash `a409c5b9636e` (harmlos, Altlast).
- ⚠️ Mountet nur `${DATA}/downloads/usenet` als `/downloads/usenet` — anderer Pfad als Radarr/Sonarr (`/data/...`). Wird aktuell durch **Remote Path Mappings** in Radarr+Sonarr (`sabnzbd:/downloads/usenet/complete/` → `/data/downloads/usenet/complete/`) kompensiert ✅, ist aber gegen TRaSH-Empfehlung (einheitliches `/data` überall, dann keine Mappings nötig).

### Prowlarr
- **1 Indexer**: „Generic Newznab" → `https://scenenzbs.com/` (privat, usenet, enabled) ✅
- Applications: Radarr + Sonarr mit `fullSync` über interne Hostnamen ✅ — Indexer ist in beide gesynct.

### Radarr (Auth: Forms)
- Root Folder: `/data/media/movies` ✅ | Download Client: SABnzbd (`sabnzbd:8080`, Kategorie `movies`) ✅
- Quality Profiles (7): Any, SD, HD-720p, HD-1080p, Ultra-HD, „HD - 720p/1080p", **„German DL 4k"** | **5 Custom Formats** (manuell gepflegt, kein Recyclarr)
- Naming: rename an, `{Movie Title} ({Release Year}) {Quality Full}`

### Sonarr (Auth: Forms)
- Root Folder: `/data/media/tv` ✅ | Download Client: SABnzbd (Kategorie `tv`) ✅
- Quality Profiles (6): Standardprofile — **kein** „German DL"-Profil (asymmetrisch zu Radarr) | 4 Custom Formats
- Naming: rename an, `{Series Title} - S{season:00}E{episode:00} - {Episode Title} {Quality Full}`

### Bazarr
- Mit Radarr + Sonarr verbunden (API-Keys stimmen überein) ✅ | Provider: nur `opensubtitlescom`

### Jellyfin
- Wizard abgeschlossen, Server „jellyfinmarvin", Bibliotheken **Filme** + **Serien** (Medien-Mount read-only) ✅

### Seerr
- Initialisiert, Media-Server Jellyfin (`jellyfin:8096`), Radarr + Sonarr als Default verbunden ✅
- ⚠️ Default-Profil für Radarr-Requests: **„Ultra-HD"**, nicht „German DL 4k".

### Threadfin
- Läuft, aber **keine M3U- und keine XMLTV-Quelle** konfiguriert → Live TV faktisch nicht eingerichtet.

### AdGuard Home
- **Conf-Verzeichnis ist leer** → Setup-Wizard wurde nie durchlaufen; DNS-Port 53 ist zwar an die LAN-IP gebunden, aber der Dienst ist unkonfiguriert.

### Vaultwarden 🔴
- **Crash-Loop**: `DOMAIN` wird vom Compose immer gesetzt (`DOMAIN=${VW_DOMAIN:-}`), `VW_DOMAIN` ist leer → Vaultwarden 1.35.4 bricht ab: *„DOMAIN variable needs to contain the protocol"*. Leerer String ≠ nicht gesetzt.
- `/mnt/user/appdata/vaultwarden/` ist **leer** → es existieren keine Vault-Daten, nichts zu verlieren.
- `VW_ADMIN_TOKEN` leer (Admin-Panel deaktiviert), `SIGNUPS_ALLOWED=true`.

### Tailscale 🔴
- **Crash-Loop (560 Restarts)**: hängt in `NeedsLogin`; der gesetzte `TS_AUTHKEY` (`kY8***`) hat **kein gültiges Format** (echte Keys: `tskey-auth-…`) — vermutlich nur die Key-ID aus der Admin-Konsole kopiert statt des vollständigen Keys.
- → **Kein Remote-Zugriff auf den Stack vorhanden.**

### Homepage
- Läuft; Widget-API-Keys in `services.yaml` nicht geprüft (kosmetisch).

## 5. Repo-Zustand

- Lokal `C:\dev\Arr-` = `origin/main` (github.com/skylevision/Arr-), untracked: `CLAUDE.md`, `prompt.md`.
- Server-Clone `/mnt/user/arr-stack` enthält `.env` mit Secrets; `git status` dort schlägt fehl („dubious ownership" — Dateien nicht root-owned).
- ⚠️ **Es gibt keine `.gitignore`** — `.env` ist zwar nicht getrackt, aber ungeschützt gegen versehentliches Committen.
- ⚠️ Repo-Stand (setup.sh mit `movies-4k`/`tv-4k`, README) ist neuer als das Deployment — Ist und Soll driften.

## 6. Probleme (priorisiert)

| # | Problem | Schwere |
|---|---|---|
| P1 | Tailscale-Restart-Loop: ungültiger `TS_AUTHKEY` → kein Remote-Zugriff | 🔴 hoch |
| P2 | Vaultwarden-Restart-Loop: leeres `DOMAIN=` crasht 1.35.4; Compose übergibt die Variable immer | 🔴 hoch |
| P3 | AdGuard Home läuft unkonfiguriert (Wizard nie durchlaufen) | 🟡 mittel |
| P4 | Keine `.gitignore` → Secrets-Risiko beim Committen | 🟡 mittel |
| P5 | Alle Images `:latest`, keine Version-Pins (Ziel Phase 2) | 🟡 mittel |
| P6 | SABnzbd-Mount ≠ `/data`-Schema → Remote Path Mappings als Workaround statt einheitlichem Mount (TRaSH) | 🟡 mittel |
| P7 | Quality-Setup asymmetrisch: Radarr hat „German DL 4k", Sonarr nicht; Seerr requestet mit „Ultra-HD"; Custom Formats manuell statt Recyclarr | 🟡 mittel |
| P8 | Threadfin ohne M3U/EPG (Live TV nicht funktional) | 🟢 niedrig |
| P9 | `data`-Unterordner ownership `root:root` statt `nobody:users` (läuft wegen 777) | 🟢 niedrig |
| P10 | `movies-4k`/`tv-4k` aus setup.sh fehlen auf dem Server; SAB `host_whitelist`-Altlast | 🟢 niedrig |

## 7. Positiv-Befunde

- Hardlink-Setup grundsätzlich korrekt (ein `/data`-Mount, gleiche Filesystem-Ebene, `copyUsingHardlinks` aktiv).
- Kernkette **Prowlarr → Radarr/Sonarr → SABnzbd → Bazarr/Jellyfin/Seerr ist vollständig verdrahtet** und konsistent (interne Hostnamen, API-Keys stimmen überein).
- Mediathek leer → ein sauberer Neuaufbau ist **praktisch risikofrei**; erhaltenswert sind nur die appdata-Configs (v. a. Quality Profiles / Custom Formats in Radarr, Indexer-Credentials, SAB-Serverdaten, Jellyfin/Seerr-Setup).
