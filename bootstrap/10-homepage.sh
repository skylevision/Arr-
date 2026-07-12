#!/usr/bin/env bash
# ============================================================
# 10-homepage.sh — Homepage: services.yaml mit echten API-Keys
#
# Generiert ${APPDATA}/homepage/services.yaml komplett neu:
# Widgets für Radarr/Sonarr/Prowlarr/Bazarr/SABnzbd/Seerr mit
# den Keys aus .env.runtime, Links über die AdGuard-DNS-Namen
# (<dienst>.<LOCAL_DOMAIN>). Jellyfin bekommt keinen Widget-Key
# (müsste manuell in Jellyfin angelegt werden) — nur Link + Ping.
#
# ACHTUNG: Die Datei wird bei jedem Lauf überschrieben — manuelle
# Anpassungen gehören ins Repo (dieses Skript), nicht in die Datei.
# Homepage lädt Config-Änderungen automatisch neu.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var RADARR_API_KEY
require_var SONARR_API_KEY
require_var PROWLARR_API_KEY
require_var SABNZBD_API_KEY
require_var BAZARR_API_KEY
require_var SEERR_API_KEY

HP="${APPDATA}/homepage"
D="${LOCAL_DOMAIN:-fritz.box}"
[[ -d "$HP" ]] || error "${HP} existiert nicht — erst bootstrap.sh laufen lassen."

# Jellyfin-Widget nur, wenn ein API-Key gesetzt ist (JELLYFIN_API_KEY in .env,
# vom Nutzer in Jellyfin → Dashboard → API-Schlüssel erzeugt). Sonst nur ein
# Erreichbarkeits-Punkt (siteMonitor), damit die Homepage keinen Fehler zeigt.
if [[ -n "${JELLYFIN_API_KEY:-}" ]]; then
  JF_ENTRY="        widget:
          type: jellyfin
          url: http://jellyfin:8096
          key: ${JELLYFIN_API_KEY}
          enableBlocks: true
          enableNowPlaying: true"
else
  JF_ENTRY="        siteMonitor: http://jellyfin:8096"
fi

info "Schreibe ${HP}/services.yaml (Widgets mit API-Keys, Links per DNS-Name) ..."

cat > "${HP}/services.yaml" <<EOF
---
# Automatisch generiert von bootstrap/10-homepage.sh — NICHT von Hand
# editieren, Änderungen dort machen und das Skript erneut ausführen.

- Media:
    - Jellyfin:
        icon: jellyfin.png
        href: http://jellyfin.${D}:${JELLYFIN_PORT_HTTP:-8096}
        description: Filme & Serien
        server: my-docker
        container: jellyfin
${JF_ENTRY}
    - Seerr:
        icon: overseerr.png
        href: http://seerr.${D}:${SEERR_PORT:-5055}
        description: Filme & Serien wünschen
        server: my-docker
        container: seerr
        widget:
          type: jellyseerr
          url: http://seerr:5055
          key: ${SEERR_API_KEY}

- Media Management:
    - Radarr:
        icon: radarr.png
        href: http://radarr.${D}:${RADARR_PORT:-7878}
        description: Filme
        server: my-docker
        container: radarr
        widget:
          type: radarr
          url: http://radarr:7878
          key: ${RADARR_API_KEY}
    - Sonarr:
        icon: sonarr.png
        href: http://sonarr.${D}:${SONARR_PORT:-8989}
        description: Serien
        server: my-docker
        container: sonarr
        widget:
          type: sonarr
          url: http://sonarr:8989
          key: ${SONARR_API_KEY}
    - Prowlarr:
        icon: prowlarr.png
        href: http://prowlarr.${D}:${PROWLARR_PORT:-9696}
        description: Indexer
        server: my-docker
        container: prowlarr
        widget:
          type: prowlarr
          url: http://prowlarr:9696
          key: ${PROWLARR_API_KEY}
    - Bazarr:
        icon: bazarr.png
        href: http://bazarr.${D}:${BAZARR_PORT:-6767}
        description: Untertitel
        server: my-docker
        container: bazarr
        widget:
          type: bazarr
          url: http://bazarr:6767
          key: ${BAZARR_API_KEY}

- Downloads:
    - SABnzbd:
        icon: sabnzbd.png
        href: http://sabnzbd.${D}:${SABNZBD_PORT:-8090}
        description: Usenet
        server: my-docker
        container: sabnzbd
        widget:
          type: sabnzbd
          url: http://sabnzbd:8080
          key: ${SABNZBD_API_KEY}

- System:
    - AdGuard Home:
        icon: adguard-home.png
        href: http://adguard.${D}:${ADGUARD_WEBUI_PORT:-8081}
        description: DNS & Werbeblocker
        server: my-docker
        container: adguardhome
        siteMonitor: http://adguardhome:80
    - Unraid:
        icon: unraid.png
        href: http://unraid.${D}
        description: Server-Verwaltung
EOF

chown "${PUID}:${PGID}" "${HP}/services.yaml"
chmod 600 "${HP}/services.yaml"   # enthält API-Keys

success "services.yaml geschrieben — Homepage lädt die Widgets automatisch neu."
