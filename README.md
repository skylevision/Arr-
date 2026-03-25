# Unraid Arr Stack

A complete, production-ready Docker Compose stack for automated movie and TV management on Unraid.

## Services

| Service | Purpose | Default Port |
|---|---|---|
| **Tailscale** | Remote access VPN (mesh) | — |
| **Tailscale VPN** | Exit-node sidecar for qBittorrent *(optional)* | — |
| **qBittorrent** | Torrent client | 8080 |
| **SABnzbd** | Usenet downloader | 8090 |
| **Prowlarr** | Indexer & tracker manager | 9696 |
| **Radarr** | Movie collection manager | 7878 |
| **Sonarr** | TV show collection manager | 8989 |
| **Lidarr** | Music collection manager *(optional)* | 8686 |
| **Readarr** | Book / AudioBook manager *(optional)* | 8787 |
| **Bazarr** | Subtitle management | 6767 |
| **Seerr** | Media request portal *(Overseerr successor)* | 5055 |
| **Jellyfin** | Media server | 8096 |
| **Homepage** | Unified dashboard | 3000 |

## Architecture

```
  ┌────────────────────────────────────────────────────────────┐
  │                    Unraid Host                             │
  │                                                            │
  │  ┌─────────────────────────┐                              │
  │  │  Tailscale  (host net)  │  ← your Tailnet (100.x.x.x) │
  │  │  hostname: arr-stack    │    remote access, no ports   │
  │  └─────────────────────────┘    needed in router          │
  │                                                            │
  │  ┌────────────────────────────────────────────────────┐   │
  │  │                   arr_net (bridge)                 │   │
  │  │                                                    │   │
  │  │  ┌──────────────┐   ┌──────────────────────────┐  │   │
  │  │  │ qBittorrent  │   │  tailscale-vpn (optional)│  │   │
  │  │  │  :8080       │   │  exit-node → VPS/server  │  │   │
  │  │  └──────┬───────┘   └──────────────────────────┘  │   │
  │  │         │           (profile: vpn — see below)     │   │
  │  │  ┌──────▼──────┐  ┌──────────────┐  ┌──────────┐  │   │
  │  │  │   Radarr    │  │    Sonarr    │  │ Prowlarr │  │   │
  │  │  └──────┬──────┘  └──────┬───────┘  └──────────┘  │   │
  │  │         └────────────────┼──────────────────────   │   │
  │  │                   ┌──────▼──────┐                  │   │
  │  │                   │    Bazarr   │                  │   │
  │  │                   └─────────────┘                  │   │
  │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐   │   │
  │  │  │    Seerr     │  │  Jellyfin   │  │ Homepage │   │   │
  │  │  └─────────────┘  └─────────────┘  └──────────┘   │   │
  │  └────────────────────────────────────────────────────┘   │
  └────────────────────────────────────────────────────────────┘
```

### Tailscale modes

| Mode | Command | qBittorrent traffic |
|---|---|---|
| **Remote access only** (default) | `docker compose up -d` | Direct internet |
| **Exit-node VPN** | `docker compose --profile vpn up -d` | Routed through exit node |

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
│   ├── seerr/
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

### Exit Node for qBittorrent (optional)

To hide your home IP from torrent trackers, route torrent traffic through a Tailscale exit node:

1. Set up an exit node (a VPS, a cloud VM, another home machine):
   ```bash
   # On the exit node machine:
   tailscale up --advertise-exit-node
   # Then approve it in the Tailscale admin console under Machines
   ```

2. Set `TS_EXIT_NODE` in `.env` to that node's Tailscale IP or name:
   ```
   TS_EXIT_NODE=100.64.0.5
   ```

3. Start the stack with the `vpn` profile:
   ```bash
   docker compose --profile vpn up -d
   ```

4. In `docker-compose.yml`, switch `qbittorrent` to use the VPN sidecar network
   (see the comments inside the `qbittorrent` service block).

> **Note**: Tailscale is a mesh VPN — perfect for remote access. For maximum torrent
> privacy you still need an exit node (your own VPS or a Tailscale-connected commercial
> VPN server). Mullvad and other providers are adding Tailscale exit node support.

---

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

### Seerr

1. Open Seerr (`http://<ip>:5055`) → follow the setup wizard
2. Connect your media server (Jellyfin: `http://jellyfin:8096`, or Plex/Emby)
3. Connect to Radarr (`http://radarr:7878`) and Sonarr (`http://sonarr:8989`) with their API keys.

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
| Can't reach services via Tailscale | Check `docker logs tailscale` — look for auth URL or errors |
| Tailscale shows "Needs login" | Run `docker exec tailscale tailscale login` or set `TS_AUTHKEY` |
| Exit node not working | Ensure the exit node is approved in the Tailscale admin console |
| qBittorrent unreachable | Check that the container started and port 8080 is not already in use |
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
| Seerr | 5055 | `SEERR_PORT` (5055) |
| Jellyfin HTTP | 8096 | `JELLYFIN_PORT_HTTP` (8096) |
| Jellyfin HTTPS | 8920 | `JELLYFIN_PORT_HTTPS` (8920) |
| Homepage | 3000 | `HOMEPAGE_PORT` (3000) |
