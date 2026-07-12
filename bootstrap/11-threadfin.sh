#!/usr/bin/env bash
# ============================================================
# 11-threadfin.sh — Threadfin: an alle Interfaces binden (0.0.0.0)
#
# Threadfin läuft im Netz-Stack von gluetun (VPN-Split-Tunnel). Da es
# nach dem VPN hochkommt, bindet es sonst an die IP der Default-Route
# (= VPN-Tunnel, z. B. 10.8.0.x) und ist dann WEDER über den
# veröffentlichten Host-Port NOCH aus dem arr_net (Jellyfin) erreichbar.
# Der image-seitige -bind=0.0.0.0 setzt sich nicht gegen ein leeres
# "bindIpAddress" in der settings.json durch → hier explizit setzen.
#
# Läuft nur, wenn Threadfin bereits konfiguriert ist (iptv-Profil aktiv).
# Sonst wird sauber übersprungen — ein normaler bootstrap.sh-Lauf ohne
# iptv-Profil darf daran nicht scheitern.
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SETTINGS="${APPDATA}/threadfin/conf/settings.json"

if [[ ! -f "$SETTINGS" ]]; then
  warn "Threadfin nicht eingerichtet (iptv-Profil noch nicht gestartet?) — 11-threadfin.sh übersprungen."
  exit 0
fi

current="$(grep -o '"bindIpAddress": *"[^"]*"' "$SETTINGS" | head -1 | sed 's/.*: *"\(.*\)"/\1/')"

if [[ "$current" == "0.0.0.0" ]]; then
  success "Threadfin bindIpAddress bereits 0.0.0.0."
  exit 0
fi

sed -i 's/"bindIpAddress": *"[^"]*"/"bindIpAddress": "0.0.0.0"/' "$SETTINGS"
chown "${PUID}:${PGID}" "$SETTINGS"
success "Threadfin bindIpAddress → 0.0.0.0 gesetzt (war: \"${current}\")."

# Nur neu starten, wenn Threadfin gerade läuft (sonst greift die Änderung
# beim nächsten Start ohnehin).
if [[ "$(docker inspect -f '{{.State.Running}}' threadfin 2>/dev/null)" == "true" ]]; then
  docker restart threadfin >/dev/null
  success "Threadfin neu gestartet — lauscht jetzt auf allen Interfaces."
fi
