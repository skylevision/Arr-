#!/usr/bin/env bash
# ============================================================
# healthcheck.sh — Phase-4-Report für den Arr-Stack
#
#   bash scripts/healthcheck.sh
#
# Prüft (nur lesend, bis auf den Hardlink-Test mit Wegwerf-Datei):
#   1. Container laufen und sind healthy
#   2. APIs erreichbar (Radarr, Sonarr, Prowlarr, SABnzbd,
#      Bazarr, Seerr, Jellyfin)
#   3. Prowlarr: Indexer-Test (kontaktiert den Indexer)
#   4. Radarr/Sonarr: Download-Client-Test (kontaktiert SABnzbd)
#   5. Hardlink-Test downloads → media (Testdatei, wird gelöscht)
#
# Exit-Code 0 = alles grün, sonst Anzahl der Fehlschläge.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/../bootstrap/lib.sh"

FAIL=0
ok()   { success "$*"; }
bad()  { echo -e "${RED}[FAIL]${NC}  $*" >&2; FAIL=$((FAIL + 1)); }

# ---------------------------------------------------------------------------
# 1. Container-Status
# ---------------------------------------------------------------------------
info "1/5 Container-Status ..."
SERVICES=(tailscale sabnzbd prowlarr radarr sonarr bazarr jellyfin seerr homepage)
for svc in "${SERVICES[@]}"; do
  state="$(docker inspect -f '{{.State.Status}}{{if .State.Health}}/{{.State.Health.Status}}{{end}}' "$svc" 2>/dev/null || echo missing)"
  case "$state" in
    running/healthy|running) ok "$svc: $state" ;;
    *)                       bad "$svc: $state (Logs: docker logs $svc)" ;;
  esac
done

# ---------------------------------------------------------------------------
# 2. API-Erreichbarkeit
# ---------------------------------------------------------------------------
info "2/5 API-Erreichbarkeit ..."
require_var RADARR_API_KEY
require_var SONARR_API_KEY
require_var PROWLARR_API_KEY
require_var SABNZBD_API_KEY
require_var BAZARR_API_KEY

RADARR="http://localhost:${RADARR_PORT:-7878}/api/v3"
SONARR="http://localhost:${SONARR_PORT:-8989}/api/v3"
PROWLARR="http://localhost:${PROWLARR_PORT:-9696}/api/v1"

# report <name> <version-oder-leer>: leere Version = API nicht erreichbar
report() {
  local name="$1" version="$2"
  if [[ -n "$version" && "$version" != "null" ]]; then
    ok "$name API erreichbar (v${version})"
  else
    bad "$name API nicht erreichbar"
  fi
}

report Radarr   "$(arr_api GET "$RADARR"   "$RADARR_API_KEY"   /system/status 2>/dev/null | jq -r .version)"
report Sonarr   "$(arr_api GET "$SONARR"   "$SONARR_API_KEY"   /system/status 2>/dev/null | jq -r .version)"
report Prowlarr "$(arr_api GET "$PROWLARR" "$PROWLARR_API_KEY" /system/status 2>/dev/null | jq -r .version)"
report SABnzbd  "$(curl -fsS -m 30 "http://localhost:${SABNZBD_PORT:-8090}/api?mode=version&output=json&apikey=${SABNZBD_API_KEY}" 2>/dev/null | jq -r .version)"
report Bazarr   "$(curl -fsS -m 30 -H "X-API-KEY: ${BAZARR_API_KEY}" "http://localhost:${BAZARR_PORT:-6767}/api/system/status" 2>/dev/null | jq -r .data.bazarr_version)"
report Seerr    "$(curl -fsS -m 30 "http://localhost:${SEERR_PORT:-5055}/api/v1/status" 2>/dev/null | jq -r .version)"

if curl -fsS -m 30 "http://localhost:${JELLYFIN_PORT_HTTP:-8096}/health" >/dev/null 2>&1; then
  ok "Jellyfin /health erreichbar"
else
  bad "Jellyfin /health nicht erreichbar"
fi

# ---------------------------------------------------------------------------
# 3. Prowlarr: Indexer-Test (kontaktiert den Indexer wirklich)
# ---------------------------------------------------------------------------
info "3/5 Prowlarr-Indexer-Test ..."
INDEXERS="$(arr_api GET "$PROWLARR" "$PROWLARR_API_KEY" /indexer 2>/dev/null || echo '[]')"
if [[ "$(echo "$INDEXERS" | jq length)" -eq 0 ]]; then
  bad "Kein Indexer in Prowlarr konfiguriert (bootstrap/03-prowlarr.sh gelaufen?)"
else
  while IFS= read -r idx; do
    name="$(echo "$idx" | jq -r .name)"
    if arr_api POST "$PROWLARR" "$PROWLARR_API_KEY" /indexer/test "$idx" >/dev/null 2>&1; then
      ok "Indexer \"$name\": Test bestanden"
    else
      bad "Indexer \"$name\": Test fehlgeschlagen (Indexer offline oder API-Key falsch?)"
    fi
  done < <(echo "$INDEXERS" | jq -c '.[]')
fi

# ---------------------------------------------------------------------------
# 4. Radarr/Sonarr: Download-Client-Test (kontaktiert SABnzbd)
# ---------------------------------------------------------------------------
info "4/5 Download-Client-Tests ..."
test_clients() {
  local app="$1" base="$2" key="$3"
  local clients name client
  clients="$(arr_api GET "$base" "$key" /downloadclient 2>/dev/null || echo '[]')"
  if [[ "$(echo "$clients" | jq length)" -eq 0 ]]; then
    bad "$app: kein Download-Client konfiguriert"
    return
  fi
  while IFS= read -r client; do
    name="$(echo "$client" | jq -r .name)"
    if arr_api POST "$base" "$key" /downloadclient/test "$client" >/dev/null 2>&1; then
      ok "$app → \"$name\": Test bestanden"
    else
      bad "$app → \"$name\": Test fehlgeschlagen"
    fi
  done < <(echo "$clients" | jq -c '.[]')
}
test_clients Radarr "$RADARR" "$RADARR_API_KEY"
test_clients Sonarr "$SONARR" "$SONARR_API_KEY"

# ---------------------------------------------------------------------------
# 5. Hardlink-Test: downloads und media müssen ein Dateisystem sein
# ---------------------------------------------------------------------------
info "5/5 Hardlink-Test ..."
SRC="${DATA}/downloads/usenet/complete/.hardlink-test-$$"
DST="${DATA}/media/movies/.hardlink-test-$$"
cleanup_hardlink_test() { rm -f "$SRC" "$DST"; }
trap cleanup_hardlink_test EXIT

if echo "hardlink-test" > "$SRC" 2>/dev/null && ln "$SRC" "$DST" 2>/dev/null; then
  if [[ "$(stat -c %i "$SRC")" == "$(stat -c %i "$DST")" ]]; then
    ok "Hardlink downloads → media funktioniert (gleiche Inode)"
  else
    bad "ln hat kopiert statt verlinkt (unterschiedliche Inodes) — verschiedene Dateisysteme?"
  fi
else
  bad "Hardlink konnte nicht angelegt werden — Split-Level/Cache-Einstellungen des data-Shares prüfen"
fi

# ---------------------------------------------------------------------------
# Ergebnis
# ---------------------------------------------------------------------------
echo ""
if [[ "$FAIL" -eq 0 ]]; then
  success "Healthcheck bestanden — alle Prüfungen grün."
else
  warn "Healthcheck mit ${FAIL} Fehlschlag/Fehlschlägen abgeschlossen (siehe [FAIL]-Zeilen)."
fi
exit "$FAIL"
