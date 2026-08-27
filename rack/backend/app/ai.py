"""Zugriff auf die Anthropic Messages API.

Der Schluessel wird ausschliesslich aus der Umgebung gelesen und taucht
weder in Logs noch in Fehlermeldungen auf. Fehlt er, wirft jeder Aufruf
AIUnavailable und die Aufrufer fallen auf die reine Rechnung zurueck.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from .config import settings

log = logging.getLogger("rack.ai")


class AIUnavailable(RuntimeError):
    """Kein Schluessel, kein Guthaben oder die API war nicht erreichbar."""

    def __init__(self, reason: str, kind: str = "fehler") -> None:
        super().__init__(reason)
        self.kind = kind


_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if not settings.api_key:
        raise AIUnavailable("Kein API-Schlüssel hinterlegt.", "kein_schluessel")
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.api_key, timeout=180.0)
    return _client


def reset_client() -> None:
    """Nach einem Schluesselwechsel per Neustart nicht noetig, aber billig."""
    global _client
    _client = None


def extract_json(text: str) -> Any:
    """Wie extractJson() im Prototypen: das aeusserste Objekt aus dem Text."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise AIUnavailable("Die Antwort enthielt kein JSON.", "format")
    return json.loads(text[start:end + 1])


def _describe(exc: Exception) -> AIUnavailable:
    """Unterscheidet die Fehlerarten, die der Nutzer auseinanderhalten muss.

    Der Schluessel selbst wird nie mit ausgegeben.
    """
    if isinstance(exc, anthropic.AuthenticationError):
        return AIUnavailable("Der API-Schlüssel wurde abgelehnt.", "schluessel")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return AIUnavailable("Der Schlüssel hat keinen Zugriff auf dieses Modell.",
                             "berechtigung")
    if isinstance(exc, anthropic.RateLimitError):
        return AIUnavailable("Das Anfragelimit ist erreicht. Später erneut versuchen.",
                             "limit")
    if isinstance(exc, anthropic.BadRequestError):
        msg = str(exc).lower()
        if "credit" in msg or "billing" in msg or "quota" in msg:
            return AIUnavailable("Das Guthaben reicht nicht aus.", "guthaben")
        return AIUnavailable("Die Anfrage wurde abgelehnt.", "anfrage")
    if isinstance(exc, anthropic.APIConnectionError):
        return AIUnavailable("Die API war nicht erreichbar.", "netzwerk")
    if isinstance(exc, anthropic.APIStatusError):
        return AIUnavailable(f"Die API antwortete mit Status {exc.status_code}.", "api")
    return AIUnavailable("Der Modellaufruf ist fehlgeschlagen.", "fehler")


def ask(content: list[dict[str, Any]], *, model: str | None = None,
        max_tokens: int = 1200, search: bool = False,
        effort: str = "medium") -> Any:
    """Ein Aufruf, JSON zurueck. Entspricht ask() im Prototypen."""
    body: dict[str, Any] = {
        "model": model or settings.model_curate,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
        "output_config": {"effort": effort},
    }
    if search:
        # Dynamisches Filtern; nur diese Variante laeuft auf Sonnet 5 / Opus 5.
        body["tools"] = [{"type": "web_search_20260209", "name": "web_search"}]

    try:
        response = client().messages.create(**body)
    except AIUnavailable:
        raise
    except Exception as exc:                       # noqa: BLE001
        log.warning("Modellaufruf fehlgeschlagen: %s", type(exc).__name__)
        raise _describe(exc) from None

    if response.stop_reason == "refusal":
        raise AIUnavailable("Das Modell hat die Anfrage abgelehnt.", "abgelehnt")

    text = "\n".join(b.text for b in response.content if b.type == "text")
    return extract_json(text)


def ping() -> dict[str, Any]:
    """Minimaler Testaufruf fuer die Schluesselpruefung.

    Gibt nie den Schluessel zurueck, hoechstens die maskierte Form.
    """
    try:
        response = client().messages.create(
            model=settings.model_vision,
            max_tokens=16,
            messages=[{"role": "user", "content": "Antworte mit dem Wort OK."}],
        )
    except AIUnavailable as exc:
        return {"ok": False, "art": exc.kind, "meldung": str(exc)}
    except Exception as exc:                       # noqa: BLE001
        err = _describe(exc)
        return {"ok": False, "art": err.kind, "meldung": str(err)}
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return {"ok": True, "art": "ok", "meldung": text[:40],
            "schluessel": settings.masked_key(),
            "modell": settings.model_vision,
            "tokens": response.usage.input_tokens + response.usage.output_tokens}
