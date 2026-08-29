"""Vergleicht den Python-Port mit dem Original rack.jsx.

Seit dem 29.08.2026 weicht der Port an einer Stelle absichtlich ab: das
Material zaehlt mit (Freigabe des Auftraggebers, siehe README). Diese
Abweichungen sind erwartet und werden getrennt ausgewiesen, damit die
Gegenprobe fuer alles Uebrige scharf bleibt — violates(), die
Farbmathematik, Silhouette, Proportion, Muster und Schuhe pruefen sich
weiterhin gegen das Original.

Was bewusst abweicht:
  score.sub.material  gibt es in rack.jsx nicht
  score.raw           gibt es in rack.jsx nicht (ungedeckelter Wert, nur
                      zum Sortieren — siehe engine.score)
  score.total         andere Gewichte, weil material 0.05 bekommen hat
  picks.total         Folge davon; ausserdem kann die Reihenfolge
                      abweichen, weil ungedeckelt sortiert wird
  derive.warmth       Vokabular statt Substring-Suche; betrifft nur
                      Materialien, die rack.jsx falsch zuordnete
                      ("Bio-Baumwolle" -> Wolle) oder gar nicht kannte
"""

import json
import math
import re

a = json.load(open("mine.json", encoding="utf-8"))
b = json.load(open("theirs.json", encoding="utf-8"))
EPS = 1e-9
diffs = []
erwartet = []

# Pfade, an denen die Abweichung gewollt ist.
ERWARTET = [
    re.compile(r"^score\[\d+\]\[\d+\]\.sub\.material$"),
    re.compile(r"^score\[\d+\]\[\d+\]\.raw$"),
    re.compile(r"^score\[\d+\]\[\d+\]\.total$"),
    re.compile(r"^picks\[\d+\]\.picks\[\d+\]\.total$"),
    re.compile(r"^derive\[\d+\]\.warmth$"),
]


def gewollt(path: str) -> bool:
    return any(r.match(path) for r in ERWARTET)


def cmp(pa, pb, path):
    if isinstance(pa, (int, float)) and isinstance(pb, (int, float)) \
            and not isinstance(pa, bool) and not isinstance(pb, bool):
        if math.isnan(pa) and math.isnan(pb):
            return
        if abs(pa - pb) > EPS:
            (erwartet if gewollt(path) else diffs).append((path, pa, pb))
        return
    if isinstance(pa, dict) and isinstance(pb, dict):
        for k in set(pa) | set(pb):
            if k not in pa or k not in pb:
                # JSON.stringify laesst undefined-Felder weg, Python schreibt
                # null. Das ist dieselbe Aussage, keine Abweichung.
                if pa.get(k) is None and pb.get(k) is None:
                    continue
                eintrag = (path + "." + k, pa.get(k, "<fehlt>"), pb.get(k, "<fehlt>"))
                (erwartet if gewollt(eintrag[0]) else diffs).append(eintrag)
            else:
                cmp(pa[k], pb[k], path + "." + k)
    elif isinstance(pa, list) and isinstance(pb, list):
        if len(pa) != len(pb):
            diffs.append((path + ".len", len(pa), len(pb)))
            return
        for i, (x, y) in enumerate(zip(pa, pb)):
            cmp(x, y, f"{path}[{i}]")
    elif pa != pb:
        diffs.append((path, pa, pb))


for key in ("derive", "score", "picks", "gaps", "violates"):
    cmp(a[key], b[key], key)

print(f"derive      : {len(a['derive'])} Faelle")
print(f"score       : {sum(len(x) for x in a['score'])} Kombinationen aus {len(a['score'])} Schraenken")
print(f"topPicks    : {len(a['picks'])} Schraenke, {sum(len(p['picks']) for p in a['picks'])} Vorschlaege")
print(f"analyseGaps : {len(a['gaps'])} Schraenke")
print(f"violates    : {len(a['violates'])} Faelle")
print("---")
if erwartet:
    print(f"{len(erwartet)} erwartete Abweichungen (Material, siehe Kopf dieser Datei)")
if not diffs:
    print("IDENTISCH: keine unerwartete Abweichung zwischen dem Python-Port und rack.jsx")
else:
    print(f"{len(diffs)} UNERWARTETE ABWEICHUNGEN, erste 25:")
    for d in diffs[:25]:
        print("  ", d)
raise SystemExit(1 if diffs else 0)
