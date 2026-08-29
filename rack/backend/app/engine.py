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
# Pflegehinweise. Bewusst grob: die genauen Symbole stehen im Etikett,
# hier geht es nur um die Frage, was zusammen in eine Maschine darf.
CARE_LABELS = ["30 Grad", "40 Grad", "60 Grad", "Handwäsche",
               "Reinigung", "nicht in den Trockner"]

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


# ── Material ────────────────────────────────────────────────────────────
#
# Bis August 2026 war material ein freies Textfeld, das nur ueber einen
# Substring-Vergleich in WARM_WORDS wirkte. Das ging in zwei Richtungen
# schief: "Kunstleder" traf "leder" und erbte dessen Waermebonus, und
# gaengige Materialien wie Cord fehlten in der Liste ganz und zaehlten
# damit wie Baumwolle. MATERIALS ist jetzt das verbindliche Vokabular,
# normalize_material() bildet Schreibweisen und Mehrfachangaben darauf ab.

MATERIALS = [
    "Baumwolle", "Cord", "Denim", "Leinen", "Jersey", "Strick", "Wolle",
    "Kaschmir", "Fleece", "Daune", "Leder", "Wildleder", "Kunstleder",
    "Seide", "Satin", "Viskose", "Synthetik", "Mesh",
]

# Schreibweisen, Fremdwoerter und Handelsnamen auf das Vokabular abbilden.
# Geprueft wird von den laengsten Begriffen zu den kuerzesten (siehe
# _MATERIAL_NEEDLES). Das ist keine Kosmetik: "wolle" steckt in
# "baumwolle", "leder" in "kunstleder" und "wildleder", "strick" in
# "grobstrick". Wer hier nach Listenreihenfolge sucht, macht aus
# Bio-Baumwolle Wolle — genau der Substring-Fehler, den diese
# Umstellung beseitigen soll.
MATERIAL_SYNONYMS: list[tuple[str, str]] = [
    ("kunstleder", "Kunstleder"), ("lederimitat", "Kunstleder"),
    ("veganes leder", "Kunstleder"), ("kunststoffleder", "Kunstleder"),
    ("wildleder", "Wildleder"), ("veloursleder", "Wildleder"),
    ("rauleder", "Wildleder"), ("suede", "Wildleder"), ("nubuk", "Wildleder"),
    ("cord", "Cord"), ("kord", "Cord"), ("corduroy", "Cord"), ("rippsamt", "Cord"),
    ("denim", "Denim"), ("jeansstoff", "Denim"), ("jeans", "Denim"),
    ("kaschmir", "Kaschmir"), ("cashmere", "Kaschmir"),
    ("merino", "Wolle"), ("schurwolle", "Wolle"), ("wolle", "Wolle"),
    ("walk", "Wolle"), ("tweed", "Wolle"), ("filz", "Wolle"),
    ("fleece", "Fleece"), ("teddy", "Fleece"), ("sherpa", "Fleece"),
    ("daune", "Daune"), ("down", "Daune"), ("federn", "Daune"),
    ("grobstrick", "Strick"), ("feinstrick", "Strick"), ("gestrickt", "Strick"),
    ("strick", "Strick"),
    ("leinen", "Leinen"), ("linnen", "Leinen"), ("flachs", "Leinen"),
    ("seide", "Seide"), ("silk", "Seide"),
    ("satin", "Satin"),
    ("viskose", "Viskose"), ("rayon", "Viskose"), ("modal", "Viskose"),
    ("lyocell", "Viskose"), ("tencel", "Viskose"), ("bambus", "Viskose"),
    ("mesh", "Mesh"), ("netz", "Mesh"),
    ("jersey", "Jersey"), ("sweat", "Jersey"), ("frottee", "Jersey"),
    ("polyester", "Synthetik"), ("nylon", "Synthetik"), ("polyamid", "Synthetik"),
    ("elasthan", "Synthetik"), ("acryl", "Synthetik"), ("kunstfaser", "Synthetik"),
    ("synthetik", "Synthetik"), ("synthetisch", "Synthetik"),
    ("softshell", "Synthetik"), ("gore-tex", "Synthetik"), ("goretex", "Synthetik"),
    ("baumwolle", "Baumwolle"), ("cotton", "Baumwolle"), ("popeline", "Baumwolle"),
    ("canvas", "Baumwolle"), ("twill", "Baumwolle"), ("musselin", "Baumwolle"),
    ("leder", "Leder"),
]

