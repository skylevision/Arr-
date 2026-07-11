#!/usr/bin/env bash
# ============================================================
# backup-appdata.sh — konsistentes Backup aller appdata-Configs
#
# Ablauf: Container stoppen → tar.gz mit Zeitstempel → Container starten.
# Idempotent und jederzeit wiederholbar. Als Unraid User Script planbar
# (Settings → User Scripts → neues Skript → dieses Skript aufrufen).
#
# Ziel:   ${BACKUP_ROOT:-/mnt/user/backups/arr-stack}/<timestamp>/
# Restore: siehe RESTORE.md, das neben jedem Backup abgelegt wird.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "${SCRIPT_DIR}")"

# .env sicher laden (nur KEY=VALUE-Zeilen)
if [[ -f "${REPO_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${REPO_DIR}/.env")
  set +a
fi

APPDATA="${APPDATA:-/mnt/user/appdata}"
BACKUP_ROOT="${BACKUP_ROOT:-/mnt/user/backups/arr-stack}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${BACKUP_ROOT}/${STAMP}"

SERVICES=(
  tailscale sabnzbd prowlarr radarr sonarr bazarr seerr
  vaultwarden threadfin adguardhome jellyfin homepage
  lidarr readarr
)

# Nur existierende Verzeichnisse sichern
EXISTING=()
for s in "${SERVICES[@]}"; do
  [[ -d "${APPDATA}/${s}" ]] && EXISTING+=("${s}")
done
[[ ${#EXISTING[@]} -gt 0 ]] || { echo "Nichts zu sichern unter ${APPDATA}" >&2; exit 1; }

mkdir -p "${DEST}"

GIT_REV="$(git -C "${REPO_DIR}" -c safe.directory='*' rev-parse HEAD 2>/dev/null || echo 'unbekannt')"

echo "[1/4] Stoppe Container für konsistentes Backup ..."
( cd "${REPO_DIR}" && COMPOSE_PROFILES='*' docker compose stop )

# Container in JEDEM Fall wieder starten — auch wenn tar fehlschlägt
restart_stack() {
  echo "[4/4] Starte Container wieder ..."
  ( cd "${REPO_DIR}" && docker compose up -d )
}
trap restart_stack EXIT

echo "[2/4] Erstelle ${DEST}/appdata-${STAMP}.tar.gz ..."
tar -C "${APPDATA}" -czf "${DEST}/appdata-${STAMP}.tar.gz" "${EXISTING[@]}"
sha256sum "${DEST}/appdata-${STAMP}.tar.gz" > "${DEST}/appdata-${STAMP}.tar.gz.sha256"

echo "[3/4] Sichere .env und schreibe Restore-Anleitung ..."
[[ -f "${REPO_DIR}/.env" ]] && cp "${REPO_DIR}/.env" "${DEST}/env.backup"

cat > "${DEST}/RESTORE.md" <<EOF
# Restore-Anleitung (Backup ${STAMP})

Gesichert: ${EXISTING[*]}
Repo-Commit zum Backup-Zeitpunkt: ${GIT_REV}

## Wiederherstellen

    cd ${REPO_DIR}
    COMPOSE_PROFILES='*' docker compose stop
    tar -C ${APPDATA} -xzf ${DEST}/appdata-${STAMP}.tar.gz
    cp ${DEST}/env.backup ${REPO_DIR}/.env
    # Optional: Repo auf den damaligen Stand bringen:
    #   git -C ${REPO_DIR} checkout ${GIT_REV}
    docker compose up -d

Integritätscheck vor dem Entpacken:

    sha256sum -c ${DEST}/appdata-${STAMP}.tar.gz.sha256
EOF

echo ""
echo "Backup fertig: ${DEST}"
du -sh "${DEST}"
