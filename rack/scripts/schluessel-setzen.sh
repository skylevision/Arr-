#!/bin/bash
# Traegt den Anthropic-API-Schluessel in die .env ein.
#
# Die Eingabe ist verdeckt, der Schluessel wird nicht angezeigt, nicht in
# die Shell-Historie geschrieben und nicht protokolliert. Ausgegeben wird
# hoechstens die maskierte Form.
#
# Aufruf auf dem Unraid-Server:
#   bash /mnt/user/rack/scripts/schluessel-setzen.sh

set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$DIR/.env"

if [ ! -f "$ENV" ]; then
  cp "$DIR/.env.example" "$ENV"
  chmod 600 "$ENV"
fi

echo "Anthropic-Schlüssel eintragen. Die Eingabe bleibt unsichtbar."
echo "Leer lassen und Enter drücken entfernt einen vorhandenen Schlüssel."
printf 'Schlüssel: '
read -rs KEY
echo

if [ -n "$KEY" ] && [[ "$KEY" != sk-ant-* ]]; then
  echo "Das sieht nicht nach einem Anthropic-Schlüssel aus, er beginnt mit sk-ant-." >&2
  echo "Nichts geändert." >&2
  exit 1
fi

# Zeile ersetzen, ohne den Rest der Datei anzufassen. Der Wert geht ueber
# die Umgebung an awk, damit er nicht im Prozessaufruf sichtbar wird.
TMP="$(mktemp)"
chmod 600 "$TMP"
KEY="$KEY" awk '
  BEGIN { done = 0 }
  /^ANTHROPIC_API_KEY=/ { print "ANTHROPIC_API_KEY=" ENVIRON["KEY"]; done = 1; next }
  { print }
  END { if (!done) print "ANTHROPIC_API_KEY=" ENVIRON["KEY"] }
' "$ENV" > "$TMP"
mv "$TMP" "$ENV"
chmod 600 "$ENV"
chown 99:100 "$ENV" 2>/dev/null || true
unset KEY

if [ -s "$ENV" ]; then
  MASK="$(grep '^ANTHROPIC_API_KEY=' "$ENV" | cut -d= -f2-)"
  if [ -n "$MASK" ]; then
    echo "Eingetragen: sk-ant-…${MASK: -4}"
  else
    echo "Schlüssel entfernt. Die Regel-Engine läuft weiter, die KI-Funktionen sind aus."
  fi
  unset MASK
fi

echo
# Wichtig: "docker compose restart" startet den Container mit seiner alten
# Umgebung neu und liest die .env gar nicht. Es braucht "up -d", das den
# Container neu erzeugt. Ein Neubau des Images ist trotzdem nicht nötig.
echo "Container neu erzeugen, damit der Schlüssel wirkt (kein Neubau des Images)."
cd "$DIR" && docker compose up -d >/dev/null
sleep 8

echo "Testaufruf gegen die API:"
docker exec rack python - <<'PY'
import json
import urllib.request

req = urllib.request.Request("http://127.0.0.1:8099/api/ai-test", method="POST")
with urllib.request.urlopen(req, timeout=120) as r:
    res = json.load(r)

if res.get("ok"):
    print(f"  Erreichbar. Schlüssel {res['schluessel']}, Modell {res['modell']}, "
          f"{res['tokens']} Token verbraucht.")
else:
    art = {
        "kein_schluessel": "Es ist kein Schlüssel hinterlegt.",
        "schluessel": "Der Schlüssel wurde abgelehnt, er ist falsch oder wurde widerrufen.",
        "guthaben": "Der Schlüssel stimmt, aber das Guthaben reicht nicht. "
                    "Anthropic Console, Settings, Billing.",
        "berechtigung": "Der Schlüssel darf dieses Modell nicht benutzen.",
        "limit": "Das Anfragelimit ist gerade erreicht, später erneut versuchen.",
        "netzwerk": "Netzwerkproblem, die API war nicht erreichbar.",
    }.get(res.get("art"), res.get("meldung", "Unbekannter Fehler."))
    print(f"  Fehlgeschlagen: {art}")
PY