_MATERIAL_LOOKUP = {m.lower(): m for m in MATERIALS}
_MATERIAL_SPLIT = re.compile(r"[/,;+&]| und | mit ")
# Laengster Begriff zuerst, damit ein spezifischer Treffer einen
# allgemeineren Teilstring immer schlaegt.
_MATERIAL_NEEDLES = sorted(MATERIAL_SYNONYMS, key=lambda p: -len(p[0]))


def normalize_material(value: Any) -> str | None:
    """Freitext auf das MATERIALS-Vokabular abbilden.

    Nimmt auch Mehrfachangaben wie "Wildleder/Mesh" entgegen und liefert
    das erste erkannte Material. Unbekanntes ergibt None statt eines
    Rateversuchs — ein leeres Feld ist ehrlicher als ein falscher Bonus.
    """
    if not value:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in _MATERIAL_LOOKUP:
        return _MATERIAL_LOOKUP[text]
    parts = [p.strip() for p in _MATERIAL_SPLIT.split(text) if p.strip()]
    for candidate in [*parts, text]:
        if candidate in _MATERIAL_LOOKUP:
            return _MATERIAL_LOOKUP[candidate]
        for needle, target in _MATERIAL_NEEDLES:
            if needle in candidate:
                return target
    return None


def split_materials(value: Any) -> tuple[str | None, str | None]:
    """Zerlegt "Wildleder/Mesh" in Haupt- und Nebenmaterial."""
    if not value:
        return None, None
    parts = [p.strip() for p in _MATERIAL_SPLIT.split(str(value)) if p.strip()]
    seen: list[str] = []
    for part in parts or [str(value)]:
        m = normalize_material(part)
        if m and m not in seen:
            seen.append(m)
    if not seen:
        return normalize_material(value), None
    return seen[0], (seen[1] if len(seen) > 1 else None)


