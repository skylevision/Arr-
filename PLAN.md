# PLAN.md — Neuaufbau Arr-Stack als Code (Phase 1)

> Basiert auf `INVENTORY.md` (2026-07-11) und deinen Entscheidungen:
> Tailscale-Key vorhanden · Vaultwarden/AdGuard/Threadfin **später** (deaktiviert) ·
> Recyclarr ersetzt manuelle Profile · ein Indexer (scenenzbs) · Lidarr/Readarr aus ·
> Strategie **(b) Clean-Bootstrap** · ein Root-Folder pro Typ (kein separates 4K-Verzeichnis).

## 1. Ziel-Ordnerstruktur (TRaSH-Layout)

```
/mnt/user/data/                          nobody:users (99:100), 775
├── downloads/
│   └── usenet/
│       ├── incomplete/
│       └── complete/
│           ├── movies/                  ← SAB-Kategorie movies
│           └── tv/                      ← SAB-Kategorie tv
└── media/
    ├── movies/                          ← Radarr Root (einziger)
    └── tv/                              ← Sonarr Root (einziger)
```

**Änderungen zum Ist:**
| Schritt | Aktion |
|---|---|
| M1 | `media/music`, `media/books` bleiben leer liegen (stören nicht; Lidarr/Readarr aus). Kein Löschen ohne separate Freigabe. |
| M2 | `movies-4k`/`tv-4k` werden aus `setup.sh`/README entfernt (existieren auf dem Server ohnehin nicht). |
| M3 | Ownership-Korrektur: `chown -R nobody:users /mnt/user/data` (idempotent, behebt `root:root` auf `downloads/`+`media/`). |
| M4 | **Alle Container mounten einheitlich `${DATA}:/data`** — auch SABnzbd (bisher `/downloads/usenet`). SAB-Ordner werden per API auf `/data/downloads/usenet/{incomplete,complete}` umgestellt; die **Remote Path Mappings in Radarr/Sonarr entfallen** ersatzlos. Ausnahmen: Bazarr (`${DATA}/media` reicht) und Jellyfin (`${DATA}/media` read-only) bleiben wie gehabt. |

Hardlinks/atomic moves: bereits verifiziert möglich (ein shfs-Device, `fuse_useino=yes`); durch M4 gilt „ein Dateisystem, ein Mount-Pfad" dann auch formal nach TRaSH.

## 2. Ziel-Architektur

### Container-Umfang

| Aktiv | Deaktiviert (Compose-Profil) |
|---|---|
| tailscale, sabnzbd, prowlarr, radarr, sonarr, bazarr, jellyfin, seerr, homepage | `vaultwarden` (Profil `vaultwarden`), `adguardhome` (Profil `adguard`), `threadfin` (Profil `iptv`), lidarr/readarr (bestehende Profile) |

Deaktivierung über **Compose-Profile statt Auskommentieren** — deklarativ, jederzeit per `--profile <name> up -d` aktivierbar, und `docker compose up -d` ohne Profil räumt die laufenden Instanzen (vaultwarden, adguardhome, threadfin) automatisch ab. Der Vaultwarden-Crash-Loop (P2) ist damit sofort weg; zusätzlich wird der `DOMAIN`-Bug im Compose gefixt (Variable nur setzen, wenn nicht leer — via `env_file`-Pattern bzw. Weglassen des leeren Defaults), damit es beim späteren Aktivieren nicht erneut knallt.

### Compose-Änderungen (Phase 2)

1. **Feste Image-Tags** statt `:latest` — gepinnt auf die aktuell laufenden (verifizierten) Versionen, z. B. `radarr:6.1.1`, `sonarr:4.0.17`, `prowlarr:2.3.5`, `jellyfin:10.11.8`; SAB/Bazarr/Seerr/Homepage/Tailscale werden beim Umbau auf ihre tatsächlich laufende Version gepinnt (Digest-Abgleich auf dem Server). Update-Prozess = Tag-Bump im Repo (dokumentiert in Phase 5).
2. **Healthchecks für alle aktiven Dienste** (arr-Apps: `curl /ping`; SAB: API-Ping; Jellyfin: `/health`; Seerr: `/api/v1/status`) und `depends_on: condition: service_healthy` für die Kette SAB/Prowlarr → Radarr/Sonarr → Bazarr/Seerr.
3. SABnzbd-Mount auf `${DATA}:/data` (M4).
4. `.gitignore` neu: `.env`, `.env.runtime`, `backups/`, `recyclarr/cache/`.
5. Netzwerk `arr_net` bleibt extern (wie Ist); Bootstrap legt es an.

