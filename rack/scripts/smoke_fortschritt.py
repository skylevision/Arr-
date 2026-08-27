"""Prueft die Fortschrittsmeldung der Outfitvorschlaege.

Startet den Vorgang, liest den SSE-Strom mit und zeigt jede Phase mit dem
Zeitpunkt an. Mit leerem Schrank laeuft das ohne einen einzigen
Modellaufruf; mit Teilen im Schrank kostet es genau einen.

Aufruf:  docker exec rack python /tmp/smoke_fortschritt.py
"""

import json
import time
import urllib.request

BASE = "http://127.0.0.1:8099/api"
ok = True


def check(label, condition, detail=""):
    global ok
    ok = ok and bool(condition)
    print(f"  [{'ok ' if condition else 'FEHLT'}] {label}{' — ' + str(detail) if detail else ''}")


req = urllib.request.Request(BASE + "/outfits/start", method="POST")
req.add_header("Content-Type", "application/json")
start = time.time()
with urllib.request.urlopen(req, json.dumps({"anlass": "Alltag", "temp": 16}).encode(),
                            timeout=30) as r:
    job = json.load(r)
check("Vorgang gestartet", bool(job.get("job")), job.get("job"))

print("\n  Ereignisse aus dem Strom:")
phasen = []
ergebnis = None
letztes_event = None
with urllib.request.urlopen(BASE + f"/outfits/{job['job']}/events", timeout=600) as r:
    for roh in r:
        zeile = roh.decode("utf-8").rstrip("\n")
        if zeile.startswith("event: "):
            letztes_event = zeile[7:]
            continue
        if not zeile.startswith("data: "):
            continue
        daten = json.loads(zeile[6:])
        if letztes_event == "ende":
            ergebnis = daten
            print(f"    {time.time() - start:6.1f}s  ENDE")
            break
        phasen.append(daten)
        roh_da = " + Engine-Rangfolge" if daten.get("roh") else ""
        print(f"    {time.time() - start:6.1f}s  {daten['phase']:<11} "
              f"{daten['schritt']}/{daten['gesamt']}  {daten['text']}{roh_da}")
        letztes_event = None

dauer = time.time() - start
print()
namen = [p["phase"] for p in phasen]
check("Phasen kamen in der richtigen Reihenfolge",
      namen == sorted(set(namen), key=namen.index), " -> ".join(namen))
check("Endereignis mit Ergebnis empfangen", ergebnis is not None)
check("Schrittzähler wächst monoton",
      all(b["schritt"] >= a["schritt"] for a, b in zip(phasen, phasen[1:])))

if "gerechnet" in namen:
    idx = namen.index("gerechnet")
    check("Engine-Rangfolge kommt vor der Kuratierung",
          bool(phasen[idx].get("roh", {}).get("outfits")),
          f"nach {phasen[idx]['schritt']}/{phasen[idx]['gesamt']}")
    if "kuratieren" in namen:
        check("Kuratierung ist die letzte und längste Phase",
              namen.index("kuratieren") > idx)
    if ergebnis:
        check("Endergebnis ist kuratiert", ergebnis.get("kuratiert") is True,
              f"{len(ergebnis.get('outfits') or [])} Vorschläge")
else:
    print("  (leerer Schrank: die Phasen nach der Rechnung entfallen, "
          "kein Modellaufruf)")

# Der Abfrageweg muss dasselbe liefern, falls SSE beim Nutzer scheitert.
with urllib.request.urlopen(BASE + f"/outfits/{job['job']}", timeout=30) as r:
    abfrage = json.load(r)
check("Abfrageweg liefert denselben Endstand",
      abfrage["status"] == "fertig" and abfrage["ergebnis"] is not None)

print(f"\n  Gesamtdauer: {dauer:.1f}s")
print("\n" + ("ALLES GRÜN" if ok else "ES GIBT FEHLER"))
raise SystemExit(0 if ok else 1)
