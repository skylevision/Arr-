# Rolle
Du bist mein DevOps-Engineer für einen self-hosted Medien-Stack auf Unraid.
Ich arbeite von meinem PC aus, du hast SSH-Zugriff auf den Unraid-Server.
Das Repo (github.com/skylevision/Arr-) ist lokal geklont.

# Ziel
Der komplette Arr-Stack soll deklarativ, idempotent und
"one-command bootstrap"-fähig werden. Nach dem Bootstrap darf KEIN
manueller Klick in einer Web-UI mehr nötig sein: Indexer, Quality
Profiles, Custom Formats, Root Folder, Download-Client-Verknüpfung und
Naming Schemes werden per API bzw. Config-as-Code gesetzt.

# Ausgangslage
Der Stack läuft teilweise (gewachsen, teils manuell konfiguriert).
Er soll sauber neu aufgesetzt werden, bestehende Daten (Medien,
Historie, Datenbanken) sollen nach Möglichkeit erhalten bleiben.
Komponenten: SABnzbd, Prowlarr, Radarr, Sonarr, Bazarr, Jellyfin,
Seerr, Vaultwarden, Tailscale.

# Harte Regeln
1. NIEMALS raten. Wenn eine Information fehlt (Pfade, Ports, PUID/PGID,
   Share-Namen, Indexer-Credentials, Domain, Reverse Proxy), fragst du
   mich. Lieber eine Frage zu viel als eine falsche Annahme.
2. Keine Secrets ins Repo. Alles über .env, dazu eine .env.example mit
   Platzhaltern. .gitignore prüfen und ergänzen.
3. Idempotenz: Jedes Skript muss mehrfach laufen können, ohne Schaden
   und ohne Duplikate anzulegen.
4. Bevor du irgendetwas veränderst: Backup von /mnt/user/appdata der
   betroffenen Container, mit Zeitstempel und dokumentiertem
   Restore-Weg.
5. API-Endpunkte und Schemata nicht aus dem Gedächtnis erfinden.
   Verifiziere gegen die tatsächlich laufende Instanz
   (z. B. /api/v3/system/status) oder die offizielle Doku.
6. Destruktive Aktionen (docker rm, Löschen von appdata, Umbenennen von
   Shares) nur nach expliziter Freigabe von mir.

# Phase 0: Inventar (nur lesen, nichts ändern)
- Per SSH: laufende Container, Images, Tags, Ports, Volume-Mappings,
  Netzwerke, PUID/PGID/UMASK, Restart-Policies.
- Unraid-Shares, Cache- vs. Array-Pfade, aktuelle Ordnerstruktur der
  Medien und Downloads.
- Prüfe, ob Hardlinks und atomic moves überhaupt möglich sind
  (also ob Downloads und Medien im selben Dateisystem und unter einem
  gemeinsamen Mount liegen).
- Bestehende App-Konfiguration auslesen: API-Keys aus config.xml,
  konfigurierte Indexer, Root Folder, Download Clients, Quality
  Profiles, Custom Formats.
- Ergebnis: INVENTORY.md mit Ist-Zustand und einer expliziten Liste
  aller Probleme und offenen Fragen an mich.

# Phase 1: Plan (Freigabe abwarten)
Schreibe PLAN.md mit:
- Ziel-Ordnerstruktur (ein gemeinsamer /data-Mount für hardlink-fähiges
  Setup, TRaSH-Guides-Layout), inkl. Migrationsschritten von der
  Ist-Struktur.
- Ziel-Architektur: docker-compose, Netzwerke, Abhängigkeiten,
  Healthchecks, Zugriffsweg (Tailscale, Reverse Proxy).
- Was per Compose gelöst wird, was per API-Bootstrap, was per Recyclarr.
- Risiken, Rollback pro Schritt, geschätzte Downtime.
Stoppe hier und warte auf mein OK. Nichts vorher ausführen.

# Phase 2: Deployment als Code
- docker-compose.yml (versioniert, kein "latest" ohne Not, feste Tags),
  .env, .env.example.
- Bootstrap-Skript (bash oder python), das idempotent:
  Ordnerstruktur mit korrekten Rechten anlegt, Netzwerke erstellt,
  Container startet und auf Health/Ready wartet, bevor der nächste
  Schritt kommt.

# Phase 3: Konfiguration per API
- API-Keys nach dem ersten Start automatisch aus den config.xml
  extrahieren und in .env schreiben.
- SABnzbd: Kategorien, Ordner, Verbindung.
- Prowlarr als Single Source of Truth für Indexer, per "Applications"
  automatisch an Sonarr/Radarr syncen.
- Sonarr/Radarr: Root Folder, Download Client (SABnzbd), Naming
  Schemes, Media Management.
- Quality Profiles und Custom Formats über Recyclarr (TRaSH Guides),
  Konfig im Repo versioniert.
- Bazarr, Jellyfin und Seerr anbinden, soweit per API möglich. Was
  nicht automatisierbar ist, kommt als expliziter Manuell-Restschritt
  in die Doku, nicht stillschweigend unter den Tisch.
- Alles in nummerierte, einzeln wiederholbare Skripte aufteilen.

# Phase 4: Verifikation
- Re-Run des kompletten Bootstraps auf dem bestehenden System muss
  ohne Fehler und ohne Duplikate durchlaufen (Idempotenz-Test).
- Healthcheck-Skript: alle Container up, alle APIs erreichbar, Prowlarr
  Indexer-Test grün, Sonarr/Radarr Download-Client-Test grün,
  Hardlink-Test mit einer Testdatei.
- Ausgabe als kurzer Report.

# Phase 5: Doku und Betrieb
- README: Bootstrap in einem Befehl, Update-Prozess, Restore-Prozess.
- Backup-Skript für appdata (Stop, Sichern, Start) plus Hinweis, wie es
  per Unraid User Script geplant wird.
- Alles committen mit sauberen, kleinen Commits.

Starte jetzt mit Phase 0 und stelle mir am Ende deine offenen Fragen.