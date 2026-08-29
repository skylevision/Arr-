#!/usr/bin/env bash
# ============================================================
# vaultwarden-admin-token.sh — Admin-Token für Vaultwarden setzen
#
#   bash scripts/vaultwarden-admin-token.sh
#
# Fragt das Admin-Passwort ab (Eingabe bleibt unsichtbar), erzeugt daraus
# einen Argon2id-PHC-String und legt ihn in ${APPDATA}/vaultwarden/admin_token
# ab (chmod 600, root). Der Container liest ihn über ADMIN_TOKEN_FILE.
#
# Warum nicht in die .env: der Hash steckt voller `$`. bootstrap/lib.sh liest
# die .env per `source`, dort würde `$argon2id` zu Leerstring expandieren und
# `$$` zur Prozess-ID. Eine eigene Datei umgeht das Escaping komplett.
#
# Warum nicht `vaultwarden hash`: das Binary verlangt ein echtes TTY und
# bricht in nicht-interaktiven Umgebungen mit einem Panic ab. Der argon2-CLI
# erzeugt denselben PHC-String und lässt sich per stdin füttern.
#
# Idempotent: bei jedem Lauf wird neu gehasht (neues Salt) — derselbe
# Klartext ergibt also einen anderen Hash, was völlig in Ordnung ist.
# ============================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../bootstrap/lib.sh"

TOKEN_FILE="${APPDATA}/vaultwarden/admin_token"

[[ -d "${APPDATA}/vaultwarden" ]] || {
  echo "Verzeichnis ${APPDATA}/vaultwarden fehlt — erst den Container einmal starten." >&2
  exit 1
}

read -rsp "Neues Vaultwarden-Admin-Passwort: " PW1; echo
read -rsp "Zur Bestätigung wiederholen:      " PW2; echo
[[ -n "$PW1" ]]       || { echo "Leeres Passwort — abgebrochen." >&2; exit 1; }
[[ "$PW1" == "$PW2" ]] || { echo "Die Eingaben stimmen nicht überein — abgebrochen." >&2; exit 1; }

# Passwort geht über stdin in den Container, damit es nicht in der
# Prozessliste (ps) oder der Shell-History landet.
HASH="$(printf '%s' "$PW1" | docker run --rm -i alpine sh -c '
  apk add --no-cache argon2 >/dev/null 2>&1 || exit 9
  IFS= read -r PW
  SALT=$(head -c 24 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c 22)
  printf %s "$PW" | argon2 "$SALT" -id -t 3 -m 16 -p 4 -e
' | tr -d '\r\n')"

[[ "$HASH" == \$argon2id\$* ]] || { echo "Hash-Erzeugung fehlgeschlagen: ${HASH:-<leer>}" >&2; exit 1; }

umask 077
printf '%s' "$HASH" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"

echo "Token geschrieben: ${TOKEN_FILE}"
echo "Jetzt neu starten:  docker compose up -d vaultwarden"