# Waermebeitrag je Material. Die elf urspruenglichen Eintraege sind
# unveraendert aus rack.jsx uebernommen; ergaenzt wurden nur Materialien,
# die vorher gar nicht vorkamen und deshalb wie Baumwolle zaehlten
# (Freigabe 29.08.2026).
WARM_WORDS = {
    "wolle": 1.4, "kaschmir": 1.4, "fleece": 1.3, "daune": 2, "strick": 1,
    "leder": 0.6, "denim": 0.4, "baumwolle": 0, "jersey": 0,
    "leinen": -0.6, "seide": -0.4,
    # Ergaenzt 29.08.2026
    "cord": 0.7,        # geripptes Gewebe, spuerbar waermer als glatte Baumwolle
    "wildleder": 0.6,   # wie Leder; stand vorher nur zufaellig ueber "leder" drin
    "kunstleder": 0.3,  # winddicht, aber duenner und ohne die Fasermasse
    "satin": -0.3,      # glatt und kuehl, knapp ueber Seide
    "viskose": -0.2,    # faellt kuehl, weniger extrem als Leinen
    "synthetik": 0.1,   # Polyester und Co. isolieren leicht, aber kaum
    "mesh": -0.8,       # bewusst luftdurchlaessig
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
    # Seit 29.08.2026 ueber das Vokabular statt per Substring-Suche: frueher
    # gewann hier der letzte Treffer der Schleife, weshalb "Bio-Baumwolle"
    # ueber das Teilwort "wolle" den Wollbonus bekam und Cord gar keinen.
    material = normalize_material(a.get("material"))
    bonus = WARM_WORDS.get(material.lower(), 0.0) if material else 0.0
    mat = (material or str(a.get("material") or "")).lower()

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


# ── Waesche ─────────────────────────────────────────────────────────────
#
# Was getragen wurde, geht von selbst in die Waesche und kommt von selbst
# zurueck. Umgesetzt ohne Hintergrundjob: beim Tragen wird ein Datum
# gesetzt, und "verfuegbar" wird bei jeder Abfrage neu ausgerechnet. Das
# ueberlebt Neustarts, kann nicht auseinanderlaufen und braucht keinen
# Cron im Container.
#
# Nicht jedes Teil gehoert nach einmal Tragen in die Waesche: Jacken,
# Schuhe, Guertel und Uhren nicht. Nur was direkt auf der Haut liegt.
LAUNDRY_CATEGORIES = {"Oberteil", "Unterteil", "Kleid"}


def goes_to_laundry(item: Item) -> bool:
    return item.get("category") in LAUNDRY_CATEGORIES


def laundry_remaining(item: Item, now_ms: float | None = None) -> float:
    """Verbleibende Waeschetage, 0 wenn das Teil verfuegbar ist."""
    until = item.get("laundryUntil")
    if not until:
        return 0.0
    ms = _parse_ms(until)
    if ms is None:
        # Kaputtes Datum darf kein Teil dauerhaft sperren.
        return 0.0
    now = _now_ms() if now_ms is None else now_ms
    return max(0.0, (ms - now) / 86400000)


def is_available(item: Item, now_ms: float | None = None) -> bool:
    """Steht das Teil fuer Vorschlaege zur Verfuegung?

    Drei Gruende dagegen: von Hand pausiert, eingemottet (Saison), oder
    noch in der Waesche.
    """
    if item.get("paused") or item.get("archived"):
        return False
    return laundry_remaining(item, now_ms) <= 0


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


# Materialien, die nur in ihrer Jahreszeit ueberzeugen. Das ist bewusst
# knapp gehalten: nur Stoffe, bei denen die Fehlbesetzung offensichtlich
# ist. Ein Baumwollhemd ist ganzjaehrig richtig und steht deshalb hier
# nicht.
SOMMER_MATERIAL = {"Leinen", "Mesh"}
WINTER_MATERIAL = {"Wolle", "Kaschmir", "Fleece", "Daune"}

# Materialien mit starkem Eigencharakter. Zweimal dasselbe davon in einem
# Outfit liest sich als Anzug aus einem Stoff — Cord auf Cord, Leder auf
# Leder. Baumwolle und Denim fehlen hier absichtlich: Jeans zum
# Baumwollshirt ist der Normalfall, nicht der Fehler.
PRAEGNANTES_MATERIAL = {"Cord", "Leder", "Wildleder", "Kunstleder",
                        "Fleece", "Daune", "Satin", "Seide"}
GLAENZENDES_MATERIAL = {"Satin", "Seide"}


def materials_of(parts: list[Item]) -> list[str]:
    """Normalisierte Materialien der tragenden Teile, Accessoires ausgenommen.

    Accessoires bleiben draussen, weil ein Lederguertel zur Lederjacke
    kein Stilfehler ist — der Guertel ist Beiwerk, keine Flaeche.
    """
    out = []
    for p in parts:
        if is_acc(p):
            continue
        m = normalize_material(p.get("material"))
        if m:
            out.append(m)
    return out


def s_material(parts: list[Item], t: float) -> float:
    """Passt der Stoff zur Temperatur und zu den anderen Stoffen?

    Neu am 29.08.2026 (Freigabe des Auftraggebers). Bewusst nur ein
    weiches Kriterium: es sortiert Vorschlaege um, schliesst aber nichts
    aus. violates() bleibt unberuehrt, damit kein Outfit verschwindet,
    nur weil ein Material unbekannt oder grenzwertig ist.

    Ohne erkanntes Material gibt es 0.85 — denselben neutralen Wert, den
    s_texture bei zu duenner Datenlage liefert. Ein Teil ohne Materialangabe
    darf ein Outfit weder retten noch versenken.
    """
    mats = materials_of(parts)
    if not mats:
        return 0.85

    s = 1.0
    for m in mats:
        if m in SOMMER_MATERIAL:
            if t < 12:
                s = min(s, 0.45)
            elif t < 18:
                s = min(s, 0.75)
        if m in WINTER_MATERIAL:
            if t > 24:
                s = min(s, 0.45)
            elif t > 20:
                s = min(s, 0.75)

    praegnant = [m for m in mats if m in PRAEGNANTES_MATERIAL]
    if len(praegnant) != len(set(praegnant)):
        s *= 0.72

    if len([m for m in mats if m in GLAENZENDES_MATERIAL]) >= 2:
        s *= 0.8

    return max(0.0, min(1.0, s))


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


# Gewichte. Am 29.08.2026 kam "material" mit 0.05 dazu (Freigabe des
# Auftraggebers). Die fuenf Punkte wurden den groessten Posten entnommen,
# damit die Rangfolge der bestehenden Kriterien erhalten bleibt:
# silhouette 0.23->0.22, proportion 0.15->0.14, color 0.16->0.15,
# warmth 0.15->0.14, formality 0.12->0.11; shoes, pattern und texture
# blieben unangetastet. Beide Saetze summieren sich weiterhin auf 1.0.
W = {"silhouette": 0.22, "proportion": 0.14, "color": 0.15, "warmth": 0.14,
     "formality": 0.11, "shoes": 0.09, "pattern": 0.06, "texture": 0.04,
     "material": 0.05}
# Ohne Silhouettenvorgabe traegt die Passung zur Statur das Gewicht.
W_OPEN = {"silhouette": 0.08, "proportion": 0.28, "color": 0.15, "warmth": 0.14,
          "formality": 0.11, "shoes": 0.09, "pattern": 0.06, "texture": 0.04,
          "material": 0.05}


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
        "material": s_material(parts, ctx["temp"]),
    }
    weights = W_OPEN if ctx["mode"] == "offen" else W
    total = sum(weights[k] * sub[k] for k in weights)
    if any(is_acc(p) for p in parts):
        total += 0.02
    total *= fb_factor(parts, ctx.get("fb") or {}) * (0.9 + 0.1 * s_fresh(parts, now_ms))
    # "total" bleibt gedeckelt wie in rack.jsx — das ist die Zahl, die
    # angezeigt wird, und sie soll zwischen 0 und 1 liegen.
    #
    # "raw" ist derselbe Wert ungedeckelt und dient nur der Sortierung.
    # Der Feedbackfaktor geht bis 1.4, deshalb reicht schon eine
    # Grundbewertung von 0.71, um an die Decke zu stossen: mit wachsendem
    # Feedback landeten immer mehr Kombinationen auf exakt 1.000 und die
    # Reihenfolge wurde beliebig. Ungedeckelt sortiert bleibt sie
    # aussagekraeftig, ohne dass sich eine sichtbare Zahl aendert.
    return {"total": min(total, 1), "raw": total, "sub": sub}


