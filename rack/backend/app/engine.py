"""Regel-Engine, portiert aus rack.jsx.

Diese Datei ist eine 1:1-Uebersetzung der Fachlogik des Prototypen. Die
Schwellwerte, Gewichte und Wortlisten sind ueber mehrere Iterationen
entstanden und duerfen nicht ohne Ruecksprache angepasst werden
(Briefing Abschnitt 5).

Items sind dicts in der camelCase-Form des Prototypen (colorHex,
patternScale, shoeWeight, lastWorn). Die Umsetzung auf die snake_case-
Spalten der Datenbank passiert ausschliesslich in db.py.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

Item = dict[str, Any]

# ── Vokabulare ──────────────────────────────────────────────────────────

CATEGORIES = ["Oberteil", "Unterteil", "Kleid", "Jacke", "Schuhe", "Accessoire"]
ACCESSORY_TYPES = ["Uhr", "Schmuck", "Mütze", "Cap", "Schal", "Gürtel", "Tasche", "Brille"]
HEAD_WARM = ["Mütze", "Schal"]
FITS = ["oversize", "weit", "regular", "slim", "cropped"]
TOP_LEN = ["cropped", "hüftlang", "longline"]
BOTTOM_LEN = ["shorts", "sieben-achtel", "knöchel", "lang", "stacked"]
RISES = ["high", "mid", "low"]
THICKNESS = ["dünn", "mittel", "dick"]
PATTERNS = ["uni", "gestreift", "kariert", "gemustert", "meliert", "logo"]
SHOE_WEIGHT = ["filigran", "normal", "chunky"]
BUILDS = ["schlank", "normal", "athletisch", "kräftig"]
TORSOS = ["langer Oberkörper", "ausgeglichen", "lange Beine"]

SILHOUETTES = [
    {"key": "oversize", "label": "Durchgehend weit", "hint": "Enge Teile fallen raus"},
    {"key": "mix", "label": "Oben weit, unten gerade", "hint": "Volumen oben, klare Linie unten"},
    {"key": "frei", "label": "Proportionsspiel", "hint": "Weit zu schmal ist erwünscht"},
    {"key": "offen", "label": "Alles erlaubt",
     "hint": "Keine Silhouettenvorgabe, nur Statur und Proportion entscheiden"},
]

OCCASIONS = [
    {"key": "Alltag", "f": 2},
    {"key": "Arbeit", "f": 4},
    {"key": "Abends", "f": 3},
    {"key": "Anlass", "f": 5},
    {"key": "Sport", "f": 1},
]


# ── JS-Semantik, die Python nicht von sich aus mitbringt ────────────────

def js_round(x: float) -> float:
    """Math.round aus JavaScript: .5 rundet immer Richtung plus unendlich.

    Pythons round() rundet zur geraden Zahl und wuerde bei den halben
    Schritten in derive() abweichende Werte liefern.
    """
    return math.floor(x + 0.5)


def _index_of(seq: list[str], value: Any) -> int:
    """Array.prototype.indexOf: -1 statt ValueError."""
    try:
        return seq.index(value)
    except ValueError:
        return -1


def _or(value: Any, fallback: Any) -> Any:
    """JS-Semantik von a || b: greift auch bei 0, leerem String und None."""
    return value if value else fallback


NAN = float("nan")


def js_max(values) -> float:
    """Math.max: ein NaN im Eingang faerbt das Ergebnis auf NaN.

    Pythons max() vergleicht paarweise und liefert je nach Reihenfolge
    irgendeinen Wert. Bei kaputten Farbwerten fuehrt das zu anderen
    Bewertungen als im Prototypen.
    """
    vals = list(values)
    if not vals:
        return -math.inf
    if any(isinstance(v, float) and math.isnan(v) for v in vals):
        return NAN
    return max(vals)


def js_min(values) -> float:
    vals = list(values)
    if not vals:
        return math.inf
    if any(isinstance(v, float) and math.isnan(v) for v in vals):
        return NAN
    return min(vals)


def _hex_component(value: str) -> float:
    """parseInt(v, 16) aus JS: NaN statt ValueError.

    parseInt liest so weit wie moeglich, "1z" ergibt also 1 und nicht NaN.
    """
    m = re.match(r"[0-9a-fA-F]+", value.strip())
    return int(m.group(0), 16) if m else NAN


# ── Farbe und abgeleitete Werte ─────────────────────────────────────────

def hsl(hex_color: Any) -> dict[str, float]:
    if not hex_color or not isinstance(hex_color, str):
        return {"h": 0.0, "s": 0.0, "l": 0.5}
    m = re.findall(r".{1,2}", hex_color.replace("#", ""))
    if len(m) < 3:
        return {"h": 0.0, "s": 0.0, "l": 0.5}
    # Unparsbare Werte werden zu NaN und faerben alles Folgende ein, genau
    # wie parseInt/Math.max in rack.jsx. Ein frueher Ausstieg mit Ersatz-
    # werten wuerde andere Farbbewertungen ergeben.
    r, g, b = (_hex_component(v) / 255 for v in m[:3])
    mx, mn = js_max((r, g, b)), js_min((r, g, b))
    lightness = (mx + mn) / 2
    h = 0.0
    s = 0.0
    if mx != mn:
        dd = mx - mn
        s = dd / (2 - mx - mn) if lightness > 0.5 else dd / (mx + mn)
        if mx == r:
            h = ((g - b) / dd + (6 if g < b else 0)) * 60
        elif mx == g:
            h = ((b - r) / dd + 2) * 60
        else:
            h = ((r - g) / dd + 4) * 60
    return {"h": h, "s": s, "l": lightness}


def neutral(hex_color: Any) -> bool:
    c = hsl(hex_color)
    return c["s"] < 0.17 or c["l"] < 0.13 or c["l"] > 0.93


def hue_gap(a: float, b: float) -> float:
    d = math.fmod(abs(a - b), 360)
    return 360 - d if d > 180 else d


WARM_WORDS = {
    "wolle": 1.4, "kaschmir": 1.4, "fleece": 1.3, "daune": 2, "strick": 1,
    "leder": 0.6, "denim": 0.4, "baumwolle": 0, "jersey": 0,
    "leinen": -0.6, "seide": -0.4,
}

FORMAL_HINTS = [
    {"re": re.compile(
        r"(anzug|blazer|sakko|hemd|bluse|loafer|oxford|derby|mantel|rock|kleid|krawatte)",
        re.I), "v": 4.4},
    {"re": re.compile(
        r"(chino|strick|pullover|cardigan|polo|chelsea|stiefel|hemdjacke|overshirt|trench)",
        re.I), "v": 3.3},
    {"re": re.compile(
        r"(jeans|denim|sneaker|t-shirt|shirt|hoodie|sweat|cargo|parka|bomber|kapuze|beanie|mütze)",
        re.I), "v": 2},
    {"re": re.compile(r"(jogging|trainings|sport|lauf|shorts|flip|slide)", re.I), "v": 1.2},
]


def derive(a: Item) -> dict[str, float]:
    """Waerme und Formalitaet aus sichtbaren Fakten ableiten.

    Wird nie vom Modell geschaetzt. Die Reihenfolge der WARM_WORDS-Schleife
    ist bedeutsam: der letzte Treffer gewinnt, genau wie in rack.jsx.
    """
    th = max(0, _index_of(THICKNESS, a.get("thickness")))
    mat = str(a.get("material") or "").lower()
    bonus = 0.0
    for key in WARM_WORDS:
        if key in mat:
            bonus = WARM_WORDS[key]

    cat = a.get("category")
    if cat == "Jacke":
        warmth = 2.2 + th * 1.4 + bonus
    elif cat == "Oberteil":
        warmth = 0.9 + th * 1.1 + bonus + (0.5 if a.get("sleeve") == "lang" else 0)
    elif cat == "Unterteil":
        warmth = 1.2 + th * 0.9 + bonus + (-1 if a.get("length") == "shorts" else 0)
    elif cat == "Kleid":
        warmth = 1 + th * 1 + bonus
    elif cat == "Schuhe":
        warmth = 1 + th * 0.6
    else:
        warmth = 1.5 + th * 0.5 if a.get("subcategory") in HEAD_WARM else 0.4

    hay = f"{a.get('subcategory') or ''} {a.get('name') or ''} {mat}"
    formality = 2.6
    for hint in FORMAL_HINTS:
        if hint["re"].search(hay):
            formality = hint["v"]
            break
    if a.get("pattern") == "logo":
        formality -= 0.7
    if a.get("texture") == "glänzend":
        formality += 0.4
    if a.get("fit") == "oversize":
        formality -= 0.4

    return {
        "warmth": max(0.4, min(5, js_round(warmth * 2) / 2)),
        "formality": max(1, min(5, js_round(formality * 2) / 2)),
    }


# ── Regeln, hart und weich ──────────────────────────────────────────────

VOL = {"oversize": 3, "weit": 2.5, "regular": 2, "cropped": 2, "slim": 1}


def vol(i: Item) -> float:
    v = VOL.get(i.get("fit"))
    return 2 if v is None else v


def is_acc(p: Item) -> bool:
    return p.get("category") == "Accessoire"


def s_silhouette(top: Item, bottom: Item, mode: str) -> float:
    vt, vb = vol(top), vol(bottom)
    if mode == "offen":
        return 0.9 if abs(vt - vb) >= 1 else 0.85
    if mode == "oversize":
        if vt <= 1 or vb <= 1:
            return 0
        if vt >= 2.5 and vb >= 2.5:
            return 1
        return 0.6 if (vt >= 2.5 or vb >= 2.5) else 0.32
    if mode == "mix":
        if vb <= 1:
            return 0
        if vt >= 2.5 and vb == 2:
            return 1
        return 0.6 if vt >= 2.5 else 0.38
    diff = abs(vt - vb)
    if diff >= 1:
        return 0.96
    return 0.72 if vt >= 2.5 else 0.78


def s_proportion(top: Item, bottom: Item, body: dict | None) -> float:
    tl = _or(top.get("length"), "hüftlang")
    bl = _or(bottom.get("length"), "lang")
    rise = _or(bottom.get("rise"), "mid")
    s = 0.8
    if tl == "cropped":
        s = 1 if rise == "high" else (0.74 if rise == "mid" else 0.32)
    if tl == "hüftlang":
        s = 0.58 if rise == "low" else 0.86
    if tl == "longline":
        s = 0.28 if bl == "shorts" else (0.7 if vol(bottom) >= 2.5 else 0.92)
    if bl == "stacked" and vol(bottom) <= 1:
        s *= 0.72

    m = 1.0
    body = body or {}
    h = _or(body.get("height"), 180)
    if h <= 172:
        if tl == "longline" and vol(bottom) >= 2.5:
            m *= 0.72
        if tl == "cropped" and rise == "high":
            m *= 1.14
        if rise == "low":
            m *= 0.84
    if h >= 188 and tl == "longline":
        m *= 1.06
    if body.get("build") == "kräftig":
        if vol(top) >= 2.5 and vol(bottom) >= 2.5:
            m *= 0.84
        if vol(top) >= 2.5 and vol(bottom) == 2:
            m *= 1.08
    if body.get("build") == "schlank" and vol(top) >= 2.5 and vol(bottom) >= 2.5:
        m *= 1.05
    if body.get("torso") == "langer Oberkörper":
        m *= 1.12 if rise == "high" else (0.76 if rise == "low" else 1)
    if body.get("torso") == "lange Beine":
        m *= 1.08 if tl == "longline" else (0.92 if tl == "cropped" else 1)

    return max(0, min(1, s * m))


def color_detail(parts: list[Item]) -> dict[str, float]:
    hexes = [p.get("colorHex") for p in parts if p.get("colorHex")]
    colored = [h for h in hexes if not neutral(h)]
    worst = 1.0
    if len(colored) > 1:
        for i in range(len(colored)):
            for j in range(i + 1, len(colored)):
                gap = hue_gap(hsl(colored[i])["h"], hsl(colored[j])["h"])
                if gap < 18:
                    v = 0.96
                elif gap < 50:
                    v = 0.9
                elif gap > 150:
                    v = 0.74
                elif gap > 100:
                    v = 0.44
                else:
                    v = 0.3
                worst = min(worst, v)
    if len(colored) > 1:
        base = worst * 0.84 if len(colored) >= 3 else worst
    else:
        base = 0.92

    lights = [hsl(h)["l"] for h in hexes]
    # Ohne Farbwerte ergibt Math.max(...[]) minus unendlich, mit einem
    # kaputten Wert NaN. Beide Male sind die Vergleiche falsch und base
    # bleibt unveraendert.
    spread = js_max(lights) - js_min(lights)
    if spread < 0.07:
        base *= 0.88
    if spread > 0.55:
        base = min(1, base * 1.05)
    return {"score": base, "worst": worst}


def bold_count(parts: list[Item]) -> int:
    return len([
        p for p in parts
        if p.get("pattern") and p.get("pattern") != "uni"
        and (p.get("patternScale") == "groß" or p.get("pattern") == "kariert")
    ])


def s_pattern(parts: list[Item]) -> float:
    bold = bold_count(parts)
    any_patterned = len([p for p in parts if p.get("pattern") and p.get("pattern") != "uni"])
    if bold > 1:
        return 0.12
    if bold == 1 and any_patterned > 2:
        return 0.48
    return 0.84 if any_patterned == 0 else 1


def s_texture(parts: list[Item]) -> float:
    t = [p.get("texture") for p in parts if p.get("texture")]
    if len(t) < 2:
        return 0.85
    u = len(set(t))
    if u == 1:
        return 0.74
    return 0.88 if u >= 3 else 1


def s_shoes(shoe: Item, bottom: Item) -> float:
    w = _or(shoe.get("shoeWeight"), "normal")
    v = vol(bottom)
    if v >= 2.5:
        return 1 if w == "chunky" else (0.82 if w == "normal" else 0.42)
    if v <= 1:
        return 0.62 if w == "chunky" else 0.92
    return 0.9


def s_formality(parts: list[Item], target: float) -> float:
    v = [_or(p.get("formality"), 3) for p in parts if not is_acc(p)]
    if not v:
        # Nur Accessoires: in JS ergibt Math.max(...[]) - Math.min(...[])
        # minus unendlich und der Mittelwert NaN, die Bewertung wird NaN und
        # damit nie ausgewaehlt. build() erzeugt diesen Zustand nie, weil
        # jede Kombination ein Oberteil oder Kleid enthaelt.
        return float("nan")
    spread = max(v) - min(v)
    mean = sum(v) / len(v)
    head = 1 if spread <= 1 else (0.56 if spread <= 2 else 0.16)
    return head * 0.55 + max(0, 1 - abs(mean - target) / 2.5) * 0.45


def need(t: float) -> float:
    if t >= 25:
        return 3
    if t >= 18:
        return 5
    if t >= 12:
        return 7
    if t >= 5:
        return 9
    return 11.5


def warmth_sum(parts: list[Item]) -> float:
    return sum(
        _or(p.get("warmth"), 3) for p in parts
        if not is_acc(p) or p.get("subcategory") in HEAD_WARM
    )


def s_warmth(parts: list[Item], t: float) -> float:
    return max(0, 1 - abs(warmth_sum(parts) - need(t)) / 5.5)


def _now_ms() -> float:
    return datetime.now(timezone.utc).timestamp() * 1000


def _parse_ms(value: Any) -> float | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp() * 1000


def s_fresh(parts: list[Item], now_ms: float | None = None) -> float:
    now = _now_ms() if now_ms is None else now_ms
    out = []
    for p in parts:
        last = p.get("lastWorn")
        if not last:
            out.append(1.0)
            continue
        ms = _parse_ms(last)
        if ms is None:
            # new Date("kaputt") ergibt NaN, jeder Vergleich ist falsch,
            # in JS greift dann der letzte Zweig.
            out.append(1.0)
            continue
        d = (now - ms) / 86400000
        if d < 2:
            out.append(0.12)
        elif d < 5:
            out.append(0.58)
        elif d < 10:
            out.append(0.88)
        else:
            out.append(1.0)
    return min(out)


def pair_key(a: str, b: str) -> str:
    return "|".join(sorted([a, b]))


def fb_factor(parts: list[Item], fb: dict) -> float:
    f = 1.0
    liked = (fb or {}).get("liked") or []
    disliked = (fb or {}).get("disliked") or []
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            k = pair_key(parts[i]["id"], parts[j]["id"])
            if k in disliked:
                f *= 0.3
            elif k in liked:
                f *= 1.12
    return min(f, 1.4)


W = {"silhouette": 0.23, "proportion": 0.15, "color": 0.16, "warmth": 0.15,
     "formality": 0.12, "shoes": 0.09, "pattern": 0.06, "texture": 0.04}
# Ohne Silhouettenvorgabe traegt die Passung zur Statur das Gewicht.
W_OPEN = {"silhouette": 0.08, "proportion": 0.30, "color": 0.16, "warmth": 0.15,
          "formality": 0.12, "shoes": 0.09, "pattern": 0.06, "texture": 0.04}


def _find(parts: list[Item], pred) -> Item | None:
    for p in parts:
        if pred(p):
            return p
    return None


def violates(parts: list[Item], ctx: dict, level: int) -> str | None:
    """Harte Ausschluesse. Was hier scheitert, wird nie vorgeschlagen."""
    top = _find(parts, lambda p: p.get("category") in ("Oberteil", "Kleid"))
    bottom = _find(parts, lambda p: p.get("category") == "Unterteil")
    shoe = _find(parts, lambda p: p.get("category") == "Schuhe")
    tol = 1 if level == 0 else (1.35 if level == 1 else 1.8)

    if top and bottom and s_silhouette(top, bottom, ctx["mode"]) == 0:
        return "Silhouette"
    if ctx["mode"] == "offen" and top and bottom \
            and s_proportion(top, bottom, ctx.get("body")) < 0.42 / tol:
        return "passt nicht zur Statur"
    if bold_count(parts) > 1:
        return "zwei laute Muster"
    f = [_or(p.get("formality"), 3) for p in parts if not is_acc(p)]
    # Ohne Nicht-Accessoire ergibt der Vergleich in JS minus unendlich und
    # schlaegt nie an; die leere Liste darf hier also nicht ausschliessen.
    if f and max(f) - min(f) > 2 * tol:
        return "Formalität"
    if abs(warmth_sum(parts) - need(ctx["temp"])) > 4.5 * tol:
        return "Wetter"
    if color_detail(parts)["worst"] < 0.34 / tol:
        return "Farbkonflikt"
    if shoe and bottom and s_shoes(shoe, bottom) < 0.45 / tol:
        return "Schuhgewicht"
    return None


def score(parts: list[Item], ctx: dict, now_ms: float | None = None) -> dict:
    top = _find(parts, lambda p: p.get("category") in ("Oberteil", "Kleid"))
    bottom = _find(parts, lambda p: p.get("category") == "Unterteil")
    shoe = _find(parts, lambda p: p.get("category") == "Schuhe")
    sub = {
        "silhouette": s_silhouette(top, bottom, ctx["mode"]) if (top and bottom) else 0.82,
        "proportion": s_proportion(top, bottom, ctx.get("body")) if (top and bottom) else 0.85,
        "color": color_detail(parts)["score"],
        "warmth": s_warmth(parts, ctx["temp"]),
        "formality": s_formality(parts, ctx["target"]),
        "shoes": s_shoes(shoe, bottom) if (shoe and bottom) else 0.85,
        "pattern": s_pattern(parts),
        "texture": s_texture(parts),
    }
    weights = W_OPEN if ctx["mode"] == "offen" else W
    total = sum(weights[k] * sub[k] for k in weights)
    if any(is_acc(p) for p in parts):
        total += 0.02
    total *= fb_factor(parts, ctx.get("fb") or {}) * (0.9 + 0.1 * s_fresh(parts, now_ms))
    return {"total": min(total, 1), "sub": sub}


def build(items: list[Item], ctx: dict, level: int = 0,
          now_ms: float | None = None) -> list[dict]:
    """Erzeugt alle zulaessigen Kombinationen, absteigend bewertet."""
    def by(c: str) -> list[Item]:
        return [i for i in items if i.get("category") == c and not i.get("paused")]

    tops, bottoms, dresses = by("Oberteil"), by("Unterteil"), by("Kleid")
    shoes, outers, accs = by("Schuhe"), by("Jacke"), by("Accessoire")
    need_outer = ctx["temp"] < 14
    out: list[dict] = []

    def finish(base: list[Item]) -> None:
        if not shoes:
            return
        best = None
        for sh in shoes:
            for ou in (outers if (need_outer and outers) else [None]):
                core = [*base, sh, ou] if ou else [*base, sh]
                parts = core
                if accs:
                    best_acc = None
                    for ac in accs:
                        if ctx["temp"] > 10 and ac.get("subcategory") in HEAD_WARM:
                            continue
                        cand = [*core, ac]
                        if violates(cand, ctx, level):
                            continue
                        s = score(cand, ctx, now_ms)["total"]
                        if best_acc is None or s > best_acc["s"]:
                            best_acc = {"s": s, "cand": cand}
                    if best_acc and best_acc["s"] > score(core, ctx, now_ms)["total"]:
                        parts = best_acc["cand"]
                if ctx.get("anchor") and not any(p["id"] == ctx["anchor"] for p in parts):
                    continue
                if violates(parts, ctx, level):
                    continue
                sc = score(parts, ctx, now_ms)
                if best is None or sc["total"] > best["score"]["total"]:
                    best = {"parts": parts, "score": sc}
        if best:
            out.append(best)

    for t in tops:
        for b in bottoms:
            finish([t, b])
    for d in dresses:
        finish([d])
    out.sort(key=lambda o: o["score"]["total"], reverse=True)
    return out


def top_picks(items: list[Item], ctx: dict, now_ms: float | None = None) -> dict:
    """Gestufte Lockerung: erst hart, dann toleranter, bis drei Treffer da sind."""
    level = 0
    all_results = build(items, ctx, 0, now_ms)
    while len(all_results) < 3 and level < 2:
        level += 1
        all_results = build(items, ctx, level, now_ms)
    picked: list[dict] = []
    seen: dict[str, int] = {}
    for r in all_results:
        k = r["parts"][0]["id"]
        if k in seen:
            continue
        seen[k] = 1
        picked.append(r)
        if len(picked) >= 8:
            break
    return {"picks": picked, "relaxed": level > 0, "total": len(all_results)}
