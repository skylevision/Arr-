#!/usr/bin/env bash
# ============================================================
# bootstrap.sh — One-Command-Bootstrap des Arr-Stacks
#
#   bash bootstrap.sh
#
# Idempotent: kann beliebig oft laufen, legt nichts doppelt an.
# Ablauf:
#   1. Ordnerstruktur + Rechte (appdata & data, TRaSH-Layout)
#   2. Homepage-Default-Konfiguration (nur falls fehlend)
#   3. Docker-Netzwerk arr_net
#   4. Compose-Validierung, Container starten
#   5. Auf Healthchecks warten
#   6. API-Konfiguration: bootstrap/NN-*.sh in Reihenfolge
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# ---------------------------------------------------------------------------
# .env laden
# ---------------------------------------------------------------------------
if [[ ! -f .env ]]; then
  [[ -f .env.example ]] || error ".env und .env.example fehlen."
  warn ".env fehlt — kopiere .env.example nach .env"
  cp .env.example .env
  warn "Bitte .env ausfüllen (TS_AUTHKEY, EWEKA_*, SCENENZBS_*), dann erneut starten."
  exit 0
fi

# Nur KEY=VALUE-Zeilen laden (kein blindes source)
set -a
# shellcheck disable=SC1090
source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env)
set +a

PUID="${PUID:-99}"
PGID="${PGID:-100}"
APPDATA="${APPDATA:-/mnt/user/appdata}"
DATA="${DATA:-/mnt/user/data}"

# ---------------------------------------------------------------------------
# 1. Ordnerstruktur + Rechte
# ---------------------------------------------------------------------------
info "Lege Verzeichnisse an (idempotent) ..."

APPDATA_DIRS=(
  tailscale sabnzbd prowlarr radarr sonarr bazarr seerr
  jellyfin/config jellyfin/cache homepage
  adguardhome/work adguardhome/conf
  # Für deaktivierte Profile vorbereitet:
  vaultwarden threadfin/conf threadfin/temp gluetun
  lidarr readarr
)
for dir in "${APPDATA_DIRS[@]}"; do
  mkdir -p "${APPDATA}/${dir}"
  chown "${PUID}:${PGID}" "${APPDATA}/${dir}"
done
# Seerr folgt nicht dem LinuxServer-PUID/PGID-Modell: der Container läuft als
# node (uid/gid 1000). Gehört das Config-Verzeichnis 99:100, kann settings.json
# nicht geschrieben werden — Seerr-API-PUTs hängen dann endlos.
chown -R 1000:1000 "${APPDATA}/seerr"
success "appdata: ${APPDATA}"

# TRaSH-Layout: ein gemeinsames /data für Downloads + Medien
DATA_DIRS=(
  media/movies media/tv media/anime
  downloads/usenet/incomplete
  downloads/usenet/complete/movies
  downloads/usenet/complete/tv
)
for dir in "${DATA_DIRS[@]}"; do
  mkdir -p "${DATA}/${dir}"
done
# Ownership auf allen Ebenen der Struktur fixen (nicht rekursiv in Medien,
# damit der Lauf auch bei großen Bibliotheken schnell bleibt)
chown "${PUID}:${PGID}" "${DATA}" "${DATA}/media" "${DATA}/downloads" \
  "${DATA}/downloads/usenet" "${DATA}/media/movies" "${DATA}/media/tv" \
  "${DATA}/media/anime" \
  "${DATA}/downloads/usenet/incomplete" "${DATA}/downloads/usenet/complete" \
  "${DATA}/downloads/usenet/complete/movies" "${DATA}/downloads/usenet/complete/tv"
success "data:    ${DATA}"

# ---------------------------------------------------------------------------
# 2. Homepage-Default-Konfiguration (nur falls Datei fehlt)
# ---------------------------------------------------------------------------
HP="${APPDATA}/homepage"

write_if_missing() {
  local file="$1" content="$2"
  if [[ ! -f "${file}" ]]; then
    echo "${content}" > "${file}"
    chown "${PUID}:${PGID}" "${file}"
    success "Erstellt: ${file}"
  fi
}

write_if_missing "${HP}/settings.yaml" "---
title: Arr Stack
theme: dark
color: slate
headerStyle: boxed
"

write_if_missing "${HP}/services.yaml" "---
- Media Management:
    - Radarr:
        icon: radarr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${RADARR_PORT:-7878}
        description: Filme
        widget:
          type: radarr
          url: http://radarr:7878
          key: # Radarr API-Key eintragen
    - Sonarr:
        icon: sonarr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${SONARR_PORT:-8989}
        description: Serien
        widget:
          type: sonarr
          url: http://sonarr:8989
          key: # Sonarr API-Key eintragen
    - Prowlarr:
        icon: prowlarr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${PROWLARR_PORT:-9696}
        description: Indexer
    - Bazarr:
        icon: bazarr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${BAZARR_PORT:-6767}
        description: Untertitel

