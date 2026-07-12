#!/usr/bin/env bash
# ============================================================
# 02-sabnzbd.sh — SABnzbd: Ordner, Kategorien, Usenet-Server
#
# Idempotent: set_config überschreibt bestehende Werte, Kategorien
# und Server werden per keyword adressiert (kein Duplikat möglich).
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var SABNZBD_API_KEY
require_var EWEKA_HOST
require_var EWEKA_USERNAME
require_var EWEKA_PASSWORD

SAB="http://localhost:${SABNZBD_PORT:-8090}/api"

sab() {
  # sab <mode> [weitere --data-urlencode Argumente ...]
  local mode="$1"; shift
  curl -fsS -m 30 -G "$SAB" \
    --data-urlencode "apikey=${SABNZBD_API_KEY}" \
    --data-urlencode "output=json" \
    --data-urlencode "mode=${mode}" "$@"
}

info "Setze Download-Ordner (TRaSH-Layout unter /data) ..."
sab set_config --data-urlencode "section=misc" \
  --data-urlencode "keyword=download_dir" \
  --data-urlencode "value=/data/downloads/usenet/incomplete" >/dev/null
sab set_config --data-urlencode "section=misc" \
  --data-urlencode "keyword=complete_dir" \
  --data-urlencode "value=/data/downloads/usenet/complete" >/dev/null

info "Setze host_whitelist (Docker-Hostname) ..."
sab set_config --data-urlencode "section=misc" \
  --data-urlencode "keyword=host_whitelist" \
  --data-urlencode "value=sabnzbd" >/dev/null

info "Lege Kategorien movies/tv an ..."
for cat in movies tv; do
  sab set_config --data-urlencode "section=categories" \
    --data-urlencode "keyword=${cat}" \
    --data-urlencode "name=${cat}" \
    --data-urlencode "dir=${cat}" >/dev/null
done

info "Konfiguriere Usenet-Server ${EWEKA_HOST} ..."
sab set_config --data-urlencode "section=servers" \
  --data-urlencode "keyword=${EWEKA_HOST}" \
  --data-urlencode "name=${EWEKA_HOST}" \
  --data-urlencode "host=${EWEKA_HOST}" \
  --data-urlencode "port=${EWEKA_PORT:-563}" \
  --data-urlencode "ssl=${EWEKA_SSL:-1}" \
  --data-urlencode "username=${EWEKA_USERNAME}" \
  --data-urlencode "password=${EWEKA_PASSWORD}" \
  --data-urlencode "connections=${EWEKA_CONNECTIONS:-45}" \
  --data-urlencode "enable=1" \
  --data-urlencode "priority=0" >/dev/null

# ---------------------------------------------------------------------------
# Verifikation
# ---------------------------------------------------------------------------
CFG="$(sab get_config)"
for check in \
  '.config.misc.download_dir == "/data/downloads/usenet/incomplete"' \
  '.config.misc.complete_dir == "/data/downloads/usenet/complete"' \
  '.config.categories | map(.name) | contains(["movies","tv"])' \
  '.config.servers  | map(.host) | contains(["'"${EWEKA_HOST}"'"])'
do
  echo "$CFG" | jq -e "$check" >/dev/null || error "Verifikation fehlgeschlagen: $check"
done

success "SABnzbd konfiguriert (Ordner, Kategorien, Server ${EWEKA_HOST})."
