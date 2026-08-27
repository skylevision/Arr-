"""Die Prompts aus rack.jsx, unveraendert uebernommen.

Der Wortlaut ist auf die JSON-Schemata abgestimmt und darf laut Briefing
Abschnitt 5 nicht angepasst werden. Uebernommen wurden nur die Template-
Einsetzungen: aus ${profile?.gender || "männlich"} wird die gleichwertige
Python-Formatierung. Die Fallback-Werte sind dabei dieselben.
"""

from __future__ import annotations

import json
from typing import Any

from .engine import SILHOUETTES

READ_PROMPT = """Lies das Foto eines einzelnen Kleidungsstücks und beschreibe ausschließlich, was sichtbar ist. Bewerte nichts.
Antworte nur mit JSON.

{
 "name": "kurze deutsche Bezeichnung, höchstens vier Wörter",
 "category": "Oberteil | Unterteil | Kleid | Jacke | Schuhe | Accessoire",
 "subcategory": "präzise Art, bei Accessoire eines von Uhr, Schmuck, Mütze, Cap, Schal, Gürtel, Tasche, Brille",
 "colorHex": "#rrggbb der dominanten Farbe",
 "colorName": "deutsche Farbbezeichnung",
 "pattern": "uni | gestreift | kariert | gemustert | meliert | logo",
 "patternScale": "klein | mittel | groß oder null",
 "material": "sichtbares Material in einem Wort",
 "thickness": "dünn | mittel | dick",
 "texture": "glatt | strukturiert | glänzend | flauschig | robust",
 "fit": "oversize | weit | regular | slim | cropped",
 "length": "Oberteil: cropped | hüftlang | longline. Unterteil: shorts | sieben-achtel | knöchel | lang | stacked. Sonst null",
 "rise": "nur Unterteil: high | mid | low",
 "sleeve": "nur Oberteil oder Jacke: ärmellos | kurz | dreiviertel | lang",
 "shoeWeight": "nur Schuhe: filigran | normal | chunky",
 "unsicher": ["Feldnamen, bei denen du unsicher bist"]
}"""

BODY_PROMPT = """Auf dem Foto steht eine erwachsene Person frontal in eng anliegender Kleidung. Schätze ausschließlich Proportionen für die Kleidungsberatung ein. Beschreibe die Person nicht weiter.
Antworte nur mit JSON:
{"build":"schlank | normal | athletisch | kräftig","torso":"langer Oberkörper | ausgeglichen | lange Beine","hinweis":"ein Satz, warum die Einschätzung unsicher sein könnte","confidence":0 bis 1}"""


def _dumps(value: Any) -> str:
    """JSON.stringify: kompakt und ohne ASCII-Escapes."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _silhouette_label(profile: dict | None) -> str:
    key = (profile or {}).get("silhouette") or "frei"
    match = next((s for s in SILHOUETTES if s["key"] == key), None)
    if match is None:
        # In JS wuerde .find() hier undefined liefern und der Zugriff auf
        # .label werfen. Ein unbekannter Wert kommt nur aus manipulierten
        # Daten; wir fallen auf die Vorgabe zurueck statt abzustuerzen.
        match = next(s for s in SILHOUETTES if s["key"] == "frei")
    return match["label"]


def _person(profile: dict | None) -> tuple[str, int, str, str, str]:
    p = profile or {}
    gender = p.get("gender") or "männlich"
    height = p.get("height") or 180
    build = p.get("build") or "normal"
    torso = p.get("torso") or "ausgeglichen"
    glasses = ", trägt Brille" if p.get("glasses") else ""
    return gender, height, build, torso, glasses


def trends_prompt(profile: dict | None) -> str:
    gender = (profile or {}).get("gender") or "männlich"
    return (
        f"""Recherchiere im Netz, welche Kleidungstrends aktuell im deutschsprachigen Raum tatsächlich getragen werden, für {gender}. Unterscheide zwischen breit getragenen Entwicklungen und kurzlebigen Nischen. Nenne auch, was aktuell als überholt gilt, aber nur wenn es dafür belastbare Hinweise gibt.
