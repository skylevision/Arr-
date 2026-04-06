# Arr Stack — Einrichtung über die Unraid-Benutzeroberfläche

Diese Anleitung zeigt, wie du jeden Container des Arr Stacks einzeln über die
**Unraid Web-Oberfläche** einrichtest — ohne Docker Compose, nur per Klick.

> **Alternative**: Wer die Kommandozeile bevorzugt, kann stattdessen
> `docker compose up -d` aus dem Hauptprojekt verwenden (siehe [README.md](README.md)).

---

## Inhaltsverzeichnis

1. [Vorbereitung](#1-vorbereitung)
2. [Tailscale](#2-tailscale)
3. [SABnzbd](#3-sabnzbd)
4. [Prowlarr](#4-prowlarr)
5. [Radarr](#5-radarr)
6. [Sonarr](#6-sonarr)
7. [Bazarr](#7-bazarr)
8. [Seerr](#8-seerr)
9. [Vaultwarden](#9-vaultwarden)
10. [AdGuard Home](#10-adguard-home)
11. [Jellyfin](#11-jellyfin)
12. [Threadfin (IPTV)](#12-threadfin-iptv)
13. [Homepage](#13-homepage)
14. [Optionale Dienste — Lidarr & Readarr](#14-optionale-dienste--lidarr--readarr)
15. [Reihenfolge der Erstkonfiguration](#15-reihenfolge-der-erstkonfiguration)

---

## 1. Vorbereitung

### 1.1 Verzeichnisse anlegen

Alle Konfigurationsdaten liegen unter `/mnt/user/appdata/`, Medien und Downloads
unter `/mnt/user/data/`. Diese Ordner müssen vor dem ersten Start existieren.

Im Unraid-Terminal (**Tools → Terminal**):

```bash
# Appdata-Verzeichnisse
mkdir -p /mnt/user/appdata/{tailscale,sabnzbd,prowlarr,radarr,sonarr,bazarr,seerr,vaultwarden}
mkdir -p /mnt/user/appdata/{threadfin/conf,threadfin/temp,adguardhome/work,adguardhome/conf}
mkdir -p /mnt/user/appdata/{jellyfin/config,jellyfin/cache,homepage,lidarr,readarr}

# Medien- und Download-Verzeichnisse
mkdir -p /mnt/user/data/media/{movies,tv,music,books}
mkdir -p /mnt/user/data/downloads/usenet/{incomplete,complete}

# Berechtigungen setzen (Unraid-Standard: nobody/users = 99/100)
chown -R 99:100 /mnt/user/appdata /mnt/user/data
```

### 1.2 Docker-Netzwerk anlegen

Alle Container müssen im selben Netzwerk sein, damit sie sich per Name erreichen
können (z. B. `http://radarr:7878`). Einmalig im Terminal:

```bash
docker network create arr_net
```

### 1.3 Container über die Unraid-UI hinzufügen — Grundprinzip

Alle Container werden nach demselben Schema hinzugefügt:

```
Docker-Tab → Add Container
```

Im Formular gibt es folgende Felder — die wichtigsten:

| Feld | Bedeutung |
|---|---|
| **Name** | Container-Name (frei wählbar, hier immer Kleinbuchstaben) |
| **Repository** | Docker-Image (z. B. `lscr.io/linuxserver/radarr:latest`) |
| **Network Type** | `arr_net` für alle (außer Tailscale: `host`) |
| **Port Mappings** | Hostport : Containerport |
| **Path Mappings** | Hostpfad : Containerpfad |
| **Variables** | Umgebungsvariablen (PUID, PGID, TZ etc.) |

Klicke auf **„+ Add another Path"**, **„+ Add another Port"** bzw.
**„+ Add another Variable"** um mehrere Einträge anzulegen.

Am Ende: **Apply** → Container startet.

---

## 2. Tailscale

> Stellt die sichere VPN-Verbindung von überall her. Startet zuerst.

| Feld | Wert |
|---|---|
| **Name** | `tailscale` |
| **Repository** | `tailscale/tailscale:latest` |
| **Network Type** | `host` ← wichtig, nicht ändern |

**Extra Parameters** (Feld ganz unten im „Advanced View"):
```
--cap-add=NET_ADMIN --cap-add=NET_RAW --device=/dev/net/tun
```

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/tailscale` | `/var/lib/tailscale` | Read/Write |

**Variables:**

| Name | Wert |
|---|---|
| `TS_AUTHKEY` | *(deinen Pre-Auth-Key von login.tailscale.com/admin/settings/keys)* |
| `TS_STATE_DIR` | `/var/lib/tailscale` |
| `TS_USERSPACE` | `false` |
| `TS_HOSTNAME` | `arr-stack` *(oder eigener Name)* |

**Apply** → Nach dem Start:
```bash
docker logs tailscale
# → URL kopieren und im Browser öffnen, wenn kein TS_AUTHKEY gesetzt
```

---

## 3. SABnzbd

> Usenet-Downloader. Lädt NZB-Dateien herunter.

| Feld | Wert |
|---|---|
| **Name** | `sabnzbd` |
| **Repository** | `lscr.io/linuxserver/sabnzbd:latest` |
| **Network Type** | `arr_net` |

**Ports:**

| Host-Port | Container-Port | Protokoll |
|---|---|---|
| `8090` | `8080` | TCP |

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/sabnzbd` | `/config` | Read/Write |
| `/mnt/user/data/downloads/usenet` | `/downloads/usenet` | Read/Write |

**Variables:**

| Name | Wert |
|---|---|
| `PUID` | `99` |
| `PGID` | `100` |
| `TZ` | `Europe/Berlin` |

**Apply** → Erreichbar unter `http://<ip>:8090`

---

## 4. Prowlarr

> Indexer-Manager. Verwaltet Usenet-Indexer und synchronisiert sie mit Radarr/Sonarr.

| Feld | Wert |
|---|---|
| **Name** | `prowlarr` |
| **Repository** | `lscr.io/linuxserver/prowlarr:latest` |
| **Network Type** | `arr_net` |

**Ports:**

| Host-Port | Container-Port | Protokoll |
|---|---|---|
| `9696` | `9696` | TCP |

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/prowlarr` | `/config` | Read/Write |

**Variables:**

| Name | Wert |
|---|---|
| `PUID` | `99` |
| `PGID` | `100` |
| `TZ` | `Europe/Berlin` |

**Apply** → Erreichbar unter `http://<ip>:9696`

---

## 5. Radarr

> Filmverwaltung. Sucht, lädt und organisiert Filme automatisch.

| Feld | Wert |
|---|---|
| **Name** | `radarr` |
| **Repository** | `lscr.io/linuxserver/radarr:latest` |
| **Network Type** | `arr_net` |

**Ports:**

| Host-Port | Container-Port | Protokoll |
|---|---|---|
| `7878` | `7878` | TCP |

**Paths:**

> ⚠️ Der `/data`-Mount muss identisch mit SABnzbd und Sonarr sein — nur so funktionieren Hardlinks!

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/radarr` | `/config` | Read/Write |
| `/mnt/user/data` | `/data` | Read/Write |

**Variables:**

| Name | Wert |
|---|---|
| `PUID` | `99` |
| `PGID` | `100` |
| `TZ` | `Europe/Berlin` |

**Apply** → Erreichbar unter `http://<ip>:7878`

---

## 6. Sonarr

> Serienmanagement. Sucht, lädt und organisiert TV-Serien automatisch.

| Feld | Wert |
|---|---|
| **Name** | `sonarr` |
| **Repository** | `lscr.io/linuxserver/sonarr:latest` |
| **Network Type** | `arr_net` |

**Ports:**

| Host-Port | Container-Port | Protokoll |
|---|---|---|
| `8989` | `8989` | TCP |

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/sonarr` | `/config` | Read/Write |
| `/mnt/user/data` | `/data` | Read/Write |

**Variables:**

| Name | Wert |
|---|---|
| `PUID` | `99` |
| `PGID` | `100` |
| `TZ` | `Europe/Berlin` |

**Apply** → Erreichbar unter `http://<ip>:8989`

---

## 7. Bazarr

> Untertitel-Verwaltung. Sucht und lädt automatisch Untertitel für Radarr/Sonarr.

| Feld | Wert |
|---|---|
| **Name** | `bazarr` |
| **Repository** | `lscr.io/linuxserver/bazarr:latest` |
| **Network Type** | `arr_net` |

**Ports:**

| Host-Port | Container-Port | Protokoll |
|---|---|---|
| `6767` | `6767` | TCP |

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/bazarr` | `/config` | Read/Write |
| `/mnt/user/data/media` | `/data/media` | Read/Write |

**Variables:**

| Name | Wert |
|---|---|
| `PUID` | `99` |
| `PGID` | `100` |
| `TZ` | `Europe/Berlin` |

**Apply** → Erreichbar unter `http://<ip>:6767`

---

## 8. Seerr

> Medien-Anfrage-Portal. Freunde können hierüber Filme und Serien wünschen.

| Feld | Wert |
|---|---|
| **Name** | `seerr` |
| **Repository** | `fallenbagel/jellyseerr:latest` |
| **Network Type** | `arr_net` |

**Ports:**

| Host-Port | Container-Port | Protokoll |
|---|---|---|
| `5055` | `5055` | TCP |

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/seerr` | `/app/config` | Read/Write |

**Variables:**

| Name | Wert |
|---|---|
| `TZ` | `Europe/Berlin` |

> ⚠️ Kein `PUID`/`PGID` — Seerr läuft unter dem internen `node`-User.

**Apply** → Erreichbar unter `http://<ip>:5055`

---

## 9. Vaultwarden

> Selbst-gehosteter Passwort-Manager (Bitwarden-kompatibel).

| Feld | Wert |
|---|---|
| **Name** | `vaultwarden` |
| **Repository** | `vaultwarden/server:latest` |
| **Network Type** | `arr_net` |

**Ports:**

| Host-Port | Container-Port | Protokoll |
|---|---|---|
| `8082` | `80` | TCP |

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/vaultwarden` | `/data` | Read/Write |

**Variables:**

| Name | Wert |
|---|---|
| `TZ` | `Europe/Berlin` |
| `WEBSOCKET_ENABLED` | `true` |
| `SIGNUPS_ALLOWED` | `true` *(nach Setup auf `false` setzen!)* |
| `ADMIN_TOKEN` | *(generieren: `openssl rand -base64 48`)* |
| `DOMAIN` | *(leer lassen — oder spätere Domain eintragen)* |
| `LOG_LEVEL` | `warn` |

**Apply** → Erreichbar unter `http://<ip>:8082`

> Admin-Panel: `http://<ip>:8082/admin`
> Vollständige Anleitung: [VAULTWARDEN_SETUP.md](VAULTWARDEN_SETUP.md)

---

## 10. AdGuard Home

> Netzwerkweiter DNS-Werbeblocker. Filtert Werbung für alle Geräte im Heimnetz.

| Feld | Wert |
|---|---|
| **Name** | `adguardhome` |
| **Repository** | `adguard/adguardhome:latest` |
| **Network Type** | `arr_net` |

**Extra Parameters:**
```
--cap-add=NET_ADMIN
```

**Ports:**

| Host-Port | Container-Port | Protokoll | Hinweis |
|---|---|---|---|
| `192.168.1.100:53` | `53` | TCP | IP ersetzen! |
| `192.168.1.100:53` | `53` | UDP | IP ersetzen! |
| `3001` | `3000` | TCP | Einrichtungs-Wizard (einmalig) |
| `8081` | `80` | TCP | Web-UI |

> ⚠️ **Port 53**: Die Host-IP `192.168.1.100` muss durch deine tatsächliche
> Unraid-IP ersetzt werden. Ohne IP-Bindung kollidiert Port 53 mit Unroids eigenem Resolver.
> Im Unraid-Port-Feld: `192.168.1.100:53` als Host-Port eintragen.

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/adguardhome/work` | `/opt/adguardhome/work` | Read/Write |
| `/mnt/user/appdata/adguardhome/conf` | `/opt/adguardhome/conf` | Read/Write |

**Variables:** *(keine erforderlich)*

**Apply** → Einrichtungs-Wizard öffnen: `http://<ip>:3001`
Nach dem Setup: Web-UI unter `http://<ip>:8081`

---

## 11. Jellyfin

> Media-Server. Filme und Serien streamen auf allen Geräten.

| Feld | Wert |
|---|---|
| **Name** | `jellyfin` |
| **Repository** | `jellyfin/jellyfin:latest` |
| **Network Type** | `arr_net` |

**Extra Parameters:**
```
--user=99:100
```

**Ports:**

| Host-Port | Container-Port | Protokoll | Hinweis |
|---|---|---|---|
| `8096` | `8096` | TCP | Web-UI / API |
| `8920` | `8920` | TCP | HTTPS (optional) |
| `7359` | `7359` | UDP | Auto-Discovery *(weglassen — oft Konflikt mit Unraid)* |
| `1900` | `1900` | UDP | DLNA *(weglassen — oft Konflikt mit Unraid)* |

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/jellyfin/config` | `/config` | Read/Write |
| `/mnt/user/appdata/jellyfin/cache` | `/cache` | Read/Write |
| `/mnt/user/data/media` | `/data/media` | Read Only |

**Variables:**

| Name | Wert |
|---|---|
| `TZ` | `Europe/Berlin` |
| `JELLYFIN_PublishedServerUrl` | `http://192.168.1.100:8096` *(eigene IP)* |

**Hardware-Transcoding (optional):**

Für Intel QuickSync / VAAPI im Feld **„Devices"** eintragen:
```
/dev/dri:/dev/dri
```

**Apply** → Erreichbar unter `http://<ip>:8096`

> Bibliotheken anlegen: `/data/media/movies` für Filme, `/data/media/tv` für Serien.

---

## 12. Threadfin (IPTV)

> IPTV-Proxy. Deutsches Live-TV in Jellyfin integrieren (ARD, ZDF, Sport1 …).

| Feld | Wert |
|---|---|
| **Name** | `threadfin` |
| **Repository** | `fyb3roptik/threadfin:latest` |
| **Network Type** | `arr_net` |

**Ports:**

| Host-Port | Container-Port | Protokoll |
|---|---|---|
| `34400` | `34400` | TCP |

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/threadfin/conf` | `/home/threadfin/conf` | Read/Write |
| `/mnt/user/appdata/threadfin/temp` | `/tmp/threadfin` | Read/Write |

**Variables:**

| Name | Wert |
|---|---|
| `PUID` | `99` |
| `PGID` | `100` |
| `TZ` | `Europe/Berlin` |

**Apply** → Erreichbar unter `http://<ip>:34400/web`

> Vollständige Anleitung: [IPTV_SETUP.md](IPTV_SETUP.md)

---

## 13. Homepage

> Einheitliches Dashboard für alle Services mit Live-Status.

| Feld | Wert |
|---|---|
| **Name** | `homepage` |
| **Repository** | `ghcr.io/gethomepage/homepage:latest` |
| **Network Type** | `arr_net` |

**Ports:**

| Host-Port | Container-Port | Protokoll |
|---|---|---|
| `3000` | `3000` | TCP |

**Paths:**

| Host-Pfad | Container-Pfad | Modus |
|---|---|---|
| `/mnt/user/appdata/homepage` | `/app/config` | Read/Write |
| `/var/run/docker.sock` | `/var/run/docker.sock` | Read Only |

**Variables:**

| Name | Wert |
|---|---|
| `PUID` | `99` |
| `PGID` | `100` |
| `TZ` | `Europe/Berlin` |

**Apply** → Erreichbar unter `http://<ip>:3000`

> Konfigurationsdateien liegen in `/mnt/user/appdata/homepage/`.
> Standard-Konfiguration aus dem Compose-Projekt kopieren oder manuell anlegen.

---

## 14. Optionale Dienste — Lidarr & Readarr

### Lidarr (Musik)

| Feld | Wert |
|---|---|
| **Name** | `lidarr` |
| **Repository** | `lscr.io/linuxserver/lidarr:latest` |
| **Network Type** | `arr_net` |

**Port:** `8686:8686`
**Paths:** `/mnt/user/appdata/lidarr:/config`, `/mnt/user/data:/data`
**Variables:** `PUID=99`, `PGID=100`, `TZ=Europe/Berlin`

### Readarr (Bücher / Hörbücher)

| Feld | Wert |
|---|---|
| **Name** | `readarr` |
| **Repository** | `lscr.io/linuxserver/readarr:develop` |
| **Network Type** | `arr_net` |

**Port:** `8787:8787`
**Paths:** `/mnt/user/appdata/readarr:/config`, `/mnt/user/data:/data`
**Variables:** `PUID=99`, `PGID=100`, `TZ=Europe/Berlin`

---

## 15. Reihenfolge der Erstkonfiguration

Nachdem alle Container laufen, müssen sie miteinander verbunden werden.
Genau dieselbe Reihenfolge wie bei der Compose-Installation:

```
① Tailscale authentifizieren (docker logs tailscale → URL öffnen)
② Prowlarr → Indexer hinzufügen
③ Prowlarr → Apps: Radarr + Sonarr verbinden (http://radarr:7878, http://sonarr:8989)
④ Radarr → Download Clients → SABnzbd (Host: sabnzbd, Port: 8080)
⑤ Sonarr → Download Clients → SABnzbd (Host: sabnzbd, Port: 8080)
⑥ Radarr → Root Folder: /data/media/movies
⑦ Sonarr → Root Folder: /data/media/tv
⑧ Bazarr → Radarr verbinden (http://radarr:7878) + Sonarr (http://sonarr:8989)
⑨ Jellyfin → Setup-Wizard → Bibliotheken: /data/media/movies + /data/media/tv
⑩ Seerr → Setup-Wizard → Jellyfin verbinden (http://jellyfin:8096)
         → Radarr (http://radarr:7878) + Sonarr (http://sonarr:8989)
⑪ AdGuard Home → Setup-Wizard (Port 3001) → Router-DNS auf Unraid-IP zeigen
⑫ Threadfin → M3U + EPG hinzufügen → Jellyfin Live TV konfigurieren
⑬ Vaultwarden → Account anlegen → Admin-Panel → Signups deaktivieren
```

> Für die detaillierte Konfiguration jedes Dienstes:
> → Hauptanleitung im [README.md](README.md) unter „First-Time Configuration"

---

## Tipps & Häufige Probleme

**Container sehen sich nicht gegenseitig**
→ Netzwerk aller Container auf `arr_net` prüfen (Docker-Tab → Container → Edit)
→ `arr_net` existiert? `docker network ls | grep arr_net`

**„Permission denied" Fehler in den Logs**
→ Berechtigungen prüfen: `ls -la /mnt/user/appdata/<service>/`
→ Korrigieren: `chown -R 99:100 /mnt/user/appdata/<service>/`

**Container startet nicht nach Unraid-Neustart**
→ Unraid Docker-Tab → Container → rechte Maustaste → Autostart aktivieren

**Container-Updates**
→ Docker-Tab → Container → rechte Maustaste → „Check for Updates"
→ Oder alle auf einmal: Docker-Tab → „Check for Updates" oben

**Compose vs. UI — kann ich beides mischen?**
→ Nein. Entweder alle Container per Compose ODER alle per UI verwalten.
→ Compose-Container erscheinen zwar im Docker-Tab, können dort aber nicht
   sinnvoll bearbeitet werden (Änderungen gehen beim nächsten `compose up` verloren).
