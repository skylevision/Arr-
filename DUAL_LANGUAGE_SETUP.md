# Radarr & Sonarr — Dual Language Setup (Deutsch + Englisch)

Anleitung für automatische „German DL"-Downloads: Radarr und Sonarr laden bevorzugt
Releases herunter, die **beide Sprachen** (Deutsch + Englisch) enthalten. Ist kein
Dual-Language-Release verfügbar, wird wahlweise die deutsche oder englische Fassung
als Fallback genommen.

> Basiert auf:
> - [PCJones — radarr-sonarr-german-dual-language](https://github.com/PCJones/radarr-sonarr-german-dual-language)
> - [TRaSH Guides — German Quality Profiles](https://trash-guides.info/Radarr/radarr-setup-quality-profiles-german-en/)

---

## Inhaltsverzeichnis

1. [Konzept & Funktionsweise](#1-konzept--funktionsweise)
2. [Voraussetzungen](#2-voraussetzungen)
3. [Globale Einstellungen](#3-globale-einstellungen)
4. [Custom Formats importieren](#4-custom-formats-importieren)
5. [Quality Profile anlegen](#5-quality-profile-anlegen)
6. [Custom Format Scoring](#6-custom-format-scoring)
7. [Sonarr — Besonderheiten](#7-sonarr--besonderheiten)
8. [Fallback-Strategie wählen](#8-fallback-strategie-wählen)
9. [Testen & Verifizieren](#9-testen--verifizieren)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Konzept & Funktionsweise

Radarr und Sonarr werten Releases anhand von **Custom Format Scores** aus.
Das Ziel: ein Dual-Language-Release soll immer höher scored werden als jedes
Single-Language-Release, unabhängig von der Qualitätsstufe.

```
Score-Hierarchie:

  German DL Release (1080p)     → Score: ~27.000  ← bevorzugt
  German DL Release (720p)      → Score: ~25.000  ← noch bevorzugt
  German-Only Release (1080p)   → Score: ~19.000  ← Fallback
  English-Only Release (1080p)  → Score:  ~6.000  ← letzter Ausweg
  Unbekannte Sprache            → Score: -30.000  ← blockiert
```

**German DL** bezeichnet Releases die in der Szene mit beiden Audiotracks
erscheinen — erkennbar an Markierungen wie `German.DL`, `[DE+EN]`, `[ger,eng]`.

---

## 2. Voraussetzungen

| Anforderung | Details |
|---|---|
| **Radarr** | Version 5+ (aktuell) |
| **Sonarr** | **Version 4** — Version 3 wird nicht unterstützt |
| **Prowlarr** | Indexer konfiguriert und mit Radarr/Sonarr verbunden |
| **Indexer** | Mindestens ein Indexer mit deutschen Releases (z. B. HDCity, RSBay, HDS, NBL) |

---

## 3. Globale Einstellungen

Diese Einstellungen müssen **vor** dem Anlegen der Quality Profiles gesetzt werden.

### 3.1 Propers & Repacks deaktivieren

Radarr und Sonarr würden sonst automatisch neuere Versionen downloaden,
was in Kombination mit Custom Formats zu Download-Schleifen führt.

**Radarr:** `Settings → Media Management → File Management`
**Sonarr:** `Settings → Media Management → File Management`

```
Propers and Repacks:   Do Not Prefer
```

> Repacks werden stattdessen über Custom Formats gesteuert (Repack/Proper: +5).

### 3.2 Sprache im Quality Profile auf „Any" setzen

Nicht hier, sondern im Quality Profile selbst (→ Schritt 5).
Der Grund: Radarr/Sonarr matchen sonst nur Releases, deren Metadaten
exakt die gewählte Sprache angeben — was bei deutschen Releases oft fehlt.

---

## 4. Custom Formats importieren

### Wo importieren?

**Radarr:** `Settings → Custom Formats → + (Add Custom Format) → Import`
**Sonarr:** `Settings → Custom Formats → + (Add Custom Format) → Import`

JSON in das Textfeld einfügen → **Import** klicken → **Save**.

---

### CF 1: German DL

Erkennt alle gängigen Dual-Language-Markierungen in Release-Namen.

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
Verhindert z. B. französische oder spanische Releases.

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

> ⚠️ Alle drei Spezifikationen müssen `required: false` haben —
> das Format greift, wenn **alle drei** zutreffen (AND-Logik bei required=false mit negate=true).

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

> **Nur eines der beiden importieren** (CF 4a oder CF 4b) — je nach gewünschtem Fallback
> (→ [Schritt 8](#8-fallback-strategie-wählen)).

---

### CF 5: MIC Dubbed *(optional, empfohlen)*

Blockiert Releases mit Mikrofon-Synchronisation (schlechte Tonqualität).

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
        "value": "(?i)\\bMIC[-. ]?DUB(bed)?\\b"
      }
    }
  ]
}
```

---

## 5. Quality Profile anlegen

**Radarr/Sonarr:** `Settings → Quality Profiles → + (Add Profile)`

### 5.1 Basis-Einstellungen

| Feld | Wert |
|---|---|
| **Name** | `German DL - 1080p` (oder nach Wunsch) |
| **Language** | `Any` |
| **Upgrades Allowed** | ✓ aktiviert |
| **Upgrade Until** | Höchste gewünschte Qualität (z. B. `Remux-1080p`) |
| **Upgrade Until Custom Format Score** | `50000` |
| **Minimum Custom Format Score** | `0` |

### 5.2 Qualities zusammenführen (Merge)

Qualitäten müssen zusammengefasst werden, damit Radarr/Sonarr
innerhalb der Gruppe nach dem **höchsten Custom Format Score** auswählt
— nicht nach der Qualitätsstufe. Sonst würde ein schlechteres
Dual-Language-Release nie ein besseres Single-Language-Release ersetzen.

**So geht's:**
1. Im Quality Profile auf die **Drag-Handles** (≡) klicken und Qualitäten
   übereinander ziehen, bis sie in **einer Gruppe** zusammengefasst sind.
2. Oder: den Pfeil „▸" neben der Gruppe anklicken → „Edit Group"

**Empfohlene Gruppen:**

```
Gruppe 1 (höchste Priorität):
  └─ Remux-1080p

Gruppe 2:
  ├─ Bluray-1080p
  ├─ WEBRip-1080p
  └─ WEBDL-1080p

Gruppe 3:
  ├─ Bluray-720p
  ├─ WEBRip-720p
  └─ WEBDL-720p
```

> Alle aktivierten Qualitäten mit ✓ markieren.
> Nicht gewünschte Qualitäten (z. B. HDTV) deaktiviert lassen.

---

## 6. Custom Format Scoring

Nach dem Anlegen des Quality Profiles → Custom Formats mit Scores versehen.

**Radarr/Sonarr:** `Settings → Quality Profiles → [Profil auswählen] → Custom Formats`

### 6.1 Pflicht-Scores

| Custom Format | Score | Zweck |
|---|---|---|
| **German DL** | `25000` | Dual-Language bevorzugen |
| **German DL 2** | `25000` | Dual-Language bevorzugen (Metadaten-basiert) |
| **Language: Not ENG/GER** | `-30000` | Andere Sprachen blockieren |
| **Language: German Only** | `15000` | Fallback Deutsch (nur CF 4a importiert) |
| **Language: English Only** | `15000` | Fallback Englisch (nur CF 4b importiert) |
| **MIC Dubbed** | `-35000` | Mic-Dubs blockieren |

### 6.2 Qualitäts-Scores *(optional, für Upgrades innerhalb Dual-Language)*

Damit Radarr/Sonarr ein besseres Dual-Language-Release bevorzugt,
wenn mehrere vorhanden sind:

| Custom Format | Score | Zweck |
|---|---|---|
| **Remux-1080p** | `6000` | Beste 1080p-Quelle bevorzugen |
| **Bluray-1080p** | `4000` | Bluray bevorzugen |
| **WEBDL-1080p** | `2000` | WEB-Quelle |
| **Bluray-720p** | `0` | Basis-Fallback |

> Diese Custom Formats müssen separat angelegt werden (je eigener CF mit
> Source + Resolution als Specification). Radarr und Sonarr haben
> unterschiedliche interne Quell-IDs — die Spezifikationen daher
> **getrennt für beide Apps anlegen**.

### 6.3 Scores visualisiert

```
Dual Language 1080p Remux:   25000 + 25000 + 6000 = 56000  ✓ Ideal
Dual Language 1080p Bluray:  25000 + 25000 + 4000 = 54000  ✓ Sehr gut
Dual Language 1080p WEB:     25000 + 25000 + 2000 = 52000  ✓ Gut
Dual Language 720p:          25000 + 25000 +    0 = 50000  ✓ OK

Deutsch Only 1080p:               0 +     0 + 4000 + 15000 = 19000  ~ Fallback
Englisch Only 1080p:              0 +     0 + 4000 + 15000 = 19000  ~ Fallback

Andere Sprache:                                             = -30000  ✗ Geblockt
Mic Dubbed:                                                = -35000  ✗ Geblockt
```

---

## 7. Sonarr — Besonderheiten

Sonarr v4 verhält sich weitgehend identisch zu Radarr. Folgende Unterschiede beachten:

### 7.1 Version prüfen

`System → About` → Version muss **4.x** sein.
Version 3 unterstützt die benötigten Sprachspezifikationen nicht.

### 7.2 Series Type

Bei Serien die **Anime** sind:
- `Series Type: Anime` setzen (in der Serie → Edit)
- Separate Quality Profile mit Anime-spezifischen Custom Formats empfehlenswert

### 7.3 Season Packs bevorzugen

Für deutsche Releases gibt es oft Season Packs mit Dual-Language.
Kein separates Custom Format nötig — Sonarr bevorzugt Season Packs automatisch,
wenn `Settings → Indexers → Season Pack Preference` auf `Prefer Season Packs` steht.

### 7.4 Unterschied: Qualitäts-Custom-Formats

Die Quell-IDs in Sonarr unterscheiden sich von Radarr:

| Quelle | Radarr ID | Sonarr ID |
|---|---|---|
| Blu-ray | `9` | `7` |
| WEB-DL | `7` | `3` |
| WEBRip | `8` | `15` |
| HDTV | — | `4` |

→ Qualitäts-Custom-Formats (Remux-1080p etc.) müssen für Sonarr
mit den richtigen IDs **neu angelegt** werden.

---

## 8. Fallback-Strategie wählen

Wenn kein Dual-Language-Release existiert, greift der Fallback.
**Nur eines** der folgenden CFs importieren und mit Score `15000` versehen:

### Option A: Fallback auf Deutsch *(empfohlen für DE-Nutzer)*

`Language: German Only` importieren und mit `15000` scoren.

```
Priorität: German DL → Deutsch → (Englisch/Andere geblockt)
```

Sinnvoll wenn: Synchronisation bevorzugt, nicht alle Titel haben DL-Release.

### Option B: Fallback auf Englisch *(empfohlen für Originaltreue)*

`Language: English Only` importieren und mit `15000` scoren.

```
Priorität: German DL → Englisch → (Deutsch/Andere geblockt)
```

Sinnvoll wenn: Originalton bevorzugt, nur Dual-Language als Kompromiss.

### Option C: Kein Fallback

Weder CF 4a noch CF 4b importieren.

```
Priorität: German DL → (alles andere geblockt durch -30000)
```

Sinnvoll wenn: **Nur** Dual-Language-Releases gewünscht werden,
alles andere soll gar nicht erst heruntergeladen werden.

---

## 9. Testen & Verifizieren

### 9.1 Custom Format-Erkennung prüfen

In Radarr/Sonarr einen Film/eine Serie manuell suchen:

1. Film öffnen → **Manual Search** (Lupe-Icon oben rechts)
2. In der Ergebnisliste auf ein Release klicken → **Custom Formats** Spalte prüfen
3. Ein German-DL-Release sollte `German DL` und/oder `German DL 2` zeigen

### 9.2 Score-Summe prüfen

In der Manual-Search-Ansicht zeigt die Spalte **„CF Score"** den Gesamtscore.
Ein German-DL-Release sollte ≥ 50000 zeigen.

### 9.3 Radarr — Interactive Search

`Movies → [Film] → Interactive Search`

Sortierung nach „CF Score" absteigend → Dual-Language-Releases sollten
ganz oben stehen.

### 9.4 Bekannte Test-Releases

Folgende Suchbegriffe im Manual Search eingeben um DL-Releases zu sehen:
- `German.DL.1080p`
- `[DE+EN]`
- `ger,eng`

---

## 10. Troubleshooting

### Kein DL-Release wird gefunden

1. **Prowlarr prüfen:** `Indexers → Test All` — alle Indexer erreichbar?
2. **Suchbegriff prüfen:** Sind Indexer mit deutschen Releases konfiguriert?
3. **Qualitätsfilter:** Ist die Qualität im Profil aktiviert und `✓` gesetzt?
4. **Score-Cutoff:** `Minimum Custom Format Score` zu hoch? → auf `0` setzen

### DL-Release wird heruntergeladen, aber kein Upgrade

- `Upgrades Allowed` im Profil aktiviert?
- `Upgrade Until Custom Format Score` auf `50000` gesetzt?
- Vorhandene Datei hat bereits höheren Score als das neue Release?

### Endlos-Download-Loop

Passiert wenn zwei Releases ständig gegeneinander tauschen.
Ursache: Scores sind so konfiguriert, dass Release A > B > A > B ...

Lösung:
1. `Settings → Media Management → File Management → Propers and Repacks: Do Not Prefer` prüfen
2. `German DL` und `German DL 2` haben **exakt** denselben Score (beide 25000)
3. Qualitäts-CFs prüfen: keine gegenseitige Überschneidung

### Deutsche Sprache wird nicht erkannt (Sonarr)

- Sonarr v4? (`System → About`)
- `LanguageSpecification` mit `value: 4` für Deutsch korrekt?
- Indexer liefert Sprachmetadaten? (nicht alle Indexer melden Sprache)
  → `German DL` (Titel-Regex) ist zuverlässiger als `German DL 2` (Metadaten)

### Umlaute / Titel-Matching-Probleme

Deutsche Titel mit Umlauten (ä, ö, ü) werden von Indexern manchmal
als `ae`, `oe`, `ue` oder weggelassen gemeldet.

Lösung: **UmlautAdaptarr** als Middleware zwischen Prowlarr und Radarr/Sonarr.
- GitHub: [PCJones/UmlautAdaptarr](https://github.com/PCJones/UmlautAdaptarr)
- Docker-Container der zwischen Prowlarr und den Arr-Apps sitzt
- Mappt Umlaute automatisch für korrekte Titel-Matches

---

## Schnellreferenz

```
Schritt 1: Settings → Media Management → Propers and Repacks: Do Not Prefer

Schritt 2: Custom Formats importieren (JSON oben):
  ✓ German DL
  ✓ German DL 2
  ✓ Language: Not ENG/GER
  ✓ Language: German Only  ODER  Language: English Only
  ✓ MIC Dubbed  (optional)

Schritt 3: Quality Profile anlegen:
  Language:   Any
  Upgrade Until CF Score:  50000
  Qualities zusammenführen (Merge)

Schritt 4: Custom Format Scores setzen:
  German DL:            25000
  German DL 2:          25000
  Language: Not ENG/GER: -30000
  German/English Only:  15000
  MIC Dubbed:           -35000

Schritt 5: Testen via Manual Search
```
