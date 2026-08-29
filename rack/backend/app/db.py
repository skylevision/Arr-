"""SQLite mit WAL. Einzige Stelle, an der snake_case und camelCase
aufeinandertreffen.

Die Engine und die API sprechen die camelCase-Form des Prototypen, die
Tabellen die snake_case-Form aus dem Briefing. Die Umsetzung passiert nur
hier, damit kein Aufrufer beide Formen kennen muss.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import settings

log = logging.getLogger("rack.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id              TEXT PRIMARY KEY,
  name            TEXT,
  category        TEXT,
  subcategory     TEXT,
  color_hex       TEXT,
  color_name      TEXT,
  pattern         TEXT,
  pattern_scale   TEXT,
  material        TEXT,
  material_secondary TEXT,
  thickness       TEXT,
  texture         TEXT,
  fit             TEXT,
  length          TEXT,
  rise            TEXT,
  sleeve          TEXT,
  shoe_weight     TEXT,
  warmth          REAL,
  formality       REAL,
  warmth_manual   INTEGER NOT NULL DEFAULT 0,
  formality_manual INTEGER NOT NULL DEFAULT 0,
  image_path      TEXT,
  cutout          INTEGER NOT NULL DEFAULT 0,
  paused          INTEGER NOT NULL DEFAULT 0,
  last_worn       TEXT,
  laundry_until   TEXT,
  price           REAL,
  bought_at       TEXT,
  brand           TEXT,
  size            TEXT,
  care            TEXT,
  archived        INTEGER NOT NULL DEFAULT 0,
  wear_count      INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile (
  id         INTEGER PRIMARY KEY CHECK (id = 1),
  gender     TEXT,
  height     INTEGER,
  build      TEXT,
  torso      TEXT,
  glasses    INTEGER NOT NULL DEFAULT 0,
  silhouette TEXT,
  notes      TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
  pair_key   TEXT PRIMARY KEY,
  verdict    TEXT NOT NULL CHECK (verdict IN ('liked', 'disliked')),
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outfit_log (
  id         TEXT PRIMARY KEY,
  worn_at    TEXT NOT NULL,
  item_ids   TEXT NOT NULL,
  occasion   TEXT,
  temp       REAL,
  score      REAL,
  photo_path TEXT
);

-- Gespeicherte Outfits: ein Vorschlag, der funktioniert hat, unter einem
-- Namen. Die Teile stehen als JSON-Liste drin und nicht als Fremdschluessel,
-- weil ein geloeschtes Teil das Outfit nicht mitreissen soll — es fehlt dann
-- eben eines, und das sieht man in der Oberflaeche.
CREATE TABLE IF NOT EXISTS saved_outfits (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  item_ids   TEXT NOT NULL,
  notes      TEXT,
  occasion   TEXT,
  created_at TEXT NOT NULL
);

-- Geplante Outfits: was an welchem Tag angezogen werden soll. Ein Tag, ein
-- Eintrag — deshalb plan_date als Primaerschluessel.
CREATE TABLE IF NOT EXISTS planned_outfits (
  plan_date  TEXT PRIMARY KEY,
  item_ids   TEXT NOT NULL,
  occasion   TEXT,
  notes      TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trends_cache (
  id         TEXT PRIMARY KEY,
  payload    TEXT NOT NULL,
  fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS items_category ON items (category);
CREATE INDEX IF NOT EXISTS outfit_log_worn ON outfit_log (worn_at);
"""

