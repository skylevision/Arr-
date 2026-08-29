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


# ── Sicherung: Export und Import ────────────────────────────────────────

def test_protokoll_kommt_beim_import_zurueck(frisch):
    """Der Export enthielt das Trageprotokoll schon immer, der Import las
    es nie — nach einer Wiederherstellung fehlte die ganze Historie."""
    db = frisch
    db.insert_item({"id": "a", "name": "A", "category": "Oberteil"})
    eintrag = db.log_outfit(["a"], "Alltag", 16, 0.9)

    # Neue, leere Datenbank simulieren: Protokoll weg, Teil noch da.
    db.connect().execute("DELETE FROM outfit_log")
    db.connect().commit()
    assert db.list_outfit_log() == []

    assert db.merge_outfit_log({"id": eintrag["id"], "worn_at": eintrag["worn_at"],
                                "item_ids": ["a"], "occasion": "Alltag",
                                "temp": 16, "score": 0.9}) is True
    zurueck = db.list_outfit_log()
    assert len(zurueck) == 1
    assert zurueck[0]["occasion"] == "Alltag"
    assert zurueck[0]["item_ids"] == ["a"]


def test_protokoll_import_ist_idempotent(frisch):
    db = frisch
    eintrag = {"id": "log_1", "worn_at": "2026-08-01T10:00:00+00:00",
               "item_ids": ["a"], "occasion": "Arbeit", "temp": 12, "score": 0.8}
    assert db.merge_outfit_log(eintrag) is True
    assert db.merge_outfit_log(eintrag) is False
    assert len(db.list_outfit_log()) == 1


def test_protokoll_import_zaehlt_die_teile_nicht_hoch(frisch):
    """log_outfit() wuerde wearCount erhoehen und die Waesche starten —
    beim Wiederherstellen einer Sicherung waere beides falsch."""
    db = frisch
    db.insert_item({"id": "a", "name": "A", "category": "Oberteil", "wearCount": 7})
    db.merge_outfit_log({"id": "log_1", "worn_at": "2026-08-01T10:00:00+00:00",
                         "item_ids": ["a"], "occasion": "Alltag"})
    teil = db.get_item("a")
    assert teil["wearCount"] == 7
    assert teil["laundryUntil"] is None


def test_gemerkte_outfits_kommen_zurueck_und_doppeln_nicht(frisch):
    db = frisch
    fit = {"id": "fit_1", "name": "Testfit", "itemIds": ["a", "b"], "occasion": "Alltag"}
    assert db.merge_saved_outfit(fit) is True
    assert db.merge_saved_outfit(fit) is False
    gespeichert = db.list_saved_outfits()
    assert len(gespeichert) == 1
    assert gespeichert[0]["itemIds"] == ["a", "b"]


def test_gemerktes_outfit_ohne_id_erkennt_sich_am_namen(frisch):
    """Ein Export aus dem Prototypen bringt keine IDs mit — ohne diese
    Regel legte jeder Lauf dieselben Outfits erneut an."""
    db = frisch
    assert db.merge_saved_outfit({"name": "Ohne Kennung", "itemIds": ["a"]}) is True
    assert db.merge_saved_outfit({"name": "Ohne Kennung", "itemIds": ["a"]}) is False
    assert len(db.list_saved_outfits()) == 1


# ── Klonen ──────────────────────────────────────────────────────────────

def test_klon_uebernimmt_die_eigenschaften(frisch):
    db = frisch
    db.insert_item({"id": "a", "name": "Cordhemd", "category": "Oberteil",
                    "material": "Cord", "brand": "Marke", "size": "M",
                    "care": "30 Grad", "fit": "regular", "tags": "büro",
                    "price": 59.0})
    kopie = db.clone_item("a")
    for feld in ("category", "material", "brand", "size", "care", "fit", "tags", "price"):
        assert kopie[feld] == db.get_item("a")[feld], feld
    assert kopie["name"] == "Cordhemd (Kopie)"
    assert kopie["id"] != "a"


def test_klon_erbt_weder_bild_noch_verlauf(frisch):
    """Das Bild zeigt das andere Teil, und getragen wurde die Kopie nie."""
    db = frisch
    db.insert_item({"id": "a", "name": "A", "category": "Oberteil",
                    "imagePath": "a.jpg", "labelPath": "label_a.jpg",
                    "wearCount": 12, "lastWorn": "2026-08-01T00:00:00+00:00",
                    "laundryUntil": "2099-01-01T00:00:00+00:00", "paused": True})
    kopie = db.clone_item("a")
    assert kopie["imagePath"] is None
    assert kopie["labelPath"] is None
    assert kopie["wearCount"] == 0
    assert kopie["lastWorn"] is None
    assert kopie["laundryUntil"] is None
    assert kopie["paused"] is False


