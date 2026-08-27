"""Prueft den Filter fuer entbehrliche Accessoires.

Das Modell darf melden, dass ein Accessoire in einem Outfit nichts
beitraegt, weil man es gar nicht sieht. Es darf dabei aber weder tragende
Stuecke aussortieren noch Teile nennen, die es im Outfit nicht gibt.
"""

from __future__ import annotations

from app.curation import entbehrliche_accessoires


def teil(name, category="Accessoire", **kw):
    return {"id": name.lower(), "name": name, "category": category, **kw}


PARTS = [
    teil("Braunes Sweatshirt", "Oberteil"),
    teil("Dunkelblaue Jeans", "Unterteil"),
    teil("New Balance 2002R", "Schuhe"),
    teil("Uhr, silber"),
    teil("Lederner Gürtel"),
]


def test_accessoire_aus_dem_outfit_wird_uebernommen():
    assert entbehrliche_accessoires({"weglassen": ["Uhr, silber"]}, PARTS) == ["Uhr, silber"]


def test_schreibweise_und_leerzeichen_spielen_keine_rolle():
    assert entbehrliche_accessoires({"weglassen": ["  uhr, SILBER "]}, PARTS) == ["Uhr, silber"]


def test_tragende_stuecke_lassen_sich_nicht_aussortieren():
    """Ein Oberteil, eine Hose oder Schuhe sind keine Zugabe. Selbst wenn
    das Modell sie nennt, bleiben sie im Outfit."""
    for name in ("Braunes Sweatshirt", "Dunkelblaue Jeans", "New Balance 2002R"):
        assert entbehrliche_accessoires({"weglassen": [name]}, PARTS) == []


def test_erfundene_teile_werden_verworfen():
    assert entbehrliche_accessoires({"weglassen": ["Sonnenbrille", "Kette"]}, PARTS) == []


def test_mehrere_und_doppelte_nennungen():
    res = entbehrliche_accessoires(
        {"weglassen": ["Uhr, silber", "Lederner Gürtel", "Uhr, silber"]}, PARTS)
    assert res == ["Uhr, silber", "Lederner Gürtel"]


def test_fehlendes_oder_kaputtes_feld_ergibt_leere_liste():
    assert entbehrliche_accessoires({}, PARTS) == []
    assert entbehrliche_accessoires({"weglassen": None}, PARTS) == []
    assert entbehrliche_accessoires({"weglassen": []}, PARTS) == []
    assert entbehrliche_accessoires({"weglassen": [None, 42]}, PARTS) == []


def test_outfit_ohne_accessoire():
    ohne = [p for p in PARTS if p["category"] != "Accessoire"]
    assert entbehrliche_accessoires({"weglassen": ["Uhr, silber"]}, ohne) == []
