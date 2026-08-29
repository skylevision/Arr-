#!/usr/bin/env bash
# ============================================================
# 10-homepage.sh — Homepage: services.yaml mit echten API-Keys
#
# Generiert ${APPDATA}/homepage/services.yaml komplett neu:
# Widgets für Radarr/Sonarr/Prowlarr/Bazarr/SABnzbd/Seerr mit
# den Keys aus .env.runtime. Jellyfin bekommt keinen Widget-Key
# (müsste manuell in Jellyfin angelegt werden) — nur Link + Ping.
#
# WELCHE ADRESSE JEDER DIENST BEKOMMT (Stand 29.08.2026):
#
# Die <dienst>.<LOCAL_DOMAIN>-Namen kommen aus den AdGuard-Rewrites und
# funktionieren nur im Heimnetz. Über Tailscale löst der Tailnet-Resolver
# sie NICHT auf, und Subnet-Routen sind bewusst keine gesetzt
# (AdvertiseRoutes ist null) — auf dem iPhone unterwegs liefen deshalb
# sämtliche Kacheln ins Leere.
#
# Deshalb bekommt jeder Dienst die Adresse, die von möglichst überall
# trägt:
#   - über SWAG veröffentlicht (Jellyfin, Seerr, Vaultwarden)
#     -> https://<sub>.${SWAG_URL}. Funktioniert im LAN, mobil und über
#        Tailscale, mit gültigem Zertifikat.
#   - nur im Tailnet (Rack)
#     -> der tailscale-serve-Name.
#   - interne Verwaltungsoberflächen (Radarr, Sonarr, SABnzbd, …)
#     -> weiterhin <dienst>.<LOCAL_DOMAIN>. Die braucht man am Rechner
#        im Heimnetz; nach außen gehören sie ohnehin nicht.
#
# Dauerhaft ließe sich auch der Rest mobil erreichbar machen: im
# Tailscale-Container --advertise-routes=<LAN>/24 setzen, die Route in
# der Tailscale-Admin-Konsole freigeben und AdGuard als Tailnet-DNS
# eintragen. Beides erfordert die Weboberfläche von Tailscale und ist
# deshalb hier nicht automatisiert.
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
D="${LOCAL_DOMAIN:-home}"
PUB="${SWAG_URL:-}"                       # leer = keine öffentlichen Links
TS_NAME="${RACK_TS_HOST:-}"               # z. B. arr-stack.tailnet.ts.net

# Öffentliche Adresse, wenn SWAG_URL gesetzt ist, sonst der LAN-Name.
# So bleibt das Skript auch auf einer Installation ohne SWAG brauchbar.
jellyfin_href="http://jellyfin.${D}:${JELLYFIN_PORT_HTTP:-8096}"
seerr_href="http://seerr.${D}:${SEERR_PORT:-5055}"
vault_href="http://${UNRAID_IP:-127.0.0.1}:${VAULTWARDEN_PORT:-8082}"
[[ -n "$PUB" ]] && jellyfin_href="https://tv.${PUB}"
[[ -n "$PUB" ]] && seerr_href="https://seer.${PUB}"
[[ -n "$PUB" ]] && vault_href="https://vault.${PUB}"

# Rack hört nur auf 127.0.0.1 und ist ausschließlich über tailscale serve
# erreichbar. Ohne bekannten Tailnet-Namen bleibt nur der lokale Port —
# der funktioniert dann allerdings nur auf dem Server selbst.
rack_href="http://${UNRAID_IP:-127.0.0.1}:${RACK_PORT:-8099}"
[[ -n "$TS_NAME" ]] && rack_href="https://${TS_NAME}"
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
        href: ${jellyfin_href}
        description: Filme & Serien
        server: my-docker
        container: jellyfin
${JF_ENTRY}
    - Seerr:
        icon: overseerr.png
        href: ${seerr_href}
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

    - qBittorrent:
        icon: qbittorrent.png
        href: http://${UNRAID_IP:-127.0.0.1}:${QBIT_PORT:-8085}
        description: Torrent (über VPN)
        server: my-docker
        container: qbittorrent
        siteMonitor: http://gluetun:8080

- Alltag:
    - Rack:
        icon: mdi-hanger
        href: ${rack_href}
        description: Kleiderschrank & Outfits
        server: my-docker
        container: rack
        siteMonitor: http://${UNRAID_IP:-127.0.0.1}:${RACK_PORT:-8099}/api/health
    - Vaultwarden:
        icon: bitwarden.png
        href: ${vault_href}
        description: Passwörter
        server: my-docker
        container: vaultwarden
        siteMonitor: http://vaultwarden:80/alive

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

# ------------------------------------------------------------------
# Lesezeichen: dieselben Verwaltungsoberflächen noch einmal, aber über
# den Tailnet-Namen.
#
# Die Kacheln oben zeigen für die internen Dienste auf <dienst>.${D} —
# das ist im Heimnetz der bequemere Weg und funktioniert dort auch ohne
# Tailscale. Unterwegs löst dieser Name nicht auf. Statt die Kacheln
# umzustellen und damit den Heimnetz-Fall zu verschlechtern, stehen die
# Tailnet-Adressen zusätzlich als Lesezeichen daneben. Beide Wege führen
# zum selben Dienst, man nimmt den, der gerade trägt.
#
# Ohne bekannten Tailnet-Namen wird der Abschnitt weggelassen, statt
# Links zu erzeugen, die ins Leere zeigen.
# ------------------------------------------------------------------
if [[ -n "$TS_NAME" ]]; then
  info "Schreibe ${HP}/bookmarks.yaml (Tailnet-Adressen für unterwegs) ..."
  cat > "${HP}/bookmarks.yaml" <<EOF
---
# Automatisch generiert von bootstrap/10-homepage.sh — NICHT von Hand
# editieren, Änderungen dort machen und das Skript erneut ausführen.

- Unterwegs über Tailscale:
    - Radarr:
        - abbr: RA
          href: http://${TS_NAME}:${RADARR_PORT:-7878}
    - Sonarr:
        - abbr: SO
          href: http://${TS_NAME}:${SONARR_PORT:-8989}
    - Prowlarr:
        - abbr: PR
          href: http://${TS_NAME}:${PROWLARR_PORT:-9696}
    - Bazarr:
        - abbr: BA
          href: http://${TS_NAME}:${BAZARR_PORT:-6767}
    - SABnzbd:
        - abbr: SA
          href: http://${TS_NAME}:${SABNZBD_PORT:-8090}
    - qBittorrent:
        - abbr: QB
          href: http://${TS_NAME}:${QBIT_PORT:-8085}
    - AdGuard:
        - abbr: AG
          href: http://${TS_NAME}:${ADGUARD_WEBUI_PORT:-8081}
    - Dashboard:
        - abbr: HP
          href: http://${TS_NAME}:${HOMEPAGE_PORT:-3000}
EOF
  chown "${PUID}:${PGID}" "${HP}/bookmarks.yaml"
else
  info "RACK_TS_HOST nicht gesetzt — bookmarks.yaml bleibt unverändert."
fi

success "services.yaml geschrieben — Homepage lädt die Widgets automatisch neu."
