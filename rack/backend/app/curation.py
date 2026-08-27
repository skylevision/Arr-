"""Nachbereitung dessen, was das Modell zur Kuration liefert.

Reine Logik, bewusst ohne FastAPI-Abhaengigkeit: so laesst sie sich
zusammen mit der Engine testen, ohne die halbe Anwendung zu laden.
"""

from __future__ import annotations

from typing import Any

from .engine import is_acc


def entbehrliche_accessoires(auswahl: dict[str, Any],
                             parts: list[dict[str, Any]]) -> list[str]:
    """Filtert, was das Modell als entbehrlich gemeldet hat.

    Zugelassen sind nur Accessoires, die auch wirklich in diesem Outfit
    stecken. Sonst koennte das Modell tragende Stuecke aussortieren oder
    Teile nennen, die es gar nicht gibt.
    """
    erlaubt = {(x.get("name") or "").strip().lower(): x.get("name")
               for x in parts if is_acc(x) and x.get("name")}
    out: list[str] = []
    for w in auswahl.get("weglassen") or []:
        if not isinstance(w, str):
            continue
        name = erlaubt.get(w.strip().lower())
        if name and name not in out:
            out.append(name)
    return out
