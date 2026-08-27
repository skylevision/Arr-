"""Funktionstest gegen die laufende API.

Laeuft ohne API-Schluessel durch: geprueft werden Speichern, die
Regel-Engine, harte Ausschluesse, Rueckmeldung, Tragen, Lueckenanalyse,
Ankerteil sowie Export und Import.

Aufruf:  docker exec rack python /tmp/smoke.py
"""

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8099/api"
ok = True


def call(path, data=None, method=None):
    req = urllib.request.Request(BASE + path,
                                 method=method or ("POST" if data is not None else "GET"))
    body = None
    if data is not None:
        req.add_header("Content-Type", "application/json")
        body = json.dumps(data).encode()
    with urllib.request.urlopen(req, body, timeout=120) as r:
        return json.load(r)


def check(label, condition, detail=""):
    global ok
    ok = ok and bool(condition)
    print(f"  [{'ok ' if condition else 'FEHLT'}] {label}{' — ' + str(detail) if detail else ''}")


TEILE = [
    {"name": "Oversize Shirt", "category": "Oberteil", "fit": "oversize", "length": "hüftlang",
     "thickness": "mittel", "material": "baumwolle", "colorHex": "#f2f0ec",
     "colorName": "weiß", "pattern": "uni", "texture": "glatt", "sleeve": "kurz"},
    {"name": "Strickpullover", "category": "Oberteil", "fit": "weit", "length": "hüftlang",
     "thickness": "dick", "material": "wolle", "colorHex": "#494c50",
     "colorName": "dunkelgrau", "pattern": "uni", "texture": "strukturiert", "sleeve": "lang"},
    {"name": "Weite Hose", "category": "Unterteil", "fit": "weit", "length": "lang",
     "rise": "high", "thickness": "mittel", "material": "baumwolle", "colorHex": "#1b1b1b",
     "colorName": "schwarz", "pattern": "uni", "texture": "glatt"},
    {"name": "Gerade Jeans", "category": "Unterteil", "fit": "regular", "length": "knöchel",
     "rise": "mid", "thickness": "mittel", "material": "denim", "colorHex": "#3f5878",
     "colorName": "mittelblau", "pattern": "uni", "texture": "robust"},
    {"name": "Boot", "category": "Schuhe", "thickness": "dick", "material": "leder",
     "colorHex": "#141414", "colorName": "schwarz", "pattern": "uni", "texture": "robust",
     "shoeWeight": "chunky"},
    {"name": "Sneaker", "category": "Schuhe", "thickness": "mittel", "material": "leder",
     "colorHex": "#eeeae4", "colorName": "weiß", "pattern": "uni", "texture": "glatt",
     "shoeWeight": "normal"},
    {"name": "Uhr", "category": "Accessoire", "subcategory": "Uhr", "thickness": "dünn",
     "material": "stahl", "colorHex": "#b8bcc0", "colorName": "silber", "pattern": "uni",
     "texture": "glänzend"},
]

print("== Gesundheit ==")
h = call("/health")
check("Status ok", h["status"] == "ok", f"KI aktiv: {h['ki']}")

print("\n== Profil ==")
p = call("/profile", {"gender": "männlich", "height": 182, "build": "normal",
                      "torso": "ausgeglichen", "silhouette": "frei",
                      "glasses": False, "notes": ""}, "PUT")
check("gespeichert und gelesen", p["height"] == 182)

print("\n== Teile anlegen, Wärme und Formalität gerechnet ==")
ids = []
for t in TEILE:
    it = call("/items", {"attrs": t})
    ids.append(it["id"])
    print(f"     {it['name']:16} warmth={it['warmth']:<4} formality={it['formality']}")
pulli = call("/items")
pulli = next(i for i in pulli if i["name"] == "Strickpullover")
check("Wollpullover, lange Ärmel, dick = 5.0", pulli["warmth"] == 5.0, pulli["warmth"])
check("nicht als manuell markiert", not pulli["warmthManual"])

print("\n== Vorschläge ==")
o = call("/outfits", {"anlass": "Alltag", "temp": 16})
check("mindestens ein Vorschlag", len(o["outfits"]) >= 1, f"{len(o['outfits'])} Stück")
check("ohne Schlüssel nicht kuratiert", o["kuratiert"] is False or h["ki"])
for x in o["outfits"]:
    print(f"     {x['punkte']:>3}  {', '.join(t['name'] for t in x['teile'])}")

print("\n== Harte Ausschlüsse ==")
# Bei 32 Grad reisst die Waermeregel, es bleiben unter drei Kombinationen
# uebrig und die Engine lockert gestuft. Genau das meldet sie auch.
warm = call("/outfits", {"anlass": "Alltag", "temp": 32})
check("Wärmeregel greift und wird als gelockert gemeldet", warm["gelockert"] is True,
      f"{len(warm['outfits'])} Vorschläge, gelockert={warm['gelockert']}")

