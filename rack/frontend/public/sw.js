/* Service Worker: haelt die Huelle der App offline verfuegbar.

   Bewusst schlank. Die Programmhuelle wird vorgehalten, Bilder werden
   nachtraeglich gecacht, API-Antworten nie. Ein veralteter Vorschlag
   waere schlimmer als gar keiner. */

/* Version hochziehen, wenn sich die Zwischenspeicherung aendert: der
   activate-Schritt loescht dann alles, was nicht mehr dazugehoert.

   v2 (29.08.2026) behebt einen Fehler, der die App nach einem Update
   schwarz starten liess: die Huelle unter "/" wurde beim Installieren
   einmal geholt und nie wieder. Nach einem Neubau zeigte sie auf ein
   Bundle mit altem Namen, das es nicht mehr gab — und weil der Start
   ueber Tailscale haeufig beginnt, bevor die Verbindung steht, griff
   genau dieser veraltete Eintrag. */
const SHELL = "rack-shell-v2";
const IMAGES = "rack-images-v1";
const SHELL_FILES = [
  "/",
  "/manifest.webmanifest",
  "/apple-touch-icon.png",
  "/icon-192.png",
  "/icon-512.png",
  "/favicon-32.png",
  "/fonts/fonts.css",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== SHELL && k !== IMAGES).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  /* Bilder aendern sich unter derselben ID nie: erst Cache, dann Netz. */
  if (url.pathname.startsWith("/api/images/")) {
    e.respondWith(
      caches.open(IMAGES).then(async (cache) => {
        const hit = await cache.match(request);
        if (hit) return hit;
        const res = await fetch(request);
        if (res.ok) cache.put(request, res.clone());
        return res;
      })
    );
    return;
  }

  /* Alles andere unter /api bleibt ungecacht. */
  if (url.pathname.startsWith("/api/")) return;

  /* Navigation: Netz zuerst — und der Erfolg wird mitgeschrieben.

     Das Mitschreiben ist der eigentliche Punkt: sonst altert die
     Offline-Huelle weg und verweist auf Bundles, die nach dem naechsten
     Neubau nicht mehr existieren. */
  if (request.mode === "navigate") {
    e.respondWith(
      fetch(request)
        .then((res) => {
          if (res.ok) {
            const kopie = res.clone();
            caches.open(SHELL).then((c) => c.put("/", kopie));
          }
          return res;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }

  /* Alles Uebrige: erst Cache, dann Netz. Die Dateien unter /assets/
     tragen den Inhalts-Hash im Namen und aendern sich unter demselben
     Namen nie — ein Treffer ist deshalb immer richtig.

     Faellt das Netz fuer ein fehlendes Bundle aus, liefert der Worker
     nichts Halbes: ohne Antwort zeigt der Browser seinen eigenen Fehler,
     das ist ehrlicher als eine leere Seite. */
  e.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ||
        fetch(request).then((res) => {
          if (res.ok && (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/fonts/"))) {
            const kopie = res.clone();
            caches.open(SHELL).then((c) => c.put(request, kopie));
          }
          return res;
        })
    )
  );
});
