"""Die HTTP-Schnittstelle.

Grundsatz: die Regel-Engine laeuft immer, das Modell ist eine Zugabe.
Jeder Endpunkt, der das Modell benutzt, hat einen Rueckfallweg auf die
reine Rechnung, damit die App auch ohne Schluessel bedienbar bleibt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Body, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from . import ai, db, images, weather
from . import engine as E
from . import prompts as P
from .config import settings
from .curation import entbehrliche_accessoires
from .gaps import analyse_gaps, catalog_for

log = logging.getLogger("rack.api")
router = APIRouter(prefix="/api")

MAX_UPLOAD = 25 * 1024 * 1024
MAX_FILES = 25


# ── Kontext fuer die Engine ─────────────────────────────────────────────

def build_ctx(occasion: str = "Alltag", temp: float = 16,
              anchor: str | None = None, regen: float = 0.0,
              wind: float = 0.0) -> dict[str, Any]:
    profile = db.get_profile()
    target = next((o["f"] for o in E.OCCASIONS if o["key"] == occasion), 2)
    return {
        "temp": temp,
        # Regen in mm, Wind in km/h — gehen in die Materialbewertung ein.
        # Ohne Angabe null, dann verhaelt sich alles wie zuvor.
        "regen": regen,
        "wind": wind,
        "target": target,
        "mode": profile.get("silhouette") or "frei",
        "body": profile,
        "gender": profile.get("gender") or "männlich",
        "fb": db.get_feedback(),
        "anchor": anchor,
    }


# ── Gesundheit ──────────────────────────────────────────────────────────

@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    """Kurzer Zustandsbericht.

    "teile" zaehlt die der aktiven Person — vorher waren es alle, und die
    Zahl passte dann nicht zu dem, was die App anzeigt. Genau diese
    Abweichung hat verwaiste Datensaetze aufgedeckt; deshalb steht die
    Zahl jetzt auch ausdruecklich mit dabei, statt sich in einer
    Gesamtsumme zu verstecken.
    """
    db.setze_person(person_id(request))
    verwaist = db.verwaiste_datensaetze()
    return {
        "status": "ok",
        "teile": len(db.list_items()),
        "verwaist": verwaist or None,
        "ki": settings.ai_enabled,
        "modelle": {"lesen": settings.model_vision, "kuratieren": settings.model_curate}
        if settings.ai_enabled else None,
    }


@router.post("/ai-test")
def ai_test() -> dict[str, Any]:
    """Minimaler Testaufruf. Gibt den Schluessel nur maskiert zurueck."""
    if not settings.ai_enabled:
        return {"ok": False, "art": "kein_schluessel",
                "meldung": "Kein API-Schlüssel hinterlegt. Die KI-Funktionen sind aus, "
                           "die Regel-Engine läuft normal weiter."}
    return ai.ping()


# ── Personen ────────────────────────────────────────────────────────────
#
# Die aktive Person kommt als Kopfzeile X-Rack-Person oder als Parameter
# ?person=. Ohne Angabe ist es Person 1 — fuer den Einzelnutzer aendert
# sich damit nichts.

def person_id(request: Request) -> int:
    roh = request.headers.get("X-Rack-Person") or request.query_params.get("person")
    try:
        wert = int(roh) if roh else db.PERSON_DEFAULT
    except (TypeError, ValueError):
        return db.PERSON_DEFAULT
    return wert if wert > 0 else db.PERSON_DEFAULT


@router.get("/personen")
def personen() -> list[dict[str, Any]]:
    return db.list_persons()


@router.post("/personen")
def person_anlegen(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Die Person braucht einen Namen.")
    return db.add_person(name)


@router.delete("/personen/{pid}")
def person_loeschen(pid: int) -> dict[str, Any]:
    if pid == db.PERSON_DEFAULT:
        raise HTTPException(400,
                            "Die erste Person lässt sich nicht löschen — sie trägt "
                            "den Bestand, der vor der Umstellung angelegt wurde.")
    weg, bilder = db.delete_person(pid)
    if not weg:
        raise HTTPException(404, "Person nicht gefunden.")
    for pfad in bilder:
        images.delete(pfad)
    return {"geloescht": pid, "bilder": len(bilder)}


# ── Profil ──────────────────────────────────────────────────────────────

@router.get("/profile")
def read_profile(request: Request) -> dict[str, Any]:
    return db.get_profile(person_id(request))


@router.put("/profile")
def write_profile(request: Request,
                  profile: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return db.save_profile(profile, person_id(request))


@router.post("/body-analysis")
async def body_analysis(foto: UploadFile = File(...)) -> dict[str, Any]:
    """Ganzkoerperfoto auswerten.

    Das Bild wird nicht gespeichert, nicht geloggt und nicht
    zwischengespeichert. Es lebt nur als lokale Variable bis zum Ende
    dieser Funktion und wird danach verworfen (Briefing Abschnitt 4).
    Auch der Dateiname wird nicht protokolliert.
    """
    if not settings.ai_enabled:
        raise HTTPException(503, "Ohne API-Schlüssel ist die Analyse nicht möglich. "
                                 "Trag Statur und Proportion von Hand ein.")
    raw = await foto.read()
    if not raw:
        raise HTTPException(400, "Leere Datei.")
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "Das Foto ist zu groß.")
    try:
        b64, media = images.prepare_for_model(raw)
    except Exception:                              # noqa: BLE001
        raise HTTPException(400, "Das Foto konnte nicht gelesen werden.") from None
    finally:
        raw = b""

    try:
        res = ai.ask(
            [{"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}},
             {"type": "text", "text": P.BODY_PROMPT}],
            # 500 waren zu knapp bemessen: die Antwort ist zwar kurz,
            # aber das Nachdenken zaehlt gegen dasselbe Limit.
            model=settings.model_vision, max_tokens=2000, effort="low")
    except ai.AIUnavailable as exc:
        raise HTTPException(502, str(exc)) from None
    finally:
        b64 = ""

    return {
        "build": res.get("build") if res.get("build") in E.BUILDS else "normal",
        "torso": res.get("torso") if res.get("torso") in E.TORSOS else "ausgeglichen",
        "hinweis": res.get("hinweis") or "",
        "confidence": res.get("confidence", 0.5),
        "gespeichert": False,
    }


# ── Vokabular ───────────────────────────────────────────────────────────
#
# Eine Quelle fuer beide Seiten. Vorher standen dieselben Listen in
# engine.py und in constants.js; laufen sie auseinander, zeigt die
# Oberflaeche stumm "nicht gesetzt" fuer einen Wert, den das Backend
# kennt — ein Fehler, bei dem nichts kaputtgeht und deshalb niemand
# etwas merkt.

VOKABULAR: dict[str, list[str]] = {
    "kategorien": E.CATEGORIES,
    "accessoires": E.ACCESSORY_TYPES,
    "schnitte": E.FITS,
    "laengenOben": E.TOP_LEN,
    "laengenUnten": E.BOTTOM_LEN,
    "bundhoehen": E.RISES,
    "dicken": E.THICKNESS,
    "muster": E.PATTERNS,
    "musterGroessen": ["klein", "mittel", "groß"],
    "printPositionen": E.PRINT_POSITIONS,
    "materialien": E.MATERIALS,
    "oberflaechen": ["glatt", "strukturiert", "glänzend", "flauschig", "robust"],
    "aermel": ["ärmellos", "kurz", "dreiviertel", "lang"],
    "schuhgewichte": E.SHOE_WEIGHT,
    "pflege": E.CARE_LABELS,
    "staturen": E.BUILDS,
    "koerperbau": E.TORSOS,
}

# Welches Feld gegen welche Liste geprueft wird. Was hier steht, wird
# beim Speichern verworfen, wenn es nicht passt — ueber die Oberflaeche
# kann das nicht vorkommen, ueber die API schon.
FELD_VOKABULAR: dict[str, str] = {
    "category": "kategorien",
    "fit": "schnitte",
    "rise": "bundhoehen",
    "thickness": "dicken",
    "pattern": "muster",
    "patternScale": "musterGroessen",
    "printPosition": "printPositionen",
    "material": "materialien",
    "texture": "oberflaechen",
    "sleeve": "aermel",
    "shoeWeight": "schuhgewichte",
    "care": "pflege",
}


@router.get("/vocab")
def vocab() -> dict[str, Any]:
    """Alle Auswahllisten. Das Frontend zieht sie hieraus."""
    return VOKABULAR


def _pruefe_vokabular(attrs: dict[str, Any]) -> list[str]:
    """Unbekannte Werte entfernen und melden.

    Bewusst verwerfen statt ablehnen: ein einzelnes schiefes Feld soll
    nicht das ganze Teil unspeicherbar machen. Das Feld bleibt dann leer
    und faellt in der Oberflaeche auf.
    """
    verworfen = []
    for feld, liste in FELD_VOKABULAR.items():
        wert = attrs.get(feld)
        if wert in (None, ""):
            continue
        if wert not in VOKABULAR[liste]:
            verworfen.append(f"{feld}={wert!r}")
            attrs[feld] = None
    # subcategory nur bei Accessoires gegen eine feste Liste pruefen;
    # sonst ist es freie Beschreibung ("Kapuzenpullover").
    if attrs.get("category") == "Accessoire" and attrs.get("subcategory")             and attrs["subcategory"] not in E.ACCESSORY_TYPES:
        verworfen.append(f"subcategory={attrs['subcategory']!r}")
        attrs["subcategory"] = None
    return verworfen


# ── Erfassen ────────────────────────────────────────────────────────────

def _normalise_tags(attrs: dict[str, Any]) -> None:
    """Freie Schlagworte aufraeumen.

    Bewusst frei und nicht aus einer Liste: feste Kategorien passen nie
    ganz, das ist die haeufigste Kritik an solchen Apps. Gespeichert wird
    eine Kommaliste, kleingeschrieben und ohne Doppelte, damit die Suche
    zuverlaessig trifft.
    """
    if "tags" not in attrs:
        return
    roh = attrs.get("tags")
    if isinstance(roh, list):
        teile = roh
    elif isinstance(roh, str):
        teile = roh.split(",")
    else:
        attrs["tags"] = None
        return
    sauber: list[str] = []
    for t in teile:
        wert = str(t).strip().lower()
        if wert and wert not in sauber:
            sauber.append(wert)
    attrs["tags"] = ", ".join(sauber) if sauber else None


def _normalise_material(attrs: dict[str, Any]) -> None:
    """material auf das Vokabular abbilden, Zweitmaterial abspalten.

    Greift an jedem Eingang: beim Lesen durch das Modell, beim Speichern
    und beim Bearbeiten von Hand. Unbekanntes wird zu None — lieber ein
    leeres Feld als ein Material, das einen falschen Waermebonus zieht.
    """
    if "material" not in attrs:
        return
    haupt, zweit = E.split_materials(attrs.get("material"))
    attrs["material"] = haupt
    # Ein von Hand gesetztes Zweitmaterial nicht ueberschreiben, wenn die
    # Eingabe selbst keines enthielt.
    if zweit or not attrs.get("materialSecondary"):
        attrs["materialSecondary"] = zweit



_jobs: dict[str, dict[str, Any]] = {}
JOB_TTL = 3600


def _prune_jobs() -> None:
    stale = [k for k, v in _jobs.items() if time.time() - v["created"] > JOB_TTL]
    for k in stale:
        _jobs.pop(k, None)


def _read_one(data: bytes) -> dict[str, Any]:
    """Ein Bild aufbereiten und lesen lassen. Gibt einen Vorschlag zurueck,
    noch kein gespeichertes Objekt."""
    fertig = images.prepare(data, cutout=settings.cutout)
    entry: dict[str, Any] = {"bild": images.to_base64(fertig.ablage),
                             "mediaType": fertig.media_type,
                             "cutout": fertig.cutout}
    if not settings.ai_enabled:
        entry["attrs"] = {"name": "", "category": "Oberteil", "fit": "regular",
                          "pattern": "uni", "thickness": "mittel",
                          "colorHex": "#888888"}
        entry["unsicher"] = ["name", "category", "fit", "length"]
        entry["status"] = "ohne_ki"
        entry["attrs"].update(E.derive(entry["attrs"]))
        return entry

    try:
        # Bewusst die groessere Fassung: das Material ist genau das
        # Merkmal, das an der Aufloesung haengt.
        attrs = ai.ask(
            [{"type": "image",
              "source": {"type": "base64", "media_type": fertig.modell_media_type,
                         "data": images.to_base64(fertig.modell)}},
             {"type": "text", "text": P.READ_PROMPT}],
            # Fuenfzehn Felder Antwort plus Bildauswertung und Denken.
            # Der Materialteil des Prompts ist seit August laenger.
            model=settings.model_vision, max_tokens=3000, effort="low")
        entry["status"] = "fertig"
    except ai.AIUnavailable as exc:
        # Wie im Prototypen: die Karte kommt trotzdem, nur mit leeren
        # Feldern und allem als unsicher markiert.
        attrs = {"name": "", "category": "Oberteil", "fit": "regular",
                 "pattern": "uni", "thickness": "mittel", "colorHex": "#888888",
                 "unsicher": ["category", "fit", "length"]}
        entry["status"] = "fehler"
        entry["meldung"] = str(exc)

    attrs["category"] = attrs.get("category") if attrs.get("category") in E.CATEGORIES \
        else "Oberteil"
    attrs["fit"] = attrs.get("fit") if attrs.get("fit") in E.FITS else "regular"
    roh_material = attrs.get("material")
    _normalise_material(attrs)
    entry["unsicher"] = attrs.pop("unsicher", []) or []
    # Ein Material, das sich nicht zuordnen liess, gehoert auf die
    # Pruefkarte — sonst speichert man stillschweigend ein leeres Feld.
    if roh_material and not attrs.get("material") and "material" not in entry["unsicher"]:
        entry["unsicher"].append("material")
    # Waerme und Formalitaet werden gerechnet, nie vom Modell uebernommen.
    attrs.pop("warmth", None)
    attrs.pop("formality", None)
    attrs.update(E.derive(attrs))
    entry["attrs"] = attrs
    return entry


@router.post("/ingest")
async def ingest(request: Request, fotos: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Startet die Erfassung und liefert eine Job-Nummer.

    Der Fortschritt kommt ueber /api/ingest/{job}/events als Server-Sent
    Events oder ueber /api/ingest/{job} per Abfrage.
    """
    _prune_jobs()
    if not fotos:
        raise HTTPException(400, "Keine Fotos übergeben.")
    if len(fotos) > MAX_FILES:
        raise HTTPException(413, f"Höchstens {MAX_FILES} Fotos auf einmal.")

    payloads = []
    for f in fotos:
        raw = await f.read()
        if not raw:
            continue
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(413, "Mindestens ein Foto ist zu groß.")
        payloads.append(raw)
    if not payloads:
        raise HTTPException(400, "Keines der Fotos konnte gelesen werden.")

    job_id = uuid.uuid4().hex[:12]
    job: dict[str, Any] = {"created": time.time(), "art": "ingest", "gesamt": len(payloads),
                           "fertig": 0, "eintraege": [], "status": "laeuft",
                           "fehler": None}
    _jobs[job_id] = job

    async def run() -> None:
        for raw in payloads:
            try:
                entry = await asyncio.to_thread(_read_one, raw)
            except Exception as exc:               # noqa: BLE001
                log.warning("Bild konnte nicht verarbeitet werden: %s", type(exc).__name__)
                entry = {"status": "fehler", "meldung": "Das Foto konnte nicht "
                                                        "verarbeitet werden.",
                         "attrs": None, "bild": None, "unsicher": []}
            job["eintraege"].append(entry)
            job["fertig"] += 1
        job["status"] = "fertig"

    asyncio.create_task(run())
    return {"job": job_id, "gesamt": len(payloads)}


