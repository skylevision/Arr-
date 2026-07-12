#!/usr/bin/env bash
# ============================================================
# 08-seerr.sh — Seerr: Default-Profile auf die German-DL-4K-
#               Profile umstellen (Radarr + Sonarr)
#
# Voraussetzung: 06-recyclarr.sh ist gelaufen (Profile existieren).
# Idempotent: PUT auf die bestehende Instanz-Konfiguration.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var SEERR_API_KEY
require_var RADARR_API_KEY
require_var SONARR_API_KEY

SEERR="http://localhost:${SEERR_PORT:-5055}/api/v1"
RADARR_PROFILE="[German] Remux + WEB 2160p"
SONARR_PROFILE="[German] UHD Remux + WEB"

seerr() { arr_api "$1" "$SEERR" "$SEERR_API_KEY" "$2" "${3:-}"; }

update_instance() {
  local kind="$1" profile_name="$2" arr_base="$3" arr_key="$4" root="$5"

  local pid
  pid="$(arr_api GET "$arr_base" "$arr_key" /qualityprofile | jq -r --arg n "$profile_name" \
    '[.[] | select(.name==$n)] | first | .id // empty')"
  [[ -n "$pid" ]] || error "${kind}: Profil \"${profile_name}\" existiert nicht — erst 06-recyclarr.sh ausführen."

  local instances
  instances="$(seerr GET "/settings/${kind}")"
  [[ "$(echo "$instances" | jq length)" -gt 0 ]] || { warn "${kind}: keine Instanz in Seerr konfiguriert — übersprungen."; return; }

  local updated id
  for id in $(echo "$instances" | jq -r '.[].id'); do
    updated="$(echo "$instances" | jq --argjson id "$id" --argjson pid "$pid" \
      --arg pname "$profile_name" --arg root "$root" '
      [.[] | select(.id==$id)] | first
      | .activeProfileId = $pid
      | .activeProfileName = $pname
      | .activeDirectory = $root
      | del(.id)')"  # id ist laut Seerr-OpenAPI read-only und darf nicht im Body stehen
    seerr PUT "/settings/${kind}/${id}" "$updated" >/dev/null
    success "Seerr ${kind} (Instanz ${id}): Default-Profil → \"${profile_name}\", Root → ${root}."
  done
}

update_instance radarr "$RADARR_PROFILE" "http://localhost:${RADARR_PORT:-7878}/api/v3" "$RADARR_API_KEY" "/data/media/movies"
update_instance sonarr "$SONARR_PROFILE" "http://localhost:${SONARR_PORT:-8989}/api/v3" "$SONARR_API_KEY" "/data/media/tv"

success "Seerr-Defaults gesetzt."
