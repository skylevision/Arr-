# Radarr & Sonarr — Dual Language Setup (Deutsch + Englisch) für 4K

Anleitung für automatische „German DL"-Downloads in **4K / 2160p mit HDR**:
Radarr und Sonarr laden bevorzugt Releases herunter, die **beide Sprachen**
(Deutsch + Englisch) enthalten. Ist kein Dual-Language-Release verfügbar, wird
wahlweise die deutsche oder englische Fassung als Fallback genommen.

> Basiert auf (Stand: Juli 2026, Werte gegen Original-Quellen verifiziert):
> - [PCJones — radarr-sonarr-german-dual-language](https://github.com/PCJones/radarr-sonarr-german-dual-language) — Scoring-System
> - [TRaSH Guides — German Quality Profiles](https://trash-guides.info/Radarr/radarr-setup-quality-profiles-german-en/) — HDR-Formate & 4K-Profile
> - Sprach-/Quell-IDs direkt aus dem Radarr/Sonarr-Quellcode verifiziert

> ⚠️ **Nicht mischen:** Diese Anleitung nutzt das **PCJones-Scoring** (German DL = 25000).
> TRaSH verwendet eine andere Skala (German DL = 11000). Wer TRaSH-Profile per
> Recyclarr/Notifiarr synct, darf die PCJones-Scores nicht parallel im selben Profil verwenden.

---

## Inhaltsverzeichnis

1. [Konzept & Funktionsweise](#1-konzept--funktionsweise)
2. [Voraussetzungen](#2-voraussetzungen)
3. [Medien-Ordner trennen (4K vs. 1080p)](#3-medien-ordner-trennen-4k-vs-1080p)
4. [Globale Einstellungen](#4-globale-einstellungen)
5. [Custom Formats — Sprache](#5-custom-formats--sprache)
6. [Custom Formats — HDR / Dolby Vision](#6-custom-formats--hdr--dolby-vision)
7. [Custom Formats — Qualität (2160p)](#7-custom-formats--qualität-2160p)
8. [Quality Profile: German DL — 4K](#8-quality-profile-german-dl--4k)
9. [Custom Format Scoring — Übersicht](#9-custom-format-scoring--übersicht)
10. [Sonarr — Besonderheiten](#10-sonarr--besonderheiten)
11. [Fallback-Strategie wählen](#11-fallback-strategie-wählen)
12. [Zwei Profile vs. zwei Instanzen](#12-zwei-profile-vs-zwei-instanzen)
13. [Jellyfin — 4K & HDR-Wiedergabe](#13-jellyfin--4k--hdr-wiedergabe)
14. [Testen & Verifizieren](#14-testen--verifizieren)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Konzept & Funktionsweise

Radarr und Sonarr werten Releases anhand von **Custom Format Scores** aus.
Das Ziel: ein 4K Dual-Language-Release mit HDR soll immer höher scored werden
als jedes Single-Language-Release — und innerhalb der DL-Releases gewinnt
das beste Bild (Remux > Bluray > WEB, DV > HDR10 > SDR).

```
Score-Hierarchie (4K-Profil):

  German DL + 2160p Remux + DV + HDR    → ~57.500  ← ideal
  German DL + 2160p Remux + HDR10       → ~56.500  ← sehr gut
  German DL + 2160p WEB-DL + HDR10      → ~52.500  ← gut
  German DL + 2160p WEB-DL (SDR)        → ~52.000  ← akzeptabel
  Deutsch Only + 2160p Remux + HDR      → ~21.500  ← Fallback
  Englisch Only + 2160p WEB-DL          → ~17.000  ← letzter Ausweg
  Andere Sprache                        → -30.000  ✗ blockiert
  Mic-Dubbed                            → -35.000  ✗ blockiert
```

**German DL** bezeichnet Releases die mit beiden Audiotracks erscheinen —
erkennbar an Markierungen wie `German.DL`, `[DE+EN]`, `[ger,eng]`.

**HDR-Hierarchie** (was das Bild verbessert, absteigend):
- **Dolby Vision mit HDR10-Fallback** — dynamisches HDR, läuft auch auf Nicht-DV-Geräten
- **HDR10+** — dynamisches HDR (v. a. Samsung)
- **HDR10** — statisches HDR, breiteste Kompatibilität
- **HLG** — Broadcast-HDR
- **SDR** — kein HDR

> ⚠️ **DV ohne HDR10-Fallback** (manche WEB-Releases) zeigt auf Nicht-DV-Geräten
> falsche Farben (grün/lila) — dafür gibt es unten ein Straf-Custom-Format.

---

## 2. Voraussetzungen

| Anforderung | Details |
|---|---|
| **Radarr** | Version 5+ (aktuell) |
| **Sonarr** | **Version 4** — Version 3 wird nicht unterstützt |
| **Prowlarr** | Indexer konfiguriert und mit Radarr/Sonarr verbunden |
| **Indexer** | Mindestens ein Indexer mit deutschen 4K-Releases |
| **Speicher** | 4K Remux: ~50–80 GB pro Film, WEB-DL: ~15–25 GB |
| **TV/Monitor** | 4K-fähig, idealerweise HDR10 oder Dolby Vision |
| **Netzwerk** | Lokal: Gigabit-LAN empfohlen (4K Remux streamt mit 80+ Mbit/s) |

> **Speicher-Tipp:** 4K-Dateien sind 3–5× größer als 1080p. Für 100 Filme
> in 4K Remux brauchst du ~5 TB, als WEB-DL ~2 TB.

---

## 3. Medien-Ordner trennen (4K vs. 1080p)

Für 4K empfehlen wir **getrennte Bibliotheken** — so kann Jellyfin die richtige
Version je nach Client ausspielen (4K-TV bekommt 4K, Handy bekommt 1080p).

### 3.1 Ordner anlegen

```bash
mkdir -p /mnt/user/data/media/movies-4k
mkdir -p /mnt/user/data/media/tv-4k
chown 99:100 /mnt/user/data/media/movies-4k /mnt/user/data/media/tv-4k
```

> `setup.sh` legt diese Ordner ab sofort automatisch mit an.

### 3.2 Root Folders in Radarr / Sonarr

**Radarr:** `Settings → Media Management → Root Folders → Add Root Folder`

| Root Folder | Verwendung |
|---|---|
| `/data/media/movies` | 1080p-Filme |
| `/data/media/movies-4k` | 4K-Filme (dieses Profil) |

**Sonarr:** analog mit `/data/media/tv` und `/data/media/tv-4k`.

### 3.3 Jellyfin-Bibliotheken

In Jellyfin separate Bibliotheken anlegen:
- **Filme** → `/data/media/movies`
- **Filme (4K)** → `/data/media/movies-4k`
- **Serien** → `/data/media/tv`
- **Serien (4K)** → `/data/media/tv-4k`

> **Warum getrennt?** Wenn ein Client kein 4K/HDR kann, muss Jellyfin transkodieren —
> das frisst CPU/GPU. Mit getrennten Bibliotheken steuerst du den Zugriff pro Nutzer.

---

## 4. Globale Einstellungen

Diese Einstellungen müssen **vor** dem Anlegen der Quality Profiles gesetzt werden.

### 4.1 Propers & Repacks deaktivieren

Radarr und Sonarr würden sonst automatisch neuere Versionen downloaden,
was in Kombination mit Custom Formats zu Download-Schleifen führt.

**Radarr:** `Settings → Media Management → File Management`
**Sonarr:** `Settings → Media Management → File Management`

```
Propers and Repacks:   Do Not Prefer
```

### 4.2 Sprache im Quality Profile auf „Any" setzen

Nicht hier, sondern im Quality Profile selbst (→ Schritt 8).
Der Grund: Radarr/Sonarr matchen sonst nur Releases, deren Metadaten
exakt die gewählte Sprache angeben — was bei deutschen Releases oft fehlt.

---

## 5. Custom Formats — Sprache

### Wo importieren?

**Radarr:** `Settings → Custom Formats → + (Add Custom Format) → Import`
**Sonarr:** `Settings → Custom Formats → + (Add Custom Format) → Import`

JSON in das Textfeld einfügen → **Import** klicken → **Save**.

> Verifizierte Sprach-IDs (aus dem Radarr/Sonarr-Quellcode, identisch in beiden):
> Englisch = `1`, Deutsch = `4`, Original = `-2`

---

### CF 1: German DL

Erkennt alle gängigen Dual-Language-Markierungen in Release-Namen
(ohne WEB-DL-Fehltreffer).

```json
{
  "name": "German DL",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "German DL",
      "implementation": "ReleaseTitleSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": "(?i)german\\s*\\.?dl|(?<=\\bGerman\\b.*)(?<!\\bWEB[-_. ])\\bDL\\b|\\[DE\\+[a-z]{2}\\]|\\[[a-z]{2}\\+DE\\]|ger,\\s*[a-z]{3}\\]|\\[[a-z]{3}\\s*,\\s*ger\\]"
      }
    }
  ]
}
```

---

### CF 2: German DL 2

Fängt Dual-Language-Releases ab, die keine explizite „German DL"-Markierung
im Titel tragen, aber beide Sprachen als Metadaten mitbringen.

```json
{
  "name": "German DL 2",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "Language: German",
      "implementation": "LanguageSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 4
      }
    },
    {
      "name": "Language: English",
      "implementation": "LanguageSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 1
      }
    },
    {
      "name": "NOT German DL",
      "implementation": "ReleaseTitleSpecification",
      "negate": true,
      "required": true,
      "fields": {
        "value": "(?i)german\\s*\\.?dl|(?<=\\bGerman\\b.*)(?<!\\bWEB[-_. ])\\bDL\\b|\\[DE\\+[a-z]{2}\\]|\\[[a-z]{2}\\+DE\\]|ger,\\s*[a-z]{3}\\]|\\[[a-z]{3}\\s*,\\s*ger\\]"
      }
    }
  ]
}
```

---

### CF 3: Language: Not ENG/GER

Blockiert Releases, die weder Englisch noch Deutsch enthalten.

```json
{
  "name": "Language: Not ENG/GER",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "Not English",
      "implementation": "LanguageSpecification",
      "negate": true,
      "required": false,
      "fields": {
        "value": 1
      }
    },
    {
      "name": "Not German",
      "implementation": "LanguageSpecification",
      "negate": true,
      "required": false,
      "fields": {
        "value": 4
      }
    },
    {
      "name": "Not Original Language",
      "implementation": "LanguageSpecification",
      "negate": true,
      "required": false,
      "fields": {
        "value": -2
      }
    }
  ]
}
```

> Alle drei Spezifikationen müssen `required: false` haben —
> das Format greift, wenn **alle drei** zutreffen.

---

### CF 4a: Language: German Only *(für Fallback auf Deutsch)*

```json
{
  "name": "Language: German Only",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "Language: German",
      "implementation": "LanguageSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 4
      }
    },
    {
      "name": "NOT German DL",
      "implementation": "ReleaseTitleSpecification",
      "negate": true,
      "required": true,
      "fields": {
        "value": "(?i)german\\s*\\.?dl|(?<=\\bGerman\\b.*)(?<!\\bWEB[-_. ])\\bDL\\b|\\[DE\\+[a-z]{2}\\]|\\[[a-z]{2}\\+DE\\]|ger,\\s*[a-z]{3}\\]|\\[[a-z]{3}\\s*,\\s*ger\\]"
      }
    },
    {
      "name": "Not English",
      "implementation": "LanguageSpecification",
      "negate": true,
      "required": true,
      "fields": {
        "value": 1
      }
    }
  ]
}
```

---

### CF 4b: Language: English Only *(für Fallback auf Englisch)*

```json
{
  "name": "Language: English Only",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "Language: English",
      "implementation": "LanguageSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 1
      }
    },
    {
      "name": "NOT German DL",
      "implementation": "ReleaseTitleSpecification",
      "negate": true,
      "required": true,
      "fields": {
        "value": "(?i)german\\s*\\.?dl|(?<=\\bGerman\\b.*)(?<!\\bWEB[-_. ])\\bDL\\b|\\[DE\\+[a-z]{2}\\]|\\[[a-z]{2}\\+DE\\]|ger,\\s*[a-z]{3}\\]|\\[[a-z]{3}\\s*,\\s*ger\\]"
      }
    },
    {
      "name": "Not German",
      "implementation": "LanguageSpecification",
      "negate": true,
      "required": true,
      "fields": {
        "value": 4
      }
    }
  ]
}
```

> **Nur eines der beiden importieren** (CF 4a oder CF 4b) — je nach gewünschtem
> Fallback (→ [Schritt 11](#11-fallback-strategie-wählen)).

---

### CF 5: MIC Dubbed

Blockiert Releases mit Mikrofon-/Line-Synchronisation (schlechte Tonqualität).
Gerade die **ersten** German-DL-Releases eines Films haben oft einen
Mic-Dubbed-Ton — dieses CF verhindert, dass sie geladen werden.

```json
{
  "name": "MIC Dubbed",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "MIC Dubbed",
      "implementation": "ReleaseTitleSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": "(?i)\\b(MIC|LINE)[-. ]?DUB(bed)?\\b|\\bLD\\b"
      }
    }
  ]
}
```

> Laut PCJones vor allem für **Radarr** wichtig (Kino-Releases) — bei Sonarr
> schadet es aber auch nicht. Wer Mic-Dubs als Zwischenlösung akzeptiert
> (wird später durch sauberes Release ersetzt): Score `-100` statt `-35000`.

---

## 6. Custom Formats — HDR / Dolby Vision

Moderner TRaSH-Ansatz (verifiziert Juli 2026): **ein** generisches HDR-Format
plus kleine „Boost"-Formate — statt vieler einzelner DV/HDR10-Formate.
In **Radarr und Sonarr** importieren.

---

### CF 6: HDR

Erkennt jede Form von HDR (HDR, HDR10, HDR10+, DV, HLG, PQ).

```json
{
  "name": "HDR",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "HDR",
      "implementation": "ReleaseTitleSpecification",
      "negate": false,
      "required": false,
      "fields": {
        "value": "(?i)\\bHDR(10(\\+|P(lus)?)?)?\\b"
      }
    },
    {
      "name": "DV",
      "implementation": "ReleaseTitleSpecification",
      "negate": false,
      "required": false,
      "fields": {
        "value": "(?i)\\b(dv|dovi|dolby[ .]?v(ision)?)\\b"
      }
    },
    {
      "name": "HLG",
      "implementation": "ReleaseTitleSpecification",
      "negate": false,
      "required": false,
      "fields": {
        "value": "(?i)\\bHLG\\b"
      }
    },
    {
      "name": "PQ",
      "implementation": "ReleaseTitleSpecification",
      "negate": false,
      "required": false,
      "fields": {
        "value": "(?i)\\bPQ\\b"
      }
    }
  ]
}
```

> Alle Spezifikationen `required: false` — **eine** davon reicht (OR-Logik).

---

### CF 7: DV Boost

Bevorzugt Dolby Vision zusätzlich zum generischen HDR-Score.

```json
{
  "name": "DV Boost",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "Dolby Vision",
      "implementation": "ReleaseTitleSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": "(?i)\\b(dv|dovi|dolby[ .]?v(ision)?)\\b"
      }
    }
  ]
}
```

---

### CF 8: HDR10+ Boost

```json
{
  "name": "HDR10+ Boost",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "HDR10+",
      "implementation": "ReleaseTitleSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": "(?i)\\bHDR10(?=[+]|P(lus)?\\b)"
      }
    }
  ]
}
```

---

### CF 9: DV (ohne HDR10-Fallback)

**Wichtig:** WEB-Releases mit reinem Dolby Vision (ohne HDR10-Layer) zeigen
auf Nicht-DV-Geräten falsche Farben. Dieses CF bestraft solche Releases.

```json
{
  "name": "DV (w/o HDR10 fallback)",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "Dolby Vision",
      "implementation": "ReleaseTitleSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": "(?i)\\b(dv|dovi|dolby[ .]?v(ision)?)\\b"
      }
    },
    {
      "name": "Not HDR",
      "implementation": "ReleaseTitleSpecification",
      "negate": true,
      "required": true,
      "fields": {
        "value": "(?i)\\bHDR(10)?(\\+|P(lus)?)?\\b"
      }
    }
  ]
}
```

> Wenn **alle** deine Abspielgeräte Dolby Vision beherrschen (z. B. nur
> Nvidia Shield / Apple TV 4K am OLED): Score `0` statt `-10000`.

---

## 7. Custom Formats — Qualität (2160p)

Diese CFs sorgen dafür, dass innerhalb der German-DL-Releases die beste
Quelle gewinnt. **Radarr und Sonarr haben unterschiedliche IDs** —
die JSONs unten sind daher pro App getrennt.

> Verifizierte Quell-IDs (aus dem Quellcode):
>
> | Quelle | Radarr `SourceSpecification` | Sonarr `SourceSpecification` |
> |---|---|---|
> | Blu-ray | `9` | `6` |
> | WEB-DL | `7` | `3` |
> | WEBRip | `8` | `4` |
> | HDTV | `6` (TV) | `1` |
> | Remux | Modifier `5` (`QualityModifierSpecification`) | BlurayRaw = `7` (als Source) |

### CF 10 (Radarr): Remux-2160p

```json
{
  "name": "Remux-2160p",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "2160p",
      "implementation": "ResolutionSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 2160
      }
    },
    {
      "name": "Remux",
      "implementation": "QualityModifierSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 5
      }
    }
  ]
}
```

### CF 10 (Sonarr): Remux-2160p

```json
{
  "name": "Remux-2160p",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "2160p",
      "implementation": "ResolutionSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 2160
      }
    },
    {
      "name": "BlurayRaw",
      "implementation": "SourceSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 7
      }
    }
  ]
}
```

### CF 11 (Radarr): Bluray-2160p

```json
{
  "name": "Bluray-2160p",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "2160p",
      "implementation": "ResolutionSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 2160
      }
    },
    {
      "name": "Bluray",
      "implementation": "SourceSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 9
      }
    },
    {
      "name": "Not Remux",
      "implementation": "QualityModifierSpecification",
      "negate": true,
      "required": true,
      "fields": {
        "value": 5
      }
    }
  ]
}
```

### CF 11 (Sonarr): Bluray-2160p

```json
{
  "name": "Bluray-2160p",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "2160p",
      "implementation": "ResolutionSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 2160
      }
    },
    {
      "name": "Bluray",
      "implementation": "SourceSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 6
      }
    }
  ]
}
```

### CF 12 (Radarr): WEBDL-2160p

```json
{
  "name": "WEBDL-2160p",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "2160p",
      "implementation": "ResolutionSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 2160
      }
    },
    {
      "name": "WEBDL",
      "implementation": "SourceSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 7
      }
    }
  ]
}
```

### CF 12 (Sonarr): WEBDL-2160p

```json
{
  "name": "WEBDL-2160p",
  "includeCustomFormatWhenRenaming": false,
  "specifications": [
    {
      "name": "2160p",
      "implementation": "ResolutionSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 2160
      }
    },
    {
      "name": "WEBDL",
      "implementation": "SourceSpecification",
      "negate": false,
      "required": true,
      "fields": {
        "value": 3
      }
    }
  ]
}
```

---

## 8. Quality Profile: German DL — 4K

**Radarr/Sonarr:** `Settings → Quality Profiles → + (Add Profile)`

### 8.1 Basis-Einstellungen

| Feld | Wert |
|---|---|
| **Name** | `German DL - 4K` |
| **Language** | `Any` |
| **Upgrades Allowed** | ✓ aktiviert |
| **Upgrade Until** | `Remux-2160p` |
| **Upgrade Until Custom Format Score** | `60000` |
| **Minimum Custom Format Score** | `0` |

> **Warum 60000 statt PCJones' 50000?** Mit 50000 stoppt das Upgrade sobald
> irgendein German-DL-Release da ist (25000 + 25000 = 50000). Mit 60000 wird
> innerhalb der DL-Releases weiter auf besseres Bild (Remux, DV/HDR)
> geupgradet — der maximale realistische Score liegt bei ≈ 57600.

### 8.2 Qualities zusammenführen (Merge)

Qualitäten müssen zusammengefasst werden, damit Radarr/Sonarr
innerhalb der Gruppe nach dem **höchsten Custom Format Score** auswählt
— nicht nach der Qualitätsstufe. Sonst schlägt Qualität immer Sprache.

**So geht's:**
1. Im Quality Profile auf die **Drag-Handles** (≡) klicken und Qualitäten
   übereinander ziehen, bis sie in **einer Gruppe** zusammengefasst sind.
2. Oder: den Pfeil „▸" neben der Gruppe anklicken → „Edit Group"

**Empfohlene 4K-Gruppe (alle in EINER Gruppe zusammenführen):**

```
Gruppe „4K German DL" (✓ aktiviert):
  ├─ Remux-2160p
  ├─ Bluray-2160p
  ├─ WEBDL-2160p
  └─ WEBRip-2160p

NICHT aktivieren:
  ✗ HDTV-2160p (schlechte Encodes)
  ✗ alle 1080p/720p-Qualitäten (gehören ins 1080p-Profil)
```

> **Alles in eine Gruppe!** Das ist der häufigste Fehler: sind Remux und WEB-DL
> in getrennten Gruppen, gewinnt immer die höhere Gruppe — auch wenn sie nur
> Englisch ist. Die Score-Steuerung funktioniert nur innerhalb **einer** Gruppe.

---

## 9. Custom Format Scoring — Übersicht

Nach dem Anlegen des Quality Profiles → Custom Formats mit Scores versehen.

**Radarr/Sonarr:** `Settings → Quality Profiles → [German DL - 4K] → Custom Formats`

### 9.1 Alle Scores auf einen Blick

| Custom Format | Score | Zweck |
|---|---|---|
| **German DL** | `25000` | Dual-Language bevorzugen (Titel) |
| **German DL 2** | `25000` | Dual-Language bevorzugen (Metadaten) |
| **Language: German Only** | `15000` | Fallback Deutsch *(nur bei Option A)* |
| **Language: English Only** | `15000` | Fallback Englisch *(nur bei Option B)* |
| **Language: Not ENG/GER** | `-30000` | Andere Sprachen blockieren |
| **MIC Dubbed** | `-35000` | Mic-/Line-Dubs blockieren |
| **Remux-2160p** | `6000` | Beste 4K-Quelle |
| **Bluray-2160p** | `4000` | Bluray-Encode |
| **WEBDL-2160p** | `2000` | WEB-Download |
| **HDR** | `500` | Jede Form von HDR bevorzugen |
| **DV Boost** | `1000` | Dolby Vision zusätzlich bevorzugen |
| **HDR10+ Boost** | `100` | HDR10+ leicht bevorzugen |
| **DV (w/o HDR10 fallback)** | `-10000` | Inkompatible DV-only-Releases abwerten |

### 9.2 Scores visualisiert

```
German DL 2160p Remux, DV+HDR10:
  25000 + 25000 + 6000 + 500 + 1000       = 57.500  ✓ Ideal

German DL 2160p Remux, HDR10:
  25000 + 25000 + 6000 + 500              = 56.500  ✓ Sehr gut

German DL 2160p WEB-DL, HDR10+:
  25000 + 25000 + 2000 + 500 + 100        = 52.600  ✓ Gut

German DL 2160p WEB-DL, SDR:
  25000 + 25000 + 2000                    = 52.000  ✓ Akzeptabel

German DL 2160p WEB-DL, DV ohne Fallback:
  25000 + 25000 + 2000 + 1000 - 10000     = 43.000  ~ abgewertet

Deutsch Only 2160p Remux, HDR:
  15000 + 6000 + 500                      = 21.500  ~ Fallback

Andere Sprache:                            = -30.000  ✗ Geblockt
Mic Dubbed:                                = -35.000  ✗ Geblockt
```

---

## 10. Sonarr — Besonderheiten

### 10.1 Version prüfen

`System → About` → Version muss **4.x** sein.
Version 3 unterstützt die benötigten Sprachspezifikationen nicht.

### 10.2 Series Type

Bei Serien die **Anime** sind:
- `Series Type: Anime` setzen (in der Serie → Edit)
- Separates Quality Profile mit Anime-spezifischen Custom Formats empfehlenswert

### 10.3 Season Packs bevorzugen

Für deutsche Releases gibt es oft Season Packs mit Dual-Language.
`Settings → Indexers → Season Pack Preference: Prefer Season Packs`

### 10.4 Eigene Quality-CFs für Sonarr

Die Quell-IDs unterscheiden sich von Radarr (→ Tabelle in [Schritt 7](#7-custom-formats--qualität-2160p)).
Die Sonarr-Varianten der Quality-CFs verwenden — nicht die Radarr-JSONs kopieren!

### 10.5 4K-Serien — Verfügbarkeit

4K-Serien sind seltener als 4K-Filme, besonders als German DL.
Beliebte Serien gibt es meist in 4K DL, viele andere nur auf Englisch.

→ Fallback-Strategie ist bei Serien besonders wichtig (→ [Schritt 11](#11-fallback-strategie-wählen)).

---

## 11. Fallback-Strategie wählen

Wenn kein Dual-Language-Release existiert, greift der Fallback.
**Nur eines** der folgenden CFs importieren und mit Score `15000` versehen:

### Option A: Fallback auf Deutsch *(empfohlen für DE-Nutzer)*

`Language: German Only` importieren und mit `15000` scoren.

```
Priorität: German DL (4K HDR) → German DL (4K) → Deutsch Only (4K) → Rest geblockt
```

Sinnvoll wenn: Synchronfassung bevorzugt wird.

### Option B: Fallback auf Englisch *(empfohlen für Originalton)*

`Language: English Only` importieren und mit `15000` scoren.

```
Priorität: German DL (4K HDR) → German DL (4K) → Englisch Only (4K) → Rest geblockt
```

### Option C: Kein Fallback

Weder CF 4a noch CF 4b importieren — nur German DL wird geladen.

> **4K-Tipp:** Bei 4K ist ein Fallback dringend empfohlen — das Angebot an
> deutschen 4K-DL-Releases ist deutlich kleiner als bei 1080p.

---

## 12. Zwei Profile vs. zwei Instanzen

### Option A: Getrennte Profile (empfohlen)

`German DL - 4K` und `German DL - 1080p` in **derselben** Radarr/Sonarr-Instanz.
Beim Hinzufügen eines Films wählst du Profil + Root Folder:

| Profil | Root Folder | Qualities |
|---|---|---|
| `German DL - 4K` | `/data/media/movies-4k` | nur 2160p |
| `German DL - 1080p` | `/data/media/movies` | nur 1080p/720p |

**Vorteil:** Einfach, ein Radarr reicht.
**Nachteil:** Ein Film ist entweder 4K **oder** 1080p — nicht beides.

### Option B: Zwei Radarr-Instanzen

Ein Radarr für 1080p, ein zweites für 4K — derselbe Film kann in beiden
Versionen existieren (Jellyfin zeigt dann beide Versionen an).

**Vorteil:** 4K für den TV **und** 1080p für unterwegs.
**Nachteil:** Doppelte Konfiguration, doppelter RAM.

> **Empfehlung:** Starte mit **Option A**. Zwei Instanzen lohnen sich erst,
> wenn du wirklich beide Versionen desselben Films brauchst.

---

## 13. Jellyfin — 4K & HDR-Wiedergabe

### 13.1 Hardware-Transcoding aktivieren

Für 4K ist Hardware-Transcoding praktisch Pflicht — Software-Transcoding
von 4K HDR schafft kaum eine CPU in Echtzeit.

**Intel QuickSync (empfohlen für Unraid):**

In `docker-compose.yml` beim Jellyfin-Service die auskommentierten Zeilen aktivieren:

```yaml
jellyfin:
  ...
  devices:
    - /dev/dri:/dev/dri
```

Dann in Jellyfin: `Admin → Playback → Transcoding`
- Hardware acceleration: **Intel QuickSync (QSV)**
- Enable hardware decoding für: H.264, HEVC, HEVC 10bit, VP9, AV1 (je nach CPU-Generation)

**Nvidia GPU:**

```yaml
jellyfin:
  ...
  runtime: nvidia
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
```

Hardware acceleration: **NVIDIA NVENC**

### 13.2 Tone-Mapping für HDR → SDR

Wenn ein Client kein HDR kann, muss Jellyfin HDR zu SDR konvertieren —
sonst sieht das Bild ausgewaschen/grau aus.

`Admin → Playback → Transcoding`:
- ✓ **Enable Tone-Mapping**
- ✓ **Enable VPP Tone-Mapping** (nur Intel — schneller als OpenCL)

### 13.3 Direct Play (das Ziel)

Am besten: gar nicht transkodieren. Wenn der Client 4K + HEVC + HDR direkt
abspielen kann, gibt es keinen Qualitätsverlust und keine Serverlast.

**Clients mit gutem 4K/HDR Direct Play:**
- Nvidia Shield Pro (auch DV)
- Apple TV 4K (auch DV)
- Moderne 4K-TVs mit nativer Jellyfin-App
- Fire TV Stick 4K / 4K Max (HDR10+, teils DV)

**Netzwerk:** 4K Remux braucht 80–120 Mbit/s → Gigabit-LAN oder WiFi 6.

### 13.4 Untertitel und Transcoding

PGS-Untertitel (Blu-ray-Bitmaps) erzwingen **immer** Video-Transcoding.
SRT/ASS-Untertitel laufen ohne Transcoding.

→ Bazarr lädt automatisch SRT-Untertitel — die bevorzugt aktivieren.

---

## 14. Testen & Verifizieren

### 14.1 Custom Format-Erkennung prüfen

1. Film öffnen → **Interactive Search** (Lupe-Icon)
2. In der Ergebnisliste die **Custom Formats**-Spalte prüfen
3. Ein 4K-German-DL-Release sollte zeigen: `German DL`, `HDR`, ggf. `DV Boost`, `Remux-2160p`

### 14.2 Score-Summe prüfen

Die Spalte **„CF Score"** zeigt den Gesamtscore.
Ein German-DL-Release mit 4K + HDR sollte **≥ 52000** zeigen.

### 14.3 HDR-Erkennung testen

Suche einen bekannten 4K-HDR-Film (z. B. „Dune", „Oppenheimer") und prüfe:
- Wird `HDR` als Custom Format erkannt?
- Bekommt ein DV-Release zusätzlich `DV Boost`?
- Ist der Score höher als beim SDR-Release desselben Films?

### 14.4 Typische 4K-DL-Release-Namen

So sehen korrekte Treffer aus:
```
Film.Titel.2024.German.DL.2160p.UHD.BluRay.HDR.HEVC.Remux-GROUP
Film.Titel.2024.German.DL.2160p.WEB.DV.HDR.DDP5.1.H265-GROUP
Serie.S01E01.German.DL.2160p.WEB.H265-GROUP
```

---

## 15. Troubleshooting

### Keine 4K-Releases gefunden

1. **Indexer prüfen:** Nicht alle Indexer führen 4K — Indexer-Suche direkt in Prowlarr testen
2. **Qualitätsfilter:** Sind die 2160p-Qualitäten im Profil aktiviert (✓)?
3. **Angebot:** Deutsche 4K-DL-Releases sind rar — Fallback aktivieren (→ Schritt 11)

### HDR wird nicht erkannt

1. **Release-Name prüfen:** Steht „HDR", „DV", „DoVi" im Titel? Nur Titel-Matching ist zuverlässig
2. **Regex testen:** [regex101.com](https://regex101.com) mit dem Release-Namen füttern

### 4K-Datei wird transkodiert statt Direct Play

1. **Client:** Unterstützt er HEVC + HDR? (ältere Geräte oft nicht)
2. **Untertitel:** PGS-Subs erzwingen Transcoding → SRT verwenden
3. **Bitrate-Limit:** Jellyfin → Playback → Streaming → Limit erhöhen (200 Mbit/s)
4. **Netzwerk:** WiFi 5 ist oft zu langsam für 4K Remux → LAN nutzen

### Endlos-Download-Loop

Zwei Releases tauschen sich ständig gegenseitig aus.

1. `Propers and Repacks: Do Not Prefer` gesetzt? (→ Schritt 4.1)
2. `German DL` und `German DL 2` haben **exakt** denselben Score (25000)?
3. `Upgrade Until Custom Format Score` erreicht? → auf 60000 prüfen

### Sprache wird nicht erkannt (Sonarr)

- Sonarr **v4**? (`System → About`)
- `LanguageSpecification` mit `value: 4` für Deutsch?
- Nicht alle Indexer melden Sprachmetadaten
  → `German DL` (Titel-Regex) ist zuverlässiger als `German DL 2` (Metadaten)

### 4K braucht zu viel Speicher

- Remux-2160p aus dem Profil nehmen → WEB-DL (15–25 GB) statt Remux (50–80 GB)
- Oder Score tauschen: `WEBDL-2160p: 6000`, `Remux-2160p: 0`

### Umlaute / Titel-Matching-Probleme

Deutsche Titel mit Umlauten (ä, ö, ü) werden von Indexern manchmal
als `ae`, `oe`, `ue` oder weggelassen gemeldet.

Lösung: **UmlautAdaptarr** (aktiv gepflegt, offiziell von TRaSH empfohlen):
- GitHub: [PCJones/UmlautAdaptarr](https://github.com/PCJones/UmlautAdaptarr)
- Docker-Container zwischen Prowlarr und den Arr-Apps
- Mappt Umlaute automatisch für korrekte Titel-Matches

---

## Schnellreferenz

```
Schritt 1: Settings → Media Management → Propers and Repacks: Do Not Prefer

Schritt 2: 4K-Ordner anlegen + als Root Folder eintragen:
  /data/media/movies-4k   (Radarr)
  /data/media/tv-4k       (Sonarr)

Schritt 3: Custom Formats importieren (JSONs oben):
  Sprache:
    ✓ German DL                        Score:  25000
    ✓ German DL 2                      Score:  25000
    ✓ Language: Not ENG/GER            Score: -30000
    ✓ German Only ODER English Only    Score:  15000
    ✓ MIC Dubbed                       Score: -35000
  HDR:
    ✓ HDR                              Score:    500
    ✓ DV Boost                         Score:   1000
    ✓ HDR10+ Boost                     Score:    100
    ✓ DV (w/o HDR10 fallback)          Score: -10000
  Qualität (Radarr- und Sonarr-Variante beachten!):
    ✓ Remux-2160p                      Score:   6000
    ✓ Bluray-2160p                     Score:   4000
    ✓ WEBDL-2160p                      Score:   2000

Schritt 4: Quality Profile "German DL - 4K":
  Language:                Any
  Upgrade Until:           Remux-2160p
  Upgrade Until CF Score:  60000
  Nur 2160p-Qualitäten — ALLE in EINER Gruppe zusammenführen!

Schritt 5: Jellyfin → Hardware-Transcoding + Tone-Mapping aktivieren
           Separate 4K-Bibliotheken anlegen

Schritt 6: Interactive Search — German DL + 4K + HDR = Score ≥ 52000
```
