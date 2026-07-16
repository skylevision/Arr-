# Dienste-Übersicht

Alle Dienste des Arr-Stacks auf einen Blick — per Name, per IP, mit Port.
Die Namen funktionieren im ganzen Heimnetz, sobald die Fritz!Box AdGuard als
lokalen DNS verteilt (Einrichtung: siehe unten).

## Dienste

| Dienst | Per Name | Per IP | Port | Zweck |
|---|---|---|---|---|
| **Homepage** | [http://homepage.fritz.box:3000](http://homepage.fritz.box:3000) | [http://192.168.178.5:3000](http://192.168.178.5:3000) | 3000 | Dashboard (Startseite) |
| **Jellyfin** | [http://jellyfin.fritz.box:8096](http://jellyfin.fritz.box:8096) | [http://192.168.178.5:8096](http://192.168.178.5:8096) | 8096 | Filme & Serien schauen |
| **Seerr** | [http://seerr.fritz.box:5055](http://seerr.fritz.box:5055) | [http://192.168.178.5:5055](http://192.168.178.5:5055) | 5055 | Filme/Serien wünschen |
| **Radarr** | [http://radarr.fritz.box:7878](http://radarr.fritz.box:7878) | [http://192.168.178.5:7878](http://192.168.178.5:7878) | 7878 | Film-Verwaltung |
| **Sonarr** | [http://sonarr.fritz.box:8989](http://sonarr.fritz.box:8989) | [http://192.168.178.5:8989](http://192.168.178.5:8989) | 8989 | Serien-Verwaltung |
| **Prowlarr** | [http://prowlarr.fritz.box:9696](http://prowlarr.fritz.box:9696) | [http://192.168.178.5:9696](http://192.168.178.5:9696) | 9696 | Indexer-Verwaltung |
| **Bazarr** | [http://bazarr.fritz.box:6767](http://bazarr.fritz.box:6767) | [http://192.168.178.5:6767](http://192.168.178.5:6767) | 6767 | Untertitel |
| **SABnzbd** | [http://sabnzbd.fritz.box:8090](http://sabnzbd.fritz.box:8090) | [http://192.168.178.5:8090](http://192.168.178.5:8090) | 8090 | Usenet-Downloads |
| **AdGuard** | [http://adguard.fritz.box:8081](http://adguard.fritz.box:8081) | [http://192.168.178.5:8081](http://192.168.178.5:8081) | 8081 | DNS & Werbeblocker (Login: siehe Server-`.env`) |
| **Unraid** | [http://unraid.fritz.box](http://unraid.fritz.box) | [http://192.168.178.5](http://192.168.178.5) | 80 | Server-Verwaltung |

> **Kurzform:** Sobald der DNS eingerichtet ist, reicht im Browser auch `jellyfin:8096`,
> `seerr:5055` usw. — die Fritz!Box verteilt `fritz.box` als Suchdomäne.
> (Beim allerersten Mal fragt Chrome evtl. „Meintest du http://jellyfin:8096?" — einmal bestätigen.)

> **Jellyfin-Apps:** In der Jellyfin-App (Handy/TV) muss gar keine Adresse getippt werden —
> der Server wird im Heimnetz automatisch gefunden (Auto-Discovery, UDP 7359) und erscheint
> beim Start der App unter „Server auswählen". Klappt nur im LAN/WLAN, nicht über Tailscale;
> unterwegs die Adresse aus der [Freunde-Anleitung](FREUNDE_ANLEITUNG.md) verwenden.

## DNS-Auflösung — wie es funktioniert

```
Gerät (Handy/PC)
   │  fragt: jellyfin.fritz.box?
   ▼
AdGuard Home (192.168.178.5:53)          ← von der Fritz!Box per DHCP verteilt
   ├─ *.fritz.box (Dienste)  → Rewrite → 192.168.178.5
   ├─ fritz.box, Drucker usw. → weiter zur Fritz!Box (192.168.178.1)
   └─ Internet-Namen          → verschlüsselt zu Cloudflare/Google (DoH)
```

## Einmalige Einrichtung in der Fritz!Box

1. **Heimnetz → Netzwerk → Netzwerkeinstellungen → IPv4-Einstellungen**
   → **Lokaler DNS-Server: `192.168.178.5`** ✅ *(das ist die richtige Stelle!)*
2. **IPv6-Einstellungen** (gleiche Seite, Abschnitt IPv6): Haken **entfernen** bei
   **„DNSv6-Server auch über Router Advertisement bekanntgeben (RFC 5006)"** ⚠️
   *(sonst verteilt die Fritz!Box sich selbst als IPv6-DNS — Geräte fragen dann
   bevorzugt den Router statt AdGuard, und `*.fritz.box`-Namen schlagen fehl)*
3. **Internet → Zugangsdaten → DNS-Server**: auf **Automatik/Provider** lassen ⚠️
   *(hier NICHT die 192.168.178.5 eintragen — das erzeugt eine DNS-Schleife
   Router → AdGuard → Router und die Fritz!Box schaltet AdGuard dann ab)*
4. Geräte einmal neu verbinden: WLAN aus/an, bzw. am PC
   `ipconfig /release && ipconfig /renew && ipconfig /flushdns`

**Test:** `nslookup jellyfin.fritz.box` muss `192.168.178.5` liefern.

> ⚠️ Ab dann läuft das Heimnetz-DNS über den Server. Wird der Server länger
> heruntergefahren: lokalen DNS-Server in der Fritz!Box wieder auf Automatik stellen.
