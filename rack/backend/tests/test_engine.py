"""Haelt die Schwellwerte der Regel-Engine fest.

Diese Tests sind bewusst hart gegen konkrete Zahlen geschrieben. Wenn einer
davon rot wird, wurde eine Gewichtung oder ein Schwellwert veraendert - das
darf laut Briefing Abschnitt 5 nur nach Ruecksprache passieren.
"""

from __future__ import annotations

import pytest

from app import engine as e
from app.gaps import analyse_gaps, catalog_for


# ── Bausteine ───────────────────────────────────────────────────────────

def item(**kw):
    """Ein Teil mit neutralen Vorgaben, damit jeder Test nur das setzt,
    worum es ihm geht."""
    base = {
        "id": kw.get("id", "x"),
        "name": "Teil",
        "category": "Oberteil",
        "colorHex": "#808080",
        "colorName": "grau",
        "pattern": "uni",
        "patternScale": None,
        "material": "baumwolle",
        "thickness": "mittel",
        "texture": "glatt",
        "fit": "regular",
        "warmth": 3,
        "formality": 3,
        "paused": 0,
        "lastWorn": None,
    }
    base.update(kw)
    return base


def ctx(**kw):
    base = {"temp": 16, "target": 2, "mode": "frei", "body": None,
            "gender": "männlich", "fb": {"liked": [], "disliked": []}, "anchor": None}
    base.update(kw)
    return base


# ── 1. Oversize-Oberteil mit slim-Unterteil im Modus oversize ───────────

def test_oversize_mode_schliesst_slim_unterteil_aus():
    top = item(id="t", category="Oberteil", fit="oversize")
    bottom = item(id="b", category="Unterteil", fit="slim")
    shoe = item(id="s", category="Schuhe", fit="regular", shoeWeight="normal")

    assert e.s_silhouette(top, bottom, "oversize") == 0
    assert e.violates([top, bottom, shoe], ctx(mode="oversize"), 0) == "Silhouette"


def test_silhouette_ausschluss_ueberlebt_jede_lockerung():
    """Die Silhouette ist ein harter Ausschluss ohne Toleranzfaktor.
    Auch auf der hoechsten Lockerungsstufe darf die Kombination nicht kommen."""
    top = item(id="t", category="Oberteil", fit="oversize")
    bottom = item(id="b", category="Unterteil", fit="slim")
    shoe = item(id="s", category="Schuhe", shoeWeight="normal")
    for level in (0, 1, 2):
        assert e.violates([top, bottom, shoe], ctx(mode="oversize"), level) == "Silhouette"

    picks = e.top_picks([top, bottom, shoe], ctx(mode="oversize"))
    assert picks["picks"] == []


def test_oversize_mode_erlaubt_weites_unterteil():
    top = item(id="t", category="Oberteil", fit="oversize")
    bottom = item(id="b", category="Unterteil", fit="weit")
    assert e.s_silhouette(top, bottom, "oversize") == 1


# ── 2. Zwei laute Muster ────────────────────────────────────────────────

def test_zwei_laute_muster_werden_ausgeschlossen():
    top = item(id="t", category="Oberteil", pattern="gemustert", patternScale="groß")
    bottom = item(id="b", category="Unterteil", pattern="kariert")
    shoe = item(id="s", category="Schuhe", shoeWeight="normal")

    assert e.bold_count([top, bottom, shoe]) == 2
    assert e.violates([top, bottom, shoe], ctx(), 0) == "zwei laute Muster"
    assert e.s_pattern([top, bottom, shoe]) == 0.12


def test_ein_lautes_muster_ist_erlaubt():
    top = item(id="t", category="Oberteil", pattern="kariert")
    bottom = item(id="b", category="Unterteil")
    shoe = item(id="s", category="Schuhe", shoeWeight="normal")
    assert e.bold_count([top, bottom, shoe]) == 1
    assert e.violates([top, bottom, shoe], ctx(), 0) is None


