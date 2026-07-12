#!/usr/bin/env bash
# ============================================================
# 03-prowlarr.sh — Prowlarr: Indexer (scenenzbs) + Applications
#
# Prowlarr ist Single Source of Truth für Indexer und synct sie
# per "Applications" (fullSync) automatisch zu Radarr & Sonarr.
# Idempotent: Indexer wird über die baseUrl identifiziert,
# Applications über ihren Namen — update statt create.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var PROWLARR_API_KEY
require_var RADARR_API_KEY
require_var SONARR_API_KEY
require_var SCENENZBS_URL
require_var SCENENZBS_APIKEY

P="http://localhost:${PROWLARR_PORT:-9696}/api/v1"
papi() { arr_api "$1" "$P" "$PROWLARR_API_KEY" "$2" "${3:-}"; }

# ---------------------------------------------------------------------------
# Indexer: scenenzbs (Newznab)
# ---------------------------------------------------------------------------
info "Stelle Indexer scenenzbs sicher ..."

# Matching über baseUrl ODER bekannte Namen — deckt auch Domain-Umzüge ab
# (z. B. scenenzbs.com → treasure-maps.com), ohne Duplikate anzulegen.
EXISTING="$(papi GET /indexer | jq --arg url "$SCENENZBS_URL" \
  '[.[] | select(
      ((.fields[] | select(.name=="baseUrl") | .value) == $url)
      or (.name == "scenenzbs") or (.name == "Generic Newznab")
    )] | first // empty')"

if [[ -n "$EXISTING" ]]; then
  # Update: Name normalisieren, baseUrl + API-Key auf Soll-Zustand setzen
  UPDATED="$(echo "$EXISTING" | jq --arg url "$SCENENZBS_URL" --arg key "$SCENENZBS_APIKEY" '
    .name = "scenenzbs"
    | .enable = true
    | .fields = (.fields | map(
        if .name=="baseUrl" then .value=$url
        elif .name=="apiKey" then .value=$key
        else . end))')"
  ID="$(echo "$EXISTING" | jq -r .id)"
  # Prowlarr kontaktiert den Indexer bei jedem Speichern (Caps-Abfrage) —
  # auch mit forceSave. Ist der Indexer gerade offline, darf der Bootstrap
  # daran nicht scheitern: der Eintrag existiert ja bereits mit korrekter
  # baseUrl. Die Erreichbarkeit prüft scripts/healthcheck.sh separat.
  if papi PUT "/indexer/${ID}?forceSave=true" "$UPDATED" >/dev/null 2>&1; then
    success "Indexer scenenzbs aktualisiert (id=${ID})."
  else
    warn "Indexer ${SCENENZBS_URL} aktuell nicht erreichbar — Eintrag (id=${ID}) bleibt unverändert bestehen."
  fi
else
  # Create: Schema-Definition der Instanz als Basis verwenden (nichts erfinden)
  SCHEMA="$(papi GET /indexer/schema | jq \
    '[.[] | select(.implementation=="Newznab" and .name=="Generic Newznab")] | first')"
  [[ -n "$SCHEMA" && "$SCHEMA" != "null" ]] || error "Newznab-Schema nicht in Prowlarr gefunden."
  NEW="$(echo "$SCHEMA" | jq --arg url "$SCENENZBS_URL" --arg key "$SCENENZBS_APIKEY" '
    .name = "scenenzbs"
    | .enable = true
    | .appProfileId = 1
    | .fields = (.fields | map(
        if .name=="baseUrl" then .value=$url
        elif .name=="apiKey" then .value=$key
        else . end))')"
  papi POST "/indexer?forceSave=true" "$NEW" >/dev/null \
    || error "Indexer-Anlage fehlgeschlagen — ist ${SCENENZBS_URL} gerade offline? Später erneut ausführen: bash bootstrap/03-prowlarr.sh"
  success "Indexer scenenzbs angelegt."
fi

# ---------------------------------------------------------------------------
# Indexer: AnimeTosho (Anime-Usenet, frei, keine Anmeldung nötig)
# ---------------------------------------------------------------------------
info "Stelle Indexer AnimeTosho sicher ..."

AT_EXISTING="$(papi GET /indexer | jq \
  '[.[] | select((.name | ascii_downcase | test("tosho")) and .protocol=="usenet")] | first // empty')"

if [[ -n "$AT_EXISTING" ]]; then
  success "Indexer AnimeTosho existiert (id=$(echo "$AT_EXISTING" | jq -r .id))."
else
  AT_SCHEMA="$(papi GET /indexer/schema | jq \
    '[.[] | select((.name | ascii_downcase | test("tosho")) and .protocol=="usenet")] | first')"
  [[ -n "$AT_SCHEMA" && "$AT_SCHEMA" != "null" ]] || error "AnimeTosho-Schema nicht in Prowlarr gefunden."
  AT_NEW="$(echo "$AT_SCHEMA" | jq '.enable = true | .appProfileId = 1')"
  papi POST "/indexer?forceSave=true" "$AT_NEW" >/dev/null \
    || error "AnimeTosho-Anlage fehlgeschlagen — später erneut: bash bootstrap/03-prowlarr.sh"
  success "Indexer AnimeTosho angelegt."
fi

# ---------------------------------------------------------------------------
# Applications: Radarr + Sonarr (fullSync)
# ---------------------------------------------------------------------------
ensure_app() {
  local name="$1" impl="$2" base_url="$3" api_key="$4"
  local existing updated schema new id

  existing="$(papi GET /applications | jq --arg n "$name" '[.[] | select(.name==$n)] | first // empty')"

  if [[ -n "$existing" ]]; then
    updated="$(echo "$existing" | jq --arg url "$base_url" --arg key "$api_key" '
      .syncLevel = "fullSync"
      | .fields = (.fields | map(
          if .name=="baseUrl" then .value=$url
          elif .name=="apiKey" then .value=$key
          elif .name=="prowlarrUrl" then .value="http://prowlarr:9696"
          else . end))')"
    id="$(echo "$existing" | jq -r .id)"
    papi PUT "/applications/${id}" "$updated" >/dev/null
    success "Application ${name} aktualisiert (fullSync)."
  else
    schema="$(papi GET /applications/schema | jq --arg impl "$impl" \
      '[.[] | select(.implementation==$impl)] | first')"
    [[ -n "$schema" && "$schema" != "null" ]] || error "${impl}-Schema nicht gefunden."
    new="$(echo "$schema" | jq --arg n "$name" --arg url "$base_url" --arg key "$api_key" '
      .name = $n
      | .syncLevel = "fullSync"
      | .fields = (.fields | map(
          if .name=="baseUrl" then .value=$url
          elif .name=="apiKey" then .value=$key
          elif .name=="prowlarrUrl" then .value="http://prowlarr:9696"
          else . end))')"
    papi POST /applications "$new" >/dev/null
    success "Application ${name} angelegt (fullSync)."
  fi
}

ensure_app "Radarr" "Radarr" "http://radarr:7878" "$RADARR_API_KEY"
ensure_app "Sonarr" "Sonarr" "http://sonarr:8989" "$SONARR_API_KEY"

info "Stoße Indexer-Sync zu den Apps an ..."
papi POST /command '{"name":"ApplicationIndexerSync"}' >/dev/null
success "Prowlarr konfiguriert."
