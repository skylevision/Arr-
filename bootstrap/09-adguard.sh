#!/usr/bin/env bash
# ============================================================
# 09-adguard.sh — AdGuard Home: lokaler DNS für das Heimnetz
#
# - schließt den Ersteinrichtungs-Wizard per API ab (Web auf
#   Container-Port 80, DNS auf 53, Login aus .env)
# - Upstreams: DoH (Cloudflare/Google) + Weiterleitung der
#   lokalen Domain (fritz.box) und PTR-Anfragen an den Router,
#   damit Router- und Geräte-Namen weiter funktionieren
# - DNS-Rewrites: <dienst>.<LOCAL_DOMAIN> → UNRAID_IP, damit
#   z. B. jellyfin.fritz.box:8096 im Browser funktioniert
#
# Idempotent: Wizard nur wenn unkonfiguriert, Rewrites werden
# per Liste abgeglichen (update statt Duplikat).
#
# Danach EINMALIG im Router eintragen (Fritz!Box):
#   Heimnetz → Netzwerk → Netzwerkeinstellungen →
#   IPv4-Einstellungen → Lokaler DNS-Server = ${UNRAID_IP}
# ============================================================
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var UNRAID_IP
require_var ADGUARD_USER
require_var ADGUARD_PASSWORD

AG="http://localhost:${ADGUARD_WEBUI_PORT:-8081}"
AG_SETUP="http://localhost:${ADGUARD_SETUP_PORT:-3001}"
DOMAIN="${LOCAL_DOMAIN:-fritz.box}"
ROUTER="${ROUTER_IP:-192.168.178.1}"

# Dienste, die einen Namen bekommen (Rewrite → UNRAID_IP)
REWRITE_NAMES=(jellyfin seerr radarr sonarr prowlarr bazarr sabnzbd homepage adguard unraid)

agapi() {
  local method="$1" path="$2" body="${3:-}"
  if [[ -n "$body" ]]; then
    curl -fsS -m 30 -u "${ADGUARD_USER}:${ADGUARD_PASSWORD}" -X "$method" \
      -H "Content-Type: application/json" -d "$body" "${AG}${path}"
  else
    curl -fsS -m 30 -u "${ADGUARD_USER}:${ADGUARD_PASSWORD}" -X "$method" "${AG}${path}"
  fi
}

[[ "$(docker inspect -f '{{.State.Running}}' adguardhome 2>/dev/null)" == "true" ]] \
  || error "Container adguardhome läuft nicht — erst 'docker compose up -d' ausführen."

# ---------------------------------------------------------------------------
# Ersteinrichtung (nur wenn noch unkonfiguriert: Wizard lauscht auf :3000)
# ---------------------------------------------------------------------------
if agapi GET /control/status >/dev/null 2>&1; then
  success "AdGuard ist bereits eingerichtet."
elif curl -fsS -m 5 "${AG_SETUP}/control/install/get_addresses" >/dev/null 2>&1; then
  info "Schließe AdGuard-Ersteinrichtung ab (Web:80, DNS:53) ..."
  curl -fsS -m 30 -X POST -H "Content-Type: application/json" -d "$(jq -n \
    --arg user "$ADGUARD_USER" --arg pass "$ADGUARD_PASSWORD" '{
      web: {ip: "0.0.0.0", port: 80},
      dns: {ip: "0.0.0.0", port: 53},
      username: $user, password: $pass
    }')" "${AG_SETUP}/control/install/configure" >/dev/null \
    || error "install/configure fehlgeschlagen."
  # Web-UI zieht von :3000 auf :80 um — kurz warten
  for _ in $(seq 1 20); do
    agapi GET /control/status >/dev/null 2>&1 && break
    sleep 2
  done
  agapi GET /control/status >/dev/null 2>&1 || error "AdGuard nach Einrichtung nicht erreichbar."
  success "Ersteinrichtung abgeschlossen (Login: ${ADGUARD_USER})."
else
  error "AdGuard weder auf ${AG} (eingerichtet) noch ${AG_SETUP} (Wizard) erreichbar — Login falsch?"
fi

# ---------------------------------------------------------------------------
# Upstreams: DoH + lokale Domain & Reverse-DNS an den Router weiterleiten
# ---------------------------------------------------------------------------
info "Setze DNS-Upstreams (DoH + ${DOMAIN} → ${ROUTER}) ..."
agapi POST /control/dns_config "$(jq -n --arg d "$DOMAIN" --arg r "$ROUTER" '{
  upstream_dns: [
    "https://dns.cloudflare.com/dns-query",
    "https://dns.google/dns-query",
    ("[/" + $d + "/]" + $r)
  ],
  bootstrap_dns: ["1.1.1.1", "8.8.8.8"],
  local_ptr_upstreams: [$r],
  use_private_ptr_resolvers: true
}')" >/dev/null
success "Upstreams gesetzt."

# ---------------------------------------------------------------------------
# Rewrites: <dienst>.<domain> → UNRAID_IP (abgleichen, nicht duplizieren)
# ---------------------------------------------------------------------------
info "Stelle DNS-Rewrites sicher (*.${DOMAIN} → ${UNRAID_IP}) ..."
EXISTING="$(agapi GET /control/rewrite/list)"

for name in "${REWRITE_NAMES[@]}"; do
  fqdn="${name}.${DOMAIN}"
  current="$(echo "$EXISTING" | jq -r --arg d "$fqdn" '[.[] | select(.domain==$d)] | first | .answer // empty')"
  if [[ "$current" == "$UNRAID_IP" ]]; then
    success "Rewrite ${fqdn} → ${UNRAID_IP} vorhanden."
  else
    if [[ -n "$current" ]]; then
      agapi POST /control/rewrite/delete \
        "$(jq -n --arg d "$fqdn" --arg a "$current" '{domain:$d, answer:$a}')" >/dev/null
    fi
    agapi POST /control/rewrite/add \
      "$(jq -n --arg d "$fqdn" --arg a "$UNRAID_IP" '{domain:$d, answer:$a}')" >/dev/null
    success "Rewrite ${fqdn} → ${UNRAID_IP} angelegt."
  fi
done

success "AdGuard konfiguriert. Router-Schritt nicht vergessen: lokaler DNS-Server = ${UNRAID_IP}."