def test_musterausschluss_ignoriert_die_lockerung():
    """boldCount hat in violates() bewusst keinen Toleranzfaktor."""
    top = item(id="t", category="Oberteil", pattern="kariert")
    bottom = item(id="b", category="Unterteil", pattern="kariert")
    shoe = item(id="s", category="Schuhe", shoeWeight="normal")
    for level in (0, 1, 2):
        assert e.violates([top, bottom, shoe], ctx(), level) == "zwei laute Muster"


# ── 3. Waermesumme ausserhalb der Toleranz ──────────────────────────────

def test_waermesumme_ausserhalb_der_toleranz_wird_ausgeschlossen():
    # need(25) == 3, die Summe hier ist 10.2 -> Abweichung 7.2 > 4.5
    top = item(id="t", category="Oberteil", warmth=5, formality=3)
    bottom = item(id="b", category="Unterteil", warmth=3, formality=3)
    shoe = item(id="s", category="Schuhe", warmth=2.2, formality=3, shoeWeight="normal")
    parts = [top, bottom, shoe]

    assert e.need(25) == 3
    assert e.warmth_sum(parts) == pytest.approx(10.2)
    assert e.violates(parts, ctx(temp=25), 0) == "Wetter"


def test_waermetoleranz_staffelt_sich_mit_der_lockerung():
    # Abweichung exakt 5.6: bei Stufe 0 (4.5) und 1 (6.075) unterschiedlich
    top = item(id="t", category="Oberteil", warmth=4.4, formality=3)
    bottom = item(id="b", category="Unterteil", warmth=2.2, formality=3)
    shoe = item(id="s", category="Schuhe", warmth=2, formality=3, shoeWeight="normal")
    parts = [top, bottom, shoe]

    assert e.warmth_sum(parts) == pytest.approx(8.6)
    assert e.need(25) == 3
    assert e.violates(parts, ctx(temp=25), 0) == "Wetter"     # 5.6 > 4.5
    assert e.violates(parts, ctx(temp=25), 1) is None          # 5.6 < 6.075


def test_waermebedarf_stufen():
    assert [e.need(t) for t in (30, 25, 20, 18, 14, 12, 7, 5, -3)] == \
        [3, 3, 5, 5, 7, 7, 9, 9, 11.5]


def test_kopfwaerme_zaehlt_mit_andere_accessoires_nicht():
    top = item(id="t", category="Oberteil", warmth=3)
    muetze = item(id="m", category="Accessoire", subcategory="Mütze", warmth=2)
    uhr = item(id="u", category="Accessoire", subcategory="Uhr", warmth=0.4)
    assert e.warmth_sum([top, muetze, uhr]) == pytest.approx(5)


# ── 4. Wollpullover mit langen Aermeln, reproduzierbar ──────────────────

def test_wollpullover_lange_aermel_ergibt_denselben_waermewert():
    pulli = {
        "name": "Strickpullover", "subcategory": "Pullover", "category": "Oberteil",
        "thickness": "dick", "material": "Wolle", "sleeve": "lang", "fit": "weit",
        "pattern": "uni", "texture": "strukturiert",
    }
    # 0.9 + 2*1.1 (dick) + 1.4 (wolle) + 0.5 (lange Aermel) = 5.0
    assert e.derive(pulli) == {"warmth": 5.0, "formality": 3.5}
    # zweimal aufgerufen identisch, und unabhaengig von der Schreibweise
    assert e.derive(pulli) == e.derive({**pulli, "material": "wolle"})


def test_derive_kurze_aermel_geben_einen_halben_punkt_weniger():
    pulli = {"category": "Oberteil", "thickness": "dick", "material": "wolle",
             "sleeve": "lang", "name": "Pullover"}
    kurz = {**pulli, "sleeve": "kurz"}
    assert e.derive(pulli)["warmth"] - e.derive(kurz)["warmth"] == pytest.approx(0.5)


def test_derive_deckelt_und_bodent():
    dick = e.derive({"category": "Jacke", "thickness": "dick", "material": "daune",
                     "name": "Daunenjacke"})
    assert dick["warmth"] == 5          # 2.2 + 2.8 + 2 = 7.0, gedeckelt auf 5
    duenn = e.derive({"category": "Accessoire", "subcategory": "Uhr", "thickness": "dünn",
                      "material": "stahl", "name": "Uhr"})
    # Rohwert 0.4, aber erst auf halbe Schritte gerundet (0.5) und dann
    # gedeckelt - genau die Reihenfolge aus rack.jsx.
    assert duenn["warmth"] == 0.5


