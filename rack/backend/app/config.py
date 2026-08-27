"""Konfiguration, ausschliesslich aus der Umgebung.

Der Anthropic-Schluessel wird hier nur gelesen, nie geschrieben und nie
geloggt. Fehlt er, laeuft die Anwendung im Engine-Modus weiter
(Briefing Abschnitt 11).
"""

from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(_env("RACK_DATA_DIR", "/data"))
        self.db_path = self.data_dir / "db" / "rack.sqlite3"
        self.images_dir = self.data_dir / "images"
        self.static_dir = Path(_env("RACK_STATIC_DIR", "/app/static"))

        self.api_key = _env("ANTHROPIC_API_KEY")
        self.model_vision = _env("RACK_MODEL_VISION", "claude-sonnet-5")
        self.model_curate = _env("RACK_MODEL_CURATE", "claude-sonnet-5")

        # Token-Schutz fuer den Fall, dass der Dienst doch im LAN landet.
        # Leer heisst offen; ueber Tailscale ist das die Vorgabe.
        self.auth_token = _env("RACK_TOKEN")

        self.trend_max_age_days = int(_env("RACK_TREND_MAX_AGE_DAYS", "30"))
        self.weather_cache_minutes = int(_env("RACK_WEATHER_CACHE_MINUTES", "30"))
        self.max_image_dim = int(_env("RACK_MAX_IMAGE_DIM", "1000"))
        self.cutout = _env("RACK_CUTOUT", "1") != "0"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.api_key)

    def masked_key(self) -> str:
        """Nur fuer Statusausgaben. Zeigt nie mehr als die letzten vier Zeichen."""
        if not self.api_key:
            return ""
        return f"sk-ant-…{self.api_key[-4:]}"

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
