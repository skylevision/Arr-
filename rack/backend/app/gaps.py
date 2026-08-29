"""Lueckenanalyse mit virtuellem Test, portiert aus rack.jsx.

catalogFor() und analyseGaps() unveraendert uebernommen. Der virtuelle Test
baut den Schrank einmal mit und einmal ohne jedes Kandidatenteil neu auf und
misst, wie viele zusaetzliche gute Kombinationen dabei entstehen.
"""

from __future__ import annotations

from typing import Any

from .engine import CATEGORIES, Item, build, derive, is_acc

GOOD = 0.62


def catalog_for(gender: str | None) -> list[Item]:
    base: list[Item] = [
        {"name": "weite Hose, schwarz, hoher Bund", "category": "Unterteil", "fit": "weit",
         "length": "lang", "rise": "high", "colorHex": "#1b1b1b", "thickness": "mittel",
         "material": "baumwolle", "pattern": "uni", "texture": "glatt", "preisklasse": "mittel"},
        {"name": "gerade Jeans, mittelblau", "category": "Unterteil", "fit": "regular",
         "length": "knöchel", "rise": "mid", "colorHex": "#3f5878", "thickness": "mittel",
         "material": "denim", "pattern": "uni", "texture": "robust", "preisklasse": "mittel"},
        {"name": "Oversize T-Shirt, weiß", "category": "Oberteil", "fit": "oversize",
         "length": "hüftlang", "colorHex": "#f2f0ec", "thickness": "mittel",
         "material": "baumwolle", "pattern": "uni", "texture": "glatt", "sleeve": "kurz",
         "preisklasse": "budget"},
        {"name": "Overshirt, sand", "category": "Jacke", "fit": "oversize",
         "length": "hüftlang", "colorHex": "#b9a894", "thickness": "mittel",
         "material": "baumwolle", "pattern": "uni", "texture": "strukturiert",
         "sleeve": "lang", "preisklasse": "mittel"},
        {"name": "Strickpullover, dunkelgrau", "category": "Oberteil", "fit": "weit",
         "length": "hüftlang", "colorHex": "#494c50", "thickness": "dick", "material": "wolle",
         "pattern": "uni", "texture": "strukturiert", "sleeve": "lang", "preisklasse": "mittel"},
        {"name": "Sneaker, weiß", "category": "Schuhe", "fit": "regular",
         "colorHex": "#eeeae4", "thickness": "mittel", "material": "leder", "pattern": "uni",
         "texture": "glatt", "shoeWeight": "normal", "preisklasse": "mittel"},
        {"name": "Boot, schwarz, grobe Sohle", "category": "Schuhe", "fit": "regular",
         "colorHex": "#141414", "thickness": "dick", "material": "leder", "pattern": "uni",
         "texture": "robust", "shoeWeight": "chunky", "preisklasse": "premium"},
        {"name": "Parka, oliv", "category": "Jacke", "fit": "oversize", "length": "longline",
         "colorHex": "#4a4f3a", "thickness": "dick", "material": "baumwolle", "pattern": "uni",
         "texture": "robust", "sleeve": "lang", "preisklasse": "premium"},
        {"name": "Mütze, schwarz", "category": "Accessoire", "subcategory": "Mütze",
         "fit": "regular", "colorHex": "#191919", "thickness": "mittel", "material": "wolle",
         "pattern": "uni", "texture": "strukturiert", "preisklasse": "budget"},
        {"name": "Uhr, silber", "category": "Accessoire", "subcategory": "Uhr",
         "fit": "regular", "colorHex": "#b8bcc0", "thickness": "dünn", "material": "stahl",
         "pattern": "uni", "texture": "glänzend", "preisklasse": "premium"},
        {"name": "Tasche, schwarz", "category": "Accessoire", "subcategory": "Tasche",
         "fit": "regular", "colorHex": "#161616", "thickness": "mittel", "material": "nylon",
         "pattern": "uni", "texture": "glatt", "preisklasse": "mittel"},
    ]
    male: list[Item] = [
        {"name": "Hemd, weiß, weit", "category": "Oberteil", "fit": "oversize",
         "length": "hüftlang", "colorHex": "#f4f2ee", "thickness": "dünn",
         "material": "baumwolle", "pattern": "uni", "texture": "glatt", "sleeve": "lang",
         "preisklasse": "mittel"},
        {"name": "Cargohose, dunkelgrün", "category": "Unterteil", "fit": "weit",
         "length": "stacked", "rise": "mid", "colorHex": "#3c443a", "thickness": "mittel",
         "material": "baumwolle", "pattern": "uni", "texture": "robust", "preisklasse": "mittel"},
        {"name": "Hoodie, grau meliert", "category": "Oberteil", "fit": "oversize",
         "length": "hüftlang", "colorHex": "#8a8d90", "thickness": "dick",
         "material": "baumwolle", "pattern": "meliert", "texture": "flauschig",
         "sleeve": "lang", "preisklasse": "mittel"},
    ]
    female: list[Item] = [
        {"name": "Oversize Hemd, weiß", "category": "Oberteil", "fit": "oversize",
         "length": "longline", "colorHex": "#f4f2ee", "thickness": "dünn",
         "material": "baumwolle", "pattern": "uni", "texture": "glatt", "sleeve": "lang",
         "preisklasse": "mittel"},
        {"name": "Feinstrick, creme", "category": "Oberteil", "fit": "regular",
         "length": "cropped", "colorHex": "#e3dbcd", "thickness": "mittel", "material": "wolle",
         "pattern": "uni", "texture": "strukturiert", "sleeve": "lang", "preisklasse": "mittel"},
        {"name": "Anzughose, schwarz, weit", "category": "Unterteil", "fit": "weit",
         "length": "lang", "rise": "high", "colorHex": "#1a1a1a", "thickness": "mittel",
         "material": "wolle", "pattern": "uni", "texture": "glatt", "preisklasse": "premium"},
        {"name": "Loafer, schwarz", "category": "Schuhe", "fit": "regular",
         "colorHex": "#151515", "thickness": "mittel", "material": "leder", "pattern": "uni",
         "texture": "glänzend", "shoeWeight": "normal", "preisklasse": "premium"},
    ]
    return [*base, *(female if gender == "weiblich" else male)]