def test_derive_letztes_warm_wort_gewinnt():
    """In rack.jsx bricht die Schleife ueber WARM_WORDS nicht ab.
    Bei 'Wolle-Leinen' zaehlt deshalb leinen, nicht wolle."""
    a = e.derive({"category": "Oberteil", "thickness": "mittel",
                  "material": "wolle leinen", "name": "Teil"})
    b = e.derive({"category": "Oberteil", "thickness": "mittel",
                  "material": "leinen", "name": "Teil"})
    assert a["warmth"] == b["warmth"]


def test_derive_formalitaets_modifikatoren():
    hemd = {"category": "Oberteil", "name": "Hemd", "thickness": "dünn",
            "material": "baumwolle", "fit": "regular", "pattern": "uni"}
    assert e.derive(hemd)["formality"] == 4.5          # 4.4 -> 4.5
    assert e.derive({**hemd, "pattern": "logo"})["formality"] == 3.5      # -0.7
    assert e.derive({**hemd, "fit": "oversize"})["formality"] == 4.0      # -0.4
    assert e.derive({**hemd, "texture": "glänzend"})["formality"] == 5.0  # +0.4, gedeckelt


def test_js_round_rundet_halbe_nach_oben():
    """Pythons round() rundet zur geraden Zahl. Die Engine braucht die
    JavaScript-Regel, sonst kippen die halben Schritte in derive()."""
    assert e.js_round(4.5) == 5
    assert e.js_round(5.5) == 6
    assert e.js_round(-0.5) == 0
    assert round(4.5) == 4          # zur Erinnerung, warum js_round existiert


# ── Farbmathematik ──────────────────────────────────────────────────────

def test_hsl_grundwerte():
    assert e.hsl("#000000") == {"h": 0.0, "s": 0.0, "l": 0.0}
    assert e.hsl("#ffffff")["l"] == 1.0
    rot = e.hsl("#ff0000")
    assert rot["h"] == pytest.approx(0) and rot["s"] == pytest.approx(1)
    assert e.hsl("#00ff00")["h"] == pytest.approx(120)
    assert e.hsl("#0000ff")["h"] == pytest.approx(240)
    assert e.hsl(None)["l"] == 0.5
    assert e.hsl("#ab")["l"] == 0.5      # zu kurz, JS steigt frueh aus
    # "kaputt" ist lang genug fuer den Ausstieg, parseInt macht daraus NaN
    assert e.hsl("kaputt")["l"] != e.hsl("kaputt")["l"]


def test_neutral_erkennt_unbunt_und_extreme_helligkeit():
    assert e.neutral("#808080")     # kaum Saettigung
    assert e.neutral("#050505")     # zu dunkel
    assert e.neutral("#fafafa")     # zu hell
    assert not e.neutral("#c8542f")


def test_hue_gap_nimmt_den_kurzen_weg():
    assert e.hue_gap(10, 350) == 20
    assert e.hue_gap(0, 180) == 180
    assert e.hue_gap(200, 20) == 180


def test_farbkonflikt_wird_ausgeschlossen():
    # zwei bunte Farben mit Abstand zwischen 50 und 100 Grad -> worst 0.3
    top = item(id="t", category="Oberteil", colorHex="#cc2200")      # 10 Grad
    bottom = item(id="b", category="Unterteil", colorHex="#aacc00")  # 70 Grad
    shoe = item(id="s", category="Schuhe", colorHex="#222222", shoeWeight="normal")
    detail = e.color_detail([top, bottom, shoe])
    assert detail["worst"] == 0.3
    assert e.violates([top, bottom, shoe], ctx(), 0) == "Farbkonflikt"
    # bei voller Lockerung greift 0.34/1.8 = 0.189
    assert e.violates([top, bottom, shoe], ctx(), 2) is None


