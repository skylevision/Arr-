import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
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
