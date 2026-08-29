"""SQLite mit WAL. Einzige Stelle, an der snake_case und camelCase
aufeinandertreffen.

Die Engine und die API sprechen die camelCase-Form des Prototypen, die
Tabellen die snake_case-Form aus dem Briefing. Die Umsetzung passiert nur
hier, damit kein Aufrufer beide Formen kennen muss.
"""

from __future__ import annotations

import contextvars
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
  label_path      TEXT,
  tags            TEXT,
  archived        INTEGER NOT NULL DEFAULT 0,
  person_id       INTEGER NOT NULL DEFAULT 1,
  wear_count      INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL
);

-- Mehrere Personen: der CHECK (id = 1) ist seit 29.08.2026 weg. Auf
-- bestehenden Datenbanken bleibt er stehen — SQLite kann Constraints nicht
-- nachtraeglich loesen — deshalb baut migrate_profile() die Tabelle dort
-- einmal neu auf.
CREATE TABLE IF NOT EXISTS profile (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT,
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
  photo_path TEXT,
  person_id  INTEGER NOT NULL DEFAULT 1
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
  created_at TEXT NOT NULL,
  person_id  INTEGER NOT NULL DEFAULT 1
);

-- Geplante Outfits: was an welchem Tag angezogen werden soll. Ein Tag, ein
-- Eintrag — deshalb plan_date als Primaerschluessel.
CREATE TABLE IF NOT EXISTS planned_outfits (
  plan_date  TEXT NOT NULL,
  person_id  INTEGER NOT NULL DEFAULT 1,
  item_ids   TEXT NOT NULL,
  occasion   TEXT,
  notes      TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (person_id, plan_date)
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
    ("care", "care"), ("label_path", "labelPath"), ("tags", "tags"),
    ("archived", "archived"), ("person_id", "personId"),
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
    ("items", "label_path", "TEXT"),
    ("items", "tags", "TEXT"),
    ("items", "person_id", "INTEGER NOT NULL DEFAULT 1"),
    ("outfit_log", "person_id", "INTEGER NOT NULL DEFAULT 1"),
    ("saved_outfits", "person_id", "INTEGER NOT NULL DEFAULT 1"),
    ("planned_outfits", "person_id", "INTEGER NOT NULL DEFAULT 1"),
    ("profile", "name", "TEXT"),
    ("outfit_log", "photo_path", "TEXT"),
]


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_profile(conn: sqlite3.Connection) -> bool:
    """Die alte Profiltabelle mit CHECK (id = 1) durch eine mehrzeilige ersetzen.

    SQLite kann Constraints nicht nachtraeglich entfernen, also der
    uebliche Weg: neue Tabelle, Daten kopieren, alte weg, umbenennen.
    Laeuft nur, wenn der CHECK wirklich noch dasteht — auf einer frisch
    angelegten Datenbank passiert nichts.

    Bewusst innerhalb der Transaktion des Aufrufers: bricht etwas ab,
    bleibt die alte Tabelle stehen, statt dass das Profil verschwindet.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='profile'").fetchone()
    if not row or "CHECK (id = 1)" not in (row["sql"] or ""):
        return False

    conn.execute("""
        CREATE TABLE profile_neu (
          id         INTEGER PRIMARY KEY AUTOINCREMENT,
          name       TEXT,
          gender     TEXT,
          height     INTEGER,
          build      TEXT,
          torso      TEXT,
          glasses    INTEGER NOT NULL DEFAULT 0,
          silhouette TEXT,
          notes      TEXT
        )""")
    conn.execute("""
        INSERT INTO profile_neu (id, gender, height, build, torso, glasses, silhouette, notes)
        SELECT id, gender, height, build, torso, glasses, silhouette, notes FROM profile""")
    conn.execute("DROP TABLE profile")
    conn.execute("ALTER TABLE profile_neu RENAME TO profile")
    return True


def migrate_plans(conn: sqlite3.Connection) -> bool:
    """planned_outfits auf den zusammengesetzten Schluessel umstellen.

    plan_date allein reichte, solange es eine Person gab. Mit mehreren
    kollidieren zwei Leute, die denselben Tag planen — der zweite Eintrag
    haette den ersten ueberschrieben. SQLite kann den Primaerschluessel
    nicht aendern, also neu aufbauen.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='planned_outfits'"
    ).fetchone()
    if not row:
        return False
    sql = row["sql"] or ""
    if "PRIMARY KEY (person_id, plan_date)" in sql:
        return False

    conn.execute("""
        CREATE TABLE planned_neu (
          plan_date  TEXT NOT NULL,
          person_id  INTEGER NOT NULL DEFAULT 1,
          item_ids   TEXT NOT NULL,
          occasion   TEXT,
          notes      TEXT,
          created_at TEXT NOT NULL,
          PRIMARY KEY (person_id, plan_date)
        )""")
    conn.execute("""
        INSERT OR REPLACE INTO planned_neu
            (plan_date, person_id, item_ids, occasion, notes, created_at)
        SELECT plan_date, COALESCE(person_id, 1), item_ids, occasion, notes, created_at
        FROM planned_outfits""")
    conn.execute("DROP TABLE planned_outfits")
    conn.execute("ALTER TABLE planned_neu RENAME TO planned_outfits")
    return True


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
        # Erst die Profiltabelle, dann die Spalten: der Neuaufbau bringt
        # "name" bereits mit, migrate() ueberspringt den Eintrag dann.
        profil_neu = migrate_profile(conn)
        applied = migrate(conn)
        # Erst nachdem person_id existiert, sonst kopiert der Neuaufbau
        # eine Spalte, die es noch nicht gibt.
        plaene_neu = migrate_plans(conn)
        # Person 1 muss existieren, bevor irgendetwas angelegt wird.
        # Sonst vergibt SQLite die 1 an die erste *hinzugefuegte* Person,
        # und deren Sachen landen im Bestand, der per Vorgabe Person 1
        # zugeordnet ist — beide sehen dann alles.
        if not conn.execute("SELECT 1 FROM profile WHERE id = 1").fetchone():
            conn.execute(
                "INSERT INTO profile (id, name, gender, height, build, torso, "
                "glasses, silhouette, notes) VALUES (1, NULL, :gender, :height, "
                ":build, :torso, 0, :silhouette, :notes)",
                {**PROFILE_DEFAULT, "notes": PROFILE_DEFAULT.get("notes") or ""})
        umgestellt = backfill_materials(conn)
    if profil_neu:
        log.info("Profiltabelle fuer mehrere Personen neu aufgebaut")
    if plaene_neu:
        log.info("Planungstabelle auf (Person, Datum) umgestellt")
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

