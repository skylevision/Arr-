# Unraid Arr Stack

A complete, production-ready Docker Compose stack for automated movie and TV management on Unraid.

## Services

| Service | Purpose | Default Port |
|---|---|---|
| **Gluetun** | VPN gateway (WireGuard / OpenVPN) | — |
| **qBittorrent** | Torrent client — traffic routed through VPN | 8080 |
| **SABnzbd** | Usenet downloader | 8090 |
| **Prowlarr** | Indexer & tracker manager | 9696 |
| **Radarr** | Movie collection manager | 7878 |
| **Sonarr** | TV show collection manager | 8989 |
| **Lidarr** | Music collection manager *(optional)* | 8686 |
| **Readarr** | Book / AudioBook manager *(optional)* | 8787 |
| **Bazarr** | Subtitle management | 6767 |
| **Overseerr** | User-facing media request portal | 5055 |
| **Jellyfin** | Media server | 8096 |
| **Homepage** | Unified dashboard | 3000 |

## Architecture

```
                          ┌─────────────┐
                          │   Gluetun   │  ← VPN tunnel
                          │    (VPN)    │
                          └──────┬──────┘
                                 │ network_mode: service:gluetun
                          ┌──────▼──────┐
                          │qBittorrent  │  ← all torrent traffic encrypted
                          └──────┬──────┘
                                 │
          ┌──────────────────────┼───────────────────────┐
          │                      │                       │
   ┌──────▼──────┐        ┌──────▼──────┐       ┌───────▼──────┐
   │   Radarr    │        │   Sonarr    │       │   Prowlarr   │
   │  (movies)   │        │    (TV)     │       │  (indexers)  │
   └──────┬──────┘        └──────┬──────┘       └──────────────┘
          │                      │
   ┌──────▼──────────────────────▼──────┐
   │              Bazarr                │  ← subtitles
   └────────────────────────────────────┘
          │                      │
   ┌──────▼──────┐        ┌──────▼──────┐
   │  Overseerr  │        │  Jellyfin   │  ← media playback
   │ (requests)  │        │             │
   └─────────────┘        └─────────────┘
```

## Directory Structure

```
/mnt/user/
├── appdata/                  ← container config (fast cache drive recommended)
│   ├── gluetun/
│   ├── qbittorrent/
│   ├── sabnzbd/
│   ├── prowlarr/
│   ├── radarr/
│   ├── sonarr/
│   ├── bazarr/
│   ├── overseerr/
│   ├── jellyfin/
│   └── homepage/
└── data/                     ← all media & downloads (single share = hardlinks work!)
    ├── downloads/
    │   ├── torrents/
    │   │   ├── incomplete/
    │   │   └── complete/
    │   └── usenet/
    │       ├── incomplete/
    │       └── complete/
    └── media/
        ├── movies/
        ├── tv/
        ├── music/
        └── books/
```

> **Why a single `/data` share?**
> Radarr/Sonarr mount `/data` and see both downloads and media in the same filesystem.
> This allows the arr apps to use **hardlinks** instead of copying files — instant, zero extra disk space.

## Quick Start

### 1. Prerequisites

- Unraid 6.10+ with the **Compose Manager** plugin installed
  *(Apps → search "Compose Manager" → install)*
- A VPN subscription (Mullvad, ProtonVPN, NordVPN, etc.)

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
nano .env          # fill in VPN credentials, paths, PUID/PGID
```

Get your PUID / PGID:
```bash
id $USER
# uid=1000(nobody) gid=1000(users) ...
```

### 4. Run setup

```bash
bash setup.sh
```

This creates all required directories under `APPDATA` and `DATA` and writes default Homepage config files.

### 5. Start the stack

```bash
docker compose up -d
```

### 6. Optional services

Lidarr and Readarr use [Docker Compose profiles](https://docs.docker.com/compose/profiles/) and are **off by default**.

```bash
# Start Lidarr
docker compose --profile lidarr up -d lidarr

