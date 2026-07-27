# Dienste-Übersicht

Alle Dienste des Arr-Stacks auf einen Blick — per Name, per IP, mit Port.
Die Namen funktionieren im ganzen Heimnetz, sobald die Fritz!Box als
DNS-Vermittler eingerichtet ist (Einrichtung: siehe unten).

## Dienste

| Dienst | Per Name | Per IP | Port | Zweck |
|---|---|---|---|---|
| **Homepage** | [http://homepage.home:3000](http://homepage.home:3000) | [http://192.168.178.5:3000](http://192.168.178.5:3000) | 3000 | Dashboard (Startseite) |
| **Jellyfin** | [http://jellyfin.home:8096](http://jellyfin.home:8096) | [http://192.168.178.5:8096](http://192.168.178.5:8096) | 8096 | Filme & Serien schauen |
| **Seerr** | [http://seerr.home:5055](http://seerr.home:5055) | [http://192.168.178.5:5055](http://192.168.178.5:5055) | 5055 | Filme/Serien wünschen |
| **Radarr** | [http://radarr.home:7878](http://radarr.home:7878) | [http://192.168.178.5:7878](http://192.168.178.5:7878) | 7878 | Film-Verwaltung |
| **Sonarr** | [http://sonarr.home:8989](http://sonarr.home:8989) | [http://192.168.178.5:8989](http://192.168.178.5:8989) | 8989 | Serien-Verwaltung |
| **Prowlarr** | [http://prowlarr.home:9696](http://prowlarr.home:9696) | [http://192.168.178.5:9696](http://192.168.178.5:9696) | 9696 | Indexer-Verwaltung |
| **Bazarr** | [http://bazarr.home:6767](http://bazarr.home:6767) | [http://192.168.178.5:6767](http://192.168.178.5:6767) | 6767 | Untertitel |
| **SABnzbd** | [http://sabnzbd.home:8090](http://sabnzbd.home:8090) | [http://192.168.178.5:8090](http://192.168.178.5:8090) | 8090 | Usenet-Downloads |
| **AdGuard** | [http://adguard.home:8081](http://adguard.home:8081) | [http://192.168.178.5:8081](http://192.168.178.5:8081) | 8081 | DNS & Werbeblocker (Login: siehe Server-`.env`) |
| **Unraid** | [http://unraid.home](http://unraid.home) | [http://192.168.178.5](http://192.168.178.5) | 80 | Server-Verwaltung |

> **Namen:** Die Dienste heißen jetzt `<dienst>.home` (z. B. `jellyfin.home:8096`).
> Immer den vollen Namen tippen — anders als bei `fritz.box` verteilt die
> Fritz!Box `home` **nicht** als Suchdomäne, `jellyfin` allein reicht also nicht.
> (Beim ersten Mal fragt Chrome evtl. „Meintest du …?" — einmal bestätigen.)

> **Jellyfin-Apps:** In der Jellyfin-App (Handy/TV) muss gar keine Adresse getippt werden —
> der Server wird im Heimnetz automatisch gefunden (Auto-Discovery, UDP 7359) und erscheint
> beim Start der App unter „Server auswählen". Klappt nur im LAN/WLAN, nicht über Tailscale;
> unterwegs die Adresse aus der [Freunde-Anleitung](FREUNDE_ANLEITUNG.md) verwenden.

## DNS-Auflösung — wie es funktioniert (Vermittler-Modus)

Die Fritz!Box ist der DNS-Server der Geräte (sie läuft **immer**). Sie beantwortet
ihre eigene `fritz.box`-Zone selbst und leitet alles andere an AdGuard weiter —
mit einem öffentlichen DNS als **Fallback**, falls AdGuard (= der Server) aus ist.

```
Gerät (Handy/PC)
   │  fragt: jellyfin.home?  /  google.de?
   ▼
Fritz!Box (192.168.178.1)                 ← DNS-Server der Geräte (immer an)
   ├─ *.fritz.box, Drucker, Router  → beantwortet die Fritz!Box selbst
   └─ alles andere → Upstream-DNS:
        1) AdGuard (192.168.178.5)   ← bevorzugt: Werbeblocker + *.home-Rewrites
        2) 1.1.1.1  (Fallback)       ← springt automatisch ein, wenn AdGuard aus ist
                    │
                    ▼  (über AdGuard, solange erreichbar)
        AdGuard Home (192.168.178.5)
           ├─ *.home (Dienste)  → Rewrite → 192.168.178.5
           └─ Internet-Namen    → verschlüsselt zu Cloudflare/Google (DoH)
```

**Was das bringt:** Ist der Server mal weg (Strom, Neustart, Update), fällt die
Fritz!Box automatisch auf den öffentlichen DNS zurück → **Internet läuft weiter**.
Nur Werbeblocker und die `*.home`-Namen pausieren dann — die Dienste sind ohne
Server ohnehin nicht erreichbar. Solange der Server läuft, geht praktisch aller
Verkehr über AdGuard (bevorzugter, schnellster Upstream), Blocking bleibt aktiv.

## Einmalige Einrichtung in der Fritz!Box

1. **Internet → Zugangsdaten → DNS-Server → „Andere DNSv4-Server verwenden"**
   - **Bevorzugter DNSv4-Server: `192.168.178.5`** (AdGuard)
   - **Alternativer DNSv4-Server: `1.1.1.1`** (öffentlicher Fallback; z. B. auch `9.9.9.9`)
2. **Heimnetz → Netzwerk → Netzwerkeinstellungen → IPv4-Einstellungen**
   → **Lokaler DNS-Server: wieder auf Standard/leer** (die Fritz!Box selbst) —
   also **NICHT** mehr `192.168.178.5`. Die Geräte fragen jetzt die Fritz!Box,
   nicht mehr direkt AdGuard.
3. **DNS-Rebind-Schutz** (gleiche Seite, „Diese Domainnamen werden vom
   DNS-Rebind-Schutz ausgenommen"): **`home`** eintragen ⚠️
   *(sonst filtert die Fritz!Box die privaten `192.168.178.5`-Antworten für
   `*.home` als vermeintlichen Angriff weg — die Dienstnamen gehen dann nicht)*
4. Geräte einmal neu verbinden: WLAN aus/an, bzw. am PC
   `ipconfig /release && ipconfig /renew && ipconfig /flushdns`

**Tests:**
- `nslookup jellyfin.home` muss `192.168.178.5` liefern.
- `nslookup google.de` muss eine öffentliche IP liefern (Internet).
- Fallback prüfen: AdGuard/Server kurz aus → `nslookup google.de` geht weiter
  (jetzt über `1.1.1.1`), `jellyfin.home` nicht (erwartet).

> ℹ️ **Hinweis IPv6:** Der Fallback greift für IPv4. AdGuard hört auf einer
> IPv4-Adresse; für maximal sauberes Blocking auch bei reinen IPv6-Lookups
> könnte man AdGuard später eine feste IPv6 geben und als DNSv6-Upstream
> eintragen. Für die Ausfallsicherheit ist das nicht nötig.

> ℹ️ **Kein manueller Eingriff mehr nötig, wenn der Server ausfällt** —
> die Fritz!Box regelt den Fallback selbst. (Früher musste man den lokalen
> DNS-Server von Hand auf Automatik zurückstellen; das entfällt jetzt.)
