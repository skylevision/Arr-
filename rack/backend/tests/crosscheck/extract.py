"""Schneidet die Engine aus rack.jsx.vorlage zu einem lauffaehigen Modul.

Der Prototyp ist eine React-Datei ohne Exporte. Fuer die Gegenprobe brauchen
wir die reine Fachlogik als Modul: die Vokabulare am Dateianfang und den
Block von der Farbmathematik bis zum Ende von analyseGaps.

  python extract.py            # schreibt engine.mjs
"""

import pathlib
import re

HIER = pathlib.Path(__file__).resolve().parent
QUELLE = HIER.parents[2] / "rack.jsx.vorlage"

EXPORTE = [
    "derive", "hsl", "neutral", "hueGap", "colorDetail", "boldCount",
    "sSilhouette", "sProportion", "sPattern", "sTexture", "sShoes", "sFormality",
    "need", "warmthSum", "sWarmth", "sFresh", "pairKey", "fbFactor",
    "violates", "score", "build", "topPicks", "analyseGaps", "catalogFor",
    "W", "W_OPEN", "vol",
]


def schnitt(text: str, start: str, ende: str) -> str:
    i = text.index(start)
    j = text.index(ende, i)
    return text[i:j]


def main() -> None:
    if not QUELLE.is_file():
        raise SystemExit(f"Vorlage nicht gefunden: {QUELLE}")
    src = QUELLE.read_text(encoding="utf-8")

    # Vokabulare: von CATEGORIES bis zum Ende der OCCASIONS-Liste.
    vokabular = schnitt(src, "const CATEGORIES =", "\nconst META")
    # Fachlogik: von der Farbmathematik bis zum Ende von analyseGaps.
    logik = schnitt(src, "/* ─────────────────────── Farbe und abgeleitete Werte",
                    "/* ──────────────────────────── Modellzugriff")

    ziel = HIER / "engine.mjs"
    ziel.write_text(
        "/* Automatisch erzeugt aus rack.jsx.vorlage - nicht von Hand ändern.\n"
        "   Erzeugen mit: python extract.py */\n\n"
        + vokabular + "\n" + logik
        + "\nexport { " + ", ".join(EXPORTE) + " };\n",
        encoding="utf-8")

    zeilen = ziel.read_text(encoding="utf-8").count("\n")
    fehlend = [name for name in EXPORTE
               if not re.search(rf"\b(function|const)\s+{re.escape(name)}\b",
                                ziel.read_text(encoding="utf-8"))]
    print(f"engine.mjs geschrieben, {zeilen} Zeilen")
    if fehlend:
        raise SystemExit(f"FEHLT im Ausschnitt: {fehlend}")
    print("alle erwarteten Funktionen enthalten")


if __name__ == "__main__":
    main()
