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

# ---------------------------------------------------------------------------
# Standard-Sprachprofil sicherstellen + bestehenden Titeln zuweisen
#
# Ohne zugewiesenes Sprachprofil sucht Bazarr für NICHTS Untertitel — die
# häufigste Ursache für „Bazarr lädt keine Untertitel". Das Anlegen des
# Profils selbst (Sprachen, Cutoff) bleibt ein UI-Schritt (Provider-Login
# nötig); ist eines vorhanden, wird es hier als Standard gesetzt und allen
# Serien/Filmen ohne Profil zugewiesen. Idempotent.
# ---------------------------------------------------------------------------
bapi() { curl -fsS -m 30 -H "X-API-KEY: ${BAZARR_API_KEY}" "$@"; }
bpost() { curl -fsS -m 30 -o /dev/null -w '%{http_code}' -X POST \
  -H "X-API-KEY: ${BAZARR_API_KEY}" -H "Content-Type: application/x-www-form-urlencoded" "$@"; }

PID="$(bapi "${B}/system/languages/profiles" | jq -r '[.[].profileId] | first // empty')"
if [[ -z "$PID" ]]; then
  warn "Bazarr: kein Sprachprofil vorhanden — Untertitel sind AUS."
  warn "  Anlegen: Bazarr-UI → Settings → Languages → Profil (z. B. de+en) erstellen, dann erneut ausführen."
else
  SET="$(bapi "${B}/system/settings")"
  s_def="$(echo "$SET" | jq -r '.general.serie_default_profile // ""')"
  m_def="$(echo "$SET" | jq -r '.general.movie_default_profile // ""')"
  if [[ "$s_def" != "$PID" || "$m_def" != "$PID" ]]; then
    bpost "${B}/system/settings" --data "settings-general-serie_default_enabled=true&settings-general-serie_default_profile=${PID}&settings-general-movie_default_enabled=true&settings-general-movie_default_profile=${PID}" >/dev/null
    success "Bazarr: Standard-Sprachprofil (id=${PID}) für Serien + Filme gesetzt."
  else
    success "Bazarr: Standard-Sprachprofil (id=${PID}) bereits gesetzt."
  fi

  # Bestehenden Serien/Filmen ohne Profil das Standardprofil zuweisen
  n=0
  for sid in $(bapi "${B}/series?length=-1" | jq -r '.data[] | select((.profileId // 0) == 0) | .sonarrSeriesId'); do
    bpost "${B}/series" --data "seriesid=${sid}&profileid=${PID}" >/dev/null && n=$((n+1))
  done
  for rid in $(bapi "${B}/movies?length=-1" | jq -r '.data[] | select((.profileId // 0) == 0) | .radarrId'); do
    bpost "${B}/movies" --data "radarrid=${rid}&profileid=${PID}" >/dev/null && n=$((n+1))
  done
  success "Bazarr: Sprachprofil ${n} Titel(n) ohne Profil zugewiesen (bereits zugewiesene unberührt)."
fi

[[ "$FAIL" == "0" ]] || warn "Bazarr-Verifikation mit Abweichungen abgeschlossen (siehe oben)."
