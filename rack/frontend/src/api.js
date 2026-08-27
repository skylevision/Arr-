/* Der gesamte Serverzugriff an einer Stelle.

   Im Prototypen lag hier der Speicheradapter mit seinen vier Varianten.
   Der faellt weg: der Server ist die einzige Wahrheit. */

const TOKEN_KEY = "rack_token";

export function token() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setToken(value) {
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* Privater Modus: dann eben nur fuer diese Sitzung. */
  }
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function call(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const t = token();
  if (t) headers["X-Rack-Token"] = t;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError("Der Server ist nicht erreichbar.", 0);
  }

  if (!res.ok) {
    let detail = `Fehler ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = typeof data.detail === "string" ? data.detail : detail;
    } catch {
      /* Antwort war kein JSON */
    }
    throw new ApiError(detail, res.status);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  health: () => call("/health"),
  aiTest: () => call("/ai-test", { method: "POST" }),

  profile: () => call("/profile"),
  saveProfile: (p) => call("/profile", { method: "PUT", body: p }),

  bodyAnalysis: (file) => {
    const fd = new FormData();
    fd.append("foto", file);
    return call("/body-analysis", { method: "POST", form: fd });
  },

  items: () => call("/items"),
  createItem: (payload) => call("/items", { method: "POST", body: payload }),
  patchItem: (id, patch) => call(`/items/${id}`, { method: "PATCH", body: patch }),
  deleteItem: (id) => call(`/items/${id}`, { method: "DELETE" }),

  startIngest: (files) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("fotos", f));
    return call("/ingest", { method: "POST", form: fd });
  },
  ingestStatus: (job) => call(`/ingest/${job}`),

  outfits: (payload) => call("/outfits", { method: "POST", body: payload }),
  startOutfits: (payload) => call("/outfits/start", { method: "POST", body: payload }),
  outfitStatus: (job) => call(`/outfits/${job}`),
  feedback: (payload) => call("/feedback", { method: "POST", body: payload }),
  worn: (payload) => call("/worn", { method: "POST", body: payload }),
  gaps: (payload) => call("/gaps", { method: "POST", body: payload }),
  weather: (lat, lon) => call(`/weather?lat=${lat}&lon=${lon}`),
  importAll: (data) => call("/import", { method: "POST", body: data }),
};

/* Bild-URL eines Teils. Der Server setzt einen langen Cache-Header,
   deshalb reicht die schlichte Adresse ohne Zeitstempel. */
export function imageUrl(id) {
  const t = token();
  return `/api/images/${id}${t ? `?token=${encodeURIComponent(t)}` : ""}`;
}

/* Fortschritt eines laufenden Vorgangs verfolgen.

   Bevorzugt Server-Sent Events, faellt bei Problemen auf Abfrage zurueck,
   damit die Anzeige nie haengen bleibt. `fertig` entscheidet, wann der
   Vorgang durch ist, `ergebnis` liefert das, was der Aufrufer haben will. */
function followJob(pfad, job, { status, fertig, ergebnis, onProgress, onDone, onError }) {
  const t = token();
  const url = `/api/${pfad}/${job}/events${t ? `?token=${encodeURIComponent(t)}` : ""}`;
  let closed = false;

  const poll = () => {
    if (closed) return;
    const tick = async () => {
      if (closed) return;
      try {
        const state = await status(job);
        onProgress?.(state);
        if (fertig(state)) return onDone?.(ergebnis(state));
        setTimeout(tick, 700);
      } catch (err) {
        onError?.(err);
      }
    };
    tick();
  };

  let source;
  try {
    source = new EventSource(url);
  } catch {
    poll();
    return () => {
      closed = true;
    };
  }

  source.onmessage = (e) => {
    try {
      onProgress?.(JSON.parse(e.data));
    } catch {
      /* unvollstaendiges Ereignis ignorieren */
    }
  };
  source.addEventListener("ende", (e) => {
    source.close();
    if (closed) return;
    try {
      onDone?.(JSON.parse(e.data));
    } catch {
      poll();
    }
  });
  source.onerror = () => {
    source.close();
    if (!closed) poll();
  };

  return () => {
    closed = true;
    source?.close();
  };
}

export function followIngest(job, handlers) {
  return followJob("ingest", job, {
    status: api.ingestStatus,
    fertig: (s) => s.status === "fertig",
    ergebnis: (s) => s,
    ...handlers,
  });
}

export function followOutfits(job, handlers) {
  return followJob("outfits", job, {
    status: api.outfitStatus,
    fertig: (s) => s.status === "fertig",
    ergebnis: (s) => s.ergebnis,
    ...handlers,
  });
}
