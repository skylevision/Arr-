#!/usr/bin/env bash
# ============================================================
# lib.sh — gemeinsame Helfer für alle bootstrap/NN-*.sh
# Wird per source eingebunden, nicht direkt ausgeführt.
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# Repo-Root = Elternverzeichnis von bootstrap/
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "${LIB_DIR}")"

# .env und .env.runtime laden (nur KEY=VALUE-Zeilen)
load_env_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  set -a
  # shellcheck disable=SC1090
  source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$f")
  set +a
}
load_env_file "${REPO_DIR}/.env"
load_env_file "${REPO_DIR}/.env.runtime"

APPDATA="${APPDATA:-/mnt/user/appdata}"
DATA="${DATA:-/mnt/user/data}"
PUID="${PUID:-99}"
PGID="${PGID:-100}"

# ---------------------------------------------------------------------------
# API-Helfer für Radarr/Sonarr/Prowlarr (X-Api-Key-Auth)
#   arr_api GET  <base> <key> <pfad>
#   arr_api POST <base> <key> <pfad> <json>
# ---------------------------------------------------------------------------
arr_api() {
  local method="$1" base="$2" key="$3" path="$4" body="${5:-}"
  if [[ -n "$body" ]]; then
    curl -fsS -m 30 -X "$method" -H "X-Api-Key: $key" -H "Content-Type: application/json" \
      -d "$body" "${base}${path}"
  else
    curl -fsS -m 30 -X "$method" -H "X-Api-Key: $key" "${base}${path}"
  fi
}

require_var() {
  local var="$1"
  [[ -n "${!var:-}" ]] || error "Variable ${var} ist nicht gesetzt (fehlt .env / .env.runtime? Erst 01-extract-keys.sh laufen lassen.)"
}
