"""Bildaufbereitung: skalieren, freistellen, ablegen.

Die Freistellung macht rembg mit u2net serverseitig und ersetzt damit die
Flutfuellung des Prototypen. Das Modell liegt im Image, der erste Start
laedt nichts nach.
"""

from __future__ import annotations

import base64
import io
import logging
import threading
from pathlib import Path
from typing import NamedTuple

from PIL import Image

from .config import settings

log = logging.getLogger("rack.images")

_session = None
_session_lock = threading.Lock()


def _rembg_session():
    """Das Freistellungsmodell wird einmal geladen und wiederverwendet.

    Das Laden kostet auf dem N150 spuerbar Zeit, deshalb nicht pro Bild.
    Welches Modell, steht in RACK_REMBG_MODEL; im Image liegt genau
    dieses vor, ein anderer Wert wuerde beim ersten Foto nachladen.
    """
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                from rembg import new_session
                log.info("Freistellungsmodell: %s", settings.rembg_model)
                _session = new_session(settings.rembg_model)
    return _session


def _fit(img: Image.Image, max_dim: int) -> Image.Image:
    scale = min(1.0, max_dim / max(img.width, img.height))
    if scale >= 1.0:
        return img
    return img.resize((round(img.width * scale), round(img.height * scale)),
                      Image.LANCZOS)


def _trim_to_square(img: Image.Image) -> Image.Image:
    """Auf das sichtbare Motiv beschneiden und quadratisch einbetten.

    Entspricht dem Zuschnitt im Prototypen: Rahmen um die Bounding Box,
    Faktor 1.14, damit nichts am Rand klebt.
    """
    alpha = img.getchannel("A")
    box = alpha.getbbox()
    if not box:
        return img
    left, upper, right, lower = box
    w, h = right - left, lower - upper
    side = round(max(w, h) * 1.14)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(img.crop(box), ((side - w) // 2, (side - h) // 2))
    return out


class Prepared(NamedTuple):
    """Zwei Fassungen desselben Fotos.

    ablage geht ins Volume und in die App, modell an die Vision-API. Sie
    zu trennen kostet einen zweiten Encode und spart die schlechtere
    Alternative: entweder ein grobes Bild fuer die Erkennung oder ein
    unnoetig grosses in der Ablage.
    """
    ablage: bytes
    media_type: str
    cutout: bool
    modell: bytes
    modell_media_type: str


def _encode(img: Image.Image, cut: bool) -> tuple[bytes, str]:
    buf = io.BytesIO()
    if cut:
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), "image/png"
    flat = Image.new("RGB", img.size, (242, 240, 237))
    flat.paste(img, (0, 0), img if img.mode == "RGBA" else None)
    flat.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue(), "image/jpeg"


def prepare(raw: bytes, cutout: bool = True) -> Prepared:
    """Foto aufbereiten: einmal fuer die Ablage, einmal fuer das Modell.

    Freigestellt wird auf der groesseren Fassung und nur einmal — rembg
    ist der teure Teil, und auf dem N150 will man ihn nicht doppelt.
    """
    img = Image.open(io.BytesIO(raw))
    img.load()
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    gross = _fit(img, max(settings.max_image_dim, settings.model_image_dim))

    freigestellt = False
    if cutout:
        try:
            from rembg import remove
            gross = _trim_to_square(remove(gross.convert("RGBA"),
                                           session=_rembg_session()))
            freigestellt = True
        except Exception as exc:                    # noqa: BLE001
            # Freistellung ist optional, wie im Prototypen. Das Bild wird
            # trotzdem gespeichert, nur eben mit Hintergrund. Die Meldung
            # gehoert mit ins Log, sonst ist der Fall nicht zu finden.
            log.warning("Freistellung fehlgeschlagen: %s: %s",
                        type(exc).__name__, exc)

    ablage, ablage_mt = _encode(_fit(gross, settings.max_image_dim), freigestellt)
    modell, modell_mt = _encode(_fit(gross, settings.model_image_dim), freigestellt)
    return Prepared(ablage, ablage_mt, freigestellt, modell, modell_mt)


def prepare_for_model(raw: bytes, max_dim: int = 620) -> tuple[str, str]:
    """Kleinere Fassung fuer den Modellaufruf, base64.

    Wird fuer das Ganzkoerperfoto verwendet und nirgends abgelegt.
    """
    img = Image.open(io.BytesIO(raw))
    img.load()
    img = _fit(img.convert("RGB"), max_dim)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"


def to_base64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")


def store(item_id: str, data: bytes, media_type: str) -> str:
    """Legt das Bild als Datei ab und gibt den Pfad relativ zu images/ zurueck."""
    settings.ensure_dirs()
    suffix = ".png" if media_type == "image/png" else ".jpg"
    name = f"{item_id}{suffix}"
    (settings.images_dir / name).write_bytes(data)
    return name


def path_for(rel: str) -> Path | None:
    if not rel:
        return None
    # Kein Ausbrechen aus dem Bilderordner, egal was in der DB steht.
    candidate = (settings.images_dir / rel).resolve()
    if not str(candidate).startswith(str(settings.images_dir.resolve())):
        return None
    return candidate if candidate.is_file() else None


def delete(rel: str) -> None:
    target = path_for(rel)
    if target:
        target.unlink(missing_ok=True)