def test_klon_eines_unbekannten_teils(frisch):
    assert frisch.clone_item("gibtsnicht") is None


def test_klon_landet_bei_der_aktiven_person(frisch):
    db = frisch
    p2 = db.add_person("Zweite")
    db.insert_item({"id": "a", "name": "A", "category": "Oberteil"})
    db.setze_person(p2["id"])
    try:
        # Das Quellteil gehoert Person 1 und ist von hier aus unsichtbar.
        assert db.clone_item("a") is None
    finally:
        db.setze_person(1)


# ── Verwaiste Bilder ────────────────────────────────────────────────────

def test_bildpfade_sammeln_ueber_alle_personen(frisch):
    """Ohne das loescht ein Aufraeumen die Bilder der jeweils anderen
    Person als vermeintlich verwaist."""
    db = frisch
    p2 = db.add_person("Zweite")
    db.insert_item({"id": "a", "name": "A", "category": "Oberteil",
                    "imagePath": "a.jpg", "labelPath": "label_a.jpg"})
    db.insert_item({"id": "b", "name": "B", "category": "Oberteil",
                    "imagePath": "b.jpg", "personId": p2["id"]})
    db.merge_outfit_log({"id": "log_1", "worn_at": "2026-08-01T00:00:00+00:00",
                         "item_ids": ["a"]}, foto="ootd_log_1.jpg")
    pfade = db.alle_bildpfade()
    assert pfade == {"a.jpg", "label_a.jpg", "b.jpg", "ootd_log_1.jpg"}


def test_fremdes_teil_ist_nicht_erreichbar(frisch):
    """get_item() ohne Personenfilter war ein Leck: samtliche
    Einzelzugriffe — andern, loschen, klonen, Bild abrufen — laufen
    darueber. Wer die Kennung kannte, kam an fremde Teile."""
    db = frisch
    db.insert_item({"id": "a", "name": "Von Person 1", "category": "Oberteil"})
    p2 = db.add_person("Zweite")
    db.setze_person(p2["id"])
    try:
        assert db.get_item("a") is None
        assert db.update_item("a", {"name": "gekapert"}) is None
        assert db.delete_item("a") is False
        assert db.clone_item("a") is None
    finally:
        db.setze_person(1)
    # unversehrt
    assert db.get_item("a")["name"] == "Von Person 1"


def test_kennung_bleibt_ueber_personen_hinweg_eindeutig(frisch):
    """Der Primaerschluessel gilt global — item_exists() sieht das auch
    dann, wenn get_item() die fremde Zeile ausblendet."""
    db = frisch
    db.insert_item({"id": "a", "name": "A", "category": "Oberteil"})
    p2 = db.add_person("Zweite")
    db.setze_person(p2["id"])
    try:
        assert db.get_item("a") is None
        assert db.item_exists("a") is True
    finally:
        db.setze_person(1)


def test_rueckmeldungen_bleiben_je_person_getrennt(frisch):
    db = frisch
    db.set_feedback("a|b", "liked")
    p2 = db.add_person("Zweite")
    db.setze_person(p2["id"])
    try:
        assert db.get_feedback() == {"liked": [], "disliked": []}
        db.set_feedback("c|d", "disliked")
        assert db.get_feedback()["disliked"] == ["c|d"]
    finally:
        db.setze_person(1)
    assert db.get_feedback()["liked"] == ["a|b"]
    assert db.get_feedback()["disliked"] == []


def test_person_loeschen_nimmt_ihre_rueckmeldungen_mit(frisch):
    db = frisch
    p2 = db.add_person("Zweite")
    db.setze_person(p2["id"])
    try:
        db.set_feedback("x|y", "liked")
    finally:
        db.setze_person(1)
    db.set_feedback("a|b", "liked")
    db.delete_person(p2["id"])
    # Die eigene bleibt, die fremde ist weg.
    assert db.get_feedback()["liked"] == ["a|b"]
    uebrig = db.connect().execute("SELECT COUNT(*) c FROM feedback").fetchone()["c"]
    assert uebrig == 1


def test_verwaiste_datensaetze_werden_erkannt(frisch):
    """Zeilen ohne existierende Person tauchen in keiner Ansicht auf und
    fallen sonst niemandem auf. Genau so blieben nach einem fehlerhaften
    Import zwei Teile im Bestand liegen."""
    db = frisch
    assert db.verwaiste_datensaetze() == {}
    db.insert_item({"id": "geist", "name": "Geist", "category": "Oberteil",
                    "personId": 99})
    assert db.verwaiste_datensaetze() == {"items": 1}
    assert db.get_item("geist") is None
    assert [i["id"] for i in db.list_items()] == []