def test_color_detail_ohne_farbwerte():
    """Ohne colorHex ergibt Math.max(...[]) - Math.min(...[]) in JS
    -Infinity. Der Vergleich mit 0.07 trifft dann zu, die Spreizungs-
    strafe greift also auch ohne jede Farbe."""
    parts = [item(id="a", colorHex=None), item(id="b", colorHex=None)]
    assert e.color_detail(parts) == {"score": pytest.approx(0.92 * 0.88), "worst": 1.0}


def test_kaputter_farbwert_faerbt_auf_nan_statt_auf_ersatzwerte():
    """parseInt("zz", 16) ist NaN, und Math.max faerbt weiter. Ein Teil mit
    kaputtem colorHex gilt deshalb nicht als neutral und die Helligkeits-
    korrektur faellt aus - beides anders als bei einem Ersatzwert."""
    assert e.neutral("#zzzzzz") is False
    kaputt = e.hsl("#zzzzzz")
    assert all(isinstance(v, float) and v != v for v in kaputt.values())
    parts = [item(id="a", colorHex="#zzzzzz"), item(id="b", colorHex="#808080")]
    assert e.color_detail(parts) == {"score": 0.92, "worst": 1.0}


# ── Proportion und Silhouette ───────────────────────────────────────────

def test_proportion_koerpermodifikatoren():
    # Longline zu weitem Unterteil: Grundwert 0.7, bei 170 cm Faktor 0.72.
    # Bewusst ein Fall unterhalb der Deckelung, sonst verschluckt min(1, ...)
    # den Modifikator und der Test prueft nichts.
    top = item(category="Oberteil", length="longline")
    bottom = item(category="Unterteil", fit="weit", length="lang", rise="mid")
    ohne = e.s_proportion(top, bottom, None)
    klein = e.s_proportion(top, bottom, {"height": 170})
    assert ohne == pytest.approx(0.7)
    assert klein == pytest.approx(0.7 * 0.72)

    gross = e.s_proportion(top, bottom, {"height": 190})
    assert gross == pytest.approx(0.7 * 1.06)
    lange_beine = e.s_proportion(top, bottom, {"height": 180, "torso": "lange Beine"})
    assert lange_beine == pytest.approx(0.7 * 1.08)


def test_proportion_tiefer_bund_bestraft_kleine_koerpergroesse():
    top = item(category="Oberteil", length="hüftlang")
    bottom = item(category="Unterteil", fit="regular", length="lang", rise="low")
    assert e.s_proportion(top, bottom, {"height": 170}) == pytest.approx(0.58 * 0.84)


def test_offener_modus_schliesst_ueber_die_statur_aus():
    """Ohne Silhouettenvorgabe entscheidet die Proportion, und sie kann
    hart ausschliessen."""
    top = item(id="t", category="Oberteil", length="longline")
    bottom = item(id="b", category="Unterteil", fit="regular", length="shorts", rise="mid")
    shoe = item(id="s", category="Schuhe", shoeWeight="normal")
    assert e.s_proportion(top, bottom, None) == pytest.approx(0.28)
    assert e.violates([top, bottom, shoe], ctx(mode="offen", temp=25), 0) \
        == "passt nicht zur Statur"


def test_gewichte_summieren_sich_auf_eins():
    assert sum(e.W.values()) == pytest.approx(1.0)
    assert sum(e.W_OPEN.values()) == pytest.approx(1.0)
    # Im offenen Modus traegt die Proportion das Gewicht, nicht die Silhouette
    assert e.W_OPEN["proportion"] > e.W["proportion"]
    assert e.W_OPEN["silhouette"] < e.W["silhouette"]


# ── Schuhe, Textur, Formalitaet ─────────────────────────────────────────

def test_schuhgewicht_zu_weiter_hose():
    weit = item(category="Unterteil", fit="weit")
    schmal = item(category="Unterteil", fit="slim")
    assert e.s_shoes(item(shoeWeight="chunky"), weit) == 1
    assert e.s_shoes(item(shoeWeight="filigran"), weit) == 0.42
    assert e.s_shoes(item(shoeWeight="chunky"), schmal) == 0.62


