# Unraid Server Setup — Schritt-für-Schritt

Vollständige Anleitung vom leeren Server bis zum laufenden Arr Stack.

---

## Inhaltsverzeichnis

1. [Hardware-Voraussetzungen](#1-hardware-voraussetzungen)
2. [BIOS konfigurieren](#2-bios-konfigurieren)
3. [Unraid USB-Stick erstellen & booten](#3-unraid-usb-stick-erstellen--booten)
4. [Erster Start & Grundkonfiguration](#4-erster-start--grundkonfiguration)
5. [Netzwerk — 2×2.5G Bonding](#5-netzwerk--225g-bonding)
6. [Speicher-Setup: HDDs + NVMe](#6-speicher-setup-hdds--nvme)
7. [Shares konfigurieren](#7-shares-konfigurieren)
8. [Plugins installieren](#8-plugins-installieren)
9. [Docker vorbereiten](#9-docker-vorbereiten)
10. [Arr Stack deployen](#10-arr-stack-deployen)

---

## 1. Hardware-Voraussetzungen

### Empfohlene Mindestanforderungen

| Komponente | Empfehlung |
|---|---|
| CPU | x86-64, min. 4 Kerne (Intel 8th Gen+ / Ryzen für QuickSync/AMF) |
| RAM | 16 GB (32 GB empfohlen, ECC optional) |
| USB-Stick | 2–32 GB, USB 2.0/3.0 — **ausschließlich** für Unraid OS |
| Parity-HDD | Größte HDD im System (≥ alle Datenlaufwerke) |
| Daten-HDDs | Beliebig viele, unterschiedliche Größen OK |
| NVMe SSD | Min. 250 GB für Cache/Appdata (z. B. Samsung 980, WD SN770) |
| Netzwerk | 2× 2.5GbE NIC (onboard oder PCIe, z. B. Intel I225-V) |

> **USB-Stick-Tipp**: Einen qualitativ hochwertigen Stick verwenden (SanDisk Ultra, Kingston).
> Billige Sticks fallen häufig aus. Ein zweiter Stick als Backup ist empfehlenswert.

---

## 2. BIOS konfigurieren

Vor dem ersten Boot folgende Einstellungen im BIOS/UEFI vornehmen:

### Zwingend erforderlich

| Einstellung | Wert | Ort (typisch) |
|---|---|---|
| **Secure Boot** | Disabled | Boot → Secure Boot |
| **Boot-Reihenfolge** | USB-Stick an erster Stelle | Boot → Boot Priority |
| **SATA Mode** | AHCI | Advanced → Storage |
| **Above 4G Decoding** | Enabled | Advanced → PCI Subsystem |

### Für Virtualisierung & Hardware-Transcoding (empfohlen)

| Einstellung | Wert | Zweck |
|---|---|---|
| **VT-d / AMD-Vi (IOMMU)** | Enabled | GPU-Passthrough, Docker GPU |
| **VT-x / SVM** | Enabled | VMs |
| **SR-IOV** | Enabled | GPU-Sharing |
| **Intel GVT-g** | Enabled | Intel iGPU-Sharing (nur Intel) |

### Energieverwaltung (NAS-optimiert)

| Einstellung | Wert |
|---|---|
| **EIST / SpeedStep** | Enabled |
| **C-States** | Enabled (bis C6 oder C8) |
| **ErP / S5 Wake** | Nach Bedarf |
| **Wake on LAN (WOL)** | Enabled (für Fernzugriff) |

> **BIOS speichern**: F10 (meistens) → „Save & Exit"

---

## 3. Unraid USB-Stick erstellen & booten

### USB-Stick flashen

1. **Unraid USB Flash Creator** herunterladen:
   - Windows/macOS: [unraid.net/download](https://unraid.net/download)

2. USB-Stick einstecken (mindestens 2 GB, FAT32 formatiert)

3. Flash Creator starten:
   ```
   ① Stick auswählen
   ② "Allow EFI Boot" aktivieren (für moderne Mainboards)
   ③ Neueste Unraid-Version wählen
   ④ "Write" klicken → warten bis fertig
   ```

4. Server neu starten, vom USB booten

### Boot-Menü

Beim Start erscheint das Unraid-Boot-Menü:

```
Unraid OS (Headless)        ← Standard für Server
Unraid OS GUI Mode          ← Mit Desktop, nur bei Monitor am Server
Unraid OS Safe Mode         ← Bei Problemen
Memtest86+                  ← RAM-Test bei neuem Hardware
```

→ **„Unraid OS (Headless)"** wählen und Enter drücken.

---

## 4. Erster Start & Grundkonfiguration

### Webinterface aufrufen

Nach dem Boot im Browser öffnen:
```
http://tower          ← Standard-Hostname
http://tower.local    ← mDNS (macOS/Linux)
http://<IP-Adresse>   ← z. B. http://192.168.1.100
```

> IP-Adresse am Router (DHCP-Leases) oder direkt am Server (falls Monitor angeschlossen) ablesen.

### Lizenz aktivieren

1. **Main → Registration** → Trial starten oder Lizenzschlüssel eingeben
2. Trial läuft 30 Tage (alle Features verfügbar)
3. Lizenz-Typen:
   - **Starter** — bis 6 Laufwerke
   - **Basic** — bis 12 Laufwerke
   - **Plus** — bis 24 Laufwerke
   - **Pro** — unbegrenzt

### Grundeinstellungen

**Settings → System Settings → Identification:**

| Feld | Empfehlung |
|---|---|
| Server Name | `tower` (oder eigener Name, z. B. `nas`) |
| Description | Optional |
| Time Zone | `Europe/Berlin` |

**Settings → Date and Time:**
- NTP Server: `de.pool.ntp.org` (oder `0.de.pool.ntp.org`)
- Sync jetzt ausführen

**Root-Passwort setzen:**
→ Oben rechts auf den Login-Button → Passwort vergeben

---

## 5. Netzwerk — 2×2.5G Bonding

Zwei 2.5GbE-Interfaces können als **Bond** zusammengeschlossen werden für:
- **Failover** (ein Link stirbt, der andere übernimmt)
- **Aggregation** (beide Links gleichzeitig aktiv, ~5 Gbit/s mit LACP)

### Voraussetzungen prüfen

**Settings → Network Settings** → prüfen ob beide NICs erkannt sind (z. B. `eth0`, `eth1`).

### Szenario A — Managed Switch (LACP 802.3ad) ← empfohlen

Bietet echte Link-Aggregation. Benötigt einen Switch der LACP unterstützt (z. B. TP-Link TL-SG108E, Netgear GS308E, Ubiquiti).

**1. Switch konfigurieren** (am Switch-Webinterface):
- Beide Ports in eine **Trunk/LAG-Gruppe** zusammenfassen
- Modus: **LACP / 802.3ad**

**2. Unraid — Settings → Network Settings:**

```
Network Protocol:      IPv4 only (oder Dual Stack)
Enable Bonding:        Yes

Bond name:             bond0
Bonding Mode:          802.3ad
MII Monitoring:        100ms
LACP Rate:             Fast
Xmit Hash Policy:      layer3+4

Interface 1 (eth0):    ✓ (in Bond aufnehmen)
Interface 2 (eth1):    ✓ (in Bond aufnehmen)

IPv4 Address:          (DHCP oder statisch, s. u.)
```

**Statische IP vergeben (empfohlen):**
```
IPv4 address:     192.168.1.100     ← freie IP im Heimnetz
IPv4 netmask:     255.255.255.0
IPv4 gateway:     192.168.1.1
IPv4 DNS:         1.1.1.1           ← erst mal öffentlicher DNS
                  8.8.8.8           ← Fallback
```

→ **Apply** → Server kurz trennen, wieder verbinden.

> **Hinweis DNS → AdGuard Home**: Sobald der Arr Stack (Kapitel 10) läuft und AdGuard Home
> eingerichtet ist, kannst du die DNS-Einträge hier auf `192.168.1.100` (eigene IP) + `1.1.1.1`
> als Fallback ändern. Jetzt schon `192.168.1.100` einzutragen würde scheitern, da AdGuard
> noch nicht läuft.

### Szenario B — Unmanaged Switch (Active-Backup)

Nur Failover, kein echter Durchsatzzuwachs, aber null Switch-Konfiguration.

```
Bonding Mode:    active-backup
Primary:         eth0
```

Alles andere identisch zu Szenario A.

### Bonding prüfen

Im Unraid-Terminal (Tools → Terminal):
```bash
cat /proc/net/bonding/bond0
```

Erwartete Ausgabe bei 802.3ad:
```
Bonding Mode: IEEE 802.3ad Dynamic link aggregation
...
Slave Interface: eth0
  MII Status: up
  Speed: 2500 Mbps
  ...
Slave Interface: eth1
  MII Status: up
  Speed: 2500 Mbps
```

---

## 6. Speicher-Setup: HDDs + NVMe

### Übersicht

```
┌─────────────────────────────────────────────────────┐
│                   Unraid Array                      │
│                                                     │
│  Parity 1: [größte HDD]   (z. B. 8 TB)             │
│  Disk 1:   [HDD]          (z. B. 4 TB)             │
│  Disk 2:   [HDD]          (z. B. 4 TB)             │
│  Disk 3:   [HDD]          (z. B. 6 TB)             │
│                                                     │
│  Cache Pool: [NVMe SSD]   (z. B. 1 TB)             │
│  → Appdata, Downloads: immer auf NVMe (schnell)     │
│  → Medien: landen erst auf NVMe, Mover schiebt     │
│    sie nachts auf die HDDs                          │
└─────────────────────────────────────────────────────┘
```

### Array aufbauen

**Main → Array Operation (noch gestoppt)**

1. **Parity-Laufwerk zuweisen:**
   - „Parity Device" → Dropdown → größte HDD wählen
   - ⚠️ Diese HDD wird formatiert!

2. **Datenlaufwerke zuweisen:**
   - Disk 1, Disk 2, … → jeweils eine HDD auswählen
   - Größen können variieren

3. **Dateisystem wählen** (für jede Disk):
   - **XFS** ← Standard, empfohlen
   - BTRFS (wenn du Snapshots willst)

4. **Array starten:**
   - „Start" klicken
   - Bei neuem Array: „Format" bestätigen
   - Parity-Sync startet automatisch (Dauer: Stunden je nach Größe — Server läuft normal weiter)

### NVMe Cache Pool einrichten

**Main → Pool Devices**

1. Unter **„Cache"** (oder eigener Pool-Name) → NVMe SSD zuweisen
2. Dateisystem: **BTRFS** (ermöglicht Pool-RAID1 mit 2 SSDs) oder XFS (einzelne SSD)
3. **„Format"** bestätigen

**Mit 2 NVMe SSDs für Redundanz:**
```
Pool Name:     cache
Device 1:      nvme0n1
Device 2:      nvme1n1
RAID Level:    RAID1 (empfohlen — schützt vor SSD-Ausfall)
```

### Array-Status prüfen

**Main** → alle Laufwerke sollten grün (✓) zeigen.

Parity-Sync läuft im Hintergrund — erkennbar am Fortschrittsbalken.
Server ist sofort nutzbar, auch während Sync.

---

## 7. Shares konfigurieren

Shares sind Ordner, die über das Netzwerk (SMB/NFS) und innerhalb von Docker erreichbar sind.

### Share: `appdata` (für Docker-Konfiguration)

**Shares → Add Share:**

| Einstellung | Wert |
|---|---|
| Share Name | `appdata` |
| Minimum Free Space | 20 GB |
| Included disk(s) | leer lassen (alle) |
| Cache | **Only** ← NUR auf Cache/NVMe, nie auf Array |
| Use Cache | **Only** |
| SMB Security | Private (nur root-Zugriff) |

> `appdata` muss schnell sein (Datenbank-Zugriffe etc.) → immer auf NVMe.

### Share: `data` (für Medien & Downloads)

| Einstellung | Wert |
|---|---|
| Share Name | `data` |
| Minimum Free Space | 50 GB |
| Cache | **Yes** ← Downloads landen erst auf NVMe, Mover schiebt sie auf HDD |
| Use Cache | **Yes** |
| SMB Security | Private |

> Mit `Use Cache: Yes` schreibt Unraid Downloads zunächst auf die schnelle NVMe
> und der **Mover** (läuft standardmäßig um 3:40 Uhr) transferiert sie auf die HDDs.

### Share: `media` (optional, wenn Medien direkt auf HDD)

| Einstellung | Wert |
|---|---|
| Share Name | `media` |
| Cache | **No** ← direkt auf Array |

### Mover-Zeitplan anpassen

**Settings → Scheduler → Mover:**
- Schedule: `Daily` at `03:40` (Standard ist gut)
- Oder manuell auslösen: **Main → Move Now**

### SMB-Netzwerkzugriff

**Settings → SMB → Global Share Settings:**

```
SMB Security Mode:   User
Guest Access:        Disabled
Workgroup:           WORKGROUP
NetBIOS Name:        tower (oder eigener Name)
```

User anlegen: **Users → Add User** → Passwort vergeben.

---

## 8. Plugins installieren

### Community Applications (CA) — zwingend erforderlich

1. **Apps → Install Applications (Plugin)**
2. Link: Unraid sucht CA automatisch, oder manuell:
   `https://raw.githubusercontent.com/Squidly271/community.applications/master/plugins/community.applications.plg`
3. Installieren → Neustart

Nach der Installation: **Apps** im Menü erscheint.

### Empfohlene Plugins (alle via Apps → Plugins)

| Plugin | Zweck | Wichtig? |
|---|---|---|
| **Compose Manager** | Docker Compose auf Unraid | ✓ Pflicht für diesen Stack |
| **CA Auto Update Applications** | Hält Docker-Images aktuell | ✓ Empfohlen |
| **Dynamix System Stats** | CPU/RAM/Netz-Monitoring im Dashboard | Empfohlen |
| **Disk Location** | Zeigt welche HDD in welchem Slot steckt | Empfohlen |
| **Unassigned Devices** | USB/externe Laufwerke einbinden | Optional |
| **Fix Common Problems** | Scannt nach häufigen Konfigurationsfehlern | Empfohlen |
| **Nerd Tools** | bash, python, curl etc. im Terminal | Optional |
| **GPU Statistics** | GPU-Auslastung im Dashboard | Optional |

**Compose Manager installieren:**
1. Apps → Suche: `Compose Manager`
2. Installieren
3. Nach Neustart: **Tools → Compose Manager**

---

## 9. Docker vorbereiten

### Docker aktivieren

**Settings → Docker:**

| Einstellung | Wert |
|---|---|
| Enable Docker | **Yes** |
| Docker storage driver | **overlay2** |
| Docker data-root | `/var/lib/docker` |
| Docker image path | `/mnt/user/appdata/docker` (auf NVMe Cache!) |
| Network type | `bridge` |
| Privileged (default) | No |
| Preserve user defined networks | Yes |

→ **Apply** → Docker startet.

### Docker-Netzwerk für den Arr Stack anlegen

Im Terminal (Tools → Terminal):
```bash
docker network create arr_net
```

> Compose erstellt das Netzwerk automatisch beim ersten Start — dieser Schritt ist optional.

### Docker-Verzeichnis auf NVMe sicherstellen

```bash
# Prüfen ob appdata auf Cache liegt:
ls -la /mnt/cache/appdata/
# Sollte existieren (NVMe-Cache)

# Falls nicht: Share-Einstellung prüfen (s. Schritt 7)
```

---

## 10. Arr Stack deployen

### Repository klonen

Im Unraid-Terminal (Tools → Terminal oder SSH):

```bash
cd /mnt/user/
git clone https://github.com/skylevision/arr- arr-stack
cd arr-stack
```

### Konfiguration

```bash
cp .env.example .env
nano .env
```

Mindest-Konfiguration:

```env
# Eigene Werte eintragen:
PUID=99           # Unraid "nobody" UID
PGID=100          # Unraid "users" GID
TZ=Europe/Berlin

APPDATA=/mnt/user/appdata
DATA=/mnt/user/data

UNRAID_IP=192.168.1.100   # Eigene Unraid-IP

TS_HOSTNAME=arr-stack
TS_AUTHKEY=                # Optional: Key von login.tailscale.com/admin/settings/keys
```

> **PUID/PGID auf Unraid:** Der Standard-User `nobody` hat UID=99, GID=100.
> Das ist der korrekte Wert für Unraid-Docker-Container:
> ```bash
> id nobody
> # uid=99(nobody) gid=100(users)
> ```

### Setup-Skript ausführen

```bash
bash setup.sh
```

Das Skript:
- Erstellt alle Verzeichnisse unter `/mnt/user/appdata/` und `/mnt/user/data/`
- Schreibt Standard-Homepage-Konfiguration
- Validiert die `.env`

### Stack starten

```bash
docker compose up -d
```

### Tailscale authentifizieren

```bash
docker logs tailscale
# URL kopieren und im Browser öffnen → mit Tailscale-Account einloggen
```

### Dual Language (Deutsch + Englisch) einrichten

Nach dem ersten Start von Radarr und Sonarr:
→ Siehe **[DUAL_LANGUAGE_SETUP.md](DUAL_LANGUAGE_SETUP.md)** für die vollständige Anleitung
zu Custom Formats, Quality Profiles und Scoring für automatische German-DL-Downloads.

### Dienste aufrufen

| Service | URL (LAN) | URL (Tailscale) |
|---|---|---|
| SABnzbd | `http://192.168.1.100:8090` | `http://100.x.x.x:8090` |
| Prowlarr | `http://192.168.1.100:9696` | `http://100.x.x.x:9696` |
| Radarr | `http://192.168.1.100:7878` | `http://100.x.x.x:7878` |
| Sonarr | `http://192.168.1.100:8989` | `http://100.x.x.x:8989` |
| Bazarr | `http://192.168.1.100:6767` | `http://100.x.x.x:6767` |
| Seerr | `http://192.168.1.100:5055` | `http://100.x.x.x:5055` |
| AdGuard | `http://192.168.1.100:8081` | `http://100.x.x.x:8081` |
| Jellyfin | `http://192.168.1.100:8096` | `http://100.x.x.x:8096` |
| Homepage | `http://192.168.1.100:3000` | `http://100.x.x.x:3000` |

---

## Anhang A: Wichtige Unraid-Konzepte

### Array vs. Cache

```
Array (HDDs):          Langsam, große Kapazität, Parität-geschützt
                       → Langzeitspeicher für Medien

Cache/Pool (NVMe):     Schnell, kleinere Kapazität, optional redundant
                       → Appdata, aktive Downloads, temporäre Daten
```

### Mover

Der Mover ist ein Dienst der Dateien vom Cache auf den Array verschiebt (oder umgekehrt) — je nach Share-Einstellung. Er läuft nachts (konfigurierbar) um die NVMe zu entlasten.

```
Share "data" mit Use Cache: Yes
→ Neue Datei landet auf NVMe (schnell schreiben)
→ Mover läuft um 3:40 Uhr
→ Datei wird auf HDD verschoben
→ NVMe bleibt frei für nächste Downloads
```

### Parität

Die Parity-HDD speichert keine Daten, sondern Paritätsinformationen.
Fällt eine Daten-HDD aus, kann Unraid sie aus Parität + restlichen Disks rekonstruieren.

> **Wichtig**: Nie die Parity-HDD als kleinste HDD wählen — sie muss ≥ jeder Daten-HDD sein.

---

## Anhang B: Nützliche Terminal-Befehle

```bash
# Laufwerkstatus
mdcmd status

# Array-Nutzung
df -h /mnt/user

# NVMe-Temperatur
nvme smart-log /dev/nvme0

# Docker-Logs verfolgen
docker logs -f <container-name>

# Alle Container neustarten
docker compose -f /mnt/user/arr-stack/docker-compose.yml restart

# Netzwerk-Bond-Status
cat /proc/net/bonding/bond0

# Tailscale-Status
docker exec tailscale tailscale status
```

---

## Anhang C: Backup-Empfehlung

| Was | Wie oft | Wohin |
|---|---|---|
| USB-Stick (Unraid OS + Config) | Nach jeder Änderung | Zweiter USB-Stick |
| `appdata`-Share | Täglich | Externe HDD oder Cloud |
| Array-Daten | Nach Bedarf | Externe HDD oder zweiter Standort |

**Appdata-Backup mit CA Backup / Restore Appdata Plugin** (empfohlen):
- Apps → `CA Backup / Restore Appdata`
- Sichert alle Docker-Konfigurationen automatisch

**USB-Stick-Backup:**

```bash
# Im Terminal — Stick auf zweiten Stick spiegeln:
rsync -av /boot/ /mnt/backup-usb/
```
