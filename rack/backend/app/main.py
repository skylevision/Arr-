"""FastAPI-Anwendung: API plus das kompilierte Frontend aus demselben Image.

Ein Prozess, ein Container. Statische Dateien liefert FastAPI selbst aus,
ein zusaetzlicher Webserver waere hier nur eine weitere bewegliche Teil.
"""

from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .api import router
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("rack")

# Nichts, was den Schluessel enthalten koennte, gehoert ins Log.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    db.init()
    if settings.ai_enabled:
        log.info("KI aktiv, Schlüssel %s, Lesen %s, Kuratieren %s",
                 settings.masked_key(), settings.model_vision, settings.model_curate)
    else:
        log.info("Kein API-Schlüssel gesetzt. Regel-Engine und alle Ansichten "
                 "laufen normal, die KI-Funktionen sind aus.")
    if settings.auth_token:
        log.info("Token-Schutz aktiv.")
    yield


app = FastAPI(title="Rack", docs_url=None, redoc_url=None, lifespan=lifespan)

OPEN_PATHS = {"/api/health", "/manifest.webmanifest", "/sw.js"}


@app.middleware("http")
async def token_guard(request: Request, call_next):
    """Einfacher Token-Schutz vor der API.

    Gedacht fuer den Fall, dass der Dienst doch im LAN erreichbar ist.
    Ueber Tailscale bleibt RACK_TOKEN normalerweise leer.
    """
    if settings.auth_token and request.url.path not in OPEN_PATHS:
        supplied = (request.headers.get("x-rack-token")
                    or request.cookies.get("rack_token")
                    or request.query_params.get("token") or "")
        if not secrets.compare_digest(supplied, settings.auth_token):
            if request.url.path.startswith("/api/"):
                return JSONResponse({"detail": "Token fehlt oder ist falsch."},
                                    status_code=401)
            return PlainTextResponse("Token fehlt oder ist falsch.", status_code=401)
    response = await call_next(request)
    # Kein Fremdinhalt, keine Einbettung, kein Referrer nach aussen.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return response


app.include_router(router)

ASSETS = settings.static_dir / "assets"
if ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    """Alles, was keine API ist, beantwortet die Einzelseite.

    Damit funktionieren tiefe Links und der PWA-Start direkt auf einer
    Unterseite.
    """
    if path.startswith("api/"):
        return JSONResponse({"detail": "Nicht gefunden."}, status_code=404)

    candidate = (settings.static_dir / path).resolve() if path else None
    if candidate and str(candidate).startswith(str(settings.static_dir.resolve())) \
            and candidate.is_file():
        headers = {}
        if path.endswith((".webmanifest", "sw.js")):
            headers["Cache-Control"] = "no-cache"
        return FileResponse(candidate, headers=headers)

    index = settings.static_dir / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return PlainTextResponse(
        "Das Frontend ist in diesem Image nicht enthalten. Die API läuft unter /api.",
        status_code=200)
