#!/bin/bash
# Sichert Datenbank und Bilder als ein Tar-Archiv.
#
# Auf diesem Server laeuft kein Appdata-Backup-Plugin, deshalb dieses
# Skript. Die Datenbank wird ueber die SQLite-Sicherungs-API kopiert, damit
# der Stand auch bei laufendem Container in sich stimmig ist. Ein
# schlichtes cp der WAL-Datei waere das nicht.
#
#   bash /mnt/user/rack/scripts/backup.sh [Zielverzeichnis]
#
# Wiederherstellen:
#   docker compose stop rack
#   tar xzf rack-JJJJ-MM-TT.tar.gz -C /mnt/user/appdata/rack
#   docker compose start rack

set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
APPDATA="${APPDATA:-/mnt/user/appdata}"
ZIEL="${1:-$APPDATA/rack/backups}"
STAMP="$(date +%Y-%m-%d-%H%M)"
ARCHIV="$ZIEL/rack-$STAMP.tar.gz"

mkdir -p "$ZIEL"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if docker ps --format '{{.Names}}' | grep -qx rack; then
  echo "Container läuft, sichere die Datenbank über die SQLite-Backup-API."
  docker exec rack python -c "
import sqlite3
quelle = sqlite3.connect('/data/db/rack.sqlite3')
ziel = sqlite3.connect('/data/db/backup-tmp.sqlite3')
with ziel:
    quelle.backup(ziel)
ziel.close(); quelle.close()
"
  mv "$APPDATA/rack/db/backup-tmp.sqlite3" "$TMP/rack.sqlite3"
else
  echo "Container steht, kopiere die Datenbank direkt."
  cp "$APPDATA/rack/db/rack.sqlite3" "$TMP/rack.sqlite3" 2>/dev/null || true
fi

mkdir -p "$TMP/db"
mv "$TMP/rack.sqlite3" "$TMP/db/rack.sqlite3" 2>/dev/null || true

tar czf "$ARCHIV" \
  -C "$TMP" db \
  -C "$APPDATA/rack" images

echo "Gesichert: $ARCHIV  ($(du -h "$ARCHIV" | cut -f1))"

# Nur die letzten vierzehn Sicherungen behalten.
ls -1t "$ZIEL"/rack-*.tar.gz 2>/dev/null | tail -n +15 | while read -r alt; do
  echo "Entferne alte Sicherung: $(basename "$alt")"
  rm -f "$alt"
done
