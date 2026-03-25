#!/usr/bin/env bash
# ============================================================
# Unraid Arr Stack — setup.sh
# Run this script once before the first "docker compose up -d"
# ============================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
  if [[ -f "${SCRIPT_DIR}/.env.example" ]]; then
    warn ".env not found — copying .env.example to .env"
    cp "${SCRIPT_DIR}/.env.example" "${SCRIPT_DIR}/.env"
    warn "Please edit ${SCRIPT_DIR}/.env with your actual values, then re-run this script."
    exit 0
  else
    error ".env and .env.example are both missing. Cannot continue."
  fi
fi

# shellcheck disable=SC1090
source "${SCRIPT_DIR}/.env"

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
APPDATA="${APPDATA:-/mnt/user/appdata}"
DATA="${DATA:-/mnt/user/data}"

# ---------------------------------------------------------------------------
# Create appdata directories
# ---------------------------------------------------------------------------
info "Creating appdata directories under ${APPDATA} ..."

APPDATA_DIRS=(
  tailscale
  tailscale-vpn
  qbittorrent
  sabnzbd
  prowlarr
  radarr
  sonarr
  lidarr
  readarr
  bazarr
  overseerr
  jellyfin/config
  jellyfin/cache
  homepage
)

for dir in "${APPDATA_DIRS[@]}"; do
  target="${APPDATA}/${dir}"
  mkdir -p "${target}"
  chown "${PUID}:${PGID}" "${target}"
  success "${target}"
done

# ---------------------------------------------------------------------------
# Create media / download directories
# ---------------------------------------------------------------------------
info "Creating data directories under ${DATA} ..."

DATA_DIRS=(
  media/movies
  media/tv
  media/music
  media/books
  downloads/torrents/incomplete
  downloads/torrents/complete
  downloads/usenet/incomplete
  downloads/usenet/complete
)

for dir in "${DATA_DIRS[@]}"; do
  target="${DATA}/${dir}"
  mkdir -p "${target}"
  chown "${PUID}:${PGID}" "${target}"
  success "${target}"
done

# ---------------------------------------------------------------------------
# Homepage default config (only written if missing)
# ---------------------------------------------------------------------------
HP_CONFIG="${APPDATA}/homepage"

write_if_missing() {
  local file="$1"
  local content="$2"
  if [[ ! -f "${file}" ]]; then
    echo "${content}" > "${file}"
    success "Created ${file}"
  fi
}

write_if_missing "${HP_CONFIG}/settings.yaml" "---
title: Arr Stack
theme: dark
color: slate
headerStyle: boxed
"

write_if_missing "${HP_CONFIG}/services.yaml" "---
- Media Management:
    - Radarr:
        icon: radarr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${RADARR_PORT:-7878}
        description: Movie Management
        widget:
          type: radarr
          url: http://radarr:7878
          key: # paste your Radarr API key here

    - Sonarr:
        icon: sonarr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${SONARR_PORT:-8989}
        description: TV Show Management
        widget:
          type: sonarr
          url: http://sonarr:8989
          key: # paste your Sonarr API key here

    - Prowlarr:
        icon: prowlarr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${PROWLARR_PORT:-9696}
        description: Indexer Manager

    - Bazarr:
        icon: bazarr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${BAZARR_PORT:-6767}
        description: Subtitle Manager

- Download Clients:
    - qBittorrent:
        icon: qbittorrent.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${QBITTORRENT_WEBUI_PORT:-8080}
        description: Torrent Client
        widget:
          type: qbittorrent
          url: http://qbittorrent:8080
          username: admin
          password: adminadmin

    - SABnzbd:
        icon: sabnzbd.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${SABNZBD_PORT:-8090}
        description: Usenet Downloader
        widget:
          type: sabnzbd
          url: http://sabnzbd:8080
          key: # paste your SABnzbd API key here

- Media:
    - Jellyfin:
        icon: jellyfin.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${JELLYFIN_PORT_HTTP:-8096}
        description: Media Server
        widget:
          type: jellyfin
          url: http://jellyfin:8096
          key: # paste your Jellyfin API key here

    - Overseerr:
        icon: overseerr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${OVERSEERR_PORT:-5055}
        description: Request Movies & TV
        widget:
          type: overseerr
          url: http://overseerr:5055
          key: # paste your Overseerr API key here
"

write_if_missing "${HP_CONFIG}/widgets.yaml" "---
- resources:
    cpu: true
    memory: true
    disk:
      - /
      - ${DATA}

- datetime:
    text_size: xl
    format:
      timeStyle: short
      dateStyle: short
"

write_if_missing "${HP_CONFIG}/docker.yaml" "---
# Enables container status widgets from the Docker socket
my-docker:
  socket: /var/run/docker.sock
"

# ---------------------------------------------------------------------------
# Validate critical .env values
# ---------------------------------------------------------------------------
info "Validating .env ..."

MISSING=0
check_var() {
  local var="$1"
  local val="${!var:-}"
  if [[ -z "${val}" || "${val}" == *"your_"* ]]; then
    warn "  ${var} is not set or still has a placeholder value"
    MISSING=1
  fi
}

check_var TS_HOSTNAME

# TS_AUTHKEY is optional (interactive login via URL is also valid)
if [[ -z "${TS_AUTHKEY:-}" ]]; then
  warn "  TS_AUTHKEY is not set — on first start, run 'docker logs tailscale'"
  warn "  and open the printed URL to authenticate this node interactively."
fi

# Warn if vpn profile is intended but exit node is missing
if [[ -n "${TS_EXIT_NODE:-}" ]]; then
  success "Exit node configured: ${TS_EXIT_NODE} (start with --profile vpn)"
else
  info "  TS_EXIT_NODE is not set — qBittorrent will use direct internet."
  info "  Set TS_EXIT_NODE and use --profile vpn to route torrents via an exit node."
fi

if [[ "${MISSING}" -eq 1 ]]; then
  warn "One or more variables need attention in .env before starting."
else
  success "All critical variables look good."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Review and edit .env if you haven't already"
echo "  2. Start the stack:"
echo "       docker compose up -d"
echo ""
echo "  Optional services (disabled by default):"
echo "     Lidarr  (music):  docker compose --profile lidarr  up -d lidarr"
echo "     Readarr (books):  docker compose --profile readarr up -d readarr"
echo ""
echo "  Service ports:"
printf "    %-20s http://<unraid-ip>:%s\n" "qBittorrent"   "${QBITTORRENT_WEBUI_PORT:-8080}"
printf "    %-20s http://<unraid-ip>:%s\n" "SABnzbd"       "${SABNZBD_PORT:-8090}"
printf "    %-20s http://<unraid-ip>:%s\n" "Prowlarr"      "${PROWLARR_PORT:-9696}"
printf "    %-20s http://<unraid-ip>:%s\n" "Radarr"        "${RADARR_PORT:-7878}"
printf "    %-20s http://<unraid-ip>:%s\n" "Sonarr"        "${SONARR_PORT:-8989}"
printf "    %-20s http://<unraid-ip>:%s\n" "Bazarr"        "${BAZARR_PORT:-6767}"
printf "    %-20s http://<unraid-ip>:%s\n" "Overseerr"     "${OVERSEERR_PORT:-5055}"
printf "    %-20s http://<unraid-ip>:%s\n" "Jellyfin"      "${JELLYFIN_PORT_HTTP:-8096}"
printf "    %-20s http://<unraid-ip>:%s\n" "Homepage"      "${HOMEPAGE_PORT:-3000}"
echo ""