# Start Readarr
docker compose --profile readarr up -d readarr
```

## First-Time Configuration

### Prowlarr → Arr Apps

1. Open Prowlarr (`http://<ip>:9696`) → *Settings → Apps*
2. Add Radarr, Sonarr (and optionally Lidarr / Readarr) using their **internal hostnames** (`http://radarr:7878`, `http://sonarr:8989`, …) and API keys.
3. Add your indexers. Prowlarr will sync them automatically.

### Radarr / Sonarr — Download Clients

1. *Settings → Download Clients → +*
2. **qBittorrent**: host `gluetun`, port `8080`
3. **SABnzbd**: host `sabnzbd`, port `8080`

### Radarr — Root Folder

- `/data/media/movies`

### Sonarr — Root Folder

- `/data/media/tv`

### Bazarr

1. Open Bazarr (`http://<ip>:6767`) → *Settings → Radarr / Sonarr*
2. Host: `radarr` / `sonarr`, use the API keys from each service.

### Overseerr

1. Open Overseerr (`http://<ip>:5055`) → follow the setup wizard
2. Connect to Jellyfin (host: `jellyfin`, port: `8096`)
3. Connect to Radarr and Sonarr.

### Jellyfin

1. Open Jellyfin (`http://<ip>:8096`) → follow the setup wizard
2. Add libraries pointing to `/data/media/movies` and `/data/media/tv`

### Homepage

Config files are at `${APPDATA}/homepage/`. Edit `services.yaml` to add your API keys for live widgets.

## Hardware Transcoding (Jellyfin)

### Intel QuickSync / VAAPI

Uncomment in `docker-compose.yml` under the `jellyfin` service:
```yaml
devices:
  - /dev/dri:/dev/dri
```

### Nvidia

```yaml
runtime: nvidia
environment:
  - NVIDIA_VISIBLE_DEVICES=all
```
*(Requires the [Nvidia Driver plugin](https://forums.unraid.net/topic/98978-plugin-nvidia-driver/) on Unraid)*

## Updating

All images use `:latest`. To pull updates and restart:

```bash
docker compose pull
docker compose up -d
```

Or use the **Unraid "Check for Updates"** button in the Docker tab.

## Troubleshooting

| Problem | Solution |
|---|---|
| qBittorrent unreachable | Check `docker logs gluetun` — VPN must connect first |
| VPN not connecting | Verify credentials in `.env`; check `SERVER_COUNTRIES` spelling |
| No hardlinks | Ensure Radarr/Sonarr and download client all write under the same `/data` mount |
| Permission errors | Check that `PUID`/`PGID` in `.env` match the owner of your Unraid shares |
| Prowlarr sync fails | Use internal Docker hostnames (`radarr`, `sonarr`) not `localhost` or IP |

## Ports Reference

| Service | Container Port | Published Port (default) |
|---|---|---|
| qBittorrent | 8080 | `QBITTORRENT_WEBUI_PORT` (8080) |
| SABnzbd | 8080 | `SABNZBD_PORT` (8090) |
| Prowlarr | 9696 | `PROWLARR_PORT` (9696) |
| Radarr | 7878 | `RADARR_PORT` (7878) |
| Sonarr | 8989 | `SONARR_PORT` (8989) |
| Lidarr | 8686 | `LIDARR_PORT` (8686) |
| Readarr | 8787 | `READARR_PORT` (8787) |
| Bazarr | 6767 | `BAZARR_PORT` (6767) |
| Overseerr | 5055 | `OVERSEERR_PORT` (5055) |
| Jellyfin HTTP | 8096 | `JELLYFIN_PORT_HTTP` (8096) |
| Jellyfin HTTPS | 8920 | `JELLYFIN_PORT_HTTPS` (8920) |
| Homepage | 3000 | `HOMEPAGE_PORT` (3000) |
