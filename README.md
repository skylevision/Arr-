# Unraid Arr Stack

A complete, production-ready Docker Compose stack for automated movie and TV management on Unraid.

> **Neu bei Unraid?** → Zuerst die [Unraid Setup-Anleitung](UNRAID_SETUP.md) lesen.
> Sie führt Schritt für Schritt durch BIOS, HDDs, NVMe-Cache, 2×2.5G-Bonding und alle Grundeinstellungen.

> **Stack über die Unraid-Oberfläche einrichten?** → [Unraid UI Setup](UNRAID_UI_SETUP.md) —
> Jeden Container Schritt für Schritt über das Unraid Web-Interface anlegen (ohne Docker Compose).

> **Dual Language (DE+EN) in 4K?** → [Dual Language Setup](DUAL_LANGUAGE_SETUP.md) —
> Custom Formats und Quality Profiles für automatische German-DL-Downloads in 4K mit HDR/Dolby Vision.

> **Freunde & Familie einladen?** → [Freunde-Anleitung](FREUNDE_ANLEITUNG.md) —
> Tailscale-Verbindung, Jellyfin & Seerr einrichten auf Smartphone, PC und Fire TV Stick.

> **Passwort-Manager?** → [Vaultwarden Setup](VAULTWARDEN_SETUP.md) —
> Self-hosted Bitwarden-kompatiblen Passwort-Manager einrichten und mit allen Geräten verbinden.

> **Deutsches IPTV / Live TV?** → [IPTV Setup](IPTV_SETUP.md) —
> Threadfin als IPTV-Proxy einrichten, deutsche Sender (ARD, ZDF, Sport1 …) in Jellyfin Live TV streamen.

## Services

| Service | Purpose | Default Port |
|---|---|---|
| **Tailscale** | Remote access VPN (mesh) | — |
| **SABnzbd** | Usenet downloader | 8090 |
| **Prowlarr** | Indexer & tracker manager | 9696 |
| **Radarr** | Movie collection manager | 7878 |
| **Sonarr** | TV show collection manager | 8989 |
| **Lidarr** | Music collection manager *(optional, profile `lidarr`)* | 8686 |
| **Readarr** | Book / AudioBook manager *(optional, profile `readarr`)* | 8787 |
| **Bazarr** | Subtitle management | 6767 |
| **Seerr** | Media request portal — supports Jellyfin, Plex, Emby | 5055 |
| **Vaultwarden** | Self-hosted Bitwarden-compatible password manager *(optional, profile `vaultwarden`)* | 8082 |
| **Threadfin** | IPTV proxy — Live TV for Jellyfin *(optional, profile `iptv`)* | 34400 |
| **AdGuard Home** | Network-wide DNS ad blocker & parental control *(optional, profile `adguard`)* | 8081 (UI), 53 (DNS) |
| **Jellyfin** | Media server | 8096 |
| **Homepage** | Unified dashboard | 3000 |

## Architecture

```
  ┌──────────────────────────────────────────────────────────────┐
  │                      Unraid Host                             │
  │                                                              │
  │  ┌─────────────────────────┐                                │
  │  │  Tailscale  (host net)  │  ← your Tailnet (100.x.x.x)   │
  │  │  hostname: arr-stack    │    remote access, no ports     │
  │  └─────────────────────────┘    needed in router            │
  │                                                              │
  │  ┌──────────────────────────────────────────────────────┐   │
  │  │                   arr_net (bridge)                   │   │
  │  │                                                      │   │
  │  │  ┌──────────────┐                                    │   │
  │  │  │   SABnzbd    │  ← Usenet downloader               │   │
  │  │  └──────┬───────┘                                    │   │
  │  │  ┌──────▼──────┐  ┌──────────────┐  ┌──────────┐    │   │
  │  │  │   Radarr    │  │    Sonarr    │  │ Prowlarr │    │   │
  │  │  └──────┬──────┘  └──────┬───────┘  └──────────┘    │   │
  │  │         └────────────────┼──────────────────────     │   │
  │  │                   ┌──────▼──────┐                    │   │
  │  │                   │    Bazarr   │                    │   │
  │  │                   └─────────────┘                    │   │
  │  │  ┌──────────┐  ┌─────────────┐  ┌──────────────┐    │   │
  │  │  │  Seerr   │  │ AdGuard Home│  │   Jellyfin   │    │   │
  │  │  └──────────┘  └─────────────┘  └──────┬───────┘    │   │
  │  │  ┌─────────────┐  ┌──────────────────────▼───────┐  │   │
  │  │  │ Vaultwarden │  │  Threadfin ──────► Live TV   │  │   │
  │  │  └─────────────┘  └──────────────────────────────┘  │   │
  │  └──────────────────────────────────────────────────────┘   │
  └──────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
/mnt/user/
├── appdata/                  ← container config (fast cache drive recommended)
│   ├── tailscale/
│   ├── sabnzbd/
│   ├── prowlarr/
│   ├── radarr/
│   ├── sonarr/
│   ├── bazarr/
│   ├── lidarr/               ← optional
│   ├── readarr/              ← optional
│   ├── seerr/
│   ├── vaultwarden/
│   ├── threadfin/
│   ├── adguardhome/
│   ├── jellyfin/
│   └── homepage/
└── data/                     ← all media & downloads (single share = hardlinks work!)
    ├── downloads/
    │   └── usenet/
    │       ├── incomplete/
    │       └── complete/
    │           ├── movies/   ← SABnzbd category "movies"
    │           └── tv/       ← SABnzbd category "tv"
    └── media/
        ├── movies/           ← Radarr root folder
        └── tv/               ← Sonarr root folder
```

> **Why a single `/data` share?**
> Radarr/Sonarr mount `/data` and see both downloads and media in the same filesystem.
> This allows the arr apps to use **hardlinks** instead of copying files — instant, zero extra disk space.

## Quick Start

### 1. Prerequisites

- Unraid 6.10+ with the **Compose Manager** plugin installed
  *(Apps → search "Compose Manager" → install)*
- A free [Tailscale account](https://login.tailscale.com/start) (free tier supports up to 100 devices)

### 2. Clone / copy files

```bash
# On your Unraid terminal
cd /mnt/user/  # or wherever you want to store compose files
git clone https://github.com/skylevision/arr- arr-stack
cd arr-stack
```

### 3. Configure

```bash
cp .env.example .env
nano .env          # set UNRAID_IP, TS_HOSTNAME, TS_AUTHKEY, EWEKA_*, SCENENZBS_APIKEY
```

Get your PUID / PGID:
```bash
id $USER
# uid=99(nobody) gid=100(users) ...   ← Unraid default (nobody/users)
```

> **Unraid default**: PUID=**99** (nobody), PGID=**100** (users).
> These are Unraid's built-in media user — use them unless you created a dedicated user.

### 4. Bootstrap — one command

```bash
bash bootstrap.sh
```

This is **idempotent** (safe to re-run any time) and does everything:

1. Creates all directories under `APPDATA` and `DATA` (TRaSH layout) with correct ownership
2. Writes default Homepage config files (only if missing)
3. Creates the `arr_net` Docker network
4. Validates the compose file and starts the stack (pinned image versions)
5. Waits for all healthchecks to pass
6. Configures the services via their APIs (`bootstrap/NN-*.sh`, each re-runnable on its own):
   extracts API keys to `.env.runtime`, sets up SABnzbd (Usenet server, folders, categories),
   Prowlarr (indexer + app sync to Radarr/Sonarr), Radarr/Sonarr (root folder, download
   client, naming), Recyclarr (TRaSH German-DL-4K quality profiles) and Seerr defaults

Afterwards, verify everything with:

```bash
bash scripts/healthcheck.sh   # containers, APIs, indexer/client tests, hardlink test
```

> `setup.sh` (directories + Homepage config only, no API configuration) still exists for
> UI-based setups — see [Unraid UI Setup](UNRAID_UI_SETUP.md).

### 5. Optional services

Vaultwarden, AdGuard Home, Threadfin, Lidarr and Readarr use
[Docker Compose profiles](https://docs.docker.com/compose/profiles/) and are **off by default**.

```bash
docker compose --profile vaultwarden up -d vaultwarden
docker compose --profile adguard     up -d adguardhome
docker compose --profile iptv        up -d threadfin
docker compose --profile lidarr      up -d lidarr
docker compose --profile readarr     up -d readarr
```

## Tailscale Setup

### Remote Access (all modes)

On **first start** the `tailscale` container needs to authenticate:

```bash
# Option A — interactive (no TS_AUTHKEY needed):
docker compose up -d tailscale
docker logs tailscale   # opens a URL — paste it in your browser

# Option B — pre-auth key (recommended for automation):
# 1. Go to https://login.tailscale.com/admin/settings/keys
# 2. Create a reusable key, paste it as TS_AUTHKEY in .env
# 3. docker compose up -d   (authenticates automatically)
```

Once authenticated, all services are reachable at `http://<tailscale-ip>:<port>` from any device on your Tailnet — phone, laptop, etc. — without port forwarding.

---

## First-Time Configuration

> **Using `bootstrap.sh`?** Then SABnzbd, Prowlarr, Radarr, Sonarr, Recyclarr and Seerr
> defaults are configured automatically — the sections below only apply to manual/UI-based
> setups (or as reference for what the bootstrap configured). Manual steps that always
> remain: the Jellyfin first-run wizard, the Seerr login/Jellyfin link, and Bazarr
> subtitle-provider credentials.

### SABnzbd — Usenet Downloader

1. Open SABnzbd (`http://<ip>:8090`) → the Quick-Start wizard opens automatically
2. **Usenet provider**: Enter your news server credentials (hostname, port, SSL, username, password, connections)
   > If you don't have a Usenet provider yet: [Eweka](https://www.eweka.nl), [Newshosting](https://www.newshosting.com) and [UsenetExpress](https://www.usenetexpress.com) are popular options
3. **Download folders** — set these under *Config → Folders*:

   | Field | Value |
   |---|---|
   | Temporary Download Folder | `/data/downloads/usenet/incomplete` |
   | Completed Download Folder | `/data/downloads/usenet/complete` |

   > SABnzbd mounts the whole `${DATA}` share as `/data` (same as Radarr/Sonarr), so
   > imports can use hardlinks and no remote path mappings are needed.

4. **API key** — copy it from *Config → General → API Key* — you'll need it for Radarr, Sonarr and Homepage
5. **Categories** (optional but recommended) — *Config → Categories*:

   | Name | Folder |
   |---|---|
   | `movies` | `movies` |
   | `tv` | `tv` |

   Radarr and Sonarr will use these category names when sending downloads.

### Prowlarr → Arr Apps

1. Open Prowlarr (`http://<ip>:9696`) → *Settings → Apps*
2. Add Radarr, Sonarr (and optionally Lidarr / Readarr) using their **internal Docker hostnames** (`http://radarr:7878`, `http://sonarr:8989`, …) and API keys.
   > These hostnames only work between containers on the same `arr_net` network — not from your browser. Use `http://<unraid-ip>:<port>` when accessing UIs from outside Docker.
3. Add your indexers. Prowlarr will sync them automatically.

### Radarr / Sonarr — Download Clients

1. *Settings → Download Clients → +*
2. **SABnzbd**: host `sabnzbd`, port `8080`, paste your SABnzbd API key
   > `sabnzbd` is the internal Docker hostname — do **not** use `localhost` or the Unraid IP here

### Radarr — Root Folder

- `/data/media/movies`

### Sonarr — Root Folder

- `/data/media/tv`

### Bazarr

1. Open Bazarr (`http://<ip>:6767`) → *Settings → Radarr / Sonarr*
2. Host: `radarr` / `sonarr`, use the API keys from each service.

### Seerr

1. Open Seerr (`http://<ip>:5055`) → follow the setup wizard
2. Connect your media server (Jellyfin: `http://jellyfin:8096`)
3. Connect to Radarr (`http://radarr:7878`) and Sonarr (`http://sonarr:8989`) with their API keys.

### Threadfin (IPTV / Live TV)

1. Open the Threadfin UI (`http://<ip>:34400/web`) → Setup Wizard
3. Add your M3U playlist URL (free German TV: see [IPTV_SETUP.md](IPTV_SETUP.md))
4. Add an XMLTV EPG source and map channels
5. In Jellyfin → Admin → **Live TV** → Add tuner → **HD HomeRun** → URL: `http://threadfin:34400`
6. Add guide provider → **XMLTV** → same EPG URL used in Threadfin

> See [IPTV_SETUP.md](IPTV_SETUP.md) for recommended M3U/EPG sources, channel setup and sport options.

### Vaultwarden

1. Open Vaultwarden (`http://<ip>:8082`) → create your account
2. Open the admin panel at `http://<ip>:8082/admin` (requires `VW_ADMIN_TOKEN` in `.env`)
3. In the admin panel: disable signups once all accounts are created (`VW_SIGNUPS_ALLOWED=false`)
4. **HTTPS for mobile clients** (required by Bitwarden apps):
   ```bash
   docker exec tailscale tailscale serve https:443 / http://localhost:8082
   ```
   This exposes Vaultwarden at `https://<hostname>.<tailnet>.ts.net` with a valid cert.

> See [VAULTWARDEN_SETUP.md](VAULTWARDEN_SETUP.md) for the full guide including client setup, 2FA, import, and backup.

### AdGuard Home

1. On **first start**, open the setup wizard at `http://<ip>:3001` (mapped to `ADGUARD_SETUP_PORT`)
2. Follow the wizard — set admin username/password and configure the listen interfaces
3. After the wizard completes, the web UI is at `http://<ip>:8081` (`ADGUARD_WEBUI_PORT`)
4. Go to *Settings → DNS settings* to configure upstream servers (default: `1.1.1.1`, `8.8.8.8`)
5. Point your **router's primary DNS** to `<UNRAID_IP>` to filter ads network-wide

> **Port 53 on Unraid**: Port 53 is bound to `UNRAID_IP` (your server's LAN IP) to avoid
> conflicts with Unraid's own resolver on `127.0.0.1:53`.
> Make sure `UNRAID_IP` in `.env` matches your server's actual LAN IP.

> **Port conflict note**: The setup wizard uses port 3001 by default (`ADGUARD_SETUP_PORT`)
> to avoid clashing with Homepage on port 3000. You only need port 3001 once during setup.

### Jellyfin

1. Open Jellyfin (`http://<ip>:8096`) → follow the setup wizard
2. Add libraries pointing to `/data/media/movies` and `/data/media/tv`

### Homepage

Config files are at `${APPDATA}/homepage/`. Edit `services.yaml` to add your API keys for live widgets.

## Hardware Transcoding (Jellyfin)

### Intel QuickSync / VAAPI

**Enabled by default** — `docker-compose.yml` passes the iGPU through to Jellyfin:
```yaml
devices:
  - /dev/dri:/dev/dri
```
In Jellyfin, *Dashboard → Playback → Transcoding* must be set to **Intel QuickSync (QSV)**
with HDR tone mapping enabled (already configured by this repo's setup). On hosts without
an Intel iGPU, remove the `devices:` block.

### Nvidia

```yaml
runtime: nvidia
environment:
  - NVIDIA_VISIBLE_DEVICES=all
```
*(Requires the [Nvidia Driver plugin](https://forums.unraid.net/topic/98978-plugin-nvidia-driver/) on Unraid)*

## Updating

All images are **pinned to specific versions** in `docker-compose.yml` — no surprise
upgrades. To update a service:

1. Bump the image tag in `docker-compose.yml` (check the project's release notes)
2. `docker compose up -d` (pulls the new tag and recreates only that container)
3. Commit the tag bump so the repo always reflects what is running

## Backup & Restore

Create a consistent backup of all service configs (stops the stack briefly, tars
`appdata`, restarts):

```bash
bash scripts/backup-appdata.sh
# writes /mnt/user/backups/arr-stack/<timestamp>/appdata-<timestamp>.tar.gz (+ sha256)
# override the destination with BACKUP_ROOT=/path bash scripts/backup-appdata.sh
```

Suitable as an [Unraid User Script](https://forums.unraid.net/topic/48286-plugin-ca-user-scripts/)
on a schedule.

**Restore**:

```bash
docker compose down
tar -xzf /mnt/user/backups/arr-stack/<timestamp>/appdata-<timestamp>.tar.gz -C /mnt/user/appdata
git checkout <known-good-commit>   # if the compose file also needs rolling back
docker compose up -d
```

## Troubleshooting

| Problem | Solution |
|---|---|
| Can't reach services via Tailscale | Check `docker logs tailscale` — look for auth URL or errors |
| Tailscale shows "Needs login" | Run `docker exec tailscale tailscale login` or set `TS_AUTHKEY` |
| No hardlinks | Ensure Radarr/Sonarr and download client all write under the same `/data` mount |
| Permission errors | Check that `PUID`/`PGID` in `.env` match the owner of your Unraid shares |
| Prowlarr sync fails | Use internal Docker hostnames (`radarr`, `sonarr`) not `localhost` or IP |

## Ports Reference

| Service | Container Port | Published Port (default) |
|---|---|---|
| SABnzbd | 8080 | `SABNZBD_PORT` (8090) |
| Prowlarr | 9696 | `PROWLARR_PORT` (9696) |
| Radarr | 7878 | `RADARR_PORT` (7878) |
| Sonarr | 8989 | `SONARR_PORT` (8989) |
| Lidarr | 8686 | `LIDARR_PORT` (8686) |
| Readarr | 8787 | `READARR_PORT` (8787) |
| Bazarr | 6767 | `BAZARR_PORT` (6767) |
| Seerr | 5055 | `SEERR_PORT` (5055) |
| Vaultwarden | 80 | `VAULTWARDEN_PORT` (8082) |
| Threadfin | 34400 | `THREADFIN_PORT` (34400) |
| AdGuard Setup | 3000 | `ADGUARD_SETUP_PORT` (3001) — first start only |
| AdGuard UI | 80 | `ADGUARD_WEBUI_PORT` (8081) |
| AdGuard DNS | 53 | bound to `UNRAID_IP` |
| Jellyfin HTTP | 8096 | `JELLYFIN_PORT_HTTP` (8096) |
| Jellyfin HTTPS | 8920 | `JELLYFIN_PORT_HTTPS` (8920) |
| Homepage | 3000 | `HOMEPAGE_PORT` (3000) |
