"""Erzeugt Vergleichsfaelle und prueft die Python-Engine gegen rack.jsx."""
import json
import pathlib
import random
import sys
from datetime import datetime, timezone

sys.path.insert(0, r"C:\dev\Arr-\rack\backend")
from app import engine as E          # noqa: E402
from app.gaps import analyse_gaps    # noqa: E402

FIXED_NOW = 1750000000000

CATS = ["Oberteil", "Unterteil", "Kleid", "Jacke", "Schuhe", "Accessoire"]
SUBS = ["Uhr", "Schmuck", "Mütze", "Cap", "Schal", "Gürtel", "Tasche", "Brille",
        "Hemd", "Pullover", "Jeans", "Sneaker", "Parka", "Blazer", "Cargohose", None]
FITS = ["oversize", "weit", "regular", "slim", "cropped", None, "unbekannt"]
TOPLEN = ["cropped", "hüftlang", "longline", None]
BOTLEN = ["shorts", "sieben-achtel", "knöchel", "lang", "stacked", None]
RISES = ["high", "mid", "low", None]
THICK = ["dünn", "mittel", "dick", None, "sehr dick"]
PATS = ["uni", "gestreift", "kariert", "gemustert", "meliert", "logo", None]
SCALES = ["klein", "mittel", "groß", None]
MATS = ["wolle", "kaschmir", "fleece", "daune", "strick", "leder", "denim",
        "baumwolle", "jersey", "leinen", "seide", "wolle leinen", "stahl", "nylon", None, ""]
TEX = ["glatt", "strukturiert", "glänzend", "flauschig", "robust", None]
SHOEW = ["filigran", "normal", "chunky", None]
SLEEVE = ["ärmellos", "kurz", "dreiviertel", "lang", None]
COLORS = ["#1b1b1b", "#f2f0ec", "#cc2200", "#aacc00", "#3f5878", "#494c50", "#b9a894",
          "#4a4f3a", "#191919", "#b8bcc0", "#808080", "#7f2ba0", "#00d0c0", None, "kaputt"]
BUILDS = ["schlank", "normal", "athletisch", "kräftig", None]
TORSOS = ["langer Oberkörper", "ausgeglichen", "lange Beine", None]
MODES = ["oversize", "mix", "frei", "offen"]

rng = random.Random(20260827)


def rand_attrs():
    return {
        "name": rng.choice(["Hemd weiß", "Strickpullover", "Weite Hose", "Boot",
                            "Jogginghose", "Parka", "Uhr", "Kleid", "Trench", "Teil"]),
        "category": rng.choice(CATS),
        "subcategory": rng.choice(SUBS),
        "colorHex": rng.choice(COLORS),
        "colorName": "farbe",
        "pattern": rng.choice(PATS),
        "patternScale": rng.choice(SCALES),
        "material": rng.choice(MATS),
        "thickness": rng.choice(THICK),
        "texture": rng.choice(TEX),
        "fit": rng.choice(FITS),
        "length": rng.choice(TOPLEN + BOTLEN),
        "rise": rng.choice(RISES),
        "sleeve": rng.choice(SLEEVE),
        "shoeWeight": rng.choice(SHOEW),
    }


def rand_item(i):
    a = rand_attrs()
    a["id"] = f"i{i}"
    a.update(E.derive(a))
    a["paused"] = 1 if rng.random() < 0.12 else 0
    if rng.random() < 0.35:
        days = rng.uniform(0, 30)
        ms = FIXED_NOW - days * 86400000
        a["lastWorn"] = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
    else:
        a["lastWorn"] = None
    return a


def rand_ctx(items):
    ids = [i["id"] for i in items]
    return {
        "temp": rng.choice([-5, 0, 4, 8, 11, 13, 16, 19, 24, 27, 33]),
        "target": rng.choice([1, 2, 3, 4, 5]),
        "mode": rng.choice(MODES),
        "body": {"height": rng.choice([160, 170, 172, 180, 188, 195]),
                 "build": rng.choice(BUILDS), "torso": rng.choice(TORSOS)},
        "gender": rng.choice(["männlich", "weiblich"]),
        "fb": {"liked": [], "disliked": []},
        "anchor": rng.choice(ids + [None, None, None]) if ids else None,
    }