def list_items(person_id: int | None = None) -> list[dict[str, Any]]:
    return [row_to_item(r) for r in connect().execute(
        "SELECT * FROM items WHERE person_id = ? ORDER BY created_at DESC",
        (_pid(person_id),))]


def get_item(item_id: str) -> dict[str, Any] | None:
    row = connect().execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return row_to_item(row) if row else None


def insert_item(item: dict[str, Any]) -> dict[str, Any]:
    row = item_to_row(item)
    row.setdefault("id", new_id())
    row.setdefault("created_at", now_iso())
    row.setdefault("person_id", aktive_person())
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
    """Teil loeschen — samt der Rueckmeldungen, die es betreffen.

    Die Paare in feedback bestehen aus zwei Teile-IDs. Bleiben sie nach
    dem Loeschen stehen, wachsen sie still mit und koennen im
    unguenstigen Fall eine spaeter neu vergebene ID treffen.
    """
    conn = connect()
    with conn:
        conn.execute(
            "DELETE FROM feedback WHERE pair_key = ? OR pair_key LIKE ? OR pair_key LIKE ?",
            (item_id, f"{item_id}|%", f"%|{item_id}"))
        cur = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    return cur.rowcount > 0


# ── Profil ──────────────────────────────────────────────────────────────

PROFILE_DEFAULT = {"gender": "männlich", "height": 180, "build": "normal",
                   "torso": "ausgeglichen", "glasses": False,
                   "silhouette": "frei", "notes": ""}


def get_profile(person_id: int | None = None) -> dict[str, Any]:
    row = connect().execute(
        "SELECT * FROM profile WHERE id = ?", (_pid(person_id),)).fetchone()
    if not row:
        return dict(PROFILE_DEFAULT)
    p = {k: row[k] for k in row.keys() if k != "id"}
    p["glasses"] = bool(p.get("glasses"))
    p["id"] = row["id"]
    return p


