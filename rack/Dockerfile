# syntax=docker/dockerfile:1

# ─────────────────────────────────────────────────────────────────────
# 1. Frontend bauen. Das Ergebnis liegt statisch im Image, damit zur
#    Laufzeit kein Node und kein zweiter Webserver noetig ist.
# ─────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# ─────────────────────────────────────────────────────────────────────
# 2. Python-Abhaengigkeiten und das rembg-Modell.
#    Beides in einer eigenen Stufe, damit der Modell-Download nicht bei
#    jeder Code-Aenderung neu laeuft.
# ─────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS deps

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --prefix=/install -r /tmp/requirements.txt

# Freistellungsmodell vorab holen. Ohne das zieht der erste Start rund
# 180 MB nach. isnet-general-use statt u2net: sauberere Kanten bei
# Kleidung, vor allem an Strick, Fransen und Kapuzenzuegen. Muss mit
# RACK_REMBG_MODEL uebereinstimmen, sonst laedt der Container beim
# ersten Foto nach.
ARG REMBG_MODEL=isnet-general-use
ENV PYTHONPATH=/install/lib/python3.12/site-packages \
    U2NET_HOME=/opt/rack/models
RUN mkdir -p /opt/rack/models \
 && python -c "import sys; from rembg import new_session; new_session(sys.argv[1])" "$REMBG_MODEL" \
 && ls -la /opt/rack/models


# ─────────────────────────────────────────────────────────────────────
# 3. Engine-Tests. Laufen im Build, nicht zur Laufzeit.
#
#    Die Regel-Engine ist der Teil, den man beim Anpassen am leichtesten
#    kaputt macht, und ein Fehler faellt dort nicht auf — die App laeuft
#    weiter, sie schlaegt nur schlechtere Outfits vor. Deshalb bricht der
#    Build ab, wenn ein Schwellwert nicht mehr stimmt. Ein Image mit
#    roter Engine kann so gar nicht erst auf dem Server landen.
#
#    Zur Laufzeit werden weder pytest noch die Tests mitgeliefert.
# ─────────────────────────────────────────────────────────────────────
FROM deps AS tests

ENV PYTHONPATH=/install/lib/python3.12/site-packages \
    PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir --prefix=/install pytest==9.1.1
COPY backend/ /src/
WORKDIR /src
RUN python -m pytest -q


# ─────────────────────────────────────────────────────────────────────
# 4. Laufzeit
# ─────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="rack" \
      org.opencontainers.image.description="Kleiderschrank mit Regel-Engine und Outfitvorschlägen"

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 tini \
 && rm -rf /var/lib/apt/lists/*

COPY --from=deps /install /usr/local
COPY --from=deps /opt/rack/models /opt/rack/models
# Erzwingt, dass die Teststufe gelaufen ist, bevor das Laufzeit-Image
# entsteht — BuildKit wuerde sie sonst als unbenutzten Zweig ueberspringen.
COPY --from=tests /src/pytest.ini /app/pytest.ini
COPY backend/app /app/app
COPY --from=frontend /build/dist /app/static
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# numba uebersetzt die pymatting-Routinen unter rembg beim ersten Aufruf.
# Das kostet rund 18 Sekunden und traefe sonst das erste Foto nach jedem
# Update. Hier einmal vorkompilieren; das Ergebnis spiegelt der
# Entrypoint ins Datenverzeichnis. Der Pfad zu site-packages muss dabei
# derselbe sein wie zur Laufzeit, sonst greift der Cache nicht.
ARG REMBG_MODEL=isnet-general-use
RUN NUMBA_CACHE_DIR=/opt/rack/numba U2NET_HOME=/opt/rack/models \
    python -c "\
import sys; from PIL import Image; from rembg import new_session, remove; \
remove(Image.new('RGBA', (320, 320), (200, 200, 200, 255)), session=new_session(sys.argv[1]))" "$REMBG_MODEL" \
 && chmod -R a+rX /opt/rack/numba \
 && du -sh /opt/rack/numba

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RACK_DATA_DIR=/data \
    RACK_STATIC_DIR=/app/static \
    U2NET_HOME=/models \
    NUMBA_CACHE_DIR=/data/cache/numba \
    PUID=99 \
    PGID=100 \
    UMASK=022 \
    TZ=Europe/Berlin

WORKDIR /app
EXPOSE 8099
VOLUME ["/data"]

# Logs gehen nach stdout, kein eigenes Logfile.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8099/api/health', timeout=4).status==200 else 1)"

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8099", \
     "--no-server-header", "--proxy-headers", "--forwarded-allow-ips", "*"]
