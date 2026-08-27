import json
import math

a = json.load(open("mine.json", encoding="utf-8"))
b = json.load(open("theirs.json", encoding="utf-8"))
EPS = 1e-9
diffs = []


def cmp(pa, pb, path):
    if isinstance(pa, (int, float)) and isinstance(pb, (int, float)) \
            and not isinstance(pa, bool) and not isinstance(pb, bool):
        if math.isnan(pa) and math.isnan(pb):
            return
        if abs(pa - pb) > EPS:
            diffs.append((path, pa, pb))
        return
    if isinstance(pa, dict) and isinstance(pb, dict):
        for k in set(pa) | set(pb):
            if k not in pa or k not in pb:
                # JSON.stringify laesst undefined-Felder weg, Python schreibt
                # null. Das ist dieselbe Aussage, keine Abweichung.
                if pa.get(k) is None and pb.get(k) is None:
                    continue
                diffs.append((path + "." + k, pa.get(k, "<fehlt>"), pb.get(k, "<fehlt>")))
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
if not diffs:
    print("IDENTISCH: keine Abweichung zwischen dem Python-Port und rack.jsx")
else:
    print(f"{len(diffs)} ABWEICHUNGEN, erste 25:")
    for d in diffs[:25]:
        print("  ", d)