### Zugriffsweg

- **Tailscale** (host-net) mit neuem `tskey-auth-…` — Key kommt **nur** in die Server-`.env`, nie ins Repo. Kein Reverse Proxy, kein Port-Forwarding (wie bisher geplant). LAN-Zugriff über `192.168.178.5:<port>` bleibt.

## 3. Aufgabenteilung: Compose vs. API-Bootstrap vs. Recyclarr

| Ebene | Zuständig für |
|---|---|
| **docker-compose.yml + .env** | Container, Versionen, Mounts, Netz, Ports, PUID/PGID/TZ, Healthchecks |
| **Bootstrap-Skripte (bash, nummeriert, idempotent)** | Ordner+Rechte, Netzwerk, Start+Warten auf healthy, API-Key-Extraktion, SABnzbd (Server/Ordner/Kategorien), Prowlarr (Indexer+Applications), Radarr/Sonarr (Root Folder, Download Client, Naming, Media Management, Löschen der Remote Path Mappings), Bazarr-/Seerr-Verdrahtung soweit API-fähig |
| **Recyclarr (Container, Config im Repo)** | Quality Profiles + Custom Formats für Radarr **und** Sonarr: TRaSH-basierte **German-DL-4K**-Profile (ersetzt die 5+4 manuellen Custom Formats und „German DL 4k"/Standardprofile). Seerr-Default-Profil wird danach per API auf das neue Profil gesetzt. |
| **Dokumentierte Manuell-Restschritte** | Jellyfin-Ersteinrichtung (Admin-User existiert bereits; bei Bootstrap „from zero": Wizard + User anlegen), Seerr-Login/Jellyfin-Kopplung (OAuth-artiger Flow), Bazarr-Provider-Credentials (opensubtitles-Login), Indexer-/Usenet-Credentials in `.env` eintragen |

**Secret-Fluss:** `bootstrap/01-extract-keys.sh` liest nach dem ersten Start die API-Keys aus den `config.xml` und schreibt sie in `.env.runtime` (Server-only, gitignored). Eingabe-Secrets (Eweka-Zugang, scenenzbs-API-Key, TS-Authkey) stehen in der Server-`.env`; `.env.example` bekommt Platzhalter für alle.

## 4. Ablauf der Umsetzung (Phasen 2–4 im Detail)

| Schritt | Aktion | Rollback | Downtime |
|---|---|---|---|
| S0 | **Backup**: `backups/appdata-YYYYMMDD-HHMM.tar.gz` von `/mnt/user/appdata/{radarr,sonarr,prowlarr,sabnzbd,bazarr,jellyfin,seerr,homepage,tailscale}` (Container kurz gestoppt für konsistente DBs) + Kopie der Server-`.env`. Restore-Weg wird im Backup-Ordner als README abgelegt: Stack stoppen → tar entpacken → alten Compose-Stand auschecken → `up -d`. | — (nur lesen/sichern) | ~5 min |
| S1 | Neues Compose + `.env` + `.gitignore` ins Repo; neuen TS-Authkey in Server-`.env`; `git pull` auf Server (+ `safe.directory`-Fix) | `git checkout` alter Stand, altes Compose `up -d` | 0 |
| S2 | `bootstrap.sh` Teil 1: Ordner/Rechte (M3), Netz, `docker compose up -d` mit gepinnten Tags, warten auf healthy. Vaultwarden/AdGuard/Threadfin stoppen dabei (Profile). | Backup S0 + alter Compose | ~5–10 min (Neustart aller Container) |
| S3 | API-Bootstrap: Keys extrahieren → SAB (Ordner auf `/data/...`) → Prowlarr (Indexer, Apps) → Radarr/Sonarr (Root, Client, Naming, Mappings entfernen) | Backup S0 | 0 (Dienste laufen) |
| S4 | Recyclarr-Run (Profile/CFs) + Seerr-Default-Profil per API | Backup S0 (Radarr/Sonarr-DB enthält Profile) | 0 |
| S5 | **Idempotenz-Test**: kompletter Re-Run S2–S4 muss fehlerfrei und duplikatfrei durchlaufen | — | 0 |
| S6 | Healthcheck-Report: Container up, APIs erreichbar, Prowlarr-Indexer-Test, Radarr/Sonarr-Client-Test, **Hardlink-Test mit Testdatei** (wird danach wieder gelöscht) | — | 0 |
| S7 | Doku (README-Umbau: Bootstrap in einem Befehl, Update, Restore) + Backup-Skript für appdata + Unraid-User-Script-Hinweis; saubere kleine Commits | `git revert` | 0 |

**Geschätzte Gesamt-Downtime: unter 15 Minuten**, davon der Großteil geplanter Container-Neustart in S2. Da die Mediathek leer ist und keine Downloads laufen, ist das Verlustrisiko minimal; Worst Case ist Restore aus S0-Backup (~10 min).

## 5. Risiken

| Risiko | Einschätzung / Gegenmaßnahme |
|---|---|
| Recyclarr überschreibt bestehende Profile anders als erwartet | Gewollt (Entscheidung: ersetzen). Alte Profile stecken im S0-Backup. Seerr-Requests laufen erst nach S4-Umstellung des Default-Profils wieder aufs richtige Profil. |
| SAB-Pfadumstellung während laufender Downloads | Keine Downloads vorhanden (Queue leer, Ordner leer) → risikolos. Skript prüft trotzdem Queue vor Umstellung. |
| Gepinnte Tags weichen vom laufenden Digest ab (z. B. `:latest` inzwischen neuer) | Pin auf laufende Version per Digest-Abgleich vor S1; kein ungeplantes Upgrade beim Neuaufbau. |
| Tailscale-Key funktioniert nicht | Sofort sichtbar in S2 (Healthcheck); Fallback: interaktives Login via `docker logs tailscale`. LAN-Zugriff ist nie betroffen. |
| Jellyfin/Seerr „from zero" nicht voll automatisierbar | Bewusst als dokumentierte Manuell-Restschritte ausgewiesen (kein stiller Ausfall). Bestehende Jellyfin/Seerr-appdata bleibt erhalten, d. h. real fällt aktuell kein Manuell-Schritt an. |

## 6. Deliverables (Repo nach Phase 2/3)

```
docker-compose.yml          gepinnte Tags, Healthchecks, Profile
.env.example                alle Variablen inkl. neuer Platzhalter (EWEKA_*, SCENENZBS_APIKEY, …)
.gitignore                  .env, .env.runtime, backups/, recyclarr/cache/
bootstrap.sh                Orchestrator: ruft bootstrap/0*-*.sh in Reihenfolge, wartet auf Health
bootstrap/01-extract-keys.sh
bootstrap/02-sabnzbd.sh
bootstrap/03-prowlarr.sh
bootstrap/04-radarr.sh
bootstrap/05-sonarr.sh
bootstrap/06-recyclarr.sh   (docker run --rm recyclarr/recyclarr, config: recyclarr/recyclarr.yml)
bootstrap/07-bazarr.sh
bootstrap/08-seerr.sh
recyclarr/recyclarr.yml     German-DL-4K-Profile für Radarr + Sonarr (TRaSH)
scripts/backup-appdata.sh   Stop → tar → Start, mit Zeitstempel; Unraid-User-Script-tauglich
scripts/healthcheck.sh      Phase-4-Report
INVENTORY.md, PLAN.md       (dieses Dokument)
```

---

**⛔ STOP — warte auf deine Freigabe.** Bei OK starte ich mit S0 (Backup) und Phase 2. Änderungen am Server passieren erst danach.