def test_filigraner_schuh_zu_weiter_hose_wird_ausgeschlossen():
    top = item(id="t", category="Oberteil", fit="oversize")
    bottom = item(id="b", category="Unterteil", fit="weit")
    shoe = item(id="s", category="Schuhe", shoeWeight="filigran")
    assert e.violates([top, bottom, shoe], ctx(), 0) == "Schuhgewicht"


def test_formalitaetsspreizung_wird_ausgeschlossen():
    top = item(id="t", category="Oberteil", formality=5)
    bottom = item(id="b", category="Unterteil", formality=2.5)
    shoe = item(id="s", category="Schuhe", formality=3, shoeWeight="normal")
    # Spreizung 2.5: Stufe 0 erlaubt 2.0, Stufe 1 erlaubt 2.7
    assert e.violates([top, bottom, shoe], ctx(), 0) == "Formalität"
    assert e.violates([top, bottom, shoe], ctx(), 1) is None


def test_textur_einheitlich_ist_schlechter_als_gemischt():
    gleich = [item(texture="glatt"), item(texture="glatt")]
    gemischt = [item(texture="glatt"), item(texture="strukturiert")]
    drei = [item(texture="glatt"), item(texture="strukturiert"), item(texture="robust")]
    assert e.s_texture(gleich) == 0.74
    assert e.s_texture(gemischt) == 1
    assert e.s_texture(drei) == 0.88
    assert e.s_texture([item(texture="glatt")]) == 0.85


# ── Frische und Feedback ────────────────────────────────────────────────

def test_frische_staffelt_nach_tagen():
    now = 1_000_000_000_000
    def tage(d):
        ms = now - d * 86400000
        from datetime import datetime, timezone
        stamp = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
        return e.s_fresh([item(lastWorn=stamp)], now)

    assert tage(1) == 0.12
    assert tage(3) == 0.58
    assert tage(7) == 0.88
    assert tage(20) == 1.0
    assert e.s_fresh([item(lastWorn=None)], now) == 1.0


def test_feedback_faktor_ist_gedeckelt():
    a, b, c = item(id="a"), item(id="b"), item(id="c")
    fb = {"liked": [e.pair_key("a", "b"), e.pair_key("a", "c"), e.pair_key("b", "c")],
          "disliked": []}
    assert e.fb_factor([a, b, c], fb) == pytest.approx(min(1.12 ** 3, 1.4))
    assert e.fb_factor([a, b, c], fb) == 1.4

    schlecht = {"liked": [], "disliked": [e.pair_key("a", "b")]}
    assert e.fb_factor([a, b], schlecht) == pytest.approx(0.3)


def test_pair_key_ist_richtungsunabhaengig():
    assert e.pair_key("z", "a") == e.pair_key("a", "z") == "a|z"


# ── Zusammenbau ─────────────────────────────────────────────────────────

def wardrobe():
    return [
        item(id="t1", name="Oversize Shirt", category="Oberteil", fit="oversize",
             length="hüftlang", warmth=2, formality=2, colorHex="#f2f0ec", texture="glatt"),
        item(id="t2", name="Strickpulli", category="Oberteil", fit="weit",
             length="hüftlang", warmth=4, formality=3, colorHex="#494c50",
             texture="strukturiert"),
        item(id="b1", name="Weite Hose", category="Unterteil", fit="weit", length="lang",
             rise="high", warmth=3, formality=3, colorHex="#1b1b1b", texture="glatt"),
        item(id="s1", name="Boot", category="Schuhe", warmth=2, formality=3,
             shoeWeight="chunky", colorHex="#141414", texture="robust"),
    ]


def test_build_liefert_bewertete_kombinationen_absteigend():
    out = e.build(wardrobe(), ctx(temp=12))
    assert len(out) == 2
    assert out[0]["score"]["total"] >= out[1]["score"]["total"]
    assert all(0 <= o["score"]["total"] <= 1 for o in out)


def test_build_ohne_schuhe_liefert_nichts():
    ohne = [i for i in wardrobe() if i["category"] != "Schuhe"]
    assert e.build(ohne, ctx()) == []


