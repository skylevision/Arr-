"""Prueft den Bildweg: Hochladen, Freistellen, Vorschlagskarte, Speichern.

Erzeugt sich ein Testfoto selbst, damit der Lauf ohne Zutun funktioniert.
Ohne API-Schluessel bleiben die Felder leer, das Freistellen laeuft
trotzdem - genau das wird hier gemessen.

Aufruf:  docker exec rack python /tmp/smoke_bilder.py
"""

import io
import json
import time
import urllib.request
import uuid

from PIL import Image, ImageDraw

BASE = "http://127.0.0.1:8099/api"
ok = True


def check(label, condition, detail=""):
    global ok
    ok = ok and bool(condition)
    print(f"  [{'ok ' if condition else 'FEHLT'}] {label}{' — ' + str(detail) if detail else ''}")


def testfoto(seed: int) -> bytes:
    """Ein Kleidungsstueck auf hellem Untergrund, wie in der Fotoanleitung."""
    img = Image.new("RGB", (900, 1100), (238, 236, 232))
    d = ImageDraw.Draw(img)
    farbe = [(40, 44, 52), (120, 60, 45), (60, 80, 110)][seed % 3]
    # Rumpf
    d.rounded_rectangle([300, 300, 600, 850], radius=30, fill=farbe)
    # Aermel
    d.polygon([(300, 320), (180, 480), (240, 540), (300, 430)], fill=farbe)
    d.polygon([(600, 320), (720, 480), (660, 540), (600, 430)], fill=farbe)
    # Halsausschnitt
    d.ellipse([405, 280, 495, 340], fill=(238, 236, 232))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def multipart(files):
    grenze = uuid.uuid4().hex
    body = b""
    for i, data in enumerate(files):
        body += f"--{grenze}\r\n".encode()
        body += (f'Content-Disposition: form-data; name="fotos"; '
                 f'filename="test{i}.jpg"\r\n').encode()
        body += b"Content-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
    body += f"--{grenze}--\r\n".encode()
    return body, f"multipart/form-data; boundary={grenze}"


print("== Erfassung von drei Fotos ==")
fotos = [testfoto(i) for i in range(3)]
body, ctype = multipart(fotos)
req = urllib.request.Request(BASE + "/ingest", data=body, method="POST")
req.add_header("Content-Type", ctype)
start = time.time()
with urllib.request.urlopen(req, timeout=300) as r:
    job = json.load(r)
check("Vorgang gestartet", job["gesamt"] == 3, job["job"])

zustand = None
while time.time() - start < 300:
    with urllib.request.urlopen(BASE + f"/ingest/{job['job']}", timeout=30) as r:
        zustand = json.load(r)
    if zustand["status"] == "fertig":
        break
    time.sleep(1)

dauer = time.time() - start
check("alle Fotos verarbeitet", zustand["status"] == "fertig" and zustand["fertig"] == 3,
      f"{dauer:.1f} s für 3 Fotos, also {dauer / 3:.1f} s pro Stück")

eintraege = zustand["eintraege"]
check("jedes Foto liefert eine Prüfkarte", len(eintraege) == 3)
check("Freistellung hat gegriffen", all(e["cutout"] for e in eintraege),
      f"{sum(1 for e in eintraege if e['cutout'])} von 3 freigestellt")
check("freigestellte Bilder sind PNG mit Transparenz",
      all(e["mediaType"] == "image/png" for e in eintraege if e["cutout"]))

import base64
bild = base64.b64decode(eintraege[0]["bild"])
img = Image.open(io.BytesIO(bild))
check("Bild ist quadratisch zugeschnitten", img.width == img.height, f"{img.width}x{img.height}")
check("Bild hat einen Alphakanal", img.mode == "RGBA", img.mode)
ecke = img.convert("RGBA").getpixel((2, 2))
check("Hintergrund ist wirklich weg", ecke[3] == 0, f"Alpha in der Ecke: {ecke[3]}")

print("\n== Bestätigen und speichern ==")
e0 = eintraege[0]
attrs = dict(e0["attrs"])
attrs.update({"name": "Testpullover", "category": "Oberteil", "fit": "oversize",
              "length": "hüftlang", "thickness": "dick", "material": "wolle",
              "sleeve": "lang", "colorHex": "#282c34", "colorName": "dunkelgrau",
              "pattern": "uni", "texture": "strukturiert"})
req = urllib.request.Request(BASE + "/items", method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req, json.dumps({
        "attrs": attrs, "bild": e0["bild"], "mediaType": e0["mediaType"],
        "cutout": e0["cutout"]}).encode(), timeout=60) as r:
    gespeichert = json.load(r)
check("Teil gespeichert", bool(gespeichert["id"]), gespeichert["name"])
check("Wärme gerechnet, nicht geschätzt", gespeichert["warmth"] == 5.0, gespeichert["warmth"])
check("Bildpfad gesetzt", bool(gespeichert["imagePath"]), gespeichert["imagePath"])

with urllib.request.urlopen(BASE + f"/images/{gespeichert['id']}", timeout=30) as r:
    daten = r.read()
    cache = r.headers.get("Cache-Control", "")
check("Bild wird ausgeliefert", len(daten) > 1000, f"{len(daten) / 1024:.0f} kB")
check("mit Cache-Header", "max-age" in cache, cache)

print("\n" + ("ALLES GRÜN" if ok else "ES GIBT FEHLER"))
raise SystemExit(0 if ok else 1)
