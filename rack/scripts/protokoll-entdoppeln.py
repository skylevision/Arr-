"""Fasst versehentliche Mehrfacheinträge im Trageprotokoll zusammen.

Hintergrund: Bis die Bewertungsknöpfe eine sichtbare Quittung bekamen, sah
ein Druck folgenlos aus und wurde wiederholt. Dabei entstanden mehrere
Einträge für dasselbe Outfit innerhalb weniger Sekunden.

Zusammengefasst wird nur, was zweifelsfrei dasselbe Ereignis ist: gleicher
Teilesatz, gleicher Anlass, gleiche Temperatur und innerhalb desselben
Zeitfensters. Wer ein Outfit am nächsten Tag erneut trägt, behält beide
Einträge.

Danach werden wear_count und last_worn aus dem bereinigten Protokoll neu
berechnet - aber nur für Teile, die überhaupt darin vorkommen. Ein
Zählerstand aus einem Import bleibt unangetastet.

  python protokoll-entdoppeln.py            # nur zeigen, nichts ändern
  python protokoll-entdoppeln.py --schreiben
"""

import json
import sqlite3
import sys
from datetime import datetime

DB = "/data/db/rack.sqlite3"
FENSTER_SEKUNDEN = 300

schreiben = "--schreiben" in sys.argv


def zeit(wert: str) -> datetime:
    return datetime.fromisoformat(wert)


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

eintraege = list(conn.execute("SELECT * FROM outfit_log ORDER BY worn_at"))
print(f"Protokoll: {len(eintraege)} Einträge\n")

# ── Läufe gleicher Einträge finden ──────────────────────────────────────
behalten: list[sqlite3.Row] = []
verwerfen: list[sqlite3.Row] = []
for e in eintraege:
    passend = None
    for b in behalten:
        if (b["item_ids"], b["occasion"], b["temp"]) != (e["item_ids"], e["occasion"], e["temp"]):
            continue
        if abs((zeit(e["worn_at"]) - zeit(b["worn_at"])).total_seconds()) <= FENSTER_SEKUNDEN:
            passend = b
            break
    if passend is None:
        behalten.append(e)
    else:
        verwerfen.append(e)

if not verwerfen:
    print("Nichts zusammenzufassen. Das Protokoll ist sauber.")
    raise SystemExit(0)

namen = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM items")}
print("Zusammengefasst wird:")
for b in behalten:
    doppelt = [v for v in verwerfen if (v["item_ids"], v["occasion"], v["temp"])
               == (b["item_ids"], b["occasion"], b["temp"])]
    if not doppelt:
        continue
    teile = ", ".join(namen.get(i, "?") for i in json.loads(b["item_ids"]))
    print(f"  {len(doppelt) + 1} Einträge -> 1   {b['occasion']} {b['temp']}°C   "
          f"{b['worn_at'][:19]}")
    print(f"    {teile}")

# ── Zähler neu aus dem bereinigten Protokoll ableiten ───────────────────
zaehler: dict[str, int] = {}
zuletzt: dict[str, str] = {}
for b in behalten:
    for i in json.loads(b["item_ids"]):
        zaehler[i] = zaehler.get(i, 0) + 1
        if b["worn_at"] > zuletzt.get(i, ""):
            zuletzt[i] = b["worn_at"]

print("\nZähler danach:")
aenderungen = []
for it in conn.execute("SELECT id, name, wear_count, last_worn FROM items"):
    if it["id"] not in zaehler:
        # Kommt im Protokoll nicht vor. Ein Stand aus einem Import bleibt,
        # wie er ist; wir wissen nicht, wie er zustande kam.
        continue
    neu_zahl, neu_datum = zaehler[it["id"]], zuletzt[it["id"]]
    if (it["wear_count"], it["last_worn"]) != (neu_zahl, neu_datum):
        aenderungen.append((it["id"], neu_zahl, neu_datum))
        print(f"  {it['name'][:36]:38} {it['wear_count']} -> {neu_zahl}")

print(f"\n{len(verwerfen)} Einträge entfernen, {len(behalten)} behalten, "
      f"{len(aenderungen)} Teile korrigieren.")

if not schreiben:
    print("\nProbelauf. Zum Ausführen mit --schreiben aufrufen.")
    raise SystemExit(0)

with conn:
    conn.executemany("DELETE FROM outfit_log WHERE id = ?",
                     [(v["id"],) for v in verwerfen])
    conn.executemany("UPDATE items SET wear_count = ?, last_worn = ? WHERE id = ?",
                     [(z, d, i) for i, z, d in aenderungen])

rest = conn.execute("SELECT COUNT(*) FROM outfit_log").fetchone()[0]
print(f"\nErledigt. Protokoll hat jetzt {rest} Einträge.")