- Downloads:
    - SABnzbd:
        icon: sabnzbd.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${SABNZBD_PORT:-8090}
        description: Usenet
        widget:
          type: sabnzbd
          url: http://sabnzbd:8080
          key: # SABnzbd API-Key eintragen

- Media:
    - Jellyfin:
        icon: jellyfin.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${JELLYFIN_PORT_HTTP:-8096}
        description: Media Server
        widget:
          type: jellyfin
          url: http://jellyfin:8096
          key: # Jellyfin API-Key eintragen
    - Seerr:
        icon: overseerr.png
        href: http://{{HOMEPAGE_VAR_UNRAID_IP}}:${SEERR_PORT:-5055}
        description: Requests
        widget:
          type: overseerr
          url: http://seerr:5055
          key: # Seerr API-Key eintragen
"

write_if_missing "${HP}/widgets.yaml" "---
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

write_if_missing "${HP}/docker.yaml" "---
my-docker:
  socket: /var/run/docker.sock
"

# ---------------------------------------------------------------------------
# 3. Docker & Netzwerk
# ---------------------------------------------------------------------------
docker info >/dev/null 2>&1 || error "Docker läuft nicht oder ist nicht erreichbar."

if ! docker network inspect arr_net >/dev/null 2>&1; then
  docker network create --driver bridge arr_net >/dev/null
  success "Netzwerk arr_net erstellt."
else
  success "Netzwerk arr_net existiert."
fi

# ---------------------------------------------------------------------------
# 4. Compose validieren & starten
# ---------------------------------------------------------------------------
info "Validiere docker-compose.yml ..."
docker compose config -q || error "docker-compose.yml ist ungültig."

info "Starte Stack (gepinnte Images, Profile: nur aktive Dienste) ..."
docker compose up -d --remove-orphans

# Container deaktivierter Profile stoppen, falls sie noch von früher laufen
for c in vaultwarden threadfin; do
  if [[ "$(docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null)" == "true" ]]; then
    docker stop "$c" >/dev/null
    warn "Gestoppt (Profil deaktiviert): $c"
  fi
done

# ---------------------------------------------------------------------------
# 5. Auf Healthchecks warten
# ---------------------------------------------------------------------------
HEALTH_SERVICES=(tailscale sabnzbd prowlarr radarr sonarr bazarr jellyfin seerr homepage adguardhome)
TIMEOUT=300
info "Warte auf Healthchecks (max. ${TIMEOUT}s): ${HEALTH_SERVICES[*]}"

START=$(date +%s)
for svc in "${HEALTH_SERVICES[@]}"; do
  while true; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}nohc{{end}}' "$svc" 2>/dev/null || echo missing)"
    case "$status" in
      healthy|nohc) success "$svc: ${status/nohc/läuft (kein Healthcheck)}"; break ;;
      missing)      error "$svc: Container existiert nicht." ;;
    esac
    if (( $(date +%s) - START > TIMEOUT )); then
      docker ps --format 'table {{.Names}}\t{{.Status}}'
      error "$svc wurde nicht healthy (Status: $status). Logs: docker logs $svc"
    fi
    sleep 5
  done
done

# ---------------------------------------------------------------------------
# 6. API-Konfiguration (Phase-3-Skripte, einzeln wiederholbar)
# ---------------------------------------------------------------------------
if compgen -G "${SCRIPT_DIR}/bootstrap/[0-9][0-9]-*.sh" >/dev/null; then
  for script in "${SCRIPT_DIR}"/bootstrap/[0-9][0-9]-*.sh; do
    info "Führe aus: $(basename "$script")"
    bash "$script"
  done
else
  warn "Keine bootstrap/NN-*.sh gefunden — API-Konfiguration übersprungen."
fi

echo ""
success "Bootstrap abgeschlossen."
echo ""
echo "  Dienste:"
printf "    %-12s http://%s:%s\n" "Homepage"  "${UNRAID_IP:-<unraid-ip>}" "${HOMEPAGE_PORT:-3000}"
printf "    %-12s http://%s:%s\n" "Jellyfin"  "${UNRAID_IP:-<unraid-ip>}" "${JELLYFIN_PORT_HTTP:-8096}"
printf "    %-12s http://%s:%s\n" "Seerr"     "${UNRAID_IP:-<unraid-ip>}" "${SEERR_PORT:-5055}"
printf "    %-12s http://%s:%s\n" "Radarr"    "${UNRAID_IP:-<unraid-ip>}" "${RADARR_PORT:-7878}"
printf "    %-12s http://%s:%s\n" "Sonarr"    "${UNRAID_IP:-<unraid-ip>}" "${SONARR_PORT:-8989}"
printf "    %-12s http://%s:%s\n" "Prowlarr"  "${UNRAID_IP:-<unraid-ip>}" "${PROWLARR_PORT:-9696}"
printf "    %-12s http://%s:%s\n" "Bazarr"    "${UNRAID_IP:-<unraid-ip>}" "${BAZARR_PORT:-6767}"
printf "    %-12s http://%s:%s\n" "SABnzbd"   "${UNRAID_IP:-<unraid-ip>}" "${SABNZBD_PORT:-8090}"
