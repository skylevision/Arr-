#!/usr/bin/env bash
# ============================================================
# 13-hentai-prefs.sh — Sonarr: Uncensored + Season Packs bevorzugen
#
# Legt zwei Custom Formats an und gibt ihnen positive Scores im
# Profil "Any" (das die Hentai/Anime-Serien nutzen), damit Sonarr
# uncensored Releases und Batch/Season-Packs bevorzugt grabbt.
# Idempotent: CFs werden per Name abgeglichen, Scores gesetzt.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var SONARR_API_KEY
S="http://localhost:${SONARR_PORT:-8989}/api/v3"
sapi() { arr_api "$1" "$S" "$SONARR_API_KEY" "$2" "${3:-}"; }

PROFILE_NAME="${HENTAI_PROFILE:-Any}"
UNCENSORED_SCORE=50
PACK_SCORE=25

# CF anlegen (ReleaseTitle-Regex), falls noch nicht vorhanden
ensure_cf() { # <name> <regex>
  local name="$1" regex="$2"
  if sapi GET /customformat | jq -e --arg n "$name" '.[]|select(.name==$n)' >/dev/null; then
    success "Custom Format '${name}' vorhanden."
    return
  fi
  local body
  body="$(jq -n --arg n "$name" --arg r "$regex" '{
    name: $n, includeCustomFormatWhenRenaming: false,
    specifications: [{
      name: $n, implementation: "ReleaseTitleSpecification",
      negate: false, required: false,
      fields: [{ name: "value", value: $r }]
    }]}')"
  sapi POST /customformat "$body" >/dev/null && success "Custom Format '${name}' angelegt."
}

ensure_cf "Uncensored"  '(?i)\buncensored\b'
ensure_cf "Season Pack" '(?i)(\bbatch\b|\bcomplete\b|\bseason\b|\b[0-9]{1,3}[[:space:]]*-[[:space:]]*[0-9]{1,3}\b)'

# Scores im Ziel-Profil setzen
PID="$(sapi GET /qualityprofile | jq -r --arg n "$PROFILE_NAME" '[.[]|select(.name==$n)][0].id // empty')"
[[ -n "$PID" ]] || error "Profil '${PROFILE_NAME}' nicht gefunden."

PROF="$(sapi GET "/qualityprofile/${PID}")"
UPD="$(echo "$PROF" | jq --argjson u "$UNCENSORED_SCORE" --argjson p "$PACK_SCORE" '
  .formatItems = (.formatItems | map(
    if .name=="Uncensored"  then .score=$u
    elif .name=="Season Pack" then .score=$p
    else . end))')"
sapi PUT "/qualityprofile/${PID}" "$UPD" >/dev/null
success "Profil '${PROFILE_NAME}': Uncensored +${UNCENSORED_SCORE}, Season Pack +${PACK_SCORE} gesetzt."