# DB-Spalte -> Feldname in Engine und API
FIELDS = [
    ("id", "id"), ("name", "name"), ("category", "category"),
    ("subcategory", "subcategory"), ("color_hex", "colorHex"),
    ("color_name", "colorName"), ("pattern", "pattern"),
    ("pattern_scale", "patternScale"), ("material", "material"),
    ("material_secondary", "materialSecondary"),
    ("thickness", "thickness"), ("texture", "texture"), ("fit", "fit"),
    ("length", "length"), ("rise", "rise"), ("sleeve", "sleeve"),
    ("shoe_weight", "shoeWeight"), ("warmth", "warmth"),
    ("formality", "formality"), ("warmth_manual", "warmthManual"),
    ("formality_manual", "formalityManual"), ("image_path", "imagePath"),
    ("cutout", "cutout"), ("paused", "paused"), ("last_worn", "lastWorn"),
    ("laundry_until", "laundryUntil"), ("price", "price"),
    ("bought_at", "boughtAt"), ("brand", "brand"), ("size", "size"),
    ("care", "care"), ("archived", "archived"),
    ("wear_count", "wearCount"), ("created_at", "createdAt"),
]
COL_TO_KEY = dict(FIELDS)
KEY_TO_COL = {k: c for c, k in FIELDS}

_local = threading.local()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "it") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def connect() -> sqlite3.Connection:
    """Eine Verbindung pro Thread. FastAPI bedient Requests aus einem Pool,
    und SQLite-Verbindungen sind nicht threadsicher."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        settings.ensure_dirs()
        conn = sqlite3.connect(settings.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


# Nachtraeglich hinzugekommene Spalten. SCHEMA legt nur an, was noch
# nicht existiert ("CREATE TABLE IF NOT EXISTS") — auf einer bestehenden
# Datenbank aendert es nichts. Ohne diese Liste wuerde jede neue Spalte
# beim naechsten Start zu "no such column" fuehren, und zwar erst im
# laufenden Betrieb, nicht beim Deployment.
#
# Regeln fuer Eintraege: nur additiv (ADD COLUMN), immer NULL-faehig oder
# mit DEFAULT, nie umbenennen oder loeschen. SQLite kann ADD COLUMN ohne
# Tabellenkopie, das laeuft auch auf grossen Bestaenden sofort durch.
MIGRATIONS: list[tuple[str, str, str]] = [
    # (Tabelle, Spalte, Deklaration)
    ("items", "material_secondary", "TEXT"),
    ("items", "laundry_until", "TEXT"),
    ("items", "price", "REAL"),
    ("items", "bought_at", "TEXT"),
    ("items", "brand", "TEXT"),
    ("items", "size", "TEXT"),
    ("items", "care", "TEXT"),
    ("items", "archived", "INTEGER NOT NULL DEFAULT 0"),
    ("outfit_log", "photo_path", "TEXT"),
]


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Fehlende Spalten ergaenzen. Idempotent, gibt das Getane zurueck."""
    done: list[str] = []
    for table, column, decl in MIGRATIONS:
        if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,)).fetchone():
            continue
        if column in _columns(conn, table):
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        done.append(f"{table}.{column}")
    return done


def backfill_materials(conn: sqlite3.Connection) -> int:
    """Bestehende Materialangaben auf das Vokabular bringen.

    Vor dem 29.08.2026 war material ein Freitextfeld; im Bestand stehen
    Werte wie "Wildleder/Mesh", die kein Auswahlfeld anzeigen kann. Diese
    Migration schreibt den normalisierten Hauptwert zurueck und legt ein
    erkanntes Zweitmaterial in der neuen Spalte ab.

    Idempotent: was schon zum Vokabular passt und kein Zweitmaterial
    verbirgt, wird nicht angefasst. Nicht zuordenbare Angaben bleiben
    unveraendert stehen, statt still geloescht zu werden — dann sieht man
    sie in der Oberflaeche als "nicht gesetzt" und kann sie von Hand
    korrigieren.
    """
    from .engine import split_materials

    geaendert = 0
    for row in conn.execute(
            "SELECT id, material, material_secondary FROM items").fetchall():
        roh = row["material"]
        if not roh:
            continue
        haupt, zweit = split_materials(roh)
        if haupt is None:
            # Nicht zuordenbar: stehen lassen, damit es sichtbar bleibt.
            continue
        bestand_zweit = row["material_secondary"] or None
        # Ein bereits abgelegtes Zweitmaterial nur ersetzen, wenn der
        # Rohwert selbst eines enthaelt. Sonst wuerde der zweite Lauf
        # loeschen, was der erste gerade angelegt hat.
        neu_zweit = zweit if zweit is not None else bestand_zweit
        if roh == haupt and neu_zweit == bestand_zweit:
            continue
        conn.execute(
            "UPDATE items SET material = ?, material_secondary = ? WHERE id = ?",
            (haupt, neu_zweit, row["id"]))
        geaendert += 1
    return geaendert


