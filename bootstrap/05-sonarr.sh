#!/usr/bin/env bash
# ============================================================
# 05-sonarr.sh — Sonarr: Root Folder, Download Client, Naming,
#                Media Management, Remote Path Mappings entfernen
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var SONARR_API_KEY
require_var SABNZBD_API_KEY

S="http://localhost:${SONARR_PORT:-8989}/api/v3"
sapi() { arr_api "$1" "$S" "$SONARR_API_KEY" "$2" "${3:-}"; }

# ---------------------------------------------------------------------------
# Root Folder
# ---------------------------------------------------------------------------
for ROOT in /data/media/tv /data/media/anime; do
  if ! sapi GET /rootfolder | jq -e --arg p "$ROOT" '.[] | select(.path==$p)' >/dev/null; then
    sapi POST /rootfolder "{\"path\":\"${ROOT}\"}" >/dev/null
    success "Root Folder ${ROOT} angelegt."
  else
    success "Root Folder ${ROOT} vorhanden."
  fi
done

# ---------------------------------------------------------------------------
# Download Client: SABnzbd
# ---------------------------------------------------------------------------
EXISTING="$(sapi GET /downloadclient | jq '[.[] | select(.implementation=="Sabnzbd")] | first // empty')"

patch_fields='.enable = true
  | .name = "SABnzbd"
  | .fields = (.fields | map(
      if .name=="host" then .value="sabnzbd"
      elif .name=="port" then .value=8080
      elif .name=="useSsl" then .value=false
      elif .name=="apiKey" then .value=$key
      elif .name=="tvCategory" then .value="tv"
      else . end))'

if [[ -n "$EXISTING" ]]; then
  ID="$(echo "$EXISTING" | jq -r .id)"
  sapi PUT "/downloadclient/${ID}" "$(echo "$EXISTING" | jq --arg key "$SABNZBD_API_KEY" "$patch_fields")" >/dev/null
  success "Download Client SABnzbd aktualisiert."
else
  SCHEMA="$(sapi GET /downloadclient/schema | jq '[.[] | select(.implementation=="Sabnzbd")] | first')"
  [[ -n "$SCHEMA" && "$SCHEMA" != "null" ]] || error "Sabnzbd-Schema nicht gefunden."
  sapi POST /downloadclient "$(echo "$SCHEMA" | jq --arg key "$SABNZBD_API_KEY" "$patch_fields")" >/dev/null
  success "Download Client SABnzbd angelegt."
fi

# ---------------------------------------------------------------------------
# Remote Path Mappings entfernen — SABnzbd nutzt jetzt dasselbe /data
# ---------------------------------------------------------------------------
for id in $(sapi GET /remotepathmapping | jq -r '.[].id'); do
  sapi DELETE "/remotepathmapping/${id}" >/dev/null
  success "Remote Path Mapping ${id} entfernt (Pfade sind vereinheitlicht)."
done

# ---------------------------------------------------------------------------
# Naming (deklarativ = aktueller, bewährter Stand)
# ---------------------------------------------------------------------------
NAMING="$(sapi GET /config/naming | jq '
  .renameEpisodes = true
  | .standardEpisodeFormat = "{Series Title} - S{season:00}E{episode:00} - {Episode Title} {Quality Full}"
  | .dailyEpisodeFormat = "{Series Title} - {Air-Date} - {Episode Title} {Quality Full}"
  | .animeEpisodeFormat = "{Series Title} - S{season:00}E{episode:00} - {Episode Title} {Quality Full}"
  | .seriesFolderFormat = "{Series Title}"
  | .seasonFolderFormat = "Season {season}"')"
sapi PUT "/config/naming/$(echo "$NAMING" | jq -r .id)" "$NAMING" >/dev/null
success "Naming Scheme gesetzt."

# ---------------------------------------------------------------------------
# Media Management: Hardlinks an, Propers/Repacks per CF-Score (TRaSH)
# ---------------------------------------------------------------------------
MM="$(sapi GET /config/mediamanagement | jq '
  .copyUsingHardlinks = true
  | .downloadPropersAndRepacks = "doNotPrefer"')"
sapi PUT "/config/mediamanagement/$(echo "$MM" | jq -r .id)" "$MM" >/dev/null
success "Media Management gesetzt (Hardlinks an, Propers: doNotPrefer)."