def _job_view(job: dict[str, Any]) -> dict[str, Any]:
    return {"status": job["status"], "gesamt": job["gesamt"],
            "fertig": job["fertig"], "eintraege": job["eintraege"]}


@router.get("/ingest/{job_id}")
def ingest_status(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Unbekannter Vorgang.")
    return _job_view(job)


@router.get("/ingest/{job_id}/events")
async def ingest_events(job_id: str) -> StreamingResponse:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Unbekannter Vorgang.")

    async def stream():
        sent = -1
        while True:
            if job["fertig"] != sent or job["status"] == "fertig":
                sent = job["fertig"]
                payload = {"status": job["status"], "gesamt": job["gesamt"],
                           "fertig": sent}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if job["status"] == "fertig":
                yield f"event: ende\ndata: {json.dumps(_job_view(job), ensure_ascii=False)}\n\n"
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ── Teile ───────────────────────────────────────────────────────────────

@router.get("/items")
def list_items(request: Request) -> list[dict[str, Any]]:
    return db.list_items(person_id(request))


@router.post("/items")
def create_item(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Bestaetigtes Teil speichern. Das Bild kommt als base64 mit."""
    attrs = dict(payload.get("attrs") or payload)
    bild = payload.get("bild")
    media = payload.get("mediaType") or "image/jpeg"

    attrs.pop("bild", None)
    attrs.pop("mediaType", None)
    attrs.pop("attrs", None)
    attrs.pop("unsicher", None)

    item_id = attrs.get("id") or db.new_id()
    attrs["id"] = item_id
    attrs.setdefault("cutout", payload.get("cutout", False))
    _normalise_material(attrs)
    _normalise_tags(attrs)
    verworfen = _pruefe_vokabular(attrs)
    if verworfen:
        log.info("Unbekannte Werte verworfen: %s", ", ".join(verworfen))

    # Nur ohne Handmarkierung neu rechnen.
    computed = E.derive(attrs)
    if not attrs.get("warmthManual"):
        attrs["warmth"] = computed["warmth"]
    if not attrs.get("formalityManual"):
        attrs["formality"] = computed["formality"]

    if bild:
        import base64
        try:
            raw = base64.b64decode(bild)
        except Exception:                          # noqa: BLE001
            raise HTTPException(400, "Das Bild war nicht lesbar.") from None
        attrs["imagePath"] = images.store(item_id, raw, media)

    attrs["wearCount"] = attrs.get("wearCount") or 0
    attrs["paused"] = attrs.get("paused") or False
    return db.insert_item(attrs)


@router.patch("/items/{item_id}")
def patch_item(item_id: str, patch: dict[str, Any] = Body(...)) -> dict[str, Any]:
    current = db.get_item(item_id)
    if not current:
        raise HTTPException(404, "Teil nicht gefunden.")

    merged = {**current, **patch}
    if "material" in patch:
        _normalise_material(merged)
    if "tags" in patch:
        _normalise_tags(merged)
    # Wer ein Teil von Hand wieder freigibt, meint auch die Waesche —
    # sonst drueckt man "verfügbar" und es bleibt trotzdem gesperrt.
    if patch.get("paused") is False and current.get("paused"):
        merged["laundryUntil"] = None
    _pruefe_vokabular(merged)
    # Wer einen Wert von Hand setzt, markiert ihn damit als manuell.
    if "warmth" in patch and patch["warmth"] != current.get("warmth"):
        merged["warmthManual"] = True
    if "formality" in patch and patch["formality"] != current.get("formality"):
        merged["formalityManual"] = True

    computed = E.derive(merged)
    if not merged.get("warmthManual"):
        merged["warmth"] = computed["warmth"]
    if not merged.get("formalityManual"):
        merged["formality"] = computed["formality"]

    merged.pop("id", None)
    return db.update_item(item_id, merged)


@router.delete("/items/{item_id}")
def remove_item(item_id: str) -> dict[str, Any]:
    current = db.get_item(item_id)
    if not current:
        raise HTTPException(404, "Teil nicht gefunden.")
    for feld in ("imagePath", "labelPath"):
        if current.get(feld):
            images.delete(current[feld])
    db.delete_item(item_id)
    return {"geloescht": item_id}


@router.get("/images/{item_id}")
def get_image(item_id: str) -> FileResponse:
    item = db.get_item(item_id)
    if not item or not item.get("imagePath"):
        raise HTTPException(404, "Kein Bild.")
    path = images.path_for(item["imagePath"])
    if not path:
        raise HTTPException(404, "Kein Bild.")
    media = "image/png" if path.suffix == ".png" else "image/jpeg"
    # Der Dateiname enthaelt die Item-ID, ein Bild aendert sich nie unter
    # derselben ID. Deshalb darf der Browser es lange behalten.
    return FileResponse(path, media_type=media,
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


# ── Vorschlaege ─────────────────────────────────────────────────────────

def _payload_for_model(picks: list[dict]) -> list[dict[str, Any]]:
    return [{
        "nr": i,
        "punkte": round(p["score"]["total"] * 100),
        # kategorie gehoert dazu: "laenge" bedeutet bei einem Oberteil
        # etwas anderes als bei einer Hose, und ohne die Einordnung raet
        # das Modell, was "hueftlang" gerade heisst.
        "teile": [{"id": x.get("id"), "name": x.get("name"),
                   "kategorie": x.get("category"), "art": x.get("subcategory"),
                   "farbe": x.get("colorName"), "hex": x.get("colorHex"),
                   "schnitt": x.get("fit"), "laenge": x.get("length"),
                   "bund": x.get("rise"), "aermel": x.get("sleeve"),
                   "muster": x.get("pattern"),
                   "printPosition": x.get("printPosition"),
                   "material": x.get("material")}
                  for x in p["parts"]],
    } for i, p in enumerate(picks)]


def _cached_trends() -> dict[str, Any] | None:
    cached = db.get_trends()
    if cached:
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"])
            if age < timedelta(days=settings.trend_max_age_days):
                return cached["payload"]
        except ValueError:
            pass
    if not settings.ai_enabled:
        return cached["payload"] if cached else None
    try:
        res = ai.ask([{"type": "text", "text": P.trends_prompt(db.get_profile())}],
                     # Mit Websuche: die Recherche laeuft im selben Zug,
                     # ihre Zwischenschritte zaehlen mit. 1500 war dafuer
                     # deutlich zu wenig.
                     model=settings.model_curate, max_tokens=8000, search=True)
        return db.save_trends(res)["payload"]
    except ai.AIUnavailable:
        return cached["payload"] if cached else None


@router.get("/trends")
def get_trends(erneuern: bool = Query(False)) -> dict[str, Any]:
    """Die hinterlegte Einordnung — standardmäßig nur lesend.

    Ohne "erneuern" wird nichts nachgeholt. Der Abruf kostet eine
    Websuche, und die soll nicht dadurch ausgelöst werden, dass jemand
    eine Ansicht öffnet. Erneuert wird von selbst beim Kuratieren, sobald
    der Stand älter ist als RACK_TREND_MAX_AGE_DAYS.
    """
    if erneuern:
        _cached_trends()
    eintrag = db.get_trends()
    if not eintrag:
        return {"trends": None, "geholt": None, "alter": None,
                "maxAlterTage": settings.trend_max_age_days}
    return {"trends": eintrag["payload"],
            "geholt": eintrag["fetched_at"],
            "alter": _tage_her(eintrag["fetched_at"]),
            "maxAlterTage": settings.trend_max_age_days}


def _outfit_result(payload: dict[str, Any],
                   melden: Callable[..., None] = lambda *a, **k: None) -> dict[str, Any]:
    """Die Vorschlagslogik, in Phasen zerlegt.

    `melden` bekommt jede Phase gemeldet, damit die Oberfläche einen
    ehrlichen Fortschritt zeigen kann. Die Phasen sind echt und nicht
    geschätzt: rechnen, Trends nachschlagen, kuratieren. Die Rangfolge der
    Engine wird mitgeschickt, sobald sie steht — der Nutzer sieht damit
    sofort Ergebnisse, statt auf den Modellaufruf zu warten.
    """
    occasion = payload.get("anlass") or "Alltag"
    temp = float(payload.get("temp", 16))
    anchor = payload.get("anker")

    schritte = 3 if settings.ai_enabled else 1
    melden("rechnen", "Kombinationen rechnen", schritt=0, gesamt=schritte)

    items = db.list_items()
    ctx = build_ctx(occasion, temp, anchor,
                    float(payload.get("regen") or 0),
                    float(payload.get("wind") or 0))
    result = E.top_picks(items, ctx)
    picks = result["picks"]
    if not picks:
        leer = {"outfits": [], "gelockert": False,
                "meldung": "Keine zulässige Kombination gefunden. Es fehlen "
                           "Oberteile, Unterteile oder Schuhe."}
        melden("fertig", "Nichts gefunden", schritt=schritte, gesamt=schritte)
        return leer

    def engine_only(grund: str | None = None) -> dict[str, Any]:
        return {
            "outfits": [{"titel": f"Kombination {i + 1}",
                         "begruendung": grund or "",
                         "styling": [], "weglassen": [], "trendhinweis": "",
                         "punkte": round(p["score"]["total"] * 100),
                         "teile": p["parts"], "detail": p["score"]["sub"]}
                        for i, p in enumerate(picks[:3])],
            "gelockert": result["relaxed"], "kuratiert": False,
        }

    if not settings.ai_enabled:
        fertig = engine_only("Ohne API-Schlüssel zeigt die App die Rangfolge der Engine.")
        melden("fertig", "Fertig", schritt=schritte, gesamt=schritte)
        return fertig

    # Die reine Rechnung ist da. Sie geht sofort raus, damit die Oberfläche
    # etwas zeigen kann, während das Modell noch arbeitet.
    melden("gerechnet",
           f"{result['total']} zulässige Kombinationen, "
           f"{len(picks)} zur Auswahl",
           schritt=1, gesamt=schritte, roh=engine_only())

    melden("trends", "Aktuelle Einordnung nachschlagen", schritt=1, gesamt=schritte)
    trends = _cached_trends()

    melden("kuratieren", "Kuratieren und Styling schreiben", schritt=2, gesamt=schritte)
    try:
        res = ai.ask(
            [{"type": "text",
              "text": P.curation_prompt(db.get_profile(), occasion, temp, trends,
                                        _payload_for_model(picks))}],
            # Grosszuegig, weil max_tokens auch das Nachdenken des
            # Modells abdeckt: mit 2000 brach die Antwort regelmaessig
            # mitten im JSON ab, obwohl der Text selbst kaum 700 Zeichen
            # hatte. Bezahlt wird ohnehin nur, was tatsaechlich
            # erzeugt wird — ein hoeheres Limit kostet nichts extra.
            model=settings.model_curate, max_tokens=8000, effort="medium")
    except ai.AIUnavailable as exc:
        abbruch = engine_only(f"Die Kuratierung war nicht erreichbar ({exc}). "
                              "Das ist die Rangfolge der Engine.")
        melden("fertig", "Ohne Kuratierung", schritt=schritte, gesamt=schritte)
        return abbruch

    out = []
    for a in res.get("auswahl") or []:
        nr = a.get("nr")
        if not isinstance(nr, int) or not 0 <= nr < len(picks):
            continue
        p = picks[nr]
        out.append({"titel": a.get("titel") or "Kombination",
                    "begruendung": a.get("begruendung") or "",
                    "styling": a.get("styling") or [],
                    "weglassen": entbehrliche_accessoires(a, p["parts"]),
                    "trendhinweis": a.get("trendhinweis") or "",
                    "punkte": round(p["score"]["total"] * 100),
                    "teile": p["parts"], "detail": p["score"]["sub"]})
    melden("fertig", "Fertig", schritt=schritte, gesamt=schritte)
    if not out:
        return engine_only()
    return {"outfits": out, "gelockert": result["relaxed"], "kuratiert": True}


@router.post("/outfits")
def suggest(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Vorschläge in einem Rutsch. Für Skripte und als Rückfallweg."""
    return _outfit_result(payload)


@router.post("/outfits/start")
async def suggest_start(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Startet die Vorschläge als Vorgang und liefert eine Nummer.

    Der Fortschritt kommt über /api/outfits/{job}/events oder per Abfrage
    unter /api/outfits/{job}.
    """
    _prune_jobs()
    job_id = uuid.uuid4().hex[:12]
    job: dict[str, Any] = {
        "created": time.time(), "art": "outfits", "status": "laeuft",
        "phase": "start", "text": "Wird vorbereitet", "schritt": 0, "gesamt": 3,
        "roh": None, "ergebnis": None, "ereignisse": [],
    }
    _jobs[job_id] = job

    def melden(phase: str, text: str, *, schritt: int = 0, gesamt: int = 3,
               roh: dict | None = None) -> None:
        job.update(phase=phase, text=text, schritt=schritt, gesamt=gesamt)
        if roh is not None:
            job["roh"] = roh
        # Jede Meldung wird angehaengt, nicht nur der Zustand fortgeschrieben.
        # Ein abtastender Leser wuerde sonst kurze Phasen verschlucken.
        job["ereignisse"].append({
            "phase": phase, "text": text, "schritt": schritt, "gesamt": gesamt,
            "roh": job["roh"],
        })

    async def run() -> None:
        try:
            job["ergebnis"] = await asyncio.to_thread(_outfit_result, payload, melden)
        except Exception as exc:                   # noqa: BLE001
            log.warning("Vorschläge fehlgeschlagen: %s: %s", type(exc).__name__, exc)
            job["ergebnis"] = {"outfits": [], "gelockert": False,
                               "meldung": "Die Vorschläge konnten nicht berechnet werden."}
        job["status"] = "fertig"

    asyncio.create_task(run())
    return {"job": job_id}


def _outfit_view(job: dict[str, Any]) -> dict[str, Any]:
    return {"status": job["status"], "phase": job["phase"], "text": job["text"],
            "schritt": job["schritt"], "gesamt": job["gesamt"],
            "roh": job["roh"], "ergebnis": job["ergebnis"]}


@router.get("/outfits/{job_id}")
def suggest_status(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if not job or job.get("art") != "outfits":
        raise HTTPException(404, "Unbekannter Vorgang.")
    return _outfit_view(job)


@router.get("/outfits/{job_id}/events")
async def suggest_events(job_id: str) -> StreamingResponse:
    job = _jobs.get(job_id)
    if not job or job.get("art") != "outfits":
        raise HTTPException(404, "Unbekannter Vorgang.")

    async def stream():
        # Die Warteschlange wird geleert, nicht abgetastet. Ein abtastender
        # Leser verschluckt sonst kurze Phasen, wenn zwei Meldungen dicht
        # aufeinander folgen.
        gesendet = 0
        while True:
            while gesendet < len(job["ereignisse"]):
                yield ("data: " + json.dumps(job["ereignisse"][gesendet],
                                             ensure_ascii=False) + "\n\n")
                gesendet += 1
            if job["status"] == "fertig":
                yield ("event: ende\ndata: "
                       + json.dumps(job["ergebnis"], ensure_ascii=False) + "\n\n")
                return
            await asyncio.sleep(0.2)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ── Rueckmeldung und Tragen ─────────────────────────────────────────────

@router.post("/feedback")
def feedback(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    ids = payload.get("teile") or []
    verdict = payload.get("urteil")
    if verdict not in ("liked", "disliked", None):
        raise HTTPException(400, "Urteil muss liked, disliked oder leer sein.")
    if len(ids) < 2:
        raise HTTPException(400, "Für eine Rückmeldung braucht es mindestens zwei Teile.")
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            db.set_feedback(E.pair_key(ids[i], ids[j]), verdict)
    return db.get_feedback()


@router.post("/worn")
def worn(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    ids = payload.get("teile") or []
    if not ids:
        raise HTTPException(400, "Keine Teile übergeben.")
    eintrag = db.log_outfit(ids, payload.get("anlass"), payload.get("temp"),
                            payload.get("punkte"))
    # Zurueckmelden, was dadurch in die Waesche gewandert ist — die
    # Oberflaeche sagt es in der Quittung, damit die Automatik nicht
    # unsichtbar passiert.
    gewaschen = [db.get_item(i) for i in ids]
    eintrag["waesche"] = [
        {"id": x["id"], "name": x.get("name"), "bis": x.get("laundryUntil")}
        for x in gewaschen if x and x.get("laundryUntil")
        and E.laundry_remaining(x) > 0
    ]
    eintrag["waescheTage"] = settings.laundry_days
    return eintrag


@router.post("/items/{item_id}/verfuegbar")
def wieder_verfuegbar(item_id: str) -> dict[str, Any]:
    """Waeschefrist vorzeitig beenden.

    Fuer den Fall, dass ein Teil doch nicht in die Maschine musste.
    """
    if not db.get_item(item_id):
        raise HTTPException(404, "Teil nicht gefunden.")
    return db.update_item(item_id, {"laundryUntil": None, "paused": False})


@router.get("/worn")
def worn_log(limit: int = Query(200, ge=1, le=1000)) -> list[dict[str, Any]]:
    return db.list_outfit_log(limit)


@router.get("/items/{item_id}/diagnose")
def item_diagnose(item_id: str, anlass: str = Query("Alltag"),
                  temp: float = Query(16), regen: float = Query(0),
                  wind: float = Query(0)) -> dict[str, Any]:
    """Warum taucht dieses Teil nicht in den Vorschlägen auf — und was hülfe?"""
    items = db.list_items()
    ctx = build_ctx(anlass, temp, None, regen, wind)
    res = E.diagnose(items, item_id, ctx)
    if not res.get("gefunden"):
        raise HTTPException(404, "Teil nicht gefunden.")
    # Die Gegenfrage gleich mit: welcher Zukauf würde genau diesem Teil
    # helfen? Spart einen zweiten Aufruf, und getrennt wäre die Antwort
    # ohnehin nur die halbe Auskunft.
    profil = db.get_profile()
    res["abhilfe"] = E.abhilfe(items, item_id,
                               catalog_for(profil.get("gender")), ctx)
    return res


@router.post("/items/{item_id}/etikett")
async def etikett_hochladen(item_id: str, foto: UploadFile = File(...)) -> dict[str, Any]:
    """Foto vom Waschetikett.

    Ein zweites Bild neben dem Teil selbst — die Pflegesymbole liest man
    im Zweifel lieber ab, als sie aus einer Auswahlliste zu erraten.
    Wird nicht freigestellt: es geht um Lesbarkeit, nicht um Optik.
    """
    if not db.get_item(item_id):
        raise HTTPException(404, "Teil nicht gefunden.")
    roh = await foto.read()
    if not roh:
        raise HTTPException(400, "Das Foto war leer.")
    fertig = images.prepare(roh, cutout=False)
    pfad = images.store(f"label_{item_id}", fertig.ablage, fertig.media_type)
    db.update_item(item_id, {"labelPath": pfad})
    return {"id": item_id, "labelPath": pfad}


@router.get("/items/{item_id}/etikett")
def etikett_lesen(item_id: str) -> FileResponse:
    teil = db.get_item(item_id)
    if not teil or not teil.get("labelPath"):
        raise HTTPException(404, "Zu diesem Teil gibt es kein Etikettfoto.")
    pfad = images.path_for(teil["labelPath"])
    if not pfad:
        raise HTTPException(404, "Die Bilddatei fehlt.")
    return FileResponse(pfad, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/waschgaenge")
def waschgaenge() -> dict[str, Any]:
    """Was kann zusammen in eine Maschine?

    Gruppiert wird nach dem Pflegehinweis; innerhalb einer Gruppe noch
    einmal grob nach hell und dunkel, weil das der zweite Grund ist,
    warum man Waesche trennt. Teile ohne Pflegeangabe stehen getrennt —
    raten waere hier die falsche Hilfe.
    """
    def helligkeit(hexwert: str | None) -> str:
        if not hexwert:
            return "unbekannt"
        return "hell" if E.hsl(hexwert)["l"] >= 0.5 else "dunkel"

    offen = [i for i in db.list_items()
             if not i.get("archived") and (
                 E.laundry_remaining(i) > 0 or i.get("paused"))]

    gruppen: dict[str, dict[str, list[dict[str, Any]]]] = {}
    ohne: list[dict[str, Any]] = []
    for i in offen:
        eintrag = {"id": i["id"], "name": i.get("name"),
                   "material": i.get("material"), "farbe": i.get("colorName")}
        pflege = i.get("care")
        if not pflege:
            ohne.append(eintrag)
            continue
        gruppen.setdefault(pflege, {}).setdefault(helligkeit(i.get("colorHex")), []).append(eintrag)

    ladungen = []
    for pflege, nach_farbe in gruppen.items():
        for ton, teile in nach_farbe.items():
            ladungen.append({"pflege": pflege, "ton": ton, "teile": teile,
                             "anzahl": len(teile)})
    ladungen.sort(key=lambda x: -x["anzahl"])

    return {"wartend": len(offen), "ladungen": ladungen, "ohnePflegeangabe": ohne}


@router.post("/wiederholung")
def wiederholung(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Hattest du das schon einmal an — und wenn ja, wann und wobei?

    Fuer die Frage, ob man dieselben Leute zweimal im selben Outfit
    trifft. Gewertet wird nach Ueberschneidung: zwei Outfits, die sich
    nur im Guertel unterscheiden, sind praktisch dasselbe.
    """
    ids = set(payload.get("teile") or [])
    if not ids:
        raise HTTPException(400, "Keine Teile übergeben.")
    anlass = payload.get("anlass")
    roh_tage = payload.get("tage")
    tage = int(roh_tage) if roh_tage is not None else 21
    grenze = datetime.now(timezone.utc) - timedelta(days=tage)

    treffer = []
    for eintrag in db.list_outfit_log(limit=1000):
        getragen = _tage_her(eintrag.get("worn_at"))
        if getragen is None or getragen > tage:
            continue
        alt = set(eintrag.get("item_ids") or [])
        if not alt:
            continue
        gleich = len(ids & alt)
        anteil = gleich / max(len(ids), len(alt))
        if anteil < 0.6:
            continue
        treffer.append({
            "wann": eintrag.get("worn_at"), "vorTagen": getragen,
            "anlass": eintrag.get("occasion"), "ueberschneidung": round(anteil, 2),
            "gleicheTeile": gleich,
            "selberAnlass": bool(anlass and eintrag.get("occasion") == anlass),
        })

    treffer.sort(key=lambda x: x["vorTagen"])
    warnung = next((t for t in treffer if t["selberAnlass"]), None) or (
        treffer[0] if treffer else None)
    return {"geprueft": tage, "treffer": treffer[:5], "warnung": warnung}


@router.post("/items/{item_id}/klonen")
def klone_teil(item_id: str) -> dict[str, Any]:
    """Zweites Exemplar desselben Stücks anlegen.

    Für dasselbe Shirt in einer anderen Farbe: Schnitt, Material, Länge,
    Marke, Größe und Pflege stimmen, nur Foto und Farbe nicht. Beides
    trägt man danach nach.
    """
    kopie = db.clone_item(item_id)
    if not kopie:
        raise HTTPException(404, "Teil nicht gefunden.")
    return kopie


# ── Aufräumen ───────────────────────────────────────────────────────────

def _verwaiste_bilder() -> list[dict[str, Any]]:
    """Bilddateien, auf die kein Datensatz mehr zeigt.

    Entstehen, wenn Teile oder Personen gelöscht wurden, bevor das
    Aufräumen beim Löschen eingebaut war. Neue Löschungen hinterlassen
    keine mehr.
    """
    gebraucht = db.alle_bildpfade()
    verzeichnis = settings.images_dir
    if not verzeichnis.is_dir():
        return []
    out = []
    for datei in sorted(verzeichnis.iterdir()):
        if not datei.is_file() or datei.name in gebraucht:
            continue
        out.append({"datei": datei.name, "bytes": datei.stat().st_size})
    return out


@router.get("/verwaiste-bilder")
def verwaiste_bilder() -> dict[str, Any]:
    liste = _verwaiste_bilder()
    return {"anzahl": len(liste), "bytes": sum(x["bytes"] for x in liste),
            "dateien": liste[:200]}


@router.post("/verwaiste-bilder/loeschen")
def verwaiste_bilder_loeschen() -> dict[str, Any]:
    """Die eben ermittelten Dateien entfernen.

    Die Liste wird direkt vor dem Löschen neu bestimmt, nicht aus einem
    vorherigen Aufruf übernommen — sonst könnte zwischen Anzeigen und
    Bestätigen ein Teil entstanden sein, dessen Bild dann mit weggeräumt
    würde.
    """
    liste = _verwaiste_bilder()
    weg, fehler = 0, 0
    for eintrag in liste:
        pfad = images.path_for(eintrag["datei"])
        if not pfad:
            fehler += 1
            continue
        try:
            pfad.unlink()
            weg += 1
        except OSError:
            fehler += 1
    if weg or fehler:
        log.info("Verwaiste Bilder entfernt: %d, fehlgeschlagen: %d", weg, fehler)
    return {"geloescht": weg, "fehlgeschlagen": fehler,
            "bytes": sum(x["bytes"] for x in liste)}


# ── Auswertung ──────────────────────────────────────────────────────────

def _tage_her(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - d).days)


def _ausgaben(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Was wurde wann gekauft?

    Nur Teile mit Preis UND Kaufdatum — ohne beides ist die Zeitreihe
    irreführend, weil undatierte Käufe im ältesten Jahr landen würden.
    """
    nach_jahr: dict[str, float] = {}
    nach_kategorie: dict[str, float] = {}
    for i in items:
        preis, gekauft = i.get("price"), i.get("boughtAt")
        if preis is None:
            continue
        kat = i.get("category") or "ohne Kategorie"
        nach_kategorie[kat] = round(nach_kategorie.get(kat, 0.0) + float(preis), 2)
        if not gekauft:
            continue
        jahr = str(gekauft)[:4]
        if len(jahr) == 4 and jahr.isdigit():
            nach_jahr[jahr] = round(nach_jahr.get(jahr, 0.0) + float(preis), 2)
    return {
        "jahre": [{"jahr": j, "summe": s} for j, s in sorted(nach_jahr.items())],
        "kategorien": sorted(
            [{"kategorie": k, "summe": s} for k, s in nach_kategorie.items()],
            key=lambda x: -x["summe"]),
        "ohneDatum": len([i for i in items
                          if i.get("price") is not None and not i.get("boughtAt")]),
    }


def _waescheseit(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Wie lange wartet die Wäsche schon?

    Gemessen am ältesten Teil im Korb. Die Frist selbst sagt nur, wann
    ein Teil wieder verfügbar wäre — nicht, dass tatsächlich jemand
    gewaschen hat.
    """
    wartend = [i for i in items
               if not i.get("archived") and (E.laundry_remaining(i) > 0 or i.get("paused"))]
    if not wartend:
        return {"anzahl": 0, "laengsteTage": 0}
    tage = [_tage_her(i.get("lastWorn")) or 0 for i in wartend]
    return {"anzahl": len(wartend), "laengsteTage": max(tage) if tage else 0}


@router.get("/stats")
def stats() -> dict[str, Any]:
    """Was das Trageprotokoll hergibt.

    Es wird seit dem ersten Tag mitgeschrieben, war aber nirgends
    sichtbar. Cost-per-Wear nur fuer Teile mit hinterlegtem Preis — ohne
    Preis bleibt es bei der Zaehlung.
    """
    items = db.list_items()
    log = db.list_outfit_log(limit=1000)

    def cpw(i: dict[str, Any]) -> float | None:
        preis, n = i.get("price"), i.get("wearCount") or 0
        if preis is None or n <= 0:
            return None
        return round(float(preis) / n, 2)

    getragen = [i for i in items if (i.get("wearCount") or 0) > 0]
    nie = [i for i in items if not (i.get("wearCount") or 0)]

    mit_preis = [i for i in items if i.get("price") is not None]
    investition = round(sum(float(i["price"]) for i in mit_preis), 2)

    def kurz(i: dict[str, Any]) -> dict[str, Any]:
        return {"id": i["id"], "name": i.get("name"),
                "kategorie": i.get("category"),
                "getragen": i.get("wearCount") or 0,
                "preis": i.get("price"), "proTragen": cpw(i),
                "zuletzt": i.get("lastWorn"),
                "tageHer": _tage_her(i.get("lastWorn")),
                "seitErfassung": _tage_her(i.get("createdAt"))}

    # Ladenhueter: nie getragen, aber lange genug da, um es gekonnt zu haben.
    ladenhueter = sorted(
        [kurz(i) for i in nie if (_tage_her(i.get("createdAt")) or 0) >= 30],
        key=lambda x: -(x["seitErfassung"] or 0))

    return {
        "teile": len(items),
        "getragen": len(getragen),
        "nieGetragen": len(nie),
        "protokollEintraege": len(log),
        "investition": investition,
        "teileMitPreis": len(mit_preis),
        "teileOhnePreis": len(items) - len(mit_preis),
        "meistGetragen": sorted([kurz(i) for i in getragen],
                                key=lambda x: -x["getragen"])[:10],
        "ladenhueter": ladenhueter[:10],
        "laengsteNichtGetragen": sorted(
            [kurz(i) for i in getragen if _tage_her(i.get("lastWorn")) is not None],
            key=lambda x: -(x["tageHer"] or 0))[:10],
        "besteProTragen": sorted(
            [kurz(i) for i in mit_preis if cpw(i) is not None],
            key=lambda x: x["proTragen"])[:10],
        "ausgaben": _ausgaben(items),
        "waescheseit": _waescheseit(items),
        "inDerWaesche": [
            {"id": i["id"], "name": i.get("name"),
             "restTage": round(E.laundry_remaining(i), 1)}
            for i in items if E.laundry_remaining(i) > 0],
    }


@router.post("/worn/{log_id}/foto")
async def worn_foto(log_id: str, foto: UploadFile = File(...)) -> dict[str, Any]:
    """Foto zum Trageprotokoll.

    Anders als das Ganzkoerperfoto wird dieses bewusst gespeichert — es
    ist der Zweck der Sache. Es geht nie an ein Modell, sondern nur ins
    Volume, und wird beim Loeschen des Eintrags mit entfernt.
    """
    if not any(e["id"] == log_id for e in db.list_outfit_log(limit=1000)):
        raise HTTPException(404, "Protokolleintrag nicht gefunden.")
    roh = await foto.read()
    if not roh:
        raise HTTPException(400, "Das Foto war leer.")
    fertig = images.prepare(roh, cutout=False)
    pfad = images.store(f"ootd_{log_id}", fertig.ablage, fertig.media_type)
    db.set_outfit_photo(log_id, pfad)
    return {"id": log_id, "photoPath": pfad}


@router.get("/worn/{log_id}/foto")
def worn_foto_lesen(log_id: str) -> FileResponse:
    eintrag = next((e for e in db.list_outfit_log(limit=1000) if e["id"] == log_id), None)
    if not eintrag or not eintrag.get("photo_path"):
        raise HTTPException(404, "Zu diesem Eintrag gibt es kein Foto.")
    pfad = images.path_for(eintrag["photo_path"])
    if not pfad:
        raise HTTPException(404, "Die Bilddatei fehlt.")
    return FileResponse(pfad, headers={"Cache-Control": "public, max-age=86400"})


# ── Gespeicherte und geplante Outfits ───────────────────────────────────
#
# Bewusst NICHT unter /outfits/...: dort liegt schon /outfits/{job_id} für
# die laufende Kuration, und FastAPI prüft die Routen in der Reihenfolge
# ihrer Definition. "gespeichert" wäre dort als Job-Nummer gelandet.

@router.get("/gespeicherte-outfits")
def saved_outfits() -> list[dict[str, Any]]:
    return db.list_saved_outfits()


@router.post("/gespeicherte-outfits")
def save_outfit(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    ids = payload.get("teile") or []
    name = (payload.get("name") or "").strip()
    if not ids:
        raise HTTPException(400, "Keine Teile übergeben.")
    if not name:
        raise HTTPException(400, "Das Outfit braucht einen Namen.")
    return db.save_outfit(name, ids, payload.get("anlass"), payload.get("notiz"))


@router.delete("/gespeicherte-outfits/{outfit_id}")
def remove_saved_outfit(outfit_id: str) -> dict[str, Any]:
    if not db.delete_saved_outfit(outfit_id):
        raise HTTPException(404, "Outfit nicht gefunden.")
    return {"geloescht": outfit_id}


@router.get("/plan")
def plans(von: str | None = Query(None), bis: str | None = Query(None)) -> list[dict[str, Any]]:
    return db.list_plans(von, bis)


@router.put("/plan/{datum}")
def set_plan(datum: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    # Datum als YYYY-MM-DD; alles andere waere spaeter nicht sortierbar.
    try:
        datetime.strptime(datum, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Datum bitte als JJJJ-MM-TT.") from None
    ids = payload.get("teile") or []
    if not ids:
        raise HTTPException(400, "Keine Teile übergeben.")
    return db.set_plan(datum, ids, payload.get("anlass"), payload.get("notiz"))


@router.delete("/plan/{datum}")
def remove_plan(datum: str) -> dict[str, Any]:
    if not db.delete_plan(datum):
        raise HTTPException(404, "Für diesen Tag ist nichts geplant.")
    return {"geloescht": datum}


# ── Packliste ───────────────────────────────────────────────────────────

@router.post("/packliste")
def packliste(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Was muss mit, um <tage> Tage bei <temp> Grad angezogen zu sein?"""
    # Nicht "or 5": eine ausdrueckliche 0 ist eine Angabe und keine
    # fehlende. pack_list() klemmt sie dann auf 1, statt sie stillschweigend
    # in 5 zu verwandeln.
    roh_tage = payload.get("tage")
    tage = int(roh_tage) if roh_tage is not None else 5
    ctx = build_ctx(payload.get("anlass") or "Alltag",
                    float(payload.get("temp") if payload.get("temp") is not None else 16),
                    None,
                    float(payload.get("regen") or 0),
                    float(payload.get("wind") or 0))
    res = E.pack_list(db.list_items(), ctx, tage)

    # Teile anreichern, damit die Oberflaeche Bilder zeigen kann, ohne
    # jedes Teil einzeln nachzuladen.
    nach_id = {i["id"]: i for i in db.list_items()}
    for t in res["teile"]:
        voll = nach_id.get(t["id"], {})
        t["imagePath"] = voll.get("imagePath")
        t["material"] = voll.get("material")
    return res


# ── Aussortieren ────────────────────────────────────────────────────────

@router.get("/aussortieren")
def aussortieren(mindestalter: int = Query(60, ge=0, le=3650)) -> dict[str, Any]:
    """Was trägst du nicht?

    Bewusst nur ein Vorschlag mit Begruendung, keine Automatik: was aus
    dem Schrank fliegt, entscheidet niemand ausser dir. Gewertet wird
    nach Alter im Schrank, Tragehaeufigkeit und — falls hinterlegt —
    dem Preis pro Tragen.
    """
    items = [i for i in db.list_items() if not i.get("archived")]
    fb = db.get_feedback()
    abgelehnt: dict[str, int] = {}
    for paar in fb.get("disliked", []):
        for teil in paar.split("|"):
            abgelehnt[teil] = abgelehnt.get(teil, 0) + 1

    vorschlaege = []
    for i in items:
        alter = _tage_her(i.get("createdAt")) or 0
        if alter < mindestalter:
            continue
        getragen = i.get("wearCount") or 0
        seit = _tage_her(i.get("lastWorn"))
        gruende = []
        gewicht = 0.0

        if getragen == 0:
            gruende.append(f"seit {alter} Tagen im Schrank und nie getragen")
            gewicht += 3
        elif seit is not None and seit >= 180:
            gruende.append(f"zuletzt vor {seit} Tagen getragen")
            gewicht += 2
        elif getragen <= 2 and alter >= 180:
            gruende.append(f"in {alter} Tagen nur {getragen}× getragen")
            gewicht += 1.5

        if abgelehnt.get(i["id"], 0) >= 2:
            gruende.append("passt in Kombinationen selten")
            gewicht += 1

        preis = i.get("price")
        if preis is not None and getragen > 0 and preis / getragen >= 50:
            gruende.append(f"{preis / getragen:.0f} € pro Tragen")
            gewicht += 1

        if gruende:
            vorschlaege.append({
                "id": i["id"], "name": i.get("name"), "kategorie": i.get("category"),
                "getragen": getragen, "seitErfassung": alter, "tageHer": seit,
                "preis": preis, "gruende": gruende, "gewicht": round(gewicht, 1),
            })

    vorschlaege.sort(key=lambda x: -x["gewicht"])
    return {"geprueft": len(items), "mindestalter": mindestalter,
            "vorschlaege": vorschlaege[:20]}


# ── Lueckenanalyse ──────────────────────────────────────────────────────

@router.post("/gaps")
def gaps(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    occasion = payload.get("anlass") or "Alltag"
    temp = float(payload.get("temp", 16))
    ctx = build_ctx(occasion, temp)
    data = analyse_gaps(db.list_items(), ctx)

    if not settings.ai_enabled:
        return {"roh": data, "empfehlungen": [],
                "waisen": [{"teil": w["name"],
                            "diagnose": f"Beste Bewertung nur {w['bestePunkte']} von 100."}
                           for w in data["waisen"]],
                "hinweis": "Ohne API-Schlüssel ist das die reine Rechnung."}
    try:
        res = ai.ask([{"type": "text", "text": P.gaps_prompt(db.get_profile(), data)}],
                     # Ebenfalls mit Websuche und mehreren Vorschlaegen.
                     model=settings.model_curate, max_tokens=8000, search=True)
    except ai.AIUnavailable as exc:
        return {"roh": data, "empfehlungen": [],
                "waisen": [{"teil": w["name"],
                            "diagnose": f"Beste Bewertung nur {w['bestePunkte']} von 100."}
                           for w in data["waisen"]],
                "hinweis": f"Die Websuche war nicht erreichbar ({exc}). "
                           "Das ist die reine Rechnung."}
    return {**res, "roh": data}


# ── Wetter ──────────────────────────────────────────────────────────────

@router.get("/weather")
def get_weather(lat: float = Query(...), lon: float = Query(...)) -> dict[str, Any]:
    try:
        return weather.current(lat, lon)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from None


# ── Sichern und Wiederherstellen ────────────────────────────────────────

@router.get("/export")
def export_all() -> JSONResponse:
    """Vollstaendige Sicherung der aktiven Person.

    "Vollstaendig" ist hier woertlich gemeint: was hier fehlt, ist nach
    einer Wiederherstellung weg. Bis August 2026 enthielt der Export
    weder gemerkte noch geplante Outfits, keine Etikett- und
    Outfitfotos — und das Trageprotokoll war zwar drin, wurde vom Import
    aber nie gelesen.

    Ein Export gehoert immer genau einer Person; der Import legt ihn in
    die dann aktive.
    """
    items = db.list_items()
    log = db.list_outfit_log(10000)

    bilder: dict[str, str] = {}
    etiketten: dict[str, str] = {}
    outfitfotos: dict[str, str] = {}

    def als_data_url(rel: str | None) -> str | None:
        pfad = images.path_for(rel or "")
        if not pfad:
            return None
        media = "image/png" if pfad.suffix == ".png" else "image/jpeg"
        return f"data:{media};base64,{images.to_base64(pfad.read_bytes())}"

    for item in items:
        haupt = als_data_url(item.get("imagePath"))
        if haupt:
            bilder[item["id"]] = haupt
        etikett = als_data_url(item.get("labelPath"))
        if etikett:
            etiketten[item["id"]] = etikett

    for eintrag in log:
        foto = als_data_url(eintrag.get("photo_path"))
        if foto:
            outfitfotos[eintrag["id"]] = foto

    payload = {
        "version": 3,
        "items": items,
        "images": bilder,
        "etiketten": etiketten,
        "outfitfotos": outfitfotos,
        "profile": db.get_profile(),
        "fb": db.get_feedback(),
        "outfitLog": log,
        "gespeicherteOutfits": db.list_saved_outfits(),
        "plaene": db.list_plans(),
        # Nur zur Einordnung: aus welchem Schrank stammt die Datei?
        "person": {"id": db.aktive_person(),
                   "name": db.get_profile().get("name")},
    }
    name = f"rack-{datetime.now(timezone.utc).date().isoformat()}.json"
    return JSONResponse(payload, headers={
        "Content-Disposition": f'attachment; filename="{name}"'})


def _decode_data_url(url: str) -> tuple[bytes, str] | None:
    import base64
    if not isinstance(url, str) or not url.startswith("data:"):
        return None
    try:
        head, b64 = url.split(",", 1)
        media = head[5:].split(";")[0] or "image/jpeg"
        return base64.b64decode(b64), media
    except Exception:                              # noqa: BLE001
        return None


@router.post("/import")
def import_all(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Liest die Exportdatei des Prototypen: {version, items, images, profile, fb}.

    Idempotent: ein zweiter Import derselben Datei legt nichts doppelt an.
    Erkennungsmerkmal ist die Teile-ID aus dem Export.
    """
    items = payload.get("items") or []
    bilder = payload.get("images") or {}
    if not isinstance(items, list):
        raise HTTPException(400, "Die Datei enthält keine Teileliste.")

    neu = aktualisiert = 0
    for raw in items:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        item = {k: v for k, v in raw.items() if k in db.KEY_TO_COL}
        item["id"] = raw["id"]
        # Die Personennummer aus der Datei wird verworfen: sie zeigt auf
        # den Schrank, aus dem exportiert wurde. Beim Einlesen zaehlt die
        # Person, die gerade aktiv ist — sonst landen die Teile bei einer
        # fremden oder laengst geloeschten Person und sind unsichtbar.
        item.pop("personId", None)

        # Waerme und Formalitaet neu rechnen, ausser der Nutzer hat im
        # Export von Hand eingegriffen.
        computed = E.derive(raw)
        if not item.get("warmthManual"):
            item["warmth"] = computed["warmth"]
        if not item.get("formalityManual"):
            item["formality"] = computed["formality"]

        decoded = _decode_data_url(bilder.get(raw["id"], ""))
        if decoded:
            item["imagePath"] = images.store(item["id"], decoded[0], decoded[1])

        if db.get_item(item["id"]):
            item.pop("id", None)
            db.update_item(raw["id"], item)
            aktualisiert += 1
        else:
            # Die Kennung kann bei einer anderen Person liegen — der
            # Primaerschluessel gilt ueber alle. Dann eine neue vergeben,
            # statt am Konflikt zu scheitern.
            if db.item_exists(item["id"]):
                item["id"] = db.new_id()
            item.setdefault("createdAt", raw.get("createdAt") or db.now_iso())
            db.insert_item(item)
            neu += 1

    # Etikettfotos: seit Fassung 3 im Export.
    etiketten = payload.get("etiketten") or {}
    for item_id, url in etiketten.items():
        decoded = _decode_data_url(url)
        if decoded and db.get_item(item_id):
            db.update_item(item_id, {
                "labelPath": images.store(f"label_{item_id}", decoded[0], decoded[1])})

    if isinstance(payload.get("profile"), dict):
        db.save_profile(payload["profile"])

    fb = payload.get("fb") or {}
    for verdict in ("liked", "disliked"):
        for pair in fb.get(verdict) or []:
            db.set_feedback(pair, verdict)

    # Trageprotokoll. Es stand schon immer im Export, wurde aber nie
    # eingelesen — nach einer Wiederherstellung fehlte damit die gesamte
    # Historie, und mit ihr Zaehlung, Bilanz und Cost-per-Wear.
    #
    # Idempotent ueber die Eintrags-ID: die Zaehler an den Teilen kommen
    # aus dem Export selbst und duerfen nicht durch erneutes Buchen
    # hochgezaehlt werden, deshalb wird hier direkt geschrieben statt
    # log_outfit() aufzurufen.
    outfitfotos = payload.get("outfitfotos") or {}
    log_neu = 0
    for eintrag in payload.get("outfitLog") or []:
        if not isinstance(eintrag, dict) or not eintrag.get("id"):
            continue
        foto = None
        decoded = _decode_data_url(outfitfotos.get(eintrag["id"], ""))
        if decoded:
            foto = images.store(f"ootd_{eintrag['id']}", decoded[0], decoded[1])
        if db.merge_outfit_log(eintrag, foto):
            log_neu += 1

    # Gemerkte Outfits und Planung.
    fits_neu = 0
    for fit in payload.get("gespeicherteOutfits") or []:
        if not isinstance(fit, dict) or not fit.get("name"):
            continue
        if db.merge_saved_outfit(fit):
            fits_neu += 1

    plan_neu = 0
    for plan in payload.get("plaene") or []:
        if not isinstance(plan, dict) or not plan.get("datum"):
            continue
        db.set_plan(plan["datum"], plan.get("itemIds") or [],
                    plan.get("occasion"), plan.get("notes"))
        plan_neu += 1

    return {"neu": neu, "aktualisiert": aktualisiert,
            "bilder": len([b for b in bilder.values() if _decode_data_url(b)]),
            "protokoll": log_neu, "outfits": fits_neu, "plaene": plan_neu,
            "teile": len(db.list_items())}
