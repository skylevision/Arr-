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
ANIME_PROFILE="[German] Anime HD Bluray + WEB"

seerr() { arr_api "$1" "$SEERR" "$SEERR_API_KEY" "$2" "${3:-}"; }

profile_id() { # <arr_base> <arr_key> <profil-name>
  arr_api GET "$1" "$2" /qualityprofile | jq -r --arg n "$3" \
    '[.[] | select(.name==$n)] | first | .id // empty'
}

update_instance() {
  local kind="$1" profile_name="$2" arr_base="$3" arr_key="$4" root="$5"
  local anime_root="${6:-}"   # nur Sonarr: aktiviert Anime-Profil + -Root

  local pid apid=""
  pid="$(profile_id "$arr_base" "$arr_key" "$profile_name")"
  [[ -n "$pid" ]] || error "${kind}: Profil \"${profile_name}\" existiert nicht — erst 06-recyclarr.sh ausführen."
  if [[ -n "$anime_root" ]]; then
    apid="$(profile_id "$arr_base" "$arr_key" "$ANIME_PROFILE")"
    [[ -n "$apid" ]] || error "${kind}: Profil \"${ANIME_PROFILE}\" existiert nicht — erst 06-recyclarr.sh ausführen."
  fi

  local instances
  instances="$(seerr GET "/settings/${kind}")"
  [[ "$(echo "$instances" | jq length)" -gt 0 ]] || { warn "${kind}: keine Instanz in Seerr konfiguriert — übersprungen."; return; }

  local updated id
  for id in $(echo "$instances" | jq -r '.[].id'); do
    updated="$(echo "$instances" | jq --argjson id "$id" --argjson pid "$pid" \
      --arg pname "$profile_name" --arg root "$root" \
      --arg apid "$apid" --arg apname "$ANIME_PROFILE" --arg aroot "$anime_root" '
      [.[] | select(.id==$id)] | first
      | .activeProfileId = $pid
      | .activeProfileName = $pname
      | .activeDirectory = $root
      | (if $aroot != "" then
           .activeAnimeProfileId = ($apid | tonumber)
           | .activeAnimeProfileName = $apname
           | .activeAnimeDirectory = $aroot
           | (if has("animeSeriesType") then .animeSeriesType = "anime" else . end)
         else . end)
      | del(.id)')"  # id ist laut Seerr-OpenAPI read-only und darf nicht im Body stehen
    seerr PUT "/settings/${kind}/${id}" "$updated" >/dev/null
    success "Seerr ${kind} (Instanz ${id}): Default-Profil → \"${profile_name}\", Root → ${root}."
    if [[ -n "$anime_root" ]]; then
      success "Seerr ${kind} (Instanz ${id}): Anime-Profil → \"${ANIME_PROFILE}\", Root → ${anime_root}."
    fi
  done
}

update_instance radarr "$RADARR_PROFILE" "http://localhost:${RADARR_PORT:-7878}/api/v3" "$RADARR_API_KEY" "/data/media/movies"
update_instance sonarr "$SONARR_PROFILE" "http://localhost:${SONARR_PORT:-8989}/api/v3" "$SONARR_API_KEY" "/data/media/tv" "/data/media/anime"

success "Seerr-Defaults gesetzt."
