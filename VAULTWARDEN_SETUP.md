# Vaultwarden — Self-Hosted Passwort-Manager

Vollständige Anleitung zur Einrichtung von Vaultwarden (Bitwarden-kompatibler
Passwort-Manager) auf dem Unraid Arr Stack, erreichbar über Tailscale von überall.

---

## Inhaltsverzeichnis

1. [Was ist Vaultwarden?](#1-was-ist-vaultwarden)
2. [Stack starten & erster Aufruf](#2-stack-starten--erster-aufruf)
3. [Admin-Panel einrichten](#3-admin-panel-einrichten)
4. [HTTPS aktivieren (Tailscale Serve)](#4-https-aktivieren-tailscale-serve)
5. [Ersten Benutzer anlegen](#5-ersten-benutzer-anlegen)
6. [Registrierungen sperren](#6-registrierungen-sperren)
7. [Clients installieren](#7-clients-installieren)
8. [Passwörter importieren](#8-passwörter-importieren)
9. [Zwei-Faktor-Authentifizierung (2FA)](#9-zwei-faktor-authentifizierung-2fa)
10. [Geteilte Tresore (Organisationen)](#10-geteilte-tresore-organisationen)
11. [Backup & Wiederherstellung](#11-backup--wiederherstellung)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Was ist Vaultwarden?

**Vaultwarden** ist eine schlanke, inoffizielle Implementierung des Bitwarden-Servers —
vollständig kompatibel mit allen offiziellen Bitwarden-Clients (Browser, Mobil, Desktop).

| Eigenschaft | Details |
|---|---|
| Image | `vaultwarden/server:latest` |
| Bitwarden-kompatibel | ✓ alle offiziellen Apps funktionieren |
| Ressourcen | ~50 MB RAM — ideal für Heimserver |
| Lizenz | AGPL-3.0, Open Source |
| Daten | Liegen ausschließlich auf deinem Server |

**Vorteile gegenüber cloud-basierten Lösungen:**
- Alle Passwörter bleiben auf deinem Server — kein Cloud-Anbieter hat Zugriff
- Kostenfrei, auch für Premium-Features (Anhänge, TOTP, Notizen)
- Vollständige Kontrolle über Backup und Zugriff

---

## 2. Stack starten & erster Aufruf

### Voraussetzung: `.env` konfigurieren

Mindest-Konfiguration in `.env`:

```env
VAULTWARDEN_PORT=8082

# Sicheres Token für Admin-Panel erzeugen:
VW_ADMIN_TOKEN=   # wird im nächsten Schritt gesetzt

VW_SIGNUPS_ALLOWED=true

# URL setzen — wichtig für E-Mail-Links und mobile Apps:
VW_DOMAIN=http://100.x.x.x:8082    # vorerst HTTP, später HTTPS
```

> **Admin-Token erzeugen** (im Unraid-Terminal):
> ```bash
> openssl rand -base64 48
> ```
> Den generierten String als `VW_ADMIN_TOKEN` eintragen.

### Stack starten

```bash
docker compose up -d vaultwarden
```

### Erster Aufruf

Vaultwarden ist erreichbar unter:
```
http://<unraid-ip>:8082
```
oder über Tailscale:
```
http://<tailscale-ip>:8082
```

---

## 3. Admin-Panel einrichten

Das Admin-Panel erlaubt die Verwaltung von Nutzern, Einladungen und Servereinstellungen.

### Aufrufen

```
http://<ip>:8082/admin
```

Mit dem `VW_ADMIN_TOKEN` aus `.env` einloggen.

### Wichtige Einstellungen im Admin-Panel

**General Settings:**
| Einstellung | Empfehlung |
|---|---|
| Domain URL | Deine Vaultwarden-URL (z. B. `https://...ts.net`) |
| Allow new signups | zunächst `true`, nach Setup auf `false` |
| Require email verification | Optional (nur relevant wenn E-Mail-Server konfiguriert) |

**SMTP (optional — für E-Mail-Benachrichtigungen):**
- E-Mail-Einladungen, Passwort-Reset etc. erfordern einen SMTP-Server
- Ohne SMTP: alle Funktionen nutzbar, aber kein E-Mail-Versand
- Für Heimnetz: häufig nicht nötig

---

## 4. HTTPS aktivieren (Tailscale Serve)

> **Warum HTTPS?** Die offiziellen Bitwarden-Apps (iOS, Android) verweigern
> die Verbindung zu reinen HTTP-Endpunkten. HTTPS ist für den mobilen Einsatz Pflicht.

Tailscale kann einen HTTPS-Endpunkt mit gültigem Let's-Encrypt-Zertifikat bereitstellen —
kostenlos, ohne eigene Domain oder Reverse Proxy.

### Tailscale Serve einrichten

Im Unraid-Terminal:
```bash
# Vaultwarden über HTTPS auf Tailscale-Hostname exponieren:
docker exec tailscale tailscale serve https:443 / http://localhost:8082
```

Vaultwarden ist jetzt erreichbar unter:
```
https://arr-stack.<tailnet>.ts.net
```
(Den Hostnamen siehst du in der Tailscale-Admin-Konsole unter Machines.)

### VW_DOMAIN aktualisieren

In `.env` die Domain auf die HTTPS-Adresse setzen:
```env
VW_DOMAIN=https://arr-stack.<tailnet>.ts.net
```

Stack neu starten:
```bash
docker compose up -d vaultwarden
```

### Tailscale Serve dauerhaft aktivieren (nach Reboot)

Damit Tailscale Serve nach einem Neustart des Tailscale-Containers aktiv bleibt,
`TS_SERVE_CONFIG` in `docker-compose.yml` setzen. Erstelle zunächst die Konfigurationsdatei:

```bash
mkdir -p /mnt/user/appdata/tailscale
cat > /mnt/user/appdata/tailscale/serve.json << 'EOF'
{
  "TCP": {
    "443": {
      "HTTPS": true
    }
  },
  "Web": {
    "arr-stack.YOUR-TAILNET.ts.net:443": {
      "Handlers": {
        "/": {
          "Proxy": "http://127.0.0.1:8082"
        }
      }
    }
  }
}
EOF
```

Dann in `docker-compose.yml` unter dem `tailscale`-Service einkommentieren:
```yaml
environment:
  - TS_SERVE_CONFIG=/var/lib/tailscale/serve.json
```

> **Hinweis**: `arr-stack.YOUR-TAILNET.ts.net` durch deinen tatsächlichen Hostnamen ersetzen.
> Den vollständigen Hostnamen zeigt: `docker exec tailscale tailscale status`

---

## 5. Ersten Benutzer anlegen

1. Vaultwarden im Browser öffnen: `https://arr-stack.<tailnet>.ts.net` (oder HTTP-Adresse)
2. **„Create Account"** klicken
3. E-Mail-Adresse, Name und starkes Master-Passwort eingeben
4. **Das Master-Passwort ist nicht wiederherstellbar** — sicher verwahren!

> **Empfehlung**: Das Master-Passwort auf einem Zettel im Safe aufbewahren,
> bis du es auswendig kannst. Vergisst du es, sind alle gespeicherten Passwörter verloren.

---

## 6. Registrierungen sperren

Sobald alle Accounts angelegt sind, Registrierungen deaktivieren:

**Option A — über `.env`:**
```env
VW_SIGNUPS_ALLOWED=false
```
```bash
docker compose up -d vaultwarden
```

**Option B — über Admin-Panel:**
`http://<ip>:8082/admin` → General Settings → Allow new signups → Deaktivieren → Save

Neue Nutzer können nur noch über Einladungen aus dem Admin-Panel hinzugefügt werden.

---

## 7. Clients installieren

Alle offiziellen **Bitwarden-Clients** funktionieren mit Vaultwarden.
Bei der ersten Anmeldung muss die Server-URL auf deine Vaultwarden-Instanz gesetzt werden.

### Server-URL in den Clients einstellen

```
https://arr-stack.<tailnet>.ts.net
```
(oder deine HTTP-Adresse, falls kein HTTPS eingerichtet)

### Verfügbare Clients

| Plattform | App | Installation |
|---|---|---|
| **Browser** | Bitwarden Extension | [Chrome](https://chrome.google.com/webstore/detail/bitwarden/nngceckbapebfimnlniiiahkandclblb) / [Firefox](https://addons.mozilla.org/firefox/addon/bitwarden-password-manager/) / Edge, Brave, Safari |
| **Android** | Bitwarden | [Play Store](https://play.google.com/store/apps/details?id=com.x8bit.bitwarden) |
| **iOS / iPadOS** | Bitwarden | [App Store](https://apps.apple.com/app/bitwarden-password-manager/id1137397744) |
| **Windows** | Bitwarden Desktop | [bitwarden.com/download](https://bitwarden.com/download/) |
| **macOS** | Bitwarden Desktop | App Store oder bitwarden.com/download |
| **Linux** | Bitwarden Desktop | Snap / AppImage / .deb auf bitwarden.com/download |

### Einrichtung Browser-Extension (Beispiel Chrome)

```
① Bitwarden Extension installieren
② Extension öffnen → Einstellungen (⚙️) → Server-URL
③ Self-hosted: https://arr-stack.<tailnet>.ts.net  eingeben → Speichern
④ Mit E-Mail und Master-Passwort anmelden
⑤ Fertig — Passwörter werden synchronisiert
```

### Einrichtung Mobile App (Android/iOS)

```
① Bitwarden installieren
② App öffnen → „Self-hosted" antippen
③ Server-URL eingeben → Speichern
④ E-Mail + Master-Passwort eingeben → Anmelden
⑤ Biometrie (Fingerabdruck/Face ID) einrichten für schnellen Zugriff
```

> **Wichtig**: Tailscale muss auf dem Smartphone aktiv sein, damit die App
> die Vaultwarden-Instanz erreichen kann.

---

## 8. Passwörter importieren

Vaultwarden unterstützt den Import aus den meisten gängigen Passwort-Managern.

### Import im Web-Vault

```
https://arr-stack.<tailnet>.ts.net
→ Tools → Import Data
→ Format auswählen → Datei hochladen → Import
```

### Unterstützte Formate (Auswahl)

| Quelle | Format |
|---|---|
| **1Password** | 1PIF oder CSV |
| **LastPass** | CSV |
| **KeePass / KeePassXC** | KeePass XML |
| **Dashlane** | CSV oder JSON |
| **Chrome / Edge / Firefox** | CSV |
| **Bitwarden** | JSON (für Migration zwischen Instanzen) |

### Export aus Chrome/Edge

```
chrome://password-manager/passwords → Einstellungen → Passwörter exportieren → CSV
```

### Export aus Firefox

```
about:logins → ⋮ → Passwörter exportieren → CSV
```

---

## 9. Zwei-Faktor-Authentifizierung (2FA)

2FA schützt den Vault zusätzlich — selbst wenn das Master-Passwort kompromittiert wird.

### TOTP (Authenticator App) einrichten

Im Web-Vault:
```
Account → Security → Two-step Login → Authenticator App → Manage
```

1. QR-Code mit einer Authenticator-App scannen:
   - **Aegis** (Android, Open Source, empfohlen)
   - **Raivo** (iOS)
   - **Bitwarden Authenticator** (iOS/Android)
   - Google Authenticator, Authy
2. 6-stelligen Code eingeben → bestätigen
3. **Recovery-Codes** herunterladen und sicher aufbewahren!

> **Tipp**: Den Recovery-Code ausdrucken und getrennt vom Master-Passwort aufbewahren.
> Ohne Recovery-Code und ohne Zugriff auf die 2FA-App ist der Account gesperrt.

### E-Mail-2FA (ohne SMTP nicht möglich)

Nur relevant wenn ein SMTP-Server konfiguriert ist — dann als Fallback nutzbar.

### 2FA als Admin für alle erzwingen

Admin-Panel → `http://<ip>:8082/admin` → General Settings →
**Require 2FA** → aktivieren (empfohlen für Familieninstanzen)

---

## 10. Geteilte Tresore (Organisationen)

Mit Organisationen können Passwörter mit Familie oder Mitbewohnern geteilt werden —
jeder Nutzer hat einen eigenen privaten Vault und Zugriff auf gemeinsame Einträge.

### Organisation erstellen

Im Web-Vault:
```
Organizations → New Organization → Name vergeben (z. B. „Familie")
```

### Mitglieder einladen

```
Organizations → [Name] → Members → Invite Member
→ E-Mail-Adresse eingeben
```

> Ohne SMTP: Einladungen können auch direkt per Admin-Panel erstellt werden:
> `http://<ip>:8082/admin` → Users → Invite User

### Passwörter teilen

```
Vault → Eintrag auswählen → Share → Organisation auswählen → Collection wählen
```

### Collections (Sammlungen)

Innerhalb einer Organisation lassen sich Passwörter in **Collections** organisieren:
- z. B. „Streaming", „Banking", „WLAN", „Smart Home"
- Jede Collection kann unterschiedlichen Mitgliedern zugewiesen werden

---

## 11. Backup & Wiederherstellung

### Was gesichert werden muss

Alle Vaultwarden-Daten liegen in:
```
/mnt/user/appdata/vaultwarden/
├── db.sqlite3        ← Hauptdatenbank (alle Passwörter, verschlüsselt)
├── db.sqlite3-shm
├── db.sqlite3-wal
├── attachments/      ← Dateianhänge
├── sends/            ← Bitwarden Send (temporäre Freigaben)
└── config.json       ← Serverkonfiguration
```

### Automatisches Backup mit CA Backup Plugin

Das **CA Backup / Restore Appdata** Plugin (empfohlen für Unraid) sichert
automatisch das gesamte `appdata`-Verzeichnis inkl. Vaultwarden.

### Manuelles Backup

```bash
# Container kurz stoppen für konsistentes Backup:
docker stop vaultwarden

# Backup erstellen:
cp -r /mnt/user/appdata/vaultwarden /mnt/user/backups/vaultwarden-$(date +%Y%m%d)

# Container wieder starten:
docker start vaultwarden
```

### SQLite-Backup (ohne Container-Stop)

```bash
sqlite3 /mnt/user/appdata/vaultwarden/db.sqlite3 \
  ".backup '/mnt/user/backups/vaultwarden-$(date +%Y%m%d).sqlite3'"
```

SQLite unterstützt Online-Backups — kein Container-Stop nötig.

### Wiederherstellung

```bash
docker stop vaultwarden
cp -r /mnt/user/backups/vaultwarden-20240101 /mnt/user/appdata/vaultwarden
docker start vaultwarden
```

> **Kritisch**: Vaultwarden-Backup **getrennt** vom Server aufbewahren
> (externe HDD, Cloud, zweiter Standort). Geht der Server verloren, gehen
> sonst auch alle Passwörter verloren.

---

## 12. Troubleshooting

**„Cannot connect to server" in der App**
→ Ist Tailscale auf dem Gerät verbunden?
→ Ist die Server-URL korrekt gesetzt (inkl. Port bei HTTP)?
→ Container-Status prüfen: `docker logs vaultwarden`

**Mobile App akzeptiert keine HTTP-URL**
→ HTTPS über Tailscale Serve einrichten (→ [Abschnitt 4](#4-https-aktivieren-tailscale-serve))
→ HTTP funktioniert nur in der Browser-Extension und im Web-Vault zuverlässig

**Admin-Panel nicht erreichbar**
→ Ist `VW_ADMIN_TOKEN` in `.env` gesetzt?
→ Nach `.env`-Änderung: `docker compose up -d vaultwarden`

**„Registration not allowed"**
→ `VW_SIGNUPS_ALLOWED=true` in `.env` setzen und Container neu starten
→ Oder: Admin-Panel → Users → Invite User (funktioniert auch bei deaktivierten Signups)

**Passwörter werden nicht synchronisiert**
→ Im Client: Sync manuell anstoßen (Symbol ↺ oder Einstellungen → Sync Now)
→ Verbindung zum Server prüfen

**2FA verloren / kein Zugriff mehr**
→ Recovery-Code verwenden (beim 2FA-Setup heruntergeladen)
→ Als Admin: `http://<ip>:8082/admin` → Users → [User] → Deactivate 2FA

---

## Schnellübersicht — Adressen

| Dienst | URL |
|---|---|
| Web-Vault | `https://arr-stack.<tailnet>.ts.net` |
| Admin-Panel | `https://arr-stack.<tailnet>.ts.net/admin` |
| HTTP (lokal) | `http://192.168.1.100:8082` |

---

*Vaultwarden GitHub: [github.com/dani-garcia/vaultwarden](https://github.com/dani-garcia/vaultwarden)*
*Bitwarden Clients: [bitwarden.com/download](https://bitwarden.com/download/)*