def build(items: list[Item], ctx: dict, level: int = 0,
          now_ms: float | None = None) -> list[dict]:
    """Erzeugt alle zulaessigen Kombinationen, absteigend bewertet."""
    def by(c: str) -> list[Item]:
        return [i for i in items
                if i.get("category") == c and is_available(i, now_ms)]

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
                        s = score(cand, ctx, now_ms)["raw"]
                        if best_acc is None or s > best_acc["s"]:
                            best_acc = {"s": s, "cand": cand}
                    if best_acc and best_acc["s"] > score(core, ctx, now_ms)["raw"]:
                        parts = best_acc["cand"]
                if ctx.get("anchor") and not any(p["id"] == ctx["anchor"] for p in parts):
                    continue
                if violates(parts, ctx, level):
                    continue
                sc = score(parts, ctx, now_ms)
                if best is None or sc["raw"] > best["score"]["raw"]:
                    best = {"parts": parts, "score": sc}
        if best:
            out.append(best)

    for t in tops:
        for b in bottoms:
            finish([t, b])
    for d in dresses:
        finish([d])
    out.sort(key=lambda o: o["score"]["raw"], reverse=True)
    return out


# ── Packliste ───────────────────────────────────────────────────────────

def pack_list(items: list[Item], ctx: dict, tage: int = 5,
              now_ms: float | None = None) -> dict:
    """Kleinste Teilemenge, aus der sich fuer die Reise genug Outfits bauen laesst.

    Gierig statt vollstaendig: alle Kombinationen ueber alle Teilmengen
    durchzurechnen waere exponentiell. Stattdessen wird Runde fuer Runde
    das beste noch nicht gepackte Outfit genommen; die Teile, die es
    braucht, wandern in den Koffer, und weil sie dort bleiben, kosten sie
    in den folgenden Runden nichts mehr. Genau so packt man auch von Hand
    — ein Oberteil mehr, das zu allem passt, statt eines zweiten
    vollstaendigen Outfits.

    Rueckgabe enthaelt die Teile, die Outfits und was wofuer gebraucht wird.
    """
    tage = max(1, min(30, int(tage)))
    verfuegbar = [i for i in items if is_available(i, now_ms) and not i.get("archived")]

    koffer: dict[str, Item] = {}
    outfits: list[dict] = []
    benutzt: set[str] = set()

    for _ in range(tage):
        kandidaten = build(verfuegbar, ctx, 0, now_ms)
        if not kandidaten:
            # Ohne harte Treffer die gelockerte Stufe versuchen, sonst
            # bleibt die Liste bei einem duennen Schrank einfach leer.
            kandidaten = build(verfuegbar, ctx, 2, now_ms)
        if not kandidaten:
            break

        # Bestes Outfit, gewichtet nach dem, was es zusaetzlich kostet:
        # ein Outfit aus bereits gepackten Teilen ist bares Gewicht wert.
        bestes, bester_wert = None, -1.0
        for k in kandidaten:
            ids = [p["id"] for p in k["parts"]]
            if tuple(sorted(ids)) in benutzt:
                continue
            neu = sum(1 for i in ids if i not in koffer)
            # +1 im Nenner, damit ein Outfit ohne neue Teile nicht durch
            # Null teilt und trotzdem klar vorne liegt.
            wert = k["score"]["raw"] / (1 + neu)
            if wert > bester_wert:
                bestes, bester_wert = k, wert
        if bestes is None:
            break

        ids = [p["id"] for p in bestes["parts"]]
        benutzt.add(tuple(sorted(ids)))
        for p in bestes["parts"]:
            koffer.setdefault(p["id"], p)
        outfits.append({"itemIds": ids, "punkte": bestes["score"]["total"]})

    # Wofuer wird jedes Teil gebraucht? Macht die Liste beim Packen lesbar.
    einsatz: dict[str, int] = {}
    for o in outfits:
        for i in o["itemIds"]:
            einsatz[i] = einsatz.get(i, 0) + 1

    return {
        "tage": tage,
        "teile": [{"id": i, "name": koffer[i].get("name"),
                   "kategorie": koffer[i].get("category"),
                   "fuerOutfits": einsatz.get(i, 0)}
                  for i in sorted(koffer, key=lambda x: -einsatz.get(x, 0))],
        "outfits": outfits,
        "genug": len(outfits) >= tage,
    }


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