Antworte nur mit JSON:
{{"stand":"Monat und Jahr","trends":["höchstens fünf kurze Stichpunkte"],"ueberholt":["höchstens drei"],"unsicherheit":"ein Satz zur Belastbarkeit"}}"""
    )


def curation_prompt(profile: dict | None, occasion: str, temp: float,
                    trends: dict | None, payload: list) -> str:
    gender, height, build, torso, glasses = _person(profile)
    notes = (profile or {}).get("notes")
    notes_line = f"Eigene Vorgaben: {notes}" if notes else ""
    if trends:
        trend_line = (
            f"Aktuelle Einordnung (Stand {trends.get('stand')}): "
            f"{'; '.join(trends.get('trends') or [])}. "
            f"Gilt als überholt: {'; '.join(trends.get('ueberholt') or [])}."
        )
    else:
        trend_line = ""
    return f"""Du bist ein erfahrener Stylist. Eine Regel-Engine hat bereits alle unzulässigen Kombinationen aussortiert und die zulässigen bewertet. Wähle die drei besten aus und erkläre vor allem, wie man sie trägt.

Person: {gender}, {height} cm, Statur {build}, {torso}{glasses}.
Silhouette: {_silhouette_label(profile)}.
{notes_line}
Anlass: {occasion}. Temperatur: {temp} Grad.
{trend_line}

Regeln für deine Antwort:
- Beziehe dich ausschließlich auf Teile, die im jeweiligen Outfit enthalten sind. Erfinde nichts dazu.
- Die Styling-Schritte müssen konkret und ausführbar sein: Layering-Reihenfolge, Hemd offen oder geschlossen und wie viele Knöpfe, Ärmel gekrempelt und wie, Oberteil eingesteckt, halb eingesteckt oder offen, Hosensaum auf dem Schuh oder gekrempelt, Sitz der Mütze, ob eine Uhr sichtbar getragen wird.
- Der Trendhinweis ist optional und darf die Auswahl nicht überstimmen. Lass ihn weg, wenn er nichts beiträgt.
- Die drei Outfits sollen sich klar unterscheiden.

Kandidaten:
{_dumps(payload)}

Antworte nur mit JSON:
{{"auswahl":[{{"nr":0,"titel":"höchstens drei Wörter","begruendung":"zwei Sätze","styling":["drei bis fünf konkrete Schritte"],"trendhinweis":"ein Satz oder leer"}}]}}"""


def gaps_prompt(profile: dict | None, data: dict) -> str:
    gender, height, build, torso, glasses = _person(profile)
    return f"""Du berätst beim Aufbau einer Garderobe. Die Rechnung ist bereits gemacht, du formulierst sie nur aus und ergänzt konkrete Beispielprodukte.

Person: {gender}, {height} cm, Statur {build}, {torso}{glasses}. Silhouette: {_silhouette_label(profile)}.

Analyse des vorhandenen Schranks:
{_dumps(data)}

"kandidaten" ist nach dem gemessenen Zugewinn sortiert: neueOutfits ist die Anzahl zusätzlicher guter Kombinationen, die dieses Teil im vorhandenen Schrank ermöglichen würde. "waisen" sind vorhandene Teile, die in keiner guten Kombination auftauchen.

Suche im Netz nach aktuell erhältlichen Beispielprodukten und nenne pro Empfehlung ein bis zwei konkrete Modelle mit Marke. Wähle die Preisklasse passend zum Teil: Basics günstig, langlebige Schlüsselstücke dürfen teurer sein. Preise nur als grobe Spanne, ohne Anspruch auf Aktualität.

Regeln:
- Empfiehl nur Teile, die laut Rechnung tatsächlich etwas bringen. Nichts erfinden, was nicht in den Kandidaten steht, außer es löst nachweislich eine Waise auf.
- Nenne bei jeder Empfehlung, welche vorhandenen Teile dadurch neu kombinierbar werden.
- Zu den Waisen: erkläre, woran es liegt, und ob ein neues Teil hilft oder das Stück eher ausrangiert gehört.

Antworte nur mit JSON:
{{"empfehlungen":[{{"teil":"konkrete Beschreibung mit Farbe und Schnitt","warum":"zwei Sätze mit Bezug auf vorhandene Teile","gewinn":"Anzahl neuer Outfits als Zahl","preisspanne":"z.B. 40 bis 70 Euro","beispiele":[{{"marke":"","modell":""}}]}}],"waisen":[{{"teil":"","diagnose":"ein bis zwei Sätze"}}],"hinweis":"ein Satz zur Verlässlichkeit der Produktangaben"}}"""