cases = {"derive": [rand_attrs() for _ in range(400)], "wardrobes": [], "violates": []}

# Realistische Schraenke aus dem Kandidatenkatalog: nur so entstehen genug
# zulaessige Kombinationen, damit build() und score() wirklich abgedeckt sind.
from app.gaps import catalog_for  # noqa: E402
POOL = catalog_for("männlich") + catalog_for("weiblich")
for w in range(120):
    n = rng.randint(5, 14)
    items = []
    for k in range(n):
        c = dict(rng.choice(POOL))
        c.pop("preisklasse", None)
        if rng.random() < 0.3:
            c["fit"] = rng.choice(["oversize", "weit", "regular", "slim", "cropped"])
        if rng.random() < 0.25:
            c["pattern"] = rng.choice(PATS)
            c["patternScale"] = rng.choice(SCALES)
        if rng.random() < 0.2:
            c["colorHex"] = rng.choice(COLORS)
        c["id"] = f"r{k}"
        c.update(E.derive(c))
        c["paused"] = 1 if rng.random() < 0.1 else 0
        if rng.random() < 0.4:
            ms = FIXED_NOW - rng.uniform(0, 25) * 86400000
            c["lastWorn"] = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
        else:
            c["lastWorn"] = None
        items.append(c)
    ctx = rand_ctx(items)
    if rng.random() < 0.5:
        ids = [i["id"] for i in items]
        ctx["fb"] = {"liked": [E.pair_key(ids[0], ids[1])],
                     "disliked": [E.pair_key(ids[-1], ids[-2])]}
    cases["wardrobes"].append({"items": items, "ctx": ctx})

for _ in range(40):
    n = rng.randint(3, 11)
    items = [rand_item(i) for i in range(n)]
    ctx = rand_ctx(items)
    if rng.random() < 0.4:
        ids = [i["id"] for i in items]
        if len(ids) >= 2:
            ctx["fb"] = {"liked": [E.pair_key(ids[0], ids[1])],
                         "disliked": [E.pair_key(ids[-1], ids[-2])]}
    cases["wardrobes"].append({"items": items, "ctx": ctx})

for _ in range(300):
    n = rng.randint(2, 5)
    items = [rand_item(1000 + i) for i in range(n)]
    if not any(i["category"] != "Accessoire" for i in items):
        # reine Accessoire-Listen erzeugt build() nie und JS liefert dort NaN
        continue
    cases["violates"].append({"parts": items, "ctx": rand_ctx(items),
                              "level": rng.choice([0, 1, 2])})

with open("cases.json", "w", encoding="utf-8") as f:
    json.dump(cases, f, ensure_ascii=False)

# ── Python-Seite rechnen ────────────────────────────────────────────────
mine = {"derive": [], "score": [], "picks": [], "gaps": [], "violates": []}
for a in cases["derive"]:
    mine["derive"].append(E.derive(a))
for c in cases["wardrobes"]:
    items, ctx = c["items"], c["ctx"]
    b = E.build(items, ctx, 0, FIXED_NOW)
    mine["score"].append([
        {"ids": [p["id"] for p in o["parts"]], "total": o["score"]["total"],
         "sub": o["score"]["sub"]} for o in b])
    tp = E.top_picks(items, ctx, FIXED_NOW)
    mine["picks"].append({
        "relaxed": tp["relaxed"], "total": tp["total"],
        "picks": [{"ids": [x["id"] for x in p["parts"]], "total": p["score"]["total"]}
                  for p in tp["picks"]]})
    mine["gaps"].append(analyse_gaps(items, ctx, FIXED_NOW))
for v in cases["violates"]:
    mine["violates"].append(E.violates(v["parts"], v["ctx"], v["level"]))

with open("mine.json", "w", encoding="utf-8") as f:
    json.dump(mine, f, ensure_ascii=False)
print("cases geschrieben:", len(cases["derive"]), "derive,",
      len(cases["wardrobes"]), "schraenke,", len(cases["violates"]), "violates")
