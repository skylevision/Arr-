#!/usr/bin/env bash
# ============================================================
# 06-recyclarr.sh — Quality Profiles & Custom Formats (TRaSH)
#
# 1. Recyclarr-Sync: legt die German-DL-4K-Profile inkl. aller
#    TRaSH Custom Formats in Radarr + Sonarr an (idempotent).
# 2. Räumt danach die alten, manuell gepflegten Custom Formats
#    und das alte Profil "German DL 4k" ab — aber nur, wenn die
#    neuen Profile nachweislich existieren und nichts sie nutzt.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var RADARR_API_KEY
require_var SONARR_API_KEY

RECYCLARR_IMAGE="ghcr.io/recyclarr/recyclarr:8.6.0"
RADARR_PROFILE="[German] Remux + WEB 2160p"
SONARR_PROFILE="[German] UHD Remux + WEB"

# Alte manuell gepflegte CFs (aus DUAL_LANGUAGE_SETUP.md / PCJones-Schema).
# Werden durch die TRaSH-CFs des Recyclarr-Syncs ersetzt.
# WICHTIG: "German DL" fehlt hier bewusst — der TRaSH Guide hat ein
# gleichnamiges CF, das Recyclarr übernimmt und im neuen Profil scored.
LEGACY_CFS=("German DL 2" "Language: Not ENG/GER" "Language: English Only" "MIC Dubbed")
LEGACY_PROFILES=("German DL 4k")

mkdir -p "${REPO_DIR}/recyclarr/cache"
chown -R "${PUID}:${PGID}" "${REPO_DIR}/recyclarr" 2>/dev/null || true

info "Recyclarr-Sync (${RECYCLARR_IMAGE}) ..."
docker run --rm --network arr_net \
  --user "${PUID}:${PGID}" \
  -e RADARR_API_KEY -e SONARR_API_KEY \
  -v "${REPO_DIR}/recyclarr:/config" \
  "${RECYCLARR_IMAGE}" sync

# ---------------------------------------------------------------------------
# Aufräumen: alte CFs/Profile nur entfernen, wenn die neuen Profile da sind
# ---------------------------------------------------------------------------
cleanup_arr() {
  local base="$1" key="$2" new_profile="$3" app="$4" movie_endpoint="$5"

  local profiles
  profiles="$(arr_api GET "$base" "$key" /qualityprofile)"
  echo "$profiles" | jq -e --arg n "$new_profile" '.[] | select(.name==$n)' >/dev/null \
    || error "${app}: Neues Profil \"${new_profile}\" fehlt — Cleanup abgebrochen."

  # Alte Profile entfernen (nur wenn kein Medium sie nutzt)
  local pid in_use
  for p in "${LEGACY_PROFILES[@]}"; do
    pid="$(echo "$profiles" | jq -r --arg n "$p" '[.[] | select(.name==$n)] | first | .id // empty')"
    [[ -n "$pid" ]] || continue
    in_use="$(arr_api GET "$base" "$key" "$movie_endpoint" | jq --argjson id "$pid" \
      '[.[] | select(.qualityProfileId==$id)] | length')"
    if [[ "$in_use" == "0" ]]; then
      arr_api DELETE "$base" "$key" "/qualityprofile/${pid}" >/dev/null
      success "${app}: Altes Profil \"${p}\" entfernt."
    else
      warn "${app}: Profil \"${p}\" wird von ${in_use} Einträgen genutzt — nicht entfernt."
    fi
  done

  # Alte Custom Formats entfernen
  local cfs cfid
  cfs="$(arr_api GET "$base" "$key" /customformat)"
  for cf in "${LEGACY_CFS[@]}"; do
    cfid="$(echo "$cfs" | jq -r --arg n "$cf" '[.[] | select(.name==$n)] | first | .id // empty')"
    [[ -n "$cfid" ]] || continue
    arr_api DELETE "$base" "$key" "/customformat/${cfid}" >/dev/null
    success "${app}: Altes Custom Format \"${cf}\" entfernt."
  done
}

cleanup_arr "http://localhost:${RADARR_PORT:-7878}/api/v3" "$RADARR_API_KEY" "$RADARR_PROFILE" "Radarr" /movie
cleanup_arr "http://localhost:${SONARR_PORT:-8989}/api/v3" "$SONARR_API_KEY" "$SONARR_PROFILE" "Sonarr" /series

success "Quality Profiles & Custom Formats stehen (TRaSH German DL 4K)."