def save_profile(profile: dict[str, Any], person_id: int | None = None) -> dict[str, Any]:
    erlaubt = {**PROFILE_DEFAULT, "name": None}
    person_id = _pid(person_id)
    merged = {**get_profile(person_id),
              **{k: v for k, v in profile.items() if k in erlaubt}}
    merged["glasses"] = 1 if merged.get("glasses") else 0
    merged["id"] = person_id
    merged.setdefault("name", None)
    conn = connect()
    with conn:
        conn.execute(
            """INSERT INTO profile (id, name, gender, height, build, torso,
                                    glasses, silhouette, notes)
               VALUES (:id, :name, :gender, :height, :build, :torso,
                       :glasses, :silhouette, :notes)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name,
                 gender=excluded.gender, height=excluded.height, build=excluded.build,
                 torso=excluded.torso, glasses=excluded.glasses,
                 silhouette=excluded.silhouette, notes=excluded.notes""",
            merged)
    return get_profile(person_id)


# ── Personen ────────────────────────────────────────────────────────────
#
# Bis August 2026 gab es genau eine Profilzeile und keine Zuordnung der
# Teile. Mehrere Personen nachtraeglich einzuziehen ist billig, solange
# der Bestand klein ist, und teuer, sobald er es nicht mehr ist — deshalb
# jetzt.
#
# Der Bestand bekommt Person 1. Alle Abfragen filtern auf die aktive
# Person, die vom Client per Kopfzeile oder Parameter kommt; ohne Angabe
# ist es Person 1. Fuer den Einzelnutzer aendert sich damit nichts.

PERSON_DEFAULT = 1

# Die aktive Person haengt am Request, nicht an einem Modulzustand: eine
# ContextVar wird pro Anfrage gesetzt und ist damit auch dann korrekt,
# wenn mehrere Anfragen gleichzeitig laufen. Der Alternativweg — jede
# Abfragefunktion bekommt person_id durchgereicht — waere an zwanzig
# Aufrufstellen zu aendern gewesen, und eine vergessene haette Daten
# zwischen Personen vermischt, ohne dass etwas kaputtgeht.
_person: contextvars.ContextVar[int] = contextvars.ContextVar(
    "rack_person", default=PERSON_DEFAULT)


def aktive_person() -> int:
    return _person.get()


def setze_person(pid: int) -> None:
    _person.set(pid if pid and pid > 0 else PERSON_DEFAULT)


def _pid(person_id: int | None) -> int:
    return person_id if person_id is not None else aktive_person()


def list_persons() -> list[dict[str, Any]]:
    return [{k: r[k] for k in r.keys()} for r in
            connect().execute("SELECT * FROM profile ORDER BY id")]


def add_person(name: str) -> dict[str, Any]:
    conn = connect()
    with conn:
        cur = conn.execute(
            "INSERT INTO profile (gender, height, build, torso, glasses, silhouette, notes, name) "
            "VALUES (:gender, :height, :build, :torso, :glasses, :silhouette, :notes, :name)",
            {**PROFILE_DEFAULT, "glasses": 0, "name": name})
    row = connect().execute(
        "SELECT * FROM profile WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {k: row[k] for k in row.keys()}


def delete_person(person_id: int) -> tuple[bool, list[str]]:
    """Person und alles, was ihr gehoert.

    Gibt die Bildpfade zurueck, statt die Dateien selbst zu loeschen: db.py
    kennt das Dateisystem nicht, und der Aufrufer raeumt auf. Sonst bleiben
    verwaiste Bilder im Volume liegen.
    """
    # Person 1 bleibt: sie traegt den Bestand, der vor der Umstellung da war.
    if int(person_id) == PERSON_DEFAULT:
        return False, []
    conn = connect()
    bilder = [p for row in conn.execute(
        "SELECT image_path, label_path FROM items WHERE person_id = ?", (person_id,))
        for p in (row["image_path"], row["label_path"]) if p]
    bilder += [row["photo_path"] for row in conn.execute(
        "SELECT photo_path FROM outfit_log WHERE person_id = ?", (person_id,))
        if row["photo_path"]]
    with conn:
        conn.execute(
            "DELETE FROM feedback WHERE pair_key IN ("
            "  SELECT f.pair_key FROM feedback f JOIN items i"
            "    ON f.pair_key LIKE i.id || '|%' OR f.pair_key LIKE '%|' || i.id"
            "  WHERE i.person_id = ?)", (person_id,))
        conn.execute("DELETE FROM items WHERE person_id = ?", (person_id,))
        conn.execute("DELETE FROM outfit_log WHERE person_id = ?", (person_id,))
        conn.execute("DELETE FROM saved_outfits WHERE person_id = ?", (person_id,))
        conn.execute("DELETE FROM planned_outfits WHERE person_id = ?", (person_id,))
        cur = conn.execute("DELETE FROM profile WHERE id = ?", (person_id,))
    return cur.rowcount > 0, bilder


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
             "temp": temp, "score": score, "person_id": aktive_person()}
    frist = (datetime.now(timezone.utc)
             + timedelta(days=settings.laundry_days)).isoformat()
    # Was in den naechsten Tagen eingeplant ist, bleibt verfuegbar — sonst
    # nimmt die Waesche einem das Hemd weg, das man fuer Freitag vorgemerkt
    # hat. Wer es trotzdem waschen will, schaltet es von Hand auf pausiert.
    eingeplant = geplante_teile(datetime.now(timezone.utc).date().isoformat())
    conn = connect()
    with conn:
        conn.execute(
            """INSERT INTO outfit_log
                   (id, worn_at, item_ids, occasion, temp, score, person_id)
               VALUES (:id, :worn_at, :item_ids, :occasion, :temp, :score,
                       :person_id)""", entry)
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


