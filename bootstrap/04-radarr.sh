#!/usr/bin/env bash
# ============================================================
# 04-radarr.sh — Radarr: Root Folder, Download Client, Naming,
#                Media Management, Remote Path Mappings entfernen
# Idempotent: alles wird per Name/Pfad identifiziert und
# aktualisiert statt neu angelegt.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var RADARR_API_KEY
require_var SABNZBD_API_KEY

R="http://localhost:${RADARR_PORT:-7878}/api/v3"
rapi() { arr_api "$1" "$R" "$RADARR_API_KEY" "$2" "${3:-}"; }

# ---------------------------------------------------------------------------
# Root Folder
# ---------------------------------------------------------------------------
ROOT="/data/media/movies"
if ! rapi GET /rootfolder | jq -e --arg p "$ROOT" '.[] | select(.path==$p)' >/dev/null; then
  rapi POST /rootfolder "{\"path\":\"${ROOT}\"}" >/dev/null
  success "Root Folder ${ROOT} angelegt."
else
  success "Root Folder ${ROOT} vorhanden."
fi

# ---------------------------------------------------------------------------
# Download Client: SABnzbd
# ---------------------------------------------------------------------------
EXISTING="$(rapi GET /downloadclient | jq '[.[] | select(.implementation=="Sabnzbd")] | first // empty')"

patch_fields='.enable = true
  | .name = "SABnzbd"
  | .fields = (.fields | map(
      if .name=="host" then .value="sabnzbd"
      elif .name=="port" then .value=8080
      elif .name=="useSsl" then .value=false
      elif .name=="apiKey" then .value=$key
      elif .name=="movieCategory" then .value="movies"
      else . end))'

if [[ -n "$EXISTING" ]]; then
  ID="$(echo "$EXISTING" | jq -r .id)"
  rapi PUT "/downloadclient/${ID}" "$(echo "$EXISTING" | jq --arg key "$SABNZBD_API_KEY" "$patch_fields")" >/dev/null
  success "Download Client SABnzbd aktualisiert."
else
  SCHEMA="$(rapi GET /downloadclient/schema | jq '[.[] | select(.implementation=="Sabnzbd")] | first')"
  [[ -n "$SCHEMA" && "$SCHEMA" != "null" ]] || error "Sabnzbd-Schema nicht gefunden."
  rapi POST /downloadclient "$(echo "$SCHEMA" | jq --arg key "$SABNZBD_API_KEY" "$patch_fields")" >/dev/null
  success "Download Client SABnzbd angelegt."
fi

# ---------------------------------------------------------------------------
# Remote Path Mappings entfernen — SABnzbd nutzt jetzt dasselbe /data
# ---------------------------------------------------------------------------
for id in $(rapi GET /remotepathmapping | jq -r '.[].id'); do
  rapi DELETE "/remotepathmapping/${id}" >/dev/null
  success "Remote Path Mapping ${id} entfernt (Pfade sind vereinheitlicht)."
done

# ---------------------------------------------------------------------------
# Naming (deklarativ = aktueller, bewährter Stand)
# ---------------------------------------------------------------------------
NAMING="$(rapi GET /config/naming | jq '
  .renameMovies = true
  | .replaceIllegalCharacters = true
  | .standardMovieFormat = "{Movie Title} ({Release Year}) {Quality Full}"
  | .movieFolderFormat = "{Movie Title} ({Release Year})"')"
rapi PUT "/config/naming/$(echo "$NAMING" | jq -r .id)" "$NAMING" >/dev/null
success "Naming Scheme gesetzt."

# ---------------------------------------------------------------------------
# Media Management: Hardlinks an, Propers/Repacks per CF-Score (TRaSH)
# ---------------------------------------------------------------------------
MM="$(rapi GET /config/mediamanagement | jq '
  .copyUsingHardlinks = true
  | .downloadPropersAndRepacks = "doNotPrefer"')"
rapi PUT "/config/mediamanagement/$(echo "$MM" | jq -r .id)" "$MM" >/dev/null
success "Media Management gesetzt (Hardlinks an, Propers: doNotPrefer)."
