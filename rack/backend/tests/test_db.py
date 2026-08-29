"""Datenbank: Migrationen und die Trennung nach Personen.

Diese Tests laufen gegen eine echte SQLite-Datei in einem Temp-Ordner,
nicht gegen eine Attrappe: die Migrationen sind der Punkt, an dem eine
Attrappe nichts beweisen wuerde.
"""

from __future__ import annotations

import importlib
import os
import sqlite3

import pytest


@pytest.fixture()
def frisch(tmp_path, monkeypatch):
    """Leere Datenbank, wie beim ersten Start."""
    monkeypatch.setenv("RACK_DATA_DIR", str(tmp_path))
    os.makedirs(tmp_path / "db", exist_ok=True)
    from app import config as c
    importlib.reload(c)
    from app import db as d
    importlib.reload(d)
    d.init()
    return d


@pytest.fixture()
def altbestand(tmp_path, monkeypatch):
    """Datenbank im Zustand vor der Personen-Umstellung."""
    monkeypatch.setenv("RACK_DATA_DIR", str(tmp_path))
    os.makedirs(tmp_path / "db", exist_ok=True)
    con = sqlite3.connect(tmp_path / "db" / "rack.sqlite3")
    con.executescript("""
        CREATE TABLE items (id TEXT PRIMARY KEY, name TEXT, category TEXT,
          material TEXT, paused INTEGER NOT NULL DEFAULT 0, last_worn TEXT,
          wear_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE profile (id INTEGER PRIMARY KEY CHECK (id = 1), gender TEXT,
          height INTEGER, build TEXT, torso TEXT, glasses INTEGER NOT NULL DEFAULT 0,
          silhouette TEXT, notes TEXT);
        CREATE TABLE outfit_log (id TEXT PRIMARY KEY, worn_at TEXT NOT NULL,
          item_ids TEXT NOT NULL, occasion TEXT, temp REAL, score REAL);
        CREATE TABLE planned_outfits (plan_date TEXT PRIMARY KEY, item_ids TEXT NOT NULL,
          occasion TEXT, notes TEXT, created_at TEXT NOT NULL);
        CREATE TABLE saved_outfits (id TEXT PRIMARY KEY, name TEXT NOT NULL,
          item_ids TEXT NOT NULL, notes TEXT, occasion TEXT, created_at TEXT NOT NULL);
    """)
    con.execute("INSERT INTO items (id,name,category,material,created_at) "
                "VALUES ('alt','Altes Shirt','Oberteil','Wildleder/Mesh','2026-01-01')")
    con.execute("INSERT INTO profile VALUES (1,'männlich',183,'normal','ausgeglichen',0,'frei','Notiz')")
    con.execute("INSERT INTO planned_outfits VALUES "
                "('2026-09-05','[\"alt\"]','Arbeit',NULL,'2026-08-01')")
    con.commit()
    con.close()
    from app import config as c
    importlib.reload(c)
    from app import db as d
    importlib.reload(d)
    d.init()
    return d


def test_migration_erhaelt_den_bestand(altbestand):
    db = altbestand
    assert db.get_item("alt")["name"] == "Altes Shirt"
    assert db.get_profile()["height"] == 183
    assert db.get_plan("2026-09-05")["occasion"] == "Arbeit"


def test_migration_loest_den_profil_check(altbestand):
    sql = altbestand.connect().execute(
        "SELECT sql FROM sqlite_master WHERE name='profile'").fetchone()["sql"]
    assert "CHECK" not in sql


def test_migration_stellt_den_plan_schluessel_um(altbestand):
    sql = altbestand.connect().execute(
        "SELECT sql FROM sqlite_master WHERE name='planned_outfits'").fetchone()["sql"]
    assert "PRIMARY KEY (person_id, plan_date)" in sql


def test_migration_normalisiert_das_material(altbestand):
    teil = altbestand.get_item("alt")
    assert teil["material"] == "Wildleder"
    assert teil["materialSecondary"] == "Mesh"


def test_migrationen_sind_idempotent(altbestand):
    conn = altbestand.connect()
    assert altbestand.migrate(conn) == []
    assert altbestand.migrate_profile(conn) is False
    assert altbestand.migrate_plans(conn) is False
    assert altbestand.backfill_materials(conn) == 0


def test_person_eins_existiert_nach_init(frisch):
    """Ohne sie bekaeme die erste hinzugefuegte Person die 1 — und ihre
    Sachen laegen im Bestand, der per Vorgabe Person 1 gehoert."""
    assert [p["id"] for p in frisch.list_persons()] == [1]


def test_teile_bleiben_je_person_getrennt(frisch):
    db = frisch
    db.insert_item({"id": "a", "name": "P1", "category": "Oberteil"})
    p2 = db.add_person("Zweite")
    assert p2["id"] == 2
    db.insert_item({"id": "b", "name": "P2", "category": "Oberteil", "personId": p2["id"]})
    assert [i["name"] for i in db.list_items(1)] == ["P1"]
    assert [i["name"] for i in db.list_items(2)] == ["P2"]


def test_zwei_personen_koennen_denselben_tag_planen(frisch):
    db = frisch
    db.add_person("Zweite")
    db.set_plan("2026-09-05", ["a"], "Arbeit", person_id=1)
    db.set_plan("2026-09-05", ["b"], "Freizeit", person_id=2)
    assert db.get_plan("2026-09-05", 1)["occasion"] == "Arbeit"
    assert db.get_plan("2026-09-05", 2)["occasion"] == "Freizeit"


def test_protokoll_bleibt_je_person_getrennt(frisch):
    db = frisch
    db.insert_item({"id": "a", "name": "P1", "category": "Oberteil"})
    db.add_person("Zweite")
    db.log_outfit(["a"], "Alltag", 16, 0.9)
    assert len(db.list_outfit_log(person_id=1)) == 1
    assert len(db.list_outfit_log(person_id=2)) == 0


def test_person_eins_laesst_sich_nicht_loeschen(frisch):
    """Sie traegt den Bestand, der vor der Umstellung da war."""
    weg, bilder = frisch.delete_person(1)
    assert weg is False and bilder == []
    assert [p["id"] for p in frisch.list_persons()] == [1]


def test_person_loeschen_raeumt_ihre_sachen_weg(frisch):
    db = frisch
    p2 = db.add_person("Zweite")
    db.insert_item({"id": "b", "name": "P2", "category": "Oberteil",
                    "personId": p2["id"], "imagePath": "b.jpg"})
    weg, bilder = db.delete_person(p2["id"])
    assert weg is True
    # Die Bildpfade kommen zurueck, damit der Aufrufer die Dateien
    # entfernen kann — sonst bleiben sie verwaist im Volume liegen.
    assert bilder == ["b.jpg"]
    assert db.get_item("b") is None
    assert [p["id"] for p in db.list_persons()] == [1]


def test_geloeschtes_teil_nimmt_seine_rueckmeldungen_mit(frisch):
    """Sonst wachsen die Paare still mit und koennen spaeter eine neu
    vergebene ID treffen."""
    db = frisch
    db.insert_item({"id": "a", "name": "A", "category": "Oberteil"})
    db.insert_item({"id": "b", "name": "B", "category": "Unterteil"})
    db.set_feedback("a|b", "liked")
    assert db.get_feedback()["liked"] == ["a|b"]
    db.delete_item("a")
    assert db.get_feedback()["liked"] == []
