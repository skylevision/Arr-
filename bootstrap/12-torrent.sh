#!/usr/bin/env bash
# ============================================================
# 12-torrent.sh — Torrent-Weg (Anime/Hentai) einrichten
#
#   - qBittorrent (läuft im gluetun-Netz-Stack, aller Traffic durchs VPN):
#     WebUI-Auth-Bypass für arr_net + LAN, Save-/Temp-Pfade, Kategorie
#   - qBittorrent als Download-Client in Sonarr (Torrent)
#   - Root-Folder /data/media/hentai in Sonarr (getrennte Bibliothek)
#   - Indexer in Prowlarr: sukebei.nyaa.si, Nyaa.si, Anidex → Sync zu Sonarr
#
# Läuft nur mit aktivem torrent-Profil (qBittorrent up). Sonst wird sauber
# übersprungen — ein normaler bootstrap.sh-Lauf darf nicht scheitern.
# Idempotent: alles match-then-update / createCategory ist ohne Fehler wiederholbar.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var SONARR_API_KEY
require_var PROWLARR_API_KEY

if [[ "$(docker inspect -f '{{.State.Running}}' qbittorrent 2>/dev/null)" != "true" ]]; then
  warn "qBittorrent läuft nicht (torrent-Profil aktiv? 'docker compose --profile torrent up -d') — 12-torrent.sh übersprungen."
  exit 0
fi

QBIT="http://localhost:${QBIT_PORT:-8085}"
LAN="${LAN_SUBNET:-192.168.178.0/24}"
CAT="sonarr"
CAT_PATH="/data/downloads/torrents/${CAT}"

# ---------------------------------------------------------------------------
# qBittorrent: WebUI-Vorkonfiguration (Auth-Bypass für arr_net + LAN)
# LinuxServer-qBit loggt bei jedem Start ein temporäres Passwort, solange
# keines gesetzt ist — damit loggen wir uns einmalig ein und setzen die Prefs.
# ---------------------------------------------------------------------------
TMP_PW="$(docker logs qbittorrent 2>&1 | grep -a 'temporary password' | tail -1 | sed 's/.*: //')"
COOKIE="$(mktemp)"; trap 'rm -f "$COOKIE"' EXIT

if [[ -n "$TMP_PW" ]] && \
   curl -fsS -c "$COOKIE" --data-urlencode "username=admin" --data-urlencode "password=${TMP_PW}" \
     "${QBIT}/api/v2/auth/login" | grep -q "Ok."; then
  PREFS="$(jq -n --arg lan "$LAN" '{
    bypass_auth_subnet_whitelist_enabled: true,
    bypass_auth_subnet_whitelist: ("172.16.0.0/12\n" + $lan),
    web_ui_host_header_validation_enabled: false,
    save_path: "/data/downloads/torrents",
    temp_path_enabled: true,
    temp_path: "/data/downloads/torrents/incomplete"
  }')"
  curl -fsS -b "$COOKIE" --data-urlencode "json=${PREFS}" "${QBIT}/api/v2/app/setPreferences" >/dev/null
  # Kategorie anlegen (Fehler ignorieren, falls sie schon existiert)
  curl -fsS -b "$COOKIE" --data-urlencode "category=${CAT}" --data-urlencode "savePath=${CAT_PATH}" \
    "${QBIT}/api/v2/torrents/createCategory" >/dev/null 2>&1 || true
  success "qBittorrent konfiguriert (Auth-Bypass arr_net+LAN, Save-Pfade, Kategorie '${CAT}')."
else
  warn "qBittorrent: kein temporäres Passwort im Log (schon manuell konfiguriert?) — WebUI-Vorkonfig übersprungen."
  warn "  Falls Sonarr sich nicht verbinden kann: in qBit → Einstellungen → WebUI → 'Authentifizierung für Clients im Whitelist-Subnetz umgehen' für ${ARR_NET_SUBNET:-172.18.0.0/16} + ${LAN} aktivieren."
fi

