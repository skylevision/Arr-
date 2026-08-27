"""Weist nach, dass das Ganzkoerperfoto nicht gespeichert wird.

Prueft nach einem echten Aufruf von /api/body-analysis, dass im
Datenverzeichnis keine neue Datei liegt und weder Dateiname noch Bilddaten
im Log auftauchen (Briefing Abschnitt 4 und Abnahmekriterium 7).

Aufruf:  docker exec rack python /tmp/smoke_koerperfoto.py
"""

import hashlib
import io
import json
import os
import urllib.request
import uuid

from PIL import Image, ImageDraw

BASE = "http://127.0.0.1:8099/api"
DATA = "/data"
DATEINAME = "GEHEIMER-DATEINAME-c7f19a4b.jpg"
ok = True


def check(label, condition, detail=""):
    global ok
    ok = ok and bool(condition)
    print(f"  [{'ok ' if condition else 'FEHLT'}] {label}{' — ' + str(detail) if detail else ''}")


def dateien():
    """Jede Datei unter /data mit Groesse, ausser den fluechtigen SQLite-Dateien."""
    out = {}
    for wurzel, _, namen in os.walk(DATA):
        for n in namen:
            p = os.path.join(wurzel, n)
            if p.endswith(("-wal", "-shm")):
                continue
            try:
                out[p] = os.path.getsize(p)
            except OSError:
                pass
    return out


def koerperfoto() -> bytes:
    """Eine schematische stehende Figur. Kein echtes Foto noetig."""
    img = Image.new("RGB", (700, 1300), (232, 232, 230))
    d = ImageDraw.Draw(img)
    haut = (198, 162, 130)
    d.ellipse([310, 120, 390, 215], fill=haut)          # Kopf
    d.rounded_rectangle([300, 215, 400, 700], radius=30, fill=(70, 80, 110))
    d.rounded_rectangle([225, 240, 300, 640], radius=24, fill=haut)
    d.rounded_rectangle([400, 240, 475, 640], radius=24, fill=haut)
    d.rounded_rectangle([305, 700, 345, 1150], radius=20, fill=(50, 55, 70))
    d.rounded_rectangle([355, 700, 395, 1150], radius=20, fill=(50, 55, 70))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


print("== Zustand vor dem Aufruf ==")
vorher = dateien()
print(f"  {len(vorher)} Dateien unter {DATA}")

foto = koerperfoto()
pruefsumme = hashlib.sha256(foto).hexdigest()
print(f"  Testfoto: {len(foto) / 1024:.0f} kB, sha256 {pruefsumme[:16]}…")

print("\n== Aufruf von /api/body-analysis ==")
grenze = uuid.uuid4().hex
body = (f"--{grenze}\r\n".encode()
        + f'Content-Disposition: form-data; name="foto"; filename="{DATEINAME}"\r\n'.encode()
        + b"Content-Type: image/jpeg\r\n\r\n" + foto + b"\r\n"
        + f"--{grenze}--\r\n".encode())
req = urllib.request.Request(BASE + "/body-analysis", data=body, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={grenze}")
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.load(r)
    print(f"  Antwort: build={res['build']}, torso={res['torso']}, "
          f"confidence={res.get('confidence')}")
    check("Antwort meldet ausdrücklich, dass nichts gespeichert wurde",
          res.get("gespeichert") is False)
except urllib.error.HTTPError as e:
    print(f"  Aufruf nicht möglich ({e.code}). Der Speichertest gilt trotzdem.")

print("\n== Zustand nach dem Aufruf ==")
nachher = dateien()
neu = {p: g for p, g in nachher.items() if p not in vorher}
groesser = {p: (vorher[p], g) for p, g in nachher.items()
            if p in vorher and g > vorher[p]}
check("keine neue Datei im Datenverzeichnis", not neu, neu or "keine")
check("keine Bilddatei gewachsen",
      not any("images" in p for p in groesser), groesser or "keine")

print("\n== Suche nach Spuren ==")
treffer = []
for wurzel, _, namen in os.walk(DATA):
    for n in namen:
        p = os.path.join(wurzel, n)
        if DATEINAME.encode() in open(p, "rb").read() if os.path.getsize(p) < 50_000_000 else False:
            treffer.append(p)
check("Dateiname taucht in keiner Datei unter /data auf", not treffer, treffer or "keine")

# Die Bilddaten selbst duerfen nirgends liegen.
kopf = foto[:2048]
rest = []
for wurzel, _, namen in os.walk(DATA):
    for n in namen:
        p = os.path.join(wurzel, n)
        try:
            if os.path.getsize(p) > 1000 and kopf in open(p, "rb").read():
                rest.append(p)
        except OSError:
            pass
check("Bilddaten liegen nirgends unter /data", not rest, rest or "keine")

print("\n" + ("ALLES GRÜN" if ok else "ES GIBT FEHLER"))
print("Das Log wird von außen geprüft: docker logs rack | grep GEHEIMER-DATEINAME")
raise SystemExit(0 if ok else 1)