def analyse_gaps(items: list[Item], ctx: dict, now_ms: float | None = None) -> dict[str, Any]:
    real = [i for i in items if not i.get("paused")]
    baseline = build(real, ctx, 0, now_ms)

    best_for: dict[str, float] = {}
    for o in baseline:
        for p in o["parts"]:
            best_for[p["id"]] = max(best_for.get(p["id"], 0), o["score"]["total"])

    orphans = [
        {"name": i.get("name"), "art": i.get("subcategory"), "schnitt": i.get("fit"),
         "farbe": i.get("colorName"),
         "bestePunkte": round(best_for.get(i["id"], 0) * 100)}
        for i in real
        if i.get("category") in ("Oberteil", "Unterteil", "Kleid", "Schuhe")
        and best_for.get(i["id"], 0) < 0.55
    ]

    candidates = []
    for n, c in enumerate(catalog_for(ctx.get("gender"))):
        virt = {**c, **derive(c), "id": f"virt_{n}"}
        with_it = build([*real, virt], ctx, 0, now_ms)
        gain = len([
            o for o in with_it
            if o["score"]["total"] >= GOOD and any(p["id"] == virt["id"] for p in o["parts"])
        ])
        scores = [o["score"]["total"] for o in with_it
                  if any(p["id"] == virt["id"] for p in o["parts"])]
        best_score = max([0, *scores])
        candidates.append({
            "teil": c["name"], "kategorie": c["category"], "preisklasse": c["preisklasse"],
            "neueOutfits": gain, "bestePunkte": round(best_score * 100),
        })

    candidates.sort(key=lambda c: (c["neueOutfits"], c["bestePunkte"]), reverse=True)

    counts = {c: len([i for i in real if i.get("category") == c]) for c in CATEGORIES}
    acc_types = list(dict.fromkeys(
        i.get("subcategory") for i in real if is_acc(i) and i.get("subcategory")
    ))
    gute_outfits = len([o for o in baseline if o["score"]["total"] >= GOOD])

    return {
        "bestand": counts,
        "accessoires": acc_types,
        "guteOutfits": gute_outfits,
        "waisen": orphans[:6],
        "kandidaten": candidates[:8],
    }