def test_pausierte_teile_tauchen_nicht_auf():
    items = wardrobe()
    for i in items:
        if i["id"] == "t1":
            i["paused"] = 1
    out = e.build(items, ctx(temp=12))
    assert all(not any(p["id"] == "t1" for p in o["parts"]) for o in out)


def test_ankerteil_erzwingt_seine_anwesenheit():
    out = e.build(wardrobe(), ctx(temp=12, anchor="t2"))
    assert out and all(any(p["id"] == "t2" for p in o["parts"]) for o in out)


def test_top_picks_dedupliziert_nach_erstem_teil_und_deckelt_bei_acht():
    picks = e.top_picks(wardrobe(), ctx(temp=12))["picks"]
    erste = [p["parts"][0]["id"] for p in picks]
    assert len(erste) == len(set(erste))
    assert len(picks) <= 8


def test_top_picks_lockert_erst_wenn_zu_wenige_da_sind():
    # Genau eine zulaessige Kombination -> die Engine lockert bis Stufe 2
    knapp = [
        item(id="t", category="Oberteil", fit="oversize", warmth=3, formality=3),
        item(id="b", category="Unterteil", fit="weit", warmth=3, formality=3),
        item(id="s", category="Schuhe", shoeWeight="chunky", warmth=2, formality=3),
    ]
    res = e.top_picks(knapp, ctx(temp=12))
    assert res["relaxed"] is True
    assert len(res["picks"]) == 1


def test_jacke_kommt_erst_unter_vierzehn_grad_dazu():
    items = [*wardrobe(),
             item(id="j1", name="Parka", category="Jacke", fit="oversize", warmth=4,
                  formality=3, colorHex="#4a4f3a", texture="robust")]
    warm = e.build(items, ctx(temp=20))
    kalt = e.build(items, ctx(temp=8))
    assert all(not any(p["category"] == "Jacke" for p in o["parts"]) for o in warm)
    assert any(any(p["category"] == "Jacke" for p in o["parts"]) for o in kalt)


def test_muetze_nur_bis_zehn_grad():
    items = [*wardrobe(),
             item(id="m", name="Mütze", category="Accessoire", subcategory="Mütze",
                  warmth=2, formality=2, colorHex="#191919", texture="strukturiert")]
    warm = e.build(items, ctx(temp=16))
    assert all(not any(p["id"] == "m" for p in o["parts"]) for o in warm)


# ── Lueckenanalyse ──────────────────────────────────────────────────────

def test_catalog_unterscheidet_nach_geschlecht():
    m = {c["name"] for c in catalog_for("männlich")}
    w = {c["name"] for c in catalog_for("weiblich")}
    assert "Cargohose, dunkelgrün" in m and "Cargohose, dunkelgrün" not in w
    assert "Loafer, schwarz" in w and "Loafer, schwarz" not in m
    assert "Sneaker, weiß" in m and "Sneaker, weiß" in w


def test_gaps_liefert_bestand_waisen_und_kandidaten():
    res = analyse_gaps(wardrobe(), ctx(temp=12))
    assert res["bestand"]["Oberteil"] == 2
    assert res["bestand"]["Schuhe"] == 1
    assert len(res["kandidaten"]) <= 8
    assert len(res["waisen"]) <= 6
    # nach gemessenem Zugewinn sortiert
    gains = [k["neueOutfits"] for k in res["kandidaten"]]
    assert gains == sorted(gains, reverse=True)


def test_gaps_kandidaten_bringen_messbaren_zugewinn():
    res = analyse_gaps(wardrobe(), ctx(temp=12))
    assert res["kandidaten"][0]["neueOutfits"] >= 1
    assert all(0 <= k["bestePunkte"] <= 100 for k in res["kandidaten"])


def test_leerer_schrank_bringt_die_analyse_nicht_um():
    res = analyse_gaps([], ctx())
    assert res["guteOutfits"] == 0
    assert res["waisen"] == []
    assert all(k["neueOutfits"] == 0 for k in res["kandidaten"])