def init() -> None:
    conn = connect()
    with conn:
        conn.executescript(SCHEMA)
        applied = migrate(conn)
        umgestellt = backfill_materials(conn)
    if applied:
        log.info("Schema ergaenzt: %s", ", ".join(applied))
    if umgestellt:
        log.info("Materialangaben normalisiert: %d Teile", umgestellt)


# ── Umsetzung zwischen Zeile und Objekt ─────────────────────────────────

def row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    item = {COL_TO_KEY[c]: row[c] for c in row.keys() if c in COL_TO_KEY}
    for flag in ("cutout", "paused", "warmthManual", "formalityManual", "archived"):
        item[flag] = bool(item.get(flag))
    return item


def item_to_row(item: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for col, key in FIELDS:
        if key not in item:
            continue
        value = item[key]
        if key in ("cutout", "paused", "warmthManual", "formalityManual", "archived"):
            value = 1 if value else 0
        row[col] = value
    return row


# ── Items ───────────────────────────────────────────────────────────────

def list_items() -> list[dict[str, Any]]:
    return [row_to_item(r) for r in
            connect().execute("SELECT * FROM items ORDER BY created_at DESC")]


def get_item(item_id: str) -> dict[str, Any] | None:
    row = connect().execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return row_to_item(row) if row else None


def insert_item(item: dict[str, Any]) -> dict[str, Any]:
    row = item_to_row(item)
    row.setdefault("id", new_id())
    row.setdefault("created_at", now_iso())
    cols = ", ".join(row)
    marks = ", ".join(f":{c}" for c in row)
    conn = connect()
    with conn:
        conn.execute(f"INSERT INTO items ({cols}) VALUES ({marks})", row)
    return get_item(row["id"])


def update_item(item_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    row = item_to_row(patch)
    row.pop("id", None)
    row.pop("created_at", None)
    if not row:
        return get_item(item_id)
    sets = ", ".join(f"{c} = :{c}" for c in row)
    conn = connect()
    with conn:
        conn.execute(f"UPDATE items SET {sets} WHERE id = :id", {**row, "id": item_id})
    return get_item(item_id)


def delete_item(item_id: str) -> bool:
    conn = connect()
    with conn:
        cur = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    return cur.rowcount > 0


# ── Profil ──────────────────────────────────────────────────────────────

PROFILE_DEFAULT = {"gender": "männlich", "height": 180, "build": "normal",
                   "torso": "ausgeglichen", "glasses": False,
                   "silhouette": "frei", "notes": ""}


def get_profile() -> dict[str, Any]:
    row = connect().execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if not row:
        return dict(PROFILE_DEFAULT)
    p = {k: row[k] for k in row.keys() if k != "id"}
    p["glasses"] = bool(p.get("glasses"))
    return p


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    merged = {**get_profile(), **{k: v for k, v in profile.items() if k in PROFILE_DEFAULT}}
    merged["glasses"] = 1 if merged.get("glasses") else 0
    conn = connect()
    with conn:
        conn.execute(
            """INSERT INTO profile (id, gender, height, build, torso, glasses, silhouette, notes)
               VALUES (1, :gender, :height, :build, :torso, :glasses, :silhouette, :notes)
               ON CONFLICT(id) DO UPDATE SET
                 gender=excluded.gender, height=excluded.height, build=excluded.build,
                 torso=excluded.torso, glasses=excluded.glasses,
                 silhouette=excluded.silhouette, notes=excluded.notes""",
            merged)
    return get_profile()


# ── Feedback ────────────────────────────────────────────────────────────

def get_feedback() -> dict[str, list[str]]:
    """Liefert die Form, die die Engine erwartet."""
    out = {"liked": [], "disliked": []}
    for row in connect().execute("SELECT pair_key, verdict FROM feedback"):
        out[row["verdict"]].append(row["pair_key"])
    return out


def set_feedback(pair: str, verdict: str | None) -> None:
    conn = connect()
    with conn:
        if verdict is None:
            conn.execute("DELETE FROM feedback WHERE pair_key = ?", (pair,))
        else:
            conn.execute(
                """INSERT INTO feedback (pair_key, verdict, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(pair_key) DO UPDATE SET
                     verdict=excluded.verdict, updated_at=excluded.updated_at""",
                (pair, verdict, now_iso()))


# ── Outfit-Protokoll ────────────────────────────────────────────────────

def log_outfit(item_ids: list[str], occasion: str | None,
               temp: float | None, score: float | None) -> dict[str, Any]:
    """Outfit protokollieren und die getragenen Teile in die Waesche geben.

    Die Waeschefrist wird hier gesetzt, nicht in der API: so landet sie
    auch dann in der Datenbank, wenn das Protokollieren spaeter von
    woanders aufgerufen wird.
    """
    from .engine import goes_to_laundry

    entry = {"id": new_id("log"), "worn_at": now_iso(),
             "item_ids": json.dumps(item_ids), "occasion": occasion,
             "temp": temp, "score": score}
    frist = (datetime.now(timezone.utc)
             + timedelta(days=settings.laundry_days)).isoformat()
    # Was in den naechsten Tagen eingeplant ist, bleibt verfuegbar — sonst
    # nimmt die Waesche einem das Hemd weg, das man fuer Freitag vorgemerkt
    # hat. Wer es trotzdem waschen will, schaltet es von Hand auf pausiert.
    eingeplant = geplante_teile(datetime.now(timezone.utc).date().isoformat())
    conn = connect()
    with conn:
        conn.execute(
            """INSERT INTO outfit_log (id, worn_at, item_ids, occasion, temp, score)
               VALUES (:id, :worn_at, :item_ids, :occasion, :temp, :score)""", entry)
        for item_id in item_ids:
            row = conn.execute(
                "SELECT category FROM items WHERE id = ?", (item_id,)).fetchone()
            waesche = frist if (row and goes_to_laundry(dict(row))
                                and item_id not in eingeplant) else None
            conn.execute(
                """UPDATE items SET last_worn = ?, wear_count = wear_count + 1,
                   laundry_until = COALESCE(?, laundry_until) WHERE id = ?""",
                (entry["worn_at"], waesche, item_id))
    return {**entry, "item_ids": item_ids}


def set_outfit_photo(log_id: str, pfad: str) -> None:
    conn = connect()
    with conn:
        conn.execute("UPDATE outfit_log SET photo_path = ? WHERE id = ?", (pfad, log_id))


def list_outfit_log(limit: int = 200) -> list[dict[str, Any]]:
    rows = connect().execute(
        "SELECT * FROM outfit_log ORDER BY worn_at DESC LIMIT ?", (limit,))
    return [{**{k: r[k] for k in r.keys()}, "item_ids": json.loads(r["item_ids"])}
            for r in rows]


# ── Gespeicherte Outfits ────────────────────────────────────────────────

def _outfit_row(row: sqlite3.Row) -> dict[str, Any]:
    d = {k: row[k] for k in row.keys()}
    d["itemIds"] = json.loads(d.pop("item_ids"))
    if "created_at" in d:
        d["createdAt"] = d.pop("created_at")
    if "plan_date" in d:
        d["datum"] = d.pop("plan_date")
    return d


def list_saved_outfits() -> list[dict[str, Any]]:
    return [_outfit_row(r) for r in connect().execute(
        "SELECT * FROM saved_outfits ORDER BY created_at DESC")]


def save_outfit(name: str, item_ids: list[str], occasion: str | None = None,
                notes: str | None = None) -> dict[str, Any]:
    entry = {"id": new_id("fit"), "name": name,
             "item_ids": json.dumps(item_ids), "occasion": occasion,
             "notes": notes, "created_at": now_iso()}
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO saved_outfits (id, name, item_ids, occasion, notes, created_at) "
            "VALUES (:id, :name, :item_ids, :occasion, :notes, :created_at)", entry)
    row = connect().execute(
        "SELECT * FROM saved_outfits WHERE id = ?", (entry["id"],)).fetchone()
    return _outfit_row(row)


def delete_saved_outfit(outfit_id: str) -> bool:
    conn = connect()
    with conn:
        cur = conn.execute("DELETE FROM saved_outfits WHERE id = ?", (outfit_id,))
    return cur.rowcount > 0


# ── Geplante Outfits ────────────────────────────────────────────────────

def list_plans(von: str | None = None, bis: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM planned_outfits"
    args: list[Any] = []
    if von and bis:
        sql += " WHERE plan_date BETWEEN ? AND ?"
        args = [von, bis]
    sql += " ORDER BY plan_date"
    return [_outfit_row(r) for r in connect().execute(sql, args)]


def get_plan(datum: str) -> dict[str, Any] | None:
    row = connect().execute(
        "SELECT * FROM planned_outfits WHERE plan_date = ?", (datum,)).fetchone()
    return _outfit_row(row) if row else None


def set_plan(datum: str, item_ids: list[str], occasion: str | None = None,
             notes: str | None = None) -> dict[str, Any]:
    # Ein Tag, ein Outfit — ein zweiter Eintrag ersetzt den ersten.
    entry = {"plan_date": datum, "item_ids": json.dumps(item_ids),
             "occasion": occasion, "notes": notes, "created_at": now_iso()}
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO planned_outfits (plan_date, item_ids, occasion, notes, created_at) "
            "VALUES (:plan_date, :item_ids, :occasion, :notes, :created_at) "
            "ON CONFLICT(plan_date) DO UPDATE SET "
            "  item_ids=excluded.item_ids, occasion=excluded.occasion, "
            "  notes=excluded.notes, created_at=excluded.created_at", entry)
    return get_plan(datum)


def delete_plan(datum: str) -> bool:
    conn = connect()
    with conn:
        cur = conn.execute("DELETE FROM planned_outfits WHERE plan_date = ?", (datum,))
    return cur.rowcount > 0


def geplante_teile(ab: str) -> set[str]:
    # Teile, die ab heute noch eingeplant sind.
    #
    # Die Waesche darf nichts sperren, was in den naechsten Tagen gebraucht
    # wird — sonst plant man ein Hemd fuer Freitag ein und die Automatik
    # nimmt es einem am Mittwoch weg.
    out: set[str] = set()
    for row in connect().execute(
            "SELECT item_ids FROM planned_outfits WHERE plan_date >= ?", (ab,)):
        out.update(json.loads(row["item_ids"]))
    return out


# ── Trends ──────────────────────────────────────────────────────────────

def get_trends() -> dict[str, Any] | None:
    row = connect().execute(
        "SELECT * FROM trends_cache ORDER BY fetched_at DESC LIMIT 1").fetchone()
    if not row:
        return None
    return {"payload": json.loads(row["payload"]), "fetched_at": row["fetched_at"]}


def save_trends(payload: dict[str, Any]) -> dict[str, Any]:
    entry = {"id": new_id("tr"), "payload": json.dumps(payload, ensure_ascii=False),
             "fetched_at": now_iso()}
    conn = connect()
    with conn:
        conn.execute("DELETE FROM trends_cache")
        conn.execute(
            "INSERT INTO trends_cache (id, payload, fetched_at) VALUES (:id, :payload, :fetched_at)",
            entry)
    return {"payload": payload, "fetched_at": entry["fetched_at"]}
