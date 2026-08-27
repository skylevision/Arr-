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
from .gaps import analyse_gaps

log = logging.getLogger("rack.api")
router = APIRouter(prefix="/api")

MAX_UPLOAD = 25 * 1024 * 1024
MAX_FILES = 25


# ── Kontext fuer die Engine ─────────────────────────────────────────────

def build_ctx(occasion: str = "Alltag", temp: float = 16,
              anchor: str | None = None) -> dict[str, Any]:
    profile = db.get_profile()
    target = next((o["f"] for o in E.OCCASIONS if o["key"] == occasion), 2)
    return {
        "temp": temp,
        "target": target,
        "mode": profile.get("silhouette") or "frei",
        "body": profile,
        "gender": profile.get("gender") or "männlich",
        "fb": db.get_feedback(),
        "anchor": anchor,
    }


# ── Gesundheit ──────────────────────────────────────────────────────────

@router.get("/health")
def health() -> dict[str, Any]:
    conn = db.connect()
    count = conn.execute("SELECT COUNT(*) AS n FROM items").fetchone()["n"]
    return {
        "status": "ok",
        "teile": count,
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


# ── Profil ──────────────────────────────────────────────────────────────

@router.get("/profile")
def read_profile() -> dict[str, Any]:
    return db.get_profile()


@router.put("/profile")
def write_profile(profile: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return db.save_profile(profile)


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
            model=settings.model_vision, max_tokens=500, effort="low")
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


# ── Erfassen ────────────────────────────────────────────────────────────

_jobs: dict[str, dict[str, Any]] = {}
JOB_TTL = 3600


def _prune_jobs() -> None:
    stale = [k for k, v in _jobs.items() if time.time() - v["created"] > JOB_TTL]
    for k in stale:
        _jobs.pop(k, None)


def _read_one(data: bytes) -> dict[str, Any]:
    """Ein Bild aufbereiten und lesen lassen. Gibt einen Vorschlag zurueck,
    noch kein gespeichertes Objekt."""
    prepared, media, cut = images.prepare(data, cutout=settings.cutout)
    entry: dict[str, Any] = {"bild": images.to_base64(prepared), "mediaType": media,
                             "cutout": cut}
    if not settings.ai_enabled:
        entry["attrs"] = {"name": "", "category": "Oberteil", "fit": "regular",
                          "pattern": "uni", "thickness": "mittel",
                          "colorHex": "#888888"}
        entry["unsicher"] = ["name", "category", "fit", "length"]
        entry["status"] = "ohne_ki"
        entry["attrs"].update(E.derive(entry["attrs"]))
        return entry

    try:
        attrs = ai.ask(
            [{"type": "image",
              "source": {"type": "base64", "media_type": media, "data": entry["bild"]}},
             {"type": "text", "text": P.READ_PROMPT}],
            model=settings.model_vision, max_tokens=800, effort="low")
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
    entry["unsicher"] = attrs.pop("unsicher", []) or []
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
def list_items() -> list[dict[str, Any]]:
    return db.list_items()


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
    if current.get("imagePath"):
        images.delete(current["imagePath"])
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
        "teile": [{"id": x.get("id"), "name": x.get("name"), "art": x.get("subcategory"),
                   "farbe": x.get("colorName"), "hex": x.get("colorHex"),
                   "schnitt": x.get("fit"), "laenge": x.get("length"),
                   "bund": x.get("rise"), "aermel": x.get("sleeve"),
                   "muster": x.get("pattern"), "material": x.get("material")}
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
                     model=settings.model_curate, max_tokens=1500, search=True)
        return db.save_trends(res)["payload"]
    except ai.AIUnavailable:
        return cached["payload"] if cached else None


@router.get("/trends")
def get_trends() -> dict[str, Any]:
    cached = db.get_trends()
    payload = _cached_trends()
    return {"trends": payload,
            "abgerufen": (db.get_trends() or cached or {}).get("fetched_at")}


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
    ctx = build_ctx(occasion, temp, anchor)
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
                         "styling": [], "trendhinweis": "",
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
            model=settings.model_curate, max_tokens=2000, effort="medium")
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
    return db.log_outfit(ids, payload.get("anlass"), payload.get("temp"),
                         payload.get("punkte"))


@router.get("/worn")
def worn_log(limit: int = Query(200, ge=1, le=1000)) -> list[dict[str, Any]]:
    return db.list_outfit_log(limit)


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
                     model=settings.model_curate, max_tokens=3000, search=True)
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
    """Exportformat des Prototypen, damit ein Export hier dort wieder
    eingelesen werden koennte."""
    items = db.list_items()
    bilder: dict[str, str] = {}
    for item in items:
        path = images.path_for(item.get("imagePath") or "")
        if not path:
            continue
        media = "image/png" if path.suffix == ".png" else "image/jpeg"
        bilder[item["id"]] = f"data:{media};base64,{images.to_base64(path.read_bytes())}"

    payload = {
        "version": 2,
        "items": items,
        "images": bilder,
        "profile": db.get_profile(),
        "fb": db.get_feedback(),
        "outfitLog": db.list_outfit_log(10000),
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
            item.setdefault("createdAt", raw.get("createdAt") or db.now_iso())
            db.insert_item(item)
            neu += 1

    if isinstance(payload.get("profile"), dict):
        db.save_profile(payload["profile"])

    fb = payload.get("fb") or {}
    for verdict in ("liked", "disliked"):
        for pair in fb.get(verdict) or []:
            db.set_feedback(pair, verdict)

    return {"neu": neu, "aktualisiert": aktualisiert,
            "bilder": len([b for b in bilder.values() if _decode_data_url(b)]),
            "teile": len(db.list_items())}