def list_outfit_log(limit: int = 200, person_id: int | None = None) -> list[dict[str, Any]]:
    rows = connect().execute(
        "SELECT * FROM outfit_log WHERE person_id = ? ORDER BY worn_at DESC LIMIT ?",
        (_pid(person_id), limit))
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


def list_saved_outfits(person_id: int | None = None) -> list[dict[str, Any]]:
    return [_outfit_row(r) for r in connect().execute(
        "SELECT * FROM saved_outfits WHERE person_id = ? ORDER BY created_at DESC",
        (_pid(person_id),))]


def save_outfit(name: str, item_ids: list[str], occasion: str | None = None,
                notes: str | None = None) -> dict[str, Any]:
    entry = {"id": new_id("fit"), "name": name,
             "item_ids": json.dumps(item_ids), "occasion": occasion,
             "notes": notes, "created_at": now_iso(),
             "person_id": aktive_person()}
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO saved_outfits "
            "  (id, name, item_ids, occasion, notes, created_at, person_id) "
            "VALUES (:id, :name, :item_ids, :occasion, :notes, :created_at, "
            "        :person_id)", entry)
    row = connect().execute(
        "SELECT * FROM saved_outfits WHERE id = ?", (entry["id"],)).fetchone()
    return _outfit_row(row)


def delete_saved_outfit(outfit_id: str) -> bool:
    conn = connect()
    with conn:
        cur = conn.execute("DELETE FROM saved_outfits WHERE id = ?", (outfit_id,))
    return cur.rowcount > 0


# ── Geplante Outfits ────────────────────────────────────────────────────

def list_plans(von: str | None = None, bis: str | None = None,
               person_id: int | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM planned_outfits WHERE person_id = ?"
    args: list[Any] = [_pid(person_id)]
    if von and bis:
        sql += " AND plan_date BETWEEN ? AND ?"
        args += [von, bis]
    sql += " ORDER BY plan_date"
    return [_outfit_row(r) for r in connect().execute(sql, args)]


def get_plan(datum: str, person_id: int | None = None) -> dict[str, Any] | None:
    row = connect().execute(
        "SELECT * FROM planned_outfits WHERE plan_date = ? AND person_id = ?",
        (datum, _pid(person_id))).fetchone()
    return _outfit_row(row) if row else None


def set_plan(datum: str, item_ids: list[str], occasion: str | None = None,
             notes: str | None = None, person_id: int | None = None) -> dict[str, Any]:
    # Ein Tag, ein Outfit — je Person. Ein zweiter Eintrag ersetzt den ersten.
    person_id = _pid(person_id)
    entry = {"plan_date": datum, "person_id": person_id,
             "item_ids": json.dumps(item_ids),
             "occasion": occasion, "notes": notes, "created_at": now_iso()}
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO planned_outfits "
            "  (plan_date, person_id, item_ids, occasion, notes, created_at) "
            "VALUES (:plan_date, :person_id, :item_ids, :occasion, :notes, :created_at) "
            "ON CONFLICT(person_id, plan_date) DO UPDATE SET "
            "  item_ids=excluded.item_ids, occasion=excluded.occasion, "
            "  notes=excluded.notes, created_at=excluded.created_at", entry)
    return get_plan(datum, person_id)