# Zwei laute Muster und die Silhouette sind Ausschluesse ohne Toleranz.
# Sie muessen auch nach voller Lockerung greifen.
kariert_top = call("/items", {"attrs": {
    "name": "Karohemd", "category": "Oberteil", "fit": "oversize", "length": "hüftlang",
    "thickness": "mittel", "material": "baumwolle", "colorHex": "#7a7f86",
    "colorName": "grau", "pattern": "kariert", "texture": "glatt", "sleeve": "lang"}})
kariert_bottom = call("/items", {"attrs": {
    "name": "Karohose", "category": "Unterteil", "fit": "weit", "length": "lang",
    "rise": "high", "thickness": "mittel", "material": "baumwolle",
    "colorHex": "#6f7480", "colorName": "grau", "pattern": "kariert", "texture": "glatt"}})
alle = call("/outfits", {"anlass": "Alltag", "temp": 16})
zusammen = [x for x in alle["outfits"]
            if any(t["id"] == kariert_top["id"] for t in x["teile"])
            and any(t["id"] == kariert_bottom["id"] for t in x["teile"])]
check("zwei laute Muster kommen nie zusammen", not zusammen,
      f"{len(alle['outfits'])} Vorschläge geprüft")

call("/profile", {"silhouette": "oversize"}, "PUT")
slim = call("/items", {"attrs": {
    "name": "Slim Jeans", "category": "Unterteil", "fit": "slim", "length": "lang",
    "rise": "mid", "thickness": "mittel", "material": "denim", "colorHex": "#2f3d52",
    "colorName": "dunkelblau", "pattern": "uni", "texture": "robust"}})
ovs = call("/outfits", {"anlass": "Alltag", "temp": 16})
check("im Modus oversize taucht kein slim-Unterteil auf",
      not any(any(t["id"] == slim["id"] for t in x["teile"]) for x in ovs["outfits"]),
      f"{len(ovs['outfits'])} Vorschläge geprüft")
call("/items/" + slim["id"], None, "DELETE")
call("/items/" + kariert_top["id"], None, "DELETE")
call("/items/" + kariert_bottom["id"], None, "DELETE")
call("/profile", {"silhouette": "frei"}, "PUT")

print("\n== Rückmeldung und Tragen ==")
first = o["outfits"][0]["teile"]
fb = call("/feedback", {"teile": [t["id"] for t in first], "urteil": "liked"})
check("Feedback gespeichert", len(fb["liked"]) > 0, f"{len(fb['liked'])} Paare")
call("/worn", {"teile": [t["id"] for t in first], "anlass": "Alltag",
               "temp": 16, "punkte": o["outfits"][0]["punkte"]})
getragen = next(i for i in call("/items") if i["id"] == first[0]["id"])
check("Tragezähler erhöht", getragen["wearCount"] == 1, getragen["wearCount"])
check("Datum gesetzt", bool(getragen["lastWorn"]))
check("Protokoll geschrieben", len(call("/worn")) == 1)

print("\n== Ankerteil ==")
anker = call("/outfits", {"anlass": "Alltag", "temp": 16, "anker": ids[1]})
check("jeder Vorschlag enthält das Ankerteil",
      all(any(t["id"] == ids[1] for t in x["teile"]) for x in anker["outfits"]),
      f"{len(anker['outfits'])} Vorschläge")

print("\n== Lückenanalyse ==")
g = call("/gaps", {"anlass": "Alltag", "temp": 16})
check("Rechnung vorhanden", "roh" in g and g["roh"]["kandidaten"])
top = g["roh"]["kandidaten"][0]
check("Kandidat mit gemessenem Zugewinn", top["neueOutfits"] >= 0,
      f"{top['teil']}: +{top['neueOutfits']}")

print("\n== Manuelles Überschreiben ==")
upd = call(f"/items/{ids[1]}", {"warmth": 2.0}, "PATCH")
check("Wert übernommen", upd["warmth"] == 2.0)
check("als manuell markiert", upd["warmthManual"] is True)
upd = call(f"/items/{ids[1]}", {"material": "leinen"}, "PATCH")
check("bleibt manuell trotz Neuberechnung", upd["warmth"] == 2.0)
upd = call(f"/items/{ids[1]}", {"warmthManual": False}, "PATCH")
check("Freigabe rechnet neu", upd["warmth"] != 2.0, upd["warmth"])

print("\n== Export und Import ==")
exp = call("/export")
check("Exportformat des Prototypen", exp["version"] == 2 and len(exp["items"]) == len(TEILE),
      f"{len(exp['items'])} Teile")
imp1 = call("/import", exp)
imp2 = call("/import", exp)
check("Import ist idempotent",
      imp2["neu"] == 0 and imp2["teile"] == len(TEILE),
      f"1. Lauf {imp1['neu']} neu, 2. Lauf {imp2['neu']} neu, {imp2['teile']} Teile gesamt")

print("\n" + ("ALLES GRÜN" if ok else "ES GIBT FEHLER"))
sys.exit(0 if ok else 1)
