# Vaultwarden — Self-Hosted Passwort-Manager

Vaultwarden (Bitwarden-kompatibler Passwort-Manager) auf dem Unraid Arr Stack —
öffentlich erreichbar unter **https://vault.mmaeurer.de**, abgesichert über SWAG,
geschlossene Registrierung und fail2ban.

---

## Inhaltsverzeichnis

1. [Was ist Vaultwarden?](#1-was-ist-vaultwarden)
2. [Wie der Zugang aufgebaut ist](#2-wie-der-zugang-aufgebaut-ist)
3. [Admin-Token](#3-admin-token)
4. [Benutzerkonto anlegen](#4-benutzerkonto-anlegen)
5. [Clients einrichten](#5-clients-einrichten)
6. [Wenn du im Ausland bist](#6-wenn-du-im-ausland-bist)
7. [Sicherheit im Überblick](#7-sicherheit-im-überblick)
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
| Image | `vaultwarden/server:1.37.1` (gepinnt) |
| Bitwarden-kompatibel | ✓ alle offiziellen Apps funktionieren |
| Ressourcen | ~50 MB RAM — ideal für Heimserver |
| Lizenz | AGPL-3.0, Open Source |
| Daten | Liegen ausschließlich auf deinem Server |

**Vorteile gegenüber cloud-basierten Lösungen:**
- Alle Passwörter bleiben auf deinem Server — kein Cloud-Anbieter hat Zugriff
- Kostenfrei, auch für Premium-Features (Anhänge, TOTP, Notizen)
- Vollständige Kontrolle über Backup und Zugriff

---

## 2. Wie der Zugang aufgebaut ist

Vaultwarden läuft dauerhaft mit (kein Compose-Profil mehr) und ist von überall
unter **https://vault.mmaeurer.de** erreichbar. Der Weg von außen:

```
Handy/PC  ──HTTPS──►  Fritz!Box:443  ──►  SWAG (nginx)  ──►  vaultwarden:80
   (Internet)                              Zertifikat        nur im proxynet,
                                           *.mmaeurer.de     kein eigener Port
                                                             nach außen
```

Wichtige Eigenschaften dieses Aufbaus:

| Punkt | Umsetzung |
|---|---|
| Zertifikat | Wildcard `*.mmaeurer.de` von Let's Encrypt, das SWAG ohnehin hält — für `vault.` war kein eigener Vorgang nötig |
| Geo-Blocking | **Bewusst aus** (anders als bei `tv.`/`seer.`) — an den Passwortmanager muss man auch aus dem Ausland kommen |
| Admin-Panel | Nur aus dem LAN und dem Tailnet, von außen `403` |
| Registrierung | Zu (`SIGNUPS_ALLOWED=false`); neue Konten nur per Einladung |
| Brute-Force | Ratelimit in Vaultwarden + fail2ban-Jail `vaultwarden` in SWAG |
| Interner Zugriff | AdGuard-Rewrite `vault.mmaeurer.de → 192.168.178.5`, damit das LAN nicht über Hairpin-NAT läuft |

### Warum das trotz offener Erreichbarkeit vertretbar ist

Vaultwarden ist **Zero-Knowledge**: Ver- und Entschlüsselung passieren im
Client, der Server speichert nur einen Blob, den er selbst nicht lesen kann.
Wer den Server erreicht, hat damit noch keine Passwörter — er braucht das
Master-Passwort, das nie übertragen wird. Deshalb ist ein öffentlich
erreichbarer Vaultwarden ein anderes Risiko als ein offener Dateiserver.

---

## 3. Admin-Token

Das Admin-Token steht **nicht in der `.env`**, sondern als Argon2id-Hash in
`${APPDATA}/vaultwarden/admin_token` (chmod 600, nur root). Der Container liest
es über `ADMIN_TOKEN_FILE=/data/admin_token`.

**Warum nicht in die `.env`:** ein Argon2-PHC-String steckt voller `$`.
`bootstrap/lib.sh` liest die `.env` per `source` — dort würde `$argon2id` zu
einem Leerstring und `$$` zur Prozess-ID expandieren. Die eigene Datei umgeht
das Escaping-Problem vollständig.

**Warum ein Hash und kein Klartext-Token:** liegt der Klartext in einer Datei
oder Umgebungsvariable, kann ihn jeder lesen, der `docker inspect` ausführen
darf. Beim Hash steht dort nur die Prüfsumme.

Neu setzen (fragt das Passwort ab, Eingabe bleibt unsichtbar):

```bash
bash scripts/vaultwarden-admin-token.sh
docker compose up -d vaultwarden
```

> Das Vaultwarden-eigene `vaultwarden hash` verlangt ein echtes TTY und bricht
> nicht-interaktiv mit einem Panic ab. Das Skript nutzt deshalb den
> `argon2`-CLI, der denselben PHC-String erzeugt.

### Admin-Panel aufrufen

| Von wo | Adresse |
|---|---|
| Zuhause im LAN | `https://vault.mmaeurer.de/admin` |
| Direkt, ohne DNS | `http://192.168.178.5:8082/admin` (klappt immer) |
| Unterwegs | Erst Tailscale verbinden, dann eine der beiden Adressen |

Von einer fremden Internet-Adresse antwortet nginx mit `403` — das ist Absicht.

---

## 4. Benutzerkonto anlegen

Weil die Registrierung geschlossen ist, wird das Konto **eingeladen**. Eingeladene
dürfen sich trotz `SIGNUPS_ALLOWED=false` registrieren; ein Mailserver ist dafür
nicht nötig (ohne SMTP legt Vaultwarden den Benutzer einfach als „invited" an).

1. Admin-Panel öffnen → Reiter **Users**
2. E-Mail eintragen → **Invite User**
3. Danach `https://vault.mmaeurer.de` aufrufen, dieselbe E-Mail eingeben und die
   Registrierung mit dem **Master-Passwort** abschließen

> **Das Master-Passwort ist nicht zurücksetzbar.** Es gibt keine „Passwort
> vergessen"-Funktion, die den Tresor rettet — ohne das Master-Passwort sind die
> Daten unwiederbringlich verschlüsselt. Lang, einzigartig, und an einem zweiten
> Ort notiert.

Das Admin-Token und das Master-Passwort sind **zwei verschiedene Dinge**: das
Token öffnet die Serververwaltung, das Master-Passwort den Tresor.

---

## 5. Clients einrichten

In **allen** Clients gilt derselbe erste Schritt: **vor** dem Anmelden die
Server-URL umstellen, sonst versucht die App sich bei Bitwarden anzumelden.

**Server-URL:** `https://vault.mmaeurer.de`

### iPhone / iPad

1. App Store → **Bitwarden** installieren
2. App öffnen → oben links auf **Region** / das Zahnrad tippen
3. **Self-hosted** wählen → Server-URL eintragen → **Speichern**
4. Mit E-Mail und Master-Passwort anmelden
5. Danach **Einstellungen → Automatisches Ausfüllen → Passwörter**:
   iOS-Einstellungen → *Allgemein → AutoFill & Passwörter* → **Bitwarden** aktivieren
6. Face ID zum Entsperren: *Einstellungen → Entsperren mit Face ID*

### Android

1. Play Store → **Bitwarden** installieren
2. Vor dem Anmelden auf das **Zahnrad** oben links → **Selbst gehostet**
3. Server-URL eintragen → Speichern → anmelden
4. **Bedienungshilfen/Autofill**: *Einstellungen → Automatisches Ausfüllen →
   Autofill-Dienst* aktivieren (Android fragt beim ersten Login von selbst)
5. Fingerabdruck: *Einstellungen → Entsperren mit Biometrie*

### PC — Browser-Erweiterung (der Alltagsweg)

1. Erweiterung für Chrome/Edge/Firefox aus dem jeweiligen Store installieren
2. **Vor dem Login**: Zahnrad-Symbol → **Selbst gehostete Umgebung** →
   Server-URL eintragen → Speichern
3. Anmelden; danach füllt die Erweiterung Anmeldemasken automatisch aus

### PC — Desktop-App (optional)

Nur nötig, wenn du Passwörter auch außerhalb des Browsers brauchst.
Download von `bitwarden.com/download`, gleiche Prozedur: erst self-hosted
eintragen, dann anmelden.

### Was auf allen Geräten gleich funktioniert

- **Synchronisierung** läuft sofort über den WebSocket-Kanal `/notifications/hub`
  — eine Änderung am PC ist Sekunden später auf dem Handy
- **Offline-Zugriff**: der Tresor liegt verschlüsselt lokal, ohne Internet
  bleiben die Passwörter lesbar (nur Änderungen werden erst später synchronisiert)

---

## 6. Wenn du im Ausland bist

Der Vault ist **weltweit erreichbar** — anders als Jellyfin und Seerr, die nur
DE/AT/EG durchlassen. Im Urlaub brauchst du also weder Tailscale noch eine
Konfigurationsänderung.

Sollte der Zugang doch einmal klemmen, ist Tailscale der Rückweg: verbinden und
`http://192.168.178.5:8082` aufrufen.

---

## 7. Sicherheit im Überblick

| Schicht | Was sie abfängt |
|---|---|
| Master-Passwort (Zero-Knowledge) | Der Server kennt die Passwörter nie im Klartext |
| `SIGNUPS_ALLOWED=false` | Fremde können kein Konto anlegen |
| `/admin` nur LAN + Tailnet | Serververwaltung ist aus dem Internet unsichtbar |
| Vaultwarden-Ratelimit | 10 Loginversuche/60 s, 3 Admin-Versuche/300 s |
| fail2ban `vaultwarden` | 5 Fehlversuche in 10 min → 1 h Sperre der IP |
| `SHOW_PASSWORD_HINT=false` | Die Anmeldemaske verrät keinen Passworthinweis |
| Argon2id-Admin-Token | Kein lesbares Token in Config oder `docker inspect` |
| Let's-Encrypt-Zertifikat | Kein Zertifikatswarnung-Training für dich |

**Dringend empfohlen als nächster Schritt:** 2FA einschalten (Kapitel 9).
Damit reicht selbst ein erratenes Master-Passwort nicht mehr aus.

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
→ Server-URL exakt `https://vault.mmaeurer.de` (ohne Port, ohne Schrägstrich am Ende)?
→ Erreichbarkeit prüfen: `curl -I https://vault.mmaeurer.de`
→ Container-Status: `docker logs vaultwarden`

**Admin-Panel antwortet mit `403`**
→ Kein Fehler, sondern Absicht: `/admin` ist nur aus dem LAN und dem Tailnet offen.
→ Von unterwegs: erst Tailscale verbinden.
→ Aus dem LAN trotzdem `403`? Dann löst der Rechner `vault.mmaeurer.de` auf die
  öffentliche IP auf und läuft über Hairpin-NAT — dabei geht die LAN-Quell-IP
  verloren. Prüfen mit `nslookup vault.mmaeurer.de`; es muss `192.168.178.5`
  kommen (AdGuard-Rewrite). Notfalls direkt `http://192.168.178.5:8082/admin`.

**Admin-Panel nimmt das Token nicht an**
→ Liegt `${APPDATA}/vaultwarden/admin_token` und ist sie nicht leer?
→ Neu setzen: `bash scripts/vaultwarden-admin-token.sh`, dann
  `docker compose up -d vaultwarden`

**„Registration not allowed or user already exists"**
→ Erwartetes Verhalten: die Registrierung ist zu. Konto per Admin-Panel →
  Users → Invite User anlegen, danach klappt die Registrierung für diese Adresse.

**Aus dem Ausland kein Zugriff**
→ Vault hat bewusst kein Geo-Blocking. Falls doch gesperrt: in
  `swag/nginx/proxy-confs/vaultwarden.subdomain.conf` prüfen, ob die
  `$geo_country_allow`-Zeile versehentlich aktiviert wurde.

**IP wurde gesperrt (fail2ban)**
→ Status: `docker exec swag fail2ban-client status vaultwarden`
→ Entsperren: `docker exec swag fail2ban-client set vaultwarden unbanip <IP>`

**Passwörter werden nicht synchronisiert**
→ Im Client Sync manuell anstoßen (↺ oder Einstellungen → Sync Now)
→ WebSocket prüfen: die `/notifications/hub`-Location muss in der proxy-conf stehen

**2FA verloren / kein Zugriff mehr**
→ Recovery-Code verwenden (beim 2FA-Setup heruntergeladen)
→ Als Admin: Admin-Panel → Users → [User] → Deactivate 2FA

## Schnellübersicht — Adressen

| Zweck | Adresse | Von wo |
|---|---|---|
| Tresor (Clients + Web) | `https://vault.mmaeurer.de` | überall, kein Geo-Block |
| Admin-Panel | `https://vault.mmaeurer.de/admin` | nur LAN + Tailnet |
| Direktzugriff ohne DNS | `http://192.168.178.5:8082` | nur LAN + Tailnet |
| Token neu setzen | `bash scripts/vaultwarden-admin-token.sh` | auf dem Server |

---

*Vaultwarden GitHub: [github.com/dani-garcia/vaultwarden](https://github.com/dani-garcia/vaultwarden)*
*Bitwarden Clients: [bitwarden.com/download](https://bitwarden.com/download/)*