def delete_plan(datum: str, person_id: int | None = None) -> bool:
    conn = connect()
    with conn:
        cur = conn.execute(
            "DELETE FROM planned_outfits WHERE plan_date = ? AND person_id = ?",
            (datum, _pid(person_id)))
    return cur.rowcount > 0


def geplante_teile(ab: str, person_id: int | None = None) -> set[str]:
    # Teile, die ab heute noch eingeplant sind.
    #
    # Die Waesche darf nichts sperren, was in den naechsten Tagen gebraucht
    # wird — sonst plant man ein Hemd fuer Freitag ein und die Automatik
    # nimmt es einem am Mittwoch weg.
    out: set[str] = set()
    for row in connect().execute(
            "SELECT item_ids FROM planned_outfits "
            "WHERE plan_date >= ? AND person_id = ?", (ab, _pid(person_id))):
        out.update(json.loads(row["item_ids"]))
    return out


def merge_outfit_log(eintrag: dict[str, Any], foto: str | None = None) -> bool:
    """Protokolleintrag aus einem Export uebernehmen.

    Schreibt direkt statt ueber log_outfit(), weil dort die Zaehler an den
    Teilen hochgingen und die Waeschefrist neu gesetzt wuerde — beim
    Wiederherstellen einer Sicherung waere beides falsch. Gibt True
    zurueck, wenn der Eintrag neu war; ein zweiter Import derselben Datei
    aendert nichts.
    """
    if get_outfit_log_entry(eintrag["id"]):
        return False
    ids = eintrag.get("item_ids") or eintrag.get("itemIds") or []
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO outfit_log "
            "  (id, worn_at, item_ids, occasion, temp, score, photo_path, person_id) "
            "VALUES (:id, :worn_at, :item_ids, :occasion, :temp, :score, "
            "        :photo_path, :person_id)",
            {"id": eintrag["id"],
             "worn_at": eintrag.get("worn_at") or eintrag.get("wornAt") or now_iso(),
             "item_ids": json.dumps(ids),
             "occasion": eintrag.get("occasion"), "temp": eintrag.get("temp"),
             "score": eintrag.get("score"), "photo_path": foto,
             "person_id": aktive_person()})
    return True


def get_outfit_log_entry(log_id: str) -> dict[str, Any] | None:
    row = connect().execute(
        "SELECT * FROM outfit_log WHERE id = ?", (log_id,)).fetchone()
    if not row:
        return None
    d = {k: row[k] for k in row.keys()}
    d["item_ids"] = json.loads(d["item_ids"])
    return d


def merge_saved_outfit(fit: dict[str, Any]) -> bool:
    """Gemerktes Outfit aus einem Export uebernehmen, ohne zu doppeln.

    Erkennungsmerkmal ist die ID aus dem Export; fehlt sie, entscheidet
    der Name, damit ein Export aus dem Prototypen nicht bei jedem Lauf
    dieselben Outfits erneut anlegt.
    """
    kennung = fit.get("id")
    if kennung and connect().execute(
            "SELECT 1 FROM saved_outfits WHERE id = ?", (kennung,)).fetchone():
        return False
    if not kennung and connect().execute(
            "SELECT 1 FROM saved_outfits WHERE name = ? AND person_id = ?",
            (fit["name"], aktive_person())).fetchone():
        return False
    entry = {"id": kennung or new_id("fit"), "name": fit["name"],
             "item_ids": json.dumps(fit.get("itemIds") or fit.get("item_ids") or []),
             "occasion": fit.get("occasion"), "notes": fit.get("notes"),
             "created_at": fit.get("createdAt") or now_iso(),
             "person_id": aktive_person()}
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO saved_outfits "
            "  (id, name, item_ids, occasion, notes, created_at, person_id) "
            "VALUES (:id, :name, :item_ids, :occasion, :notes, :created_at, "
            "        :person_id)", entry)
    return True


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
