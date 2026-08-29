import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

/* Faengt Fehler beim Rendern ab.

   Ohne das endet jeder Fehler in der Oberflaeche als schwarze Flaeche:
   React haengt den Baum aus, und weil die Seite dunkel gestaltet ist,
   sieht man nicht einmal, dass etwas fehlt. Auf dem Telefon gibt es
   keine Konsole, in der man nachsehen koennte — also muss die Meldung
   auf den Bildschirm.

   Der Knopf raeumt zusaetzlich die Zwischenspeicher weg: die haeufigste
   Ursache fuer eine kaputte Huelle ist ein Service Worker, der noch auf
   eine alte Fassung zeigt. */
class Auffangnetz extends React.Component {
  constructor(props) {
    super(props);
    this.state = { fehler: null };
  }

  static getDerivedStateFromError(fehler) {
    return { fehler };
  }

  componentDidCatch(fehler, info) {
    console.error("Rack ist beim Anzeigen gescheitert:", fehler, info);
  }

  async neuLaden() {
    try {
      if ("serviceWorker" in navigator) {
        const regs = await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.map((r) => r.unregister()));
      }
      if (window.caches) {
        const keys = await caches.keys();
        await Promise.all(keys.map((k) => caches.delete(k)));
      }
    } catch {
      /* Dann eben nur neu laden. */
    }
    window.location.reload();
  }

  render() {
    if (!this.state.fehler) return this.props.children;
    return (
      <div
        style={{
          background: "#121212", color: "#e8e6e3", minHeight: "100vh",
          padding: "2rem 1.25rem", fontFamily: "system-ui, sans-serif",
        }}
      >
        <h1 style={{ fontSize: 22, marginBottom: 12 }}>Rack konnte nicht starten</h1>
        <p style={{ color: "#9a9793", fontSize: 14, lineHeight: 1.6 }}>
          Meist hilft der Knopf unten: er entfernt die gespeicherte Fassung der App
          und lädt sie frisch vom Server.
        </p>
        <button
          onClick={() => this.neuLaden()}
          style={{
            marginTop: 20, padding: "14px 18px", width: "100%",
            background: "#e8e6e3", color: "#121212", border: 0,
            fontSize: 11, letterSpacing: "0.18em", textTransform: "uppercase",
          }}
        >
          Zwischenspeicher leeren und neu laden
        </button>
        <pre
          style={{
            marginTop: 24, color: "#6f6c68", fontSize: 11, whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {String(this.state.fehler?.stack || this.state.fehler)}
        </pre>
      </div>
    );
  }
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Auffangnetz>
      <App />
    </Auffangnetz>
  </React.StrictMode>
);

/* Nur unter HTTPS registrierbar. Ueber den Tailscale-Namen ist das der
   Fall, im LAN ueber http laeuft die App ohne Offline-Huelle weiter. */
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* Ohne Service Worker funktioniert alles ausser Offline. */
    });
  });
}