# ---------------------------------------------------------------------------
# Sonarr: qBittorrent als Download-Client (Torrent)
# ---------------------------------------------------------------------------
S="http://localhost:${SONARR_PORT:-8989}/api/v3"
sapi() { arr_api "$1" "$S" "$SONARR_API_KEY" "$2" "${3:-}"; }

patch_qbit='.enable = true
  | .name = "qBittorrent"
  | .fields = (.fields | map(
      if .name=="host" then .value="gluetun"
      elif .name=="port" then .value=8080
      elif .name=="useSsl" then .value=false
      elif .name=="tvCategory" then .value=$cat
      else . end))'

EXISTING="$(sapi GET /downloadclient | jq '[.[] | select(.implementation=="QBittorrent")] | first // empty')"
if [[ -n "$EXISTING" ]]; then
  ID="$(echo "$EXISTING" | jq -r .id)"
  sapi PUT "/downloadclient/${ID}" "$(echo "$EXISTING" | jq --arg cat "$CAT" "$patch_qbit")" >/dev/null
  success "Sonarr: Download-Client qBittorrent aktualisiert."
else
  SCHEMA="$(sapi GET /downloadclient/schema | jq '[.[] | select(.implementation=="QBittorrent")] | first')"
  [[ -n "$SCHEMA" && "$SCHEMA" != "null" ]] || error "QBittorrent-Schema in Sonarr nicht gefunden."
  sapi POST /downloadclient "$(echo "$SCHEMA" | jq --arg cat "$CAT" "$patch_qbit")" >/dev/null
  success "Sonarr: Download-Client qBittorrent angelegt."
fi

# ---------------------------------------------------------------------------
# Sonarr: Root-Folder für die getrennte Hentai-Bibliothek
# ---------------------------------------------------------------------------
HROOT="/data/media/hentai"
if ! sapi GET /rootfolder | jq -e --arg p "$HROOT" '.[] | select(.path==$p)' >/dev/null; then
  sapi POST /rootfolder "{\"path\":\"${HROOT}\"}" >/dev/null
  success "Sonarr: Root-Folder ${HROOT} angelegt."
else
  success "Sonarr: Root-Folder ${HROOT} vorhanden."
fi

# ---------------------------------------------------------------------------
# Prowlarr: öffentliche Torrent-Indexer (keine Zugangsdaten nötig)
# ---------------------------------------------------------------------------
P="http://localhost:${PROWLARR_PORT:-9696}/api/v1"
papi() { arr_api "$1" "$P" "$PROWLARR_API_KEY" "$2" "${3:-}"; }

ensure_indexer() { # <schema-implementationName oder .definitionName-Regex> <Anzeigename>
  local match="$1" name="$2"
  if papi GET /indexer | jq -e --arg n "$name" '.[] | select(.name==$n)' >/dev/null; then
    success "Prowlarr: Indexer ${name} vorhanden."
    return
  fi
  local schema
  schema="$(papi GET /indexer/schema | jq --arg m "$match" \
    '[.[] | select((.name|ascii_downcase)==($m|ascii_downcase))] | first')"
  [[ -n "$schema" && "$schema" != "null" ]] || { warn "Prowlarr: Schema für '${name}' nicht gefunden — übersprungen."; return; }
  local new
  new="$(echo "$schema" | jq --arg n "$name" '.name=$n | .enable=true | .appProfileId=1')"
  if papi POST "/indexer?forceSave=true" "$new" >/dev/null 2>&1; then
    success "Prowlarr: Indexer ${name} angelegt."
  else
    warn "Prowlarr: Indexer ${name} aktuell nicht erreichbar — später erneut: bash bootstrap/12-torrent.sh"
  fi
}

ensure_indexer "sukebei.nyaa.si" "sukebei.nyaa.si"
ensure_indexer "Nyaa.si"         "Nyaa.si"
ensure_indexer "Anidex"          "Anidex"

info "Stoße Prowlarr-App-Sync an ..."
papi POST /command '{"name":"ApplicationIndexerSync"}' >/dev/null
success "Torrent-Setup abgeschlossen (qBittorrent + Sukebei/Nyaa/Anidex → Sonarr)."
