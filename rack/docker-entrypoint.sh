#!/bin/sh
# Startet die Anwendung unter der Kennung der uebrigen Unraid-Container.
#
# Ablauf: Umask setzen, Verzeichnisse anlegen, das mitgelieferte rembg-Modell
# in das Volume spiegeln (falls dort noch keins liegt), Rechte richten,
# dann als PUID:PGID weiterlaufen.
set -eu

umask "${UMASK:-022}"

PUID="${PUID:-99}"
PGID="${PGID:-100}"

DATA_DIR="${RACK_DATA_DIR:-/data}"
MODEL_DIR="${U2NET_HOME:-/models}"
# numba, das pymatting unter rembg antreibt, legt seinen JIT-Cache sonst
# neben die Bibliotheksdateien. Als Nutzer 99 ist das nicht beschreibbar,
# und die Freistellung faellt still auf das Originalfoto zurueck.
NUMBA_DIR="${NUMBA_CACHE_DIR:-$DATA_DIR/cache/numba}"

mkdir -p "$DATA_DIR/db" "$DATA_DIR/images" "$MODEL_DIR" "$NUMBA_DIR"

# Das Modell liegt im Image. Ins Volume kopieren wir es nur, wenn dort noch
# nichts ist, damit ein bewusst ausgetauschtes Modell bestehen bleibt.
if [ -d /opt/rack/models ] && [ -z "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
  cp -a /opt/rack/models/. "$MODEL_DIR/" 2>/dev/null || true
fi

# Dasselbe fuer den vorkompilierten numba-Cache, sonst zahlt das erste
# Foto nach jedem Update rund 18 Sekunden Uebersetzungszeit.
if [ -d /opt/rack/numba ] && [ -z "$(ls -A "$NUMBA_DIR" 2>/dev/null)" ]; then
  cp -a /opt/rack/numba/. "$NUMBA_DIR/" 2>/dev/null || true
fi

if [ "$(id -u)" = "0" ]; then
  if ! getent group "$PGID" >/dev/null 2>&1; then
    groupadd -g "$PGID" rack 2>/dev/null || addgroup -g "$PGID" rack 2>/dev/null || true
  fi
  if ! getent passwd "$PUID" >/dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -M -s /usr/sbin/nologin rack 2>/dev/null \
      || adduser -u "$PUID" -G rack -H -D rack 2>/dev/null || true
  fi

  # Nur die eigenen Verzeichnisse anfassen, nichts sonst.
  chown -R "$PUID:$PGID" "$DATA_DIR" "$MODEL_DIR" "$NUMBA_DIR" 2>/dev/null || true

  echo "rack: starte als ${PUID}:${PGID}, umask ${UMASK:-022}, TZ ${TZ:-unset}"
  exec setpriv --reuid "$PUID" --regid "$PGID" --clear-groups "$@"
fi

exec "$@"
