#!/usr/bin/env bash
# ============================================================
# 07-bazarr.sh — Bazarr: Verbindung zu Radarr/Sonarr verifizieren
#
# Bazarrs Settings-API ist für automatisierte Writes ungeeignet
# (Form-encoded Spezialformat). Deshalb: verifizieren statt
# stillschweigend brechen — bei Abweichung gibt es eine klare
# Handlungsanweisung (dokumentierter Manuell-Restschritt).
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var BAZARR_API_KEY
require_var RADARR_API_KEY
require_var SONARR_API_KEY

B="http://localhost:${BAZARR_PORT:-6767}/api"

info "Prüfe Bazarr-API ..."
curl -fsS -m 15 -H "X-API-KEY: ${BAZARR_API_KEY}" "${B}/system/status" >/dev/null \
  || error "Bazarr-API nicht erreichbar."
success "Bazarr-API erreichbar."

CFG="${APPDATA}/bazarr/config/config.yaml"
FAIL=0

check_key() {
  local section="$1" expected="$2"
  local configured
  configured="$(awk -v s="^${section}:" '$0 ~ s {f=1; next} f && /^[a-z]/ {f=0} f && /apikey:/ {print $2; exit}' "$CFG")"
  if [[ "$configured" == "$expected" ]]; then
    success "Bazarr → ${section}: API-Key korrekt."
  else
    warn "Bazarr → ${section}: API-Key weicht ab!"
    warn "  Manuell fixen: Bazarr-UI → Settings → ${section^} → API-Key aktualisieren, oder"
    warn "  in ${CFG} unter '${section}:' den apikey ersetzen und Bazarr neu starten."
    FAIL=1
  fi
}

check_key radarr "$RADARR_API_KEY"
check_key sonarr "$SONARR_API_KEY"

[[ "$FAIL" == "0" ]] || warn "Bazarr-Verifikation mit Abweichungen abgeschlossen (siehe oben)."
