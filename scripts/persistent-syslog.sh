#!/bin/bash
# persistent-syslog.sh — Unraid-Systemlog dauerhaft auf die Platte spiegeln.
#
# Warum: Unraid hält /var/log/syslog nur im RAM. Nach einem Absturz oder harten
# Neustart ist es weg — genau dann, wenn man es bräuchte (siehe Freeze vom
# 07.08.2026, dessen Ursache nicht mehr rekonstruierbar war).
#
# Was es tut: schreibt alle Syslog-Meldungen zusätzlich nach
# /mnt/cache/appdata/syslog/syslog.log (NVMe, nicht der USB-Stick) und richtet
# eine logrotate-Regel ein, die täglich rotiert, komprimiert und nach 14 Tagen
# löscht — der Platzbedarf ist damit gedeckelt.
#
# Installation (persistent über Reboots): Aufruf aus /boot/config/go, z. B.
#   /boot/config/persistent-syslog.sh &
# Das Skript wartet im Hintergrund darauf, dass das Array/der Cache gemountet
# ist, denn das go-Script läuft davor. /etc und /etc/logrotate.d liegen im RAM
# und werden bei jedem Boot neu befüllt — deshalb schreibt das Skript beide
# Konfigurationsdateien jedes Mal neu.

set -u

LOG_DIR="${SYSLOG_DIR:-/mnt/cache/appdata/syslog}"
LOG_FILE="$LOG_DIR/syslog.log"
KEEP_DAYS="${SYSLOG_KEEP_DAYS:-14}"
MAX_SIZE="${SYSLOG_MAX_SIZE:-50M}"
WAIT_SECONDS="${SYSLOG_WAIT_SECONDS:-900}"

# Auf den gemounteten Cache warten (go-Script läuft vor dem Array-Start).
waited=0
while [ ! -d "$(dirname "$LOG_DIR")" ] && [ "$waited" -lt "$WAIT_SECONDS" ]; do
    sleep 5
    waited=$((waited + 5))
done

if [ ! -d "$(dirname "$LOG_DIR")" ]; then
    logger -t persistent-syslog "appdata nach ${WAIT_SECONDS}s nicht verfügbar — Spiegelung nicht eingerichtet"
    exit 1
fi

mkdir -p "$LOG_DIR"

cat > /etc/rsyslog.d/99-persistent.conf <<EOF
# Von persistent-syslog.sh erzeugt — Systemlog zusätzlich auf die NVMe spiegeln.
# BEWUSST ohne führendes "-": das würde die Schreibvorgänge puffern, und genau
# die letzten Zeilen vor einem Freeze blieben dann im Puffer stecken — also die
# einzigen, die man nach einem Absturz braucht. Beim Freeze vom 10.08.2026 endete
# das Log mitten im Betrieb ohne jeden Hinweis. Das Aufkommen ist winzig
# (~1700 Zeilen/Tag), der fsync pro Zeile fällt auf der NVMe nicht ins Gewicht.
*.* $LOG_FILE
EOF

cat > /etc/logrotate.d/persistent-syslog <<EOF
$LOG_FILE {
    daily
    rotate $KEEP_DAYS
    maxsize $MAX_SIZE
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
}
EOF

# rsyslog die neue Regel einlesen lassen.
if [ -x /etc/rc.d/rc.rsyslogd ]; then
    /etc/rc.d/rc.rsyslogd restart >/dev/null 2>&1
else
    killall -HUP rsyslogd >/dev/null 2>&1
fi

logger -t persistent-syslog "Spiegelung aktiv: $LOG_FILE (Rotation: täglich, $KEEP_DAYS Tage, max $MAX_SIZE)"
