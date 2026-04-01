# Freunde & Familie — Anleitung für Zuschauer

Dein Freund hat einen eigenen Medienserver. Diese Anleitung erklärt, wie du dich verbindest,
Filme und Serien anforderst und alles auf deinen Geräten nutzt.

---

## Inhaltsverzeichnis

1. [Was du bekommst](#1-was-du-bekommst)
2. [Was du brauchst](#2-was-du-brauchst)
3. [Schritt 1 — Tailscale installieren](#3-schritt-1--tailscale-installieren-deine-verbindung)
4. [Schritt 2 — Jellyfin einrichten](#4-schritt-2--jellyfin-einrichten-dein-mediaplayer)
5. [Schritt 3 — Medien anfordern (Seerr)](#5-schritt-3--medien-anfordern-seerr)
6. [Geräteanleitung — Smartphone](#6-geräteanleitung--smartphone-androidios)
7. [Geräteanleitung — PC / Mac](#7-geräteanleitung--pc--mac)
8. [Geräteanleitung — Fire TV Stick](#8-geräteanleitung--fire-tv-stick)
9. [Was kannst du alles machen?](#9-was-kannst-du-alles-machen)
10. [Häufige Fragen (FAQ)](#10-häufige-fragen-faq)

---

## 1. Was du bekommst

| Was | Wozu |
|---|---|
| 🎬 **Jellyfin** | Dein Netflix — alle Filme und Serien streamen |
| 🔍 **Seerr** | Neue Filme / Serien anfordern |
| 🔒 **Tailscale** | Sichere Verbindung zum Server — von überall, kostenlos |

Das läuft alles auf dem privaten Server deines Freundes. Keine Werbung, kein Abo.

---

## 2. Was du brauchst

**Vom Admin (deinem Freund) erhältst du:**

- [ ] Eine **Tailscale-Einladung** (E-Mail von Tailscale)
- [ ] Dein **Jellyfin-Benutzername** und **Passwort**
- [ ] Die **Server-IP** im Tailscale-Netzwerk (z. B. `100.x.x.x`) oder der Hostname (z. B. `arr-stack`)

**Du erstellst dir selbst:**

- [ ] Ein kostenloses [Tailscale-Konto](https://login.tailscale.com/start) (mit deiner E-Mail oder Google/GitHub)

> **Wichtig**: Tailscale ist die Verbindung zum Server. Ohne Tailscale kein Zugriff,
> wenn du nicht im gleichen WLAN wie der Server bist.

---

## 3. Schritt 1 — Tailscale installieren (deine Verbindung)

Tailscale ist ein kostenloses VPN. Es verbindet dein Gerät direkt mit dem Server,
egal wo du bist — zuhause, unterwegs, im Café.

### Konto erstellen

1. Gehe zu [tailscale.com](https://tailscale.com) → **„Get started"**
2. Mit Google, Microsoft oder E-Mail registrieren
3. Teile deinen Tailscale-**Benutzernamen / E-Mail** mit dem Admin — er schickt dir eine Einladung

### Einladung annehmen

Der Admin schickt dir über die Tailscale-Konsole eine **Node-Share-Einladung**.
Du bekommst eine E-Mail von Tailscale → Link klicken → bestätigen.

Danach siehst du in deiner Tailscale-App den Server (z. B. `arr-stack`) in der Geräteliste.

### Tailscale-App installieren

| Gerät | App | Link |
|---|---|---|
| Android | Tailscale | [Play Store](https://play.google.com/store/apps/details?id=com.tailscale.ipn) |
| iPhone / iPad | Tailscale | [App Store](https://apps.apple.com/app/tailscale/id1470499037) |
| Windows | Tailscale | [tailscale.com/download](https://tailscale.com/download) |
| macOS | Tailscale | App Store oder tailscale.com/download |

### Verbinden

1. App öffnen → mit deinem Tailscale-Konto anmelden
2. **„Connect"** tippen → Tailscale läuft jetzt im Hintergrund
3. In der Geräteliste sollte der Server erscheinen (z. B. `arr-stack`)
4. Die IP des Servers (z. B. `100.x.x.x`) vom Admin erfragen oder in der App nachsehen

> **Tipp**: Tailscale im Hintergrund laufen lassen. Dann hast du immer Zugriff,
> sobald du die App öffnest.

---

## 4. Schritt 2 — Jellyfin einrichten (dein Mediaplayer)

Jellyfin ist der eigentliche Video-Player. Dein Account wird vom Admin angelegt.

### Jellyfin aufrufen

Wenn Tailscale verbunden ist, erreichst du Jellyfin im Browser oder der App unter:
```
http://arr-stack:8096
```
oder mit der direkten Tailscale-IP:
```
http://100.x.x.x:8096    ← IP beim Admin erfragen
```

### Beim ersten Login

1. Benutzername und Passwort eingeben (vom Admin erhalten)
2. Empfohlen: Passwort sofort unter **„Einstellungen → Profil"** ändern
3. Bevorzugte Sprache und Untertitel-Einstellungen setzen (einmalig)

### Apps für Jellyfin

| Gerät | App | Hinweis |
|---|---|---|
| Android | Jellyfin für Android | [Play Store](https://play.google.com/store/apps/details?id=org.jellyfin.mobile) |
| iPhone / iPad | Jellyfin | [App Store](https://apps.apple.com/app/jellyfin-mobile/id1480192618) |
| Windows / macOS | Browser (Chrome/Firefox) oder [Jellyfin Media Player](https://github.com/jellyfin/jellyfin-media-player/releases) | Desktop-App hat besseren Codec-Support |
| Fire TV Stick | Jellyfin for Android TV | Amazon Appstore (direkt suchen) |
| Apple TV | Infuse oder Jellyfin | App Store |
| Smart TV | Browser oder Jellyfin-App (je nach Modell) | |

---

## 5. Schritt 3 — Medien anfordern (Seerr)

Seerr ist wie eine Wunschliste. Du suchst einen Film oder eine Serie, klickst auf „Anfordern",
und der Admin wird benachrichtigt. Sobald er genehmigt (oder wenn Auto-Genehmigung aktiv ist),
wird automatisch gesucht, heruntergeladen und in Jellyfin hinzugefügt.

### Seerr aufrufen

```
http://arr-stack:5055
```
oder:
```
http://100.x.x.x:5055
```

### Login

1. Klicke auf **„Mit Jellyfin anmelden"**
2. Gib deine Jellyfin-Zugangsdaten ein — kein zweites Konto nötig!

### Film oder Serie anfordern

1. Suchfeld oben → Titel eingeben
2. Auf den Film/die Serie klicken
3. **„Anfordern"** (blauer Button) klicken
4. Fertig! Du bekommst eine Benachrichtigung, sobald der Inhalt verfügbar ist.

### Status deiner Anfragen

**Profil → Anfragen** zeigt dir:
- ⏳ **Ausstehend** — wartet auf Genehmigung durch den Admin
- 🔄 **Verarbeitung** — wird gerade heruntergeladen
- ✅ **Verfügbar** — in Jellyfin bereit zum Ansehen

---

## 6. Geräteanleitung — Smartphone (Android/iOS)

### Einmalige Einrichtung

```
① Tailscale installieren & anmelden
② Tailscale verbinden (Schalter in der App)
③ Jellyfin App installieren
④ Jellyfin App öffnen → Server hinzufügen:
   Adresse: http://100.x.x.x:8096
⑤ Mit Benutzername/Passwort anmelden
⑥ Im Browser: http://100.x.x.x:5055 für Seerr (als Lesezeichen speichern)
```

### Täglich nutzen

1. Tailscale öffnen → verbinden (falls nicht schon aktiv)
2. Jellyfin App öffnen → Film/Serie auswählen → abspielen
3. Seerr im Browser → neue Inhalte anfordern

### Offline-Download (nur Mobile App)

Die Jellyfin-App unterstützt **Downloads** für unterwegs:
- Film/Episode antippen → **⋮ Menü → Herunterladen**
- Gespeichert unter Einstellungen → Downloads
- Kein Internet oder Tailscale nötig zum Abspielen nach dem Download

> **Hinweis iOS**: Die Jellyfin iOS App unterstützt Downloads abhängig von der App-Version.
> Falls nicht verfügbar: Infuse (kostenpflichtig) als Alternative mit Offline-Support.

---

## 7. Geräteanleitung — PC / Mac

### Einmalige Einrichtung

```
① Tailscale herunterladen: tailscale.com/download
② Installieren & mit deinem Konto anmelden
③ Tailscale-Symbol in der Taskleiste → "Connected"
④ Browser öffnen:
   Jellyfin:  http://arr-stack:8096  (oder http://100.x.x.x:8096)
   Seerr:     http://arr-stack:5055  (oder http://100.x.x.x:5055)
⑤ Beide als Lesezeichen speichern
```

### Desktop-App (optional, bessere Wiedergabe)

**Jellyfin Media Player** bietet bessere Codec-Unterstützung als der Browser
(HDR, DTS, TrueHD Audio ohne Transcoding):

1. [github.com/jellyfin/jellyfin-media-player/releases](https://github.com/jellyfin/jellyfin-media-player/releases)
2. Installer herunterladen und starten
3. Server-Adresse eingeben → anmelden

### Qualität & Transcoding

Im Browser oder der App kannst du die Qualität manuell setzen:
- **Einstellungen → Wiedergabe → Videoqualität** → z. B. „Original" für maximale Qualität
- Bei langsamer Verbindung: niedrigere Qualität wählen (dann wandelt der Server um)

---

## 8. Geräteanleitung — Fire TV Stick

### Jellyfin installieren

Jellyfin ist direkt im Amazon Appstore:

```
① Fire TV Stick starten
② Suche → "Jellyfin" eingeben
③ Jellyfin for Android TV → Installieren
④ App öffnen → Server hinzufügen: http://100.x.x.x:8096
⑤ Benutzername & Passwort eingeben
```

### Tailscale auf Fire TV (für Zugriff außerhalb des Heimnetzes)

> **Zuhause im gleichen WLAN wie der Server?** Kein Tailscale nötig —
> direkt mit der LAN-IP des Servers verbinden: `http://192.168.1.100:8096`

Für Zugriff von einem anderen Ort (z. B. bei Freunden) braucht der Fire TV Stick ebenfalls Tailscale.
Das erfordert ein Sideload (Installation außerhalb des Amazon Stores):

```
① Fire TV: Einstellungen → Mein Fire TV → Entwickleroptionen
   → Apps aus unbekannten Quellen: AN

② Amazon Appstore → "Downloader" App installieren (kostenlos)

③ Downloader öffnen → URL eingeben:
   https://pkgs.tailscale.com/stable/tailscale-latest.apk
   (oder beim Admin nach dem aktuellen APK-Link fragen)

④ Installieren → Tailscale öffnen → anmelden
⑤ VPN-Berechtigung bestätigen
⑥ Verbinden → Jellyfin läuft jetzt auch remote
```

### Medien anfordern vom Fernseher

Seerr hat keine Fire TV App. Anfragen am besten über Smartphone oder PC stellen.

### Steuerung

| Taste | Funktion in Jellyfin |
|---|---|
| Zurück | Zurück / Menü |
| Play/Pause | Wiedergabe |
| Links/Rechts | 10 Sekunden vor/zurück |
| Menü (☰) | Untertitel, Audio-Spur, Qualität |
| Suche (🔍) | Jellyfin-Suche |

---

## 9. Was kannst du alles machen?

### Als Zuschauer

| Funktion | Wo | Beschreibung |
|---|---|---|
| 🎬 Filme & Serien schauen | Jellyfin | Vollständige Bibliothek, inkl. Infos und Trailer |
| 📺 Untertitel wählen | Jellyfin | Deutsch, Englisch, mehrere Sprachen verfügbar |
| 🔊 Tonspur wählen | Jellyfin | Original, Deutsch, Kommentar etc. |
| ⬇️ Offline herunterladen | Jellyfin Mobile App | Für unterwegs ohne Internet |
| ⭐ Favoriten markieren | Jellyfin | Eigene Merkliste |
| ▶️ Weiterschauen | Jellyfin | Fortschritt wird geräteübergreifend gespeichert |
| 🔍 Inhalte anfordern | Seerr | Filme und Serien wünschen |
| 📋 Anfragen verfolgen | Seerr → Profil | Status deiner Anfragen |

### Was der Admin macht

| Funktion | Wer |
|---|---|
| Neue Inhalte genehmigen | Admin |
| Accounts erstellen/löschen | Admin |
| Server warten | Admin |
| Speicher verwalten | Admin |

### Was du **nicht** tun kannst (als normaler Nutzer)

- Andere Nutzer-Accounts sehen oder verwalten
- Inhalte aus der Bibliothek löschen
- Server-Einstellungen ändern
- Auf Radarr/Sonarr/SABnzbd zugreifen (nur Admin)

---

## 10. Häufige Fragen (FAQ)

**„Ich kann Jellyfin nicht erreichen."**
→ Ist Tailscale verbunden? Tailscale-App öffnen → grüner Haken = verbunden.
→ Richtige IP-Adresse? Beim Admin nachfragen.
→ Stimmt der Port? Standard ist `8096`.

**„Video lädt sehr langsam / stockt."**
→ Qualität in Jellyfin auf eine niedrigere Stufe stellen (z. B. 10 Mbit statt Original).
→ Der Server wandelt das Video dann live um — das reduziert die benötigte Bandbreite.

**„Untertitel fehlen oder sind falsch."**
→ In Jellyfin während der Wiedergabe: Untertitel-Symbol antippen → andere Sprache wählen.
→ Wenn keine Untertitel vorhanden: Admin bescheid geben, er kann sie nachträglich suchen (Bazarr).

**„Ich habe meinen Film angefordert aber er ist nicht da."**
→ Status in Seerr prüfen (Profil → Anfragen).
→ „Ausstehend" = wartet auf Admin-Genehmigung.
→ „Verarbeitung" = wird gerade gesucht / heruntergeladen (kann Minuten bis Stunden dauern).
→ Wenn nach 24h noch nichts: Admin kontaktieren.

**„Kann ich auch mit Freunden zusammen schauen?"**
→ Jellyfin hat keine native Sync-Watch-Funktion.
→ Alternative: [SyncPlay](https://jellyfin.org/docs/general/clients/syncplay/) — im Jellyfin-Client verfügbar (gleiche Session starten).

**„Brauche ich immer Tailscale?"**
→ Nur wenn du **nicht** im gleichen Heimnetz wie der Server bist.
→ Zuhause beim Admin: direkt über LAN-IP verbinden, kein Tailscale nötig.

**„Kann ich Tailscale auf mehreren Geräten haben?"**
→ Ja! Installiere Tailscale auf so vielen Geräten wie du willst — kostenlos bis zu 3 Nutzer / 100 Geräte im Free-Plan.

**„Was kostet das?"**
→ Für dich als Nutzer: **nichts**. Tailscale Free Plan reicht vollständig aus.
→ Jellyfin ist Open Source und kostenlos.
→ Seerr ist kostenlos.

---

## Schnellübersicht — Adressen

Alles über Tailscale erreichbar (wenn verbunden):

| Dienst | Adresse |
|---|---|
| 🎬 Jellyfin | `http://arr-stack:8096` |
| 🔍 Seerr (Anfragen) | `http://arr-stack:5055` |

> `arr-stack` durch den tatsächlichen Tailscale-Hostnamen oder die IP ersetzen —
> diese Information bekommst du vom Admin.

---

*Bei Problemen oder Fragen: deinen Admin kontaktieren.*
