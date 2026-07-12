#!/usr/bin/env bash
# ============================================================
# 01-extract-keys.sh — API-Keys der laufenden Dienste einsammeln
#
# Liest die Keys aus den config-Dateien in ${APPDATA} und schreibt
# sie nach .env.runtime (gitignored, chmod 600). Idempotent:
# die Datei wird bei jedem Lauf komplett neu geschrieben.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

RUNTIME="${REPO_DIR}/.env.runtime"

xml_key()  { grep -oPm1 '(?<=<ApiKey>)[^<]+' "$1"; }

RADARR_API_KEY="$(xml_key "${APPDATA}/radarr/config.xml")"       || error "Radarr-Key nicht gefunden"
SONARR_API_KEY="$(xml_key "${APPDATA}/sonarr/config.xml")"       || error "Sonarr-Key nicht gefunden"
PROWLARR_API_KEY="$(xml_key "${APPDATA}/prowlarr/config.xml")"   || error "Prowlarr-Key nicht gefunden"

SABNZBD_API_KEY="$(grep -m1 '^api_key' "${APPDATA}/sabnzbd/sabnzbd.ini" | sed 's/^api_key = //')" \
  || error "SABnzbd-Key nicht gefunden"

# Bazarr: erster apikey-Eintrag unter dem auth:-Block
BAZARR_API_KEY="$(awk '/^auth:/{f=1} f && /apikey:/{print $2; exit}' "${APPDATA}/bazarr/config/config.yaml")" \
  || error "Bazarr-Key nicht gefunden"

SEERR_API_KEY="$(jq -r '.main.apiKey // empty' "${APPDATA}/seerr/settings.json")" \
  || error "Seerr-Key nicht gefunden"

for v in RADARR_API_KEY SONARR_API_KEY PROWLARR_API_KEY SABNZBD_API_KEY BAZARR_API_KEY SEERR_API_KEY; do
  [[ -n "${!v}" ]] || error "$v ist leer"
done

{
  echo "# Automatisch generiert von bootstrap/01-extract-keys.sh — nicht committen!"
  printf 'RADARR_API_KEY=%s\n'   "$RADARR_API_KEY"
  printf 'SONARR_API_KEY=%s\n'   "$SONARR_API_KEY"
  printf 'PROWLARR_API_KEY=%s\n' "$PROWLARR_API_KEY"
  printf 'SABNZBD_API_KEY=%s\n'  "$SABNZBD_API_KEY"
  printf 'BAZARR_API_KEY=%s\n'   "$BAZARR_API_KEY"
  printf 'SEERR_API_KEY=%s\n'    "$SEERR_API_KEY"
} > "$RUNTIME"
chmod 600 "$RUNTIME"

success "API-Keys nach ${RUNTIME} geschrieben (6 Dienste)."
