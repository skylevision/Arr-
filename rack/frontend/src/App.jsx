import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, followIngest, followOutfits, imageUrl, setToken, token } from "./api.js";
import {
  ACCESSORY_TYPES, BOTTOM_LEN, BUILDS, C, CATEGORIES, DISPLAY, FITS, OCCASIONS,
  PATTERNS, PHOTO_GUIDE, RISES, SANS, SHOE_WEIGHT, SILHOUETTES, THICKNESS,
  TOP_LEN, TORSOS,
} from "./constants.js";

/* ═══════════════════════════════════════════════════════════════════
   RACK
   Die Oberflaeche des Prototypen, angebunden an den eigenen Server.
   Rechnen, Freistellen und Modellzugriff liegen jetzt im Backend; hier
   bleiben Darstellung und Bedienung.
   ═══════════════════════════════════════════════════════════════════ */

const Label = ({ children, style }) => (
  <span
    style={{ fontFamily: SANS, color: C.dim, letterSpacing: "0.18em", fontSize: 9, ...style }}
    className="uppercase"
  >
    {children}
  </span>
);

function Field({ label, value, options, onChange, flagged }) {
  return (
    <div>
      <Label style={flagged ? { color: C.signal } : undefined}>
        {label}
        {flagged ? " prüfen" : ""}
      </Label>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        style={{
          background: C.raised, color: C.text,
          borderColor: flagged ? C.signal : C.line, fontFamily: SANS,
        }}
        className="w-full mt-1 border rounded-sm px-2 py-2 text-sm"
      >
        <option value="">nicht gesetzt</option>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("heute");
  const [items, setItems] = useState([]);
  const [profile, setProfile] = useState(null);
  const [health, setHealth] = useState(null);
  const [queue, setQueue] = useState([]);
  const [qIndex, setQIndex] = useState(0);
  const [progress, setProgress] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [detail, setDetail] = useState(null);
  const [settings, setSettings] = useState(false);
  const [guide, setGuide] = useState(false);
  const [bodyDraft, setBodyDraft] = useState(null);
  const [occasion, setOccasion] = useState("Alltag");
  const [temp, setTemp] = useState(16);
  const [anchor, setAnchor] = useState(null);
  const [outfits, setOutfits] = useState([]);
  const [relaxed, setRelaxed] = useState(false);
  const [curated, setCurated] = useState(true);
  const [gaps, setGaps] = useState(null);
  const [suggesting, setSuggesting] = useState(null);
  // Was der Nutzer je Vorschlag schon gedrückt hat. Ohne das gibt es
  // keine Quittung an Ort und Stelle, und man drückt mehrfach.
  const [outfitState, setOutfitState] = useState({});
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [needToken, setNeedToken] = useState(false);
  const [aiStatus, setAiStatus] = useState(null);
  const fileRef = useRef(null);
  const bodyRef = useRef(null);
  const importRef = useRef(null);
  const stopIngest = useRef(null);
  const stopSuggest = useRef(null);

  const fail = useCallback((err, fallback) => {
    if (err?.status === 401) {
      setNeedToken(true);
      setError("Dieser Server verlangt ein Zugangstoken.");
      return;
    }
    if (err?.status === 0) setOffline(true);
    setError(err?.message || fallback);
  }, []);

  const reload = useCallback(async () => {
    const [list, prof, hp] = await Promise.all([api.items(), api.profile(), api.health()]);
    setItems(list);
    setProfile(prof);
    setHealth(hp);
    setOffline(false);
    setNeedToken(false);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        await reload();
      } catch (err) {
        fail(err, "Die Daten konnten nicht geladen werden.");
      }
      setLoading(false);
    })();
    return () => {
      stopIngest.current?.();
      stopSuggest.current?.();
    };
  }, [reload, fail]);

  /* Quittungen blenden sich von selbst wieder aus. Fehler bleiben stehen,
     die muss man lesen. */
  useEffect(() => {
    if (!notice) return undefined;
    const t = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(t);
  }, [notice]);

  /* Erste Einrichtung ist erst vorbei, wenn eine Silhouette gewaehlt wurde.
     Der Server liefert eine Vorgabe, deshalb merken wir uns die Wahl. */
  const [setupDone, setSetupDone] = useState(false);
  useEffect(() => {
    if (profile?.silhouette && localStorage.getItem("rack_setup") === "1") setSetupDone(true);
  }, [profile]);

  async function saveProfile(patch) {
    const next = { ...(profile || {}), ...patch };
    setProfile(next);
    try {
      setProfile(await api.saveProfile(next));
    } catch (err) {
      fail(err, "Das Profil konnte nicht gespeichert werden.");
    }
  }

  /* ---------------------------- Erfassen ---------------------------- */
  async function onFiles(e) {
    const files = Array.from(e.target.files || []);
    if (fileRef.current) fileRef.current.value = "";
    if (!files.length) return;
    setError("");
    setBusy(`Lade ${files.length} ${files.length === 1 ? "Foto" : "Fotos"} hoch`);
    let job;
    try {
      job = await api.startIngest(files);
    } catch (err) {
      setBusy("");
      return fail(err, "Die Fotos konnten nicht übertragen werden.");
    }
    setBusy("");
    setProgress({ fertig: 0, gesamt: job.gesamt });
    setQueue([]);
    setQIndex(0);

    stopIngest.current = followIngest(job.job, {
      onProgress: (s) => setProgress({ fertig: s.fertig, gesamt: s.gesamt }),
      onDone: (s) => {
        setProgress(null);
        const usable = (s.eintraege || []).filter((x) => x.attrs);
        if (!usable.length) {
          setError("Keines der Fotos konnte gelesen werden.");
          return;
        }
        setQueue(usable);
        setQIndex(0);
      },
      onError: (err) => {
        setProgress(null);
        fail(err, "Die Erfassung wurde unterbrochen.");
      },
    });
  }

  const patchQueue = (patch) =>
    setQueue((q) => q.map((x, n) => (n === qIndex ? { ...x, attrs: { ...x.attrs, ...patch } } : x)));

  async function saveCurrent() {
    const entry = queue[qIndex];
    if (!entry?.attrs) return;
    setBusy("Speichere");
    try {
      await api.createItem({
        attrs: entry.attrs,
        bild: entry.bild,
        mediaType: entry.mediaType,
        cutout: entry.cutout,
      });
      setItems(await api.items());
      nextCard();
    } catch (err) {
      fail(err, "Das Teil konnte nicht gespeichert werden.");
    }
    setBusy("");
  }

  function nextCard() {
    if (qIndex + 1 < queue.length) setQIndex(qIndex + 1);
    else {
      setQueue([]);
      setQIndex(0);
      setView("schrank");
    }
  }

  /* ------------------------- Körperanalyse -------------------------- */
  async function onBodyPhoto(e) {
    const file = e.target.files?.[0];
    if (bodyRef.current) bodyRef.current.value = "";
    if (!file) return;
    setError("");
    setBusy("Analysiere Proportionen");
    try {
      const res = await api.bodyAnalysis(file);
      setBodyDraft(res);
    } catch (err) {
      setError(
        err?.status === 503
          ? "Ohne API-Schlüssel geht das nicht. Trag die Werte einfach von Hand ein."
          : "Die Analyse hat nicht geklappt. Trag die Werte einfach von Hand ein."
      );
    }
    setBusy("");
  }

  /* --------------------------- Vorschläge --------------------------- */
  function zeigeErgebnis(res) {
    setOutfitState({});
    setOutfits(res?.outfits || []);
    setRelaxed(!!res?.gelockert);
    setCurated(res?.kuratiert !== false);
    if (res?.meldung) setError(res.meldung);
  }

  async function suggest() {
    setError("");
    setNotice("");
    setOutfits([]);
    setOutfitState({});
    stopSuggest.current?.();
    setSuggesting({ phase: "start", text: "Wird vorbereitet", schritt: 0, gesamt: 3 });

    let job;
    try {
      job = await api.startOutfits({ anlass: occasion, temp, anker: anchor });
    } catch (err) {
      setSuggesting(null);
      // Der Vorgangsweg fehlt vielleicht, etwa nach einem Teilupdate.
      // Dann eben in einem Rutsch, nur ohne Fortschritt.
      try {
        setBusy("Kuratiere");
        zeigeErgebnis(await api.outfits({ anlass: occasion, temp, anker: anchor }));
      } catch (err2) {
        fail(err2, "Die Vorschläge konnten nicht geholt werden.");
      }
      setBusy("");
      return;
    }

    stopSuggest.current = followOutfits(job.job, {
      onProgress: (s) => {
        setSuggesting({
          phase: s.phase, text: s.text,
          schritt: s.schritt ?? 0, gesamt: s.gesamt ?? 3,
        });
        // Sobald die Engine gerechnet hat, zeigen wir ihre Rangfolge an.
        // Die kuratierte Fassung ersetzt sie gleich, aber der Bildschirm
        // bleibt nicht leer, während das Modell arbeitet.
        if (s.roh?.outfits?.length) {
          setOutfits(s.roh.outfits);
          setRelaxed(!!s.roh.gelockert);
          setCurated(false);
        }
      },
      onDone: (res) => {
        setSuggesting(null);
        zeigeErgebnis(res);
      },
      onError: (err) => {
        setSuggesting(null);
        fail(err, "Die Vorschläge wurden unterbrochen.");
      },
    });
  }

  async function useWeather() {
    if (!navigator.geolocation) {
      setError("Dieses Gerät gibt den Standort nicht heraus. Stell die Temperatur von Hand ein.");
      return;
    }
    setBusy("Hole das Wetter");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const w = await api.weather(
            pos.coords.latitude.toFixed(2),
            pos.coords.longitude.toFixed(2)
          );
          if (typeof w.temp === "number") setTemp(Math.round(w.temp));
          setNotice(
            `${Math.round(w.temp)} Grad${
              typeof w.gefuehlt === "number" ? `, gefühlt ${Math.round(w.gefuehlt)}` : ""
            }${w.gecacht ? " (gespeichert)" : ""}`
          );
        } catch (err) {
          fail(err, "Das Wetter war nicht abrufbar.");
        }
        setBusy("");
      },
      () => {
        setBusy("");
        setError("Der Standort wurde nicht freigegeben. Stell die Temperatur von Hand ein.");
      },
      { timeout: 10000, maximumAge: 600000 }
    );
  }

  async function runGaps() {
    setError("");
    setGaps(null);
    setBusy("Rechne durch, was dir fehlt");
    try {
      setGaps(await api.gaps({ anlass: occasion, temp }));
    } catch (err) {
      fail(err, "Die Analyse ist fehlgeschlagen.");
    }
    setBusy("");
  }

  const merke = (i, patch) =>
    setOutfitState((s) => ({ ...s, [i]: { ...(s[i] || {}), ...patch } }));

  async function rate(i, parts, verdict) {
    const jetzt = outfitState[i] || {};
    if (jetzt.laeuft) return;
    // Nochmal auf dieselbe Taste nimmt die Bewertung zurück.
    const ziel = jetzt.urteil === verdict ? null : verdict;
    merke(i, { laeuft: "urteil" });
    try {
      await api.feedback({
        teile: parts.map((p) => p.id),
        urteil: ziel === "gut" ? "liked" : ziel === "schlecht" ? "disliked" : null,
      });
      merke(i, { urteil: ziel, laeuft: null });
      setNotice(
        ziel === "gut" ? "Gemerkt, solche Kombinationen kommen öfter."
          : ziel === "schlecht" ? "Gemerkt, diese Paarung kommt seltener."
            : "Bewertung zurückgenommen."
      );
    } catch (err) {
      merke(i, { laeuft: null });
      fail(err, "Die Rückmeldung ging nicht durch.");
    }
  }

  async function markWorn(i, parts, punkte) {
    const jetzt = outfitState[i] || {};
    if (jetzt.laeuft || jetzt.getragen) return;
    merke(i, { laeuft: "getragen" });
    try {
      await api.worn({ teile: parts.map((p) => p.id), anlass: occasion, temp, punkte });
      setItems(await api.items());
      merke(i, { getragen: true, laeuft: null });
      setNotice("Als getragen vermerkt. Diese Teile kommen ein paar Tage seltener dran.");
    } catch (err) {
      merke(i, { laeuft: null });
      fail(err, "Das konnte nicht vermerkt werden.");
    }
  }

  async function updateItem(id, patch) {
    try {
      const updated = await api.patchItem(id, patch);
      setItems((list) => list.map((i) => (i.id === id ? updated : i)));
      setDetail((d) => (d && d.id === id ? updated : d));
    } catch (err) {
      fail(err, "Die Änderung ging nicht durch.");
    }
  }

  async function removeItem(id) {
    try {
      await api.deleteItem(id);
      setItems((list) => list.filter((i) => i.id !== id));
      setDetail(null);
    } catch (err) {
      fail(err, "Das Teil konnte nicht gelöscht werden.");
    }
  }

  function exportAll() {
    const t = token();
    const url = `/api/export${t ? `?token=${encodeURIComponent(t)}` : ""}`;
    window.location.href = url;
  }

  async function importAll(e) {
    const file = e.target.files?.[0];
    if (importRef.current) importRef.current.value = "";
    if (!file) return;
    setBusy("Lese die Sicherung ein");
    try {
      const res = await api.importAll(JSON.parse(await file.text()));
      await reload();
      setNotice(`${res.neu} neu, ${res.aktualisiert} aktualisiert, ${res.bilder} Bilder.`);
      setSettings(false);
    } catch (err) {
      setError(
        err?.status ? err.message : "Die Datei konnte nicht gelesen werden."
      );
    }
    setBusy("");
  }

  const entry = queue[qIndex];
  const attrs = entry?.attrs || {};
  const flagged = (f) => Array.isArray(entry?.unsicher) && entry.unsicher.includes(f);

  /* ---------------------------- Tokenabfrage ------------------------ */
  if (needToken) {
    return (
      <div
        style={{ background: C.bg, color: C.text, fontFamily: SANS, minHeight: "100vh" }}
        className="p-6 flex flex-col justify-center"
      >
        <h1 style={{ fontFamily: DISPLAY, fontSize: 44, lineHeight: 1 }}>Rack</h1>
        <p style={{ color: C.dim }} className="mt-3 text-sm leading-relaxed">
          Dieser Server verlangt ein Zugangstoken. Es steht in der Datei .env neben der
          Compose-Datei unter RACK_TOKEN.
        </p>
        <form
          className="mt-6"
          onSubmit={async (e) => {
            e.preventDefault();
            setToken(new FormData(e.currentTarget).get("t").toString().trim());
            setError("");
            try {
              await reload();
            } catch (err) {
              fail(err, "Das Token wurde nicht akzeptiert.");
            }
          }}
        >
          <input
            name="t"
            type="password"
            autoFocus
            placeholder="Token"
            style={{ background: C.raised, color: C.text, borderColor: C.line }}
            className="w-full border rounded-sm px-3 py-3 text-sm"
          />
          <button
            type="submit"
            style={{ background: C.text, color: C.bg, letterSpacing: "0.2em" }}
            className="mt-3 w-full py-4 text-[11px] uppercase"
          >
            Weiter
          </button>
        </form>
        {error && <p style={{ color: C.signal }} className="text-sm mt-3">{error}</p>}
      </div>
    );
  }

  /* ---------------------------- Erste Einrichtung ------------------- */
  if (!loading && !offline && !setupDone && !profile?.notes && !items.length) {
    return (
      <div
        style={{ background: C.bg, color: C.text, fontFamily: SANS, minHeight: "100vh" }}
        className="p-6 flex flex-col justify-center"
      >
        <h1 style={{ fontFamily: DISPLAY, fontSize: 48, lineHeight: 1 }}>Rack</h1>
        <p style={{ color: C.dim }} className="mt-3 text-sm leading-relaxed">
          Zwei Angaben, dann kann es losgehen. Alles Weitere findest du später unter Profil.
        </p>

        <div className="mt-7">
          <Label>Ich bin</Label>
          <div className="mt-2 flex gap-2">
            {["männlich", "weiblich"].map((g) => (
              <button
                key={g}
                onClick={() => setProfile({ ...(profile || {}), gender: g })}
                style={{
                  background: profile?.gender === g ? C.text : "transparent",
                  color: profile?.gender === g ? C.bg : C.text,
                  borderColor: profile?.gender === g ? C.text : C.line,
                }}
                className="flex-1 border rounded-sm py-3 text-sm"
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-6">
          <Label>Wie soll kombiniert werden</Label>
          <div className="mt-2 flex flex-col gap-2">
            {SILHOUETTES.map((s) => (
              <button
                key={s.key}
                onClick={async () => {
                  await saveProfile({
                    silhouette: s.key,
                    gender: profile?.gender || "männlich",
                    height: 180, build: "normal", torso: "ausgeglichen",
                    glasses: false, notes: "",
                  });
                  localStorage.setItem("rack_setup", "1");
                  setSetupDone(true);
                }}
                disabled={!profile?.gender}
                style={{
                  background: C.surface, borderColor: C.line, color: C.text,
                  opacity: profile?.gender ? 1 : 0.4,
                }}
                className="border rounded-sm p-4 text-left"
              >
                <span className="block text-base">{s.label}</span>
                <span style={{ color: C.dim }} className="text-xs">{s.hint}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: C.bg, color: C.text, fontFamily: SANS, minHeight: "100vh" }}>
      <header
        style={{ borderColor: C.line, background: `${C.bg}f5` }}
        className="sticky top-0 z-20 border-b px-5 pt-5 pb-3"
      >
        <div className="flex items-end justify-between">
          <h1 style={{ fontFamily: DISPLAY, fontSize: 30, lineHeight: 0.9 }}>Rack</h1>
          <button
            onClick={() => setSettings(true)}
            style={{ color: C.dim, letterSpacing: "0.18em" }}
            className="text-[10px] uppercase pb-1"
          >
            Profil
          </button>
        </div>
        <nav className="mt-4 flex gap-6">
          {[["heute", "Heute"], ["schrank", `Schrank ${items.length}`], ["fehlt", "Fehlt"]].map(
            ([k, l]) => (
              <button
                key={k}
                onClick={() => setView(k)}
                style={{
                  color: view === k ? C.text : C.faint,
                  borderColor: view === k ? C.text : "transparent",
                  letterSpacing: "0.18em",
                }}
                className="text-[10px] uppercase pb-2 border-b"
              >
                {l}
              </button>
            )
          )}
        </nav>
      </header>

      {offline && (
        <div style={{ borderColor: C.line, background: C.surface }} className="border-b px-5 py-3">
          <Label style={{ color: C.signal }}>Ohne Verbindung</Label>
          <p style={{ color: C.dim }} className="text-xs mt-1 leading-relaxed">
            Der Server ist gerade nicht erreichbar. Gespeichert wird nichts, sobald die
            Verbindung steht, geht es normal weiter.
          </p>
        </div>
      )}

      {health && !health.ki && (
        <div style={{ borderColor: C.line, background: C.surface }} className="border-b px-5 py-3">
          <Label>Ohne Schlüssel</Label>
          <p style={{ color: C.dim }} className="text-xs mt-1 leading-relaxed">
            Es ist kein API-Schlüssel hinterlegt. Erfassen von Hand, die Bewertung und alle
            Ansichten funktionieren normal, nur Fotos lesen und Kuratieren fallen aus.
          </p>
        </div>
      )}

      {(busy || error || progress) && (
        <div className="px-5 pt-4">
          {busy && (
            <p style={{ color: C.dim, letterSpacing: "0.18em" }} className="text-[10px] uppercase">
              {busy}
            </p>
          )}
          {progress && (
            <div className="mt-2">
              <Label>
                Liest {progress.fertig} von {progress.gesamt}
              </Label>
              <div style={{ background: C.surface }} className="mt-2 h-px">
                <div
                  style={{
                    background: C.text, height: 1,
                    width: `${Math.round((progress.fertig / Math.max(1, progress.gesamt)) * 100)}%`,
                  }}
                />
              </div>
            </div>
          )}
          {error && <p style={{ color: C.signal }} className="text-sm mt-1">{error}</p>}
        </div>
      )}

      {/* ─────────────────────────── Heute ──────────────────────────── */}
      {view === "heute" && (
        <main className="px-5 pb-32 pt-5">
          <div className="flex flex-wrap gap-2">
            {OCCASIONS.map((o) => (
              <button
                key={o.key}
                onClick={() => setOccasion(o.key)}
                style={{
                  background: occasion === o.key ? C.text : "transparent",
                  color: occasion === o.key ? C.bg : C.dim,
                  borderColor: occasion === o.key ? C.text : C.line,
                  letterSpacing: "0.14em",
                }}
                className="px-3 py-2 text-[10px] uppercase border rounded-full"
              >
                {o.key}
              </button>
            ))}
          </div>

          <div className="mt-6 flex items-baseline gap-3">
            <span style={{ fontFamily: DISPLAY, fontSize: 54, lineHeight: 1 }}>{temp}</span>
            <Label>Grad draußen</Label>
            <button
              onClick={useWeather}
              style={{ color: C.dim, letterSpacing: "0.16em" }}
              className="ml-auto text-[10px] uppercase"
            >
              Wetter holen
            </button>
          </div>
          <input
            type="range" min="-10" max="35" value={temp}
            onChange={(e) => setTemp(Number(e.target.value))}
            className="w-full mt-2" style={{ accentColor: C.text }}
          />

          {anchor && (
            <div className="mt-4 flex items-center justify-between">
              <Label>Anker {items.find((i) => i.id === anchor)?.name}</Label>
              <button
                onClick={() => setAnchor(null)}
                style={{ color: C.signal, letterSpacing: "0.16em" }}
                className="text-[10px] uppercase"
              >
                lösen
              </button>
            </div>
          )}

          <button
            onClick={suggest}
            disabled={!!busy || !!suggesting}
            style={{
              background: suggesting ? "transparent" : C.text,
              color: suggesting ? C.dim : C.bg,
              borderColor: C.line,
              letterSpacing: "0.2em",
              opacity: busy && !suggesting ? 0.5 : 1,
            }}
            className={`mt-6 w-full py-4 text-[11px] uppercase ${suggesting ? "border" : ""}`}
          >
            {suggesting ? suggesting.text : "Outfits zeigen"}
          </button>

          {suggesting && (
            <div className="mt-4" role="status" aria-live="polite">
              {/* Der Balken zeigt echte Phasen, keine geschätzte Zeit.
                  Während einer Phase pulsiert er, damit sichtbar bleibt,
                  dass etwas läuft, auch wenn er kurz stehen bleibt. */}
              <div style={{ background: C.surface }} className="h-px overflow-hidden">
                <div
                  className="rack-puls"
                  style={{
                    background: C.text,
                    height: 1,
                    width: `${Math.round(
                      (suggesting.schritt / Math.max(1, suggesting.gesamt)) * 100
                    )}%`,
                    transition: "width 400ms ease-out",
                  }}
                />
              </div>
              <div className="mt-2 flex items-baseline justify-between gap-3">
                <Label>
                  Schritt {Math.min(suggesting.schritt + 1, suggesting.gesamt)} von{" "}
                  {suggesting.gesamt}
                </Label>
                <Label style={{ color: C.faint }}>
                  {suggesting.phase === "kuratieren"
                    ? "das dauert am längsten"
                    : suggesting.phase === "trends"
                      ? "nur alle 30 Tage nötig"
                      : ""}
                </Label>
              </div>
              {outfits.length === 0 && (
                <div className="mt-6 space-y-6">
                  {[0, 1, 2].map((n) => (
                    <div key={n} className="rack-puls" style={{ opacity: 1 - n * 0.28 }}>
                      <div
                        style={{ background: C.surface }}
                        className="h-4 w-1/3"
                      />
                      <div className="mt-3 grid grid-cols-2 gap-3">
                        {[0, 1, 2, 3].map((m) => (
                          <div
                            key={m}
                            style={{ background: C.surface }}
                            className="aspect-square"
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {suggesting && outfits.length > 0 && !curated && (
            <p style={{ color: C.faint }} className="mt-4 text-xs leading-relaxed">
              Das ist schon die Rangfolge der Engine. Titel, Begründung und Styling-Schritte
              kommen gleich dazu.
            </p>
          )}

          {relaxed && outfits.length > 0 && (
            <p style={{ color: C.dim }} className="mt-4 text-xs leading-relaxed">
              Mit strengen Regeln blieb zu wenig übrig, deshalb wurden die Grenzen für diesen
              Durchlauf gelockert. Mehr Teile im Schrank lösen das.
            </p>
          )}
          {!curated && outfits.length > 0 && !suggesting && (
            <p style={{ color: C.faint }} className="mt-2 text-xs leading-relaxed">
              Das ist die reine Rangfolge der Engine, ohne Kuratierung.
            </p>
          )}

          {outfits.map((o, i) => (
            <section key={i} style={{ borderColor: C.line }} className="mt-10 border-t pt-5">
              <div className="flex items-start justify-between">
                <div>
                  <Label>Vorschlag {i + 1}</Label>
                  <h2 style={{ fontFamily: DISPLAY, fontSize: 26 }} className="mt-1">{o.titel}</h2>
                </div>
                <span style={{ fontFamily: DISPLAY, fontSize: 34, color: C.dim }}>{o.punkte}</span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3">
                {o.teile.map((p) => (
                  <div key={p.id}>
                    <div
                      style={{ background: C.surface }}
                      className="aspect-square flex items-center justify-center overflow-hidden"
                    >
                      {p.imagePath && (
                        <img
                          src={imageUrl(p.id)} alt={p.name} loading="lazy"
                          className="w-full h-full object-contain"
                        />
                      )}
                    </div>
                    <p className="text-xs mt-2 truncate">{p.name}</p>
                    <Label>{p.fit}</Label>
                  </div>
                ))}
              </div>

              {o.begruendung && (
                <p style={{ color: C.dim }} className="text-sm mt-4 leading-relaxed">
                  {o.begruendung}
                </p>
              )}

              {Array.isArray(o.styling) && o.styling.length > 0 && (
                <div style={{ borderColor: C.line }} className="mt-5 border-t pt-4">
                  <Label>So tragen</Label>
                  <ol className="mt-3 space-y-3">
                    {o.styling.map((s, n) => (
                      <li key={n} className="flex gap-3">
                        <span
                          style={{ fontFamily: DISPLAY, color: C.faint, fontSize: 18, lineHeight: 1.1 }}
                        >
                          {n + 1}
                        </span>
                        <span className="text-sm leading-relaxed">{s}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {o.trendhinweis && (
                <p style={{ color: C.dim }} className="text-xs mt-4 leading-relaxed">
                  <Label>Aktuell</Label>
                  <span className="block mt-1">{o.trendhinweis}</span>
                </p>
              )}

              <div className="mt-5 space-y-2">
                {[["Silhouette", "silhouette"], ["Proportion", "proportion"], ["Farbe", "color"],
                  ["Wetter", "warmth"], ["Anlass", "formality"], ["Schuhe", "shoes"]].map(
                  ([l, k]) => (
                    <div key={k} className="flex items-center gap-3">
                      <Label style={{ width: 74 }}>{l}</Label>
                      <div style={{ background: C.surface }} className="flex-1 h-px">
                        <div
                          style={{
                            background:
                              o.detail[k] >= 0.7 ? C.text : o.detail[k] >= 0.45 ? C.dim : C.signal,
                            width: `${Math.round(o.detail[k] * 100)}%`,
                            height: 1,
                          }}
                        />
                      </div>
                    </div>
                  )
                )}
              </div>

              {(() => {
                /* Jeder Knopf quittiert sich selbst. Der Hinweis oben am
                   Bildschirm ist bei Vorschlag zwei und drei außer Sicht,
                   ohne sichtbaren Zustand hier wirkt der Druck folgenlos. */
                const z = outfitState[i] || {};
                return (
                  <div className="mt-5 flex gap-2">
                    <button
                      onClick={() => markWorn(i, o.teile, o.punkte)}
                      disabled={!!z.laeuft || !!z.getragen}
                      style={{
                        background: z.getragen ? "transparent" : C.text,
                        color: z.getragen ? C.dim : C.bg,
                        borderColor: C.line,
                        letterSpacing: "0.16em",
                      }}
                      className={`flex-1 py-3 text-[10px] uppercase ${
                        z.getragen ? "border" : ""
                      } ${z.laeuft === "getragen" ? "rack-puls" : ""}`}
                    >
                      {z.getragen ? "Getragen ✓" : z.laeuft === "getragen"
                        ? "Wird vermerkt" : "Getragen"}
                    </button>
                    <button
                      onClick={() => rate(i, o.teile, "gut")}
                      disabled={!!z.laeuft}
                      style={{
                        background: z.urteil === "gut" ? C.text : "transparent",
                        color: z.urteil === "gut" ? C.bg : C.text,
                        borderColor: z.urteil === "gut" ? C.text : C.line,
                        letterSpacing: "0.16em",
                      }}
                      className={`px-4 py-3 text-[10px] uppercase border ${
                        z.laeuft === "urteil" ? "rack-puls" : ""
                      }`}
                    >
                      {z.urteil === "gut" ? "Gut ✓" : "Gut"}
                    </button>
                    <button
                      onClick={() => rate(i, o.teile, "schlecht")}
                      disabled={!!z.laeuft}
                      style={{
                        background: z.urteil === "schlecht" ? C.signal : "transparent",
                        color: z.urteil === "schlecht" ? C.bg : C.signal,
                        borderColor: z.urteil === "schlecht" ? C.signal : C.line,
                        letterSpacing: "0.16em",
                      }}
                      className={`px-4 py-3 text-[10px] uppercase border ${
                        z.laeuft === "urteil" ? "rack-puls" : ""
                      }`}
                    >
                      {z.urteil === "schlecht" ? "Nein ✓" : "Nein"}
                    </button>
                  </div>
                );
              })()}
            </section>
          ))}
        </main>
      )}

      {/* ────────────────────────── Schrank ─────────────────────────── */}
      {view === "schrank" && (
        <main className="px-5 pb-32 pt-5">
          {loading && <Label>lädt</Label>}
          {!loading && items.length === 0 && (
            <div className="py-14 text-center">
              <p style={{ fontFamily: DISPLAY, fontSize: 24 }}>Der Schrank ist leer</p>
              <p style={{ color: C.dim }} className="text-sm mt-3 leading-relaxed">
                Fotografiere deine Teile einzeln auf hellem, ruhigem Untergrund. Mehrere Fotos auf
                einmal sind kein Problem, du bestätigst danach der Reihe nach.
              </p>
              <button
                onClick={() => setGuide(true)}
                style={{ borderColor: C.line, color: C.text, letterSpacing: "0.16em" }}
                className="mt-5 px-4 py-3 text-[10px] uppercase border"
              >
                Wie fotografieren
              </button>
            </div>
          )}
          <div className="grid grid-cols-3 gap-3">
            {items.map((it) => (
              <button key={it.id} onClick={() => setDetail(it)} className="text-left">
                <div
                  style={{ background: C.surface, opacity: it.paused ? 0.35 : 1 }}
                  className="aspect-square overflow-hidden flex items-center justify-center"
                >
                  {it.imagePath ? (
                    <img
                      src={imageUrl(it.id)} alt={it.name} loading="lazy"
                      className="w-full h-full object-contain"
                    />
                  ) : (
                    <Label>kein Bild</Label>
                  )}
                </div>
                <p className="text-[11px] mt-2 truncate">{it.name}</p>
                <Label>{it.fit}</Label>
              </button>
            ))}
          </div>
        </main>
      )}

      {/* ──────────────────────────── Fehlt ─────────────────────────── */}
      {view === "fehlt" && (
        <main className="px-5 pb-32 pt-5">
          <p style={{ color: C.dim }} className="text-sm leading-relaxed">
            Die Analyse legt testweise einzelne Teile in deinen Schrank und misst, wie viele
            zusätzliche gute Kombinationen dadurch entstehen. Empfohlen wird nur, was rechnerisch
            etwas bringt.
          </p>
          <button
            onClick={runGaps}
            disabled={!!busy || items.length < 6}
            style={{
              background: C.text, color: C.bg, letterSpacing: "0.2em",
              opacity: items.length < 6 ? 0.4 : 1,
            }}
            className="mt-5 w-full py-4 text-[11px] uppercase"
          >
            Analyse starten
          </button>
          {items.length < 6 && (
            <p style={{ color: C.faint }} className="mt-3 text-xs">
              Ab etwa sechs Teilen wird die Rechnung aussagekräftig.
            </p>
          )}

          {gaps?.roh && (
            <p style={{ color: C.faint }} className="mt-4 text-xs leading-relaxed">
              {gaps.roh.guteOutfits} gute Kombinationen aus dem, was da ist.
            </p>
          )}

          {gaps?.empfehlungen?.map((r, i) => (
            <section key={i} style={{ borderColor: C.line }} className="mt-8 border-t pt-5">
              <div className="flex items-start justify-between gap-3">
                <h3 style={{ fontFamily: DISPLAY, fontSize: 22 }}>{r.teil}</h3>
                <span style={{ fontFamily: DISPLAY, fontSize: 26, color: C.dim }}>+{r.gewinn}</span>
              </div>
              <Label>neue Outfits</Label>
              <p className="text-sm mt-3 leading-relaxed">{r.warum}</p>
              {r.preisspanne && (
                <p style={{ color: C.dim }} className="text-xs mt-2">{r.preisspanne}</p>
              )}
              {Array.isArray(r.beispiele) && r.beispiele.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {r.beispiele.map((b, n) => (
                    <li key={n} className="text-sm">
                      <span style={{ color: C.dim }}>{b.marke}</span> {b.modell}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}

          {gaps?.waisen?.length > 0 && (
            <section style={{ borderColor: C.line }} className="mt-10 border-t pt-5">
              <Label>Liegt ungenutzt</Label>
              {gaps.waisen.map((w, i) => (
                <div key={i} className="mt-4">
                  <p className="text-sm font-medium">{w.teil}</p>
                  <p style={{ color: C.dim }} className="text-sm leading-relaxed">{w.diagnose}</p>
                </div>
              ))}
            </section>
          )}

          {gaps?.hinweis && (
            <p style={{ color: C.faint }} className="mt-8 text-xs leading-relaxed">{gaps.hinweis}</p>
          )}
        </main>
      )}

      {/* ─────────────────────── Kurzmeldung ────────────────────────── */}
      {/* Bewusst am unteren Rand und fest im Bild: Quittungen entstehen
          beim Tippen weit unten auf der Seite, oben würde sie niemand
          sehen. Verschwindet nach ein paar Sekunden von selbst. */}
      {notice && (
        <div
          className="fixed left-0 right-0 z-30 px-5"
          style={{ bottom: view === "fehlt" ? 20 : 96 }}
          role="status"
          aria-live="polite"
        >
          <div
            style={{ background: C.raised, borderColor: C.line, color: C.text }}
            className="border rounded-sm px-4 py-3 text-sm shadow-lg"
          >
            {notice}
          </div>
        </div>
      )}

      {/* ───────────────────────── Erfassen-Leiste ──────────────────── */}
      {view !== "fehlt" && (
        <div
          className="fixed bottom-0 left-0 right-0 px-5 pb-5 pt-3"
          style={{ background: `linear-gradient(to top, ${C.bg} 62%, transparent)` }}
        >
          <input
            ref={fileRef} type="file" accept="image/*" multiple
            onChange={onFiles} className="hidden"
          />
          <div className="flex gap-2">
            <button
              onClick={() => fileRef.current?.click()}
              disabled={!!busy || !!progress}
              style={{ borderColor: C.text, color: C.text, letterSpacing: "0.2em" }}
              className="flex-1 py-4 text-[11px] uppercase border"
            >
              Teile erfassen
            </button>
            <button
              onClick={() => setGuide(true)}
              style={{ borderColor: C.line, color: C.dim }}
              className="px-4 py-4 text-[11px] uppercase border"
            >
              ?
            </button>
          </div>
        </div>
      )}

      {/* ─────────────────────────── Prüfkarte ──────────────────────── */}
      {entry && (
        <div style={{ background: C.bg }} className="fixed inset-0 z-40 overflow-y-auto">
          <div className="px-5 pt-6 pb-24">
            <div className="flex items-center justify-between">
              <Label>
                Teil {qIndex + 1} von {queue.length}
              </Label>
              <button
                onClick={() => { setQueue([]); setQIndex(0); }}
                style={{ color: C.dim, letterSpacing: "0.16em" }}
                className="text-[10px] uppercase"
              >
                abbrechen
              </button>
            </div>

            <div
              style={{ background: C.surface }}
              className="mt-4 aspect-square flex items-center justify-center overflow-hidden"
            >
              {entry.bild && (
                <img
                  src={`data:${entry.mediaType};base64,${entry.bild}`}
                  alt="" className="w-full h-full object-contain"
                />
              )}
            </div>
            {!entry.cutout && (
              <p style={{ color: C.faint }} className="mt-2 text-xs">
                Das Teil konnte nicht freigestellt werden. Das Originalfoto bleibt erhalten.
              </p>
            )}
            {entry.status === "fehler" && (
              <p style={{ color: C.signal }} className="mt-2 text-xs">
                {entry.meldung || "Das Foto wurde nicht gelesen."} Trag die Felder von Hand ein.
              </p>
            )}
            {entry.status === "ohne_ki" && (
              <p style={{ color: C.faint }} className="mt-2 text-xs">
                Ohne API-Schlüssel: bitte alle Felder selbst setzen.
              </p>
            )}

            <input
              value={attrs.name || ""}
              onChange={(e) => patchQueue({ name: e.target.value })}
              placeholder="Bezeichnung"
              style={{
                background: "transparent", color: C.text, borderColor: C.line,
                fontFamily: DISPLAY, fontSize: 26,
              }}
              className="w-full mt-5 border-b pb-2"
            />

            <div className="mt-5 grid grid-cols-2 gap-3">
              <Field
                label="Kategorie" value={attrs.category} options={CATEGORIES}
                flagged={flagged("category")} onChange={(v) => patchQueue({ category: v })}
              />
              {attrs.category === "Accessoire" ? (
                <Field
                  label="Art" value={attrs.subcategory} options={ACCESSORY_TYPES}
                  flagged={flagged("subcategory")} onChange={(v) => patchQueue({ subcategory: v })}
                />
              ) : (
                <Field
                  label="Schnitt" value={attrs.fit} options={FITS}
                  flagged={flagged("fit")} onChange={(v) => patchQueue({ fit: v })}
                />
              )}
              {attrs.category !== "Accessoire" && attrs.category !== "Schuhe" && (
                <Field
                  label="Länge" value={attrs.length}
                  options={attrs.category === "Unterteil" ? BOTTOM_LEN : TOP_LEN}
                  flagged={flagged("length")} onChange={(v) => patchQueue({ length: v })}
                />
              )}
              {attrs.category === "Unterteil" && (
                <Field
                  label="Bundhöhe" value={attrs.rise} options={RISES}
                  flagged={flagged("rise")} onChange={(v) => patchQueue({ rise: v })}
                />
              )}
              {attrs.category === "Schuhe" && (
                <Field
                  label="Gewicht" value={attrs.shoeWeight} options={SHOE_WEIGHT}
                  flagged={flagged("shoeWeight")} onChange={(v) => patchQueue({ shoeWeight: v })}
                />
              )}
              <Field
                label="Dicke" value={attrs.thickness} options={THICKNESS}
                flagged={flagged("thickness")} onChange={(v) => patchQueue({ thickness: v })}
              />
              <Field
                label="Muster" value={attrs.pattern} options={PATTERNS}
                flagged={flagged("pattern")} onChange={(v) => patchQueue({ pattern: v })}
              />
            </div>

            <div className="mt-4 flex items-center gap-3">
              <span
                style={{ background: attrs.colorHex || "#888", borderColor: C.line }}
                className="w-8 h-8 rounded-full border"
              />
              <div className="flex-1">
                <Label>Farbe</Label>
                <input
                  value={attrs.colorName || ""}
                  onChange={(e) => patchQueue({ colorName: e.target.value })}
                  style={{ background: "transparent", color: C.text, borderColor: C.line }}
                  className="w-full border-b text-sm pb-1"
                />
              </div>
              <input
                type="color" value={attrs.colorHex || "#888888"}
                onChange={(e) => patchQueue({ colorHex: e.target.value })}
                className="w-10 h-10 bg-transparent"
              />
            </div>

            <p style={{ color: C.faint }} className="mt-4 text-xs leading-relaxed">
              Wärme und Formalität werden aus Art, Material und Dicke berechnet und lassen sich
              später im Detail überschreiben.
            </p>

            <div className="mt-6 flex gap-2">
              <button
                onClick={saveCurrent} disabled={!!busy}
                style={{ background: C.text, color: C.bg, letterSpacing: "0.18em" }}
                className="flex-1 py-4 text-[11px] uppercase"
              >
                Speichern
              </button>
              <button
                onClick={nextCard}
                style={{ borderColor: C.line, color: C.dim, letterSpacing: "0.18em" }}
                className="px-5 py-4 text-[11px] uppercase border"
              >
                Weg
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ───────────────────────── Fotoanleitung ────────────────────── */}
      {guide && (
        <div className="fixed inset-0 z-40 flex items-end" style={{ background: "#000000cc" }}>
          <div
            style={{ background: C.surface, borderColor: C.line }}
            className="w-full max-h-[88vh] overflow-y-auto border-t p-5"
          >
            <div className="flex justify-between items-start">
              <h2 style={{ fontFamily: DISPLAY, fontSize: 26 }}>Fotografieren</h2>
              <button
                onClick={() => setGuide(false)}
                style={{ color: C.dim, letterSpacing: "0.16em" }}
                className="text-[10px] uppercase"
              >
                schließen
              </button>
            </div>
            {PHOTO_GUIDE.map(([t, d]) => (
              <div key={t} className="mt-5">
                <Label>{t}</Label>
                <p className="text-sm mt-1 leading-relaxed">{d}</p>
              </div>
            ))}
            <p style={{ color: C.faint }} className="mt-6 mb-2 text-xs leading-relaxed">
              Freigestellt wird auf dem Server. Ein ruhiger Untergrund hilft trotzdem, weil das
              Teil dann klarer vom Hintergrund zu trennen ist.
            </p>
          </div>
        </div>
      )}

      {/* ──────────────────────────── Detail ────────────────────────── */}
      {detail && (
        <div className="fixed inset-0 z-40 flex items-end" style={{ background: "#000000cc" }}>
          <div
            style={{ background: C.surface, borderColor: C.line }}
            className="w-full max-h-[90vh] overflow-y-auto border-t p-5"
          >
            <div className="flex justify-between items-start">
              <div>
                <Label>{detail.subcategory || detail.category}</Label>
                <h2 style={{ fontFamily: DISPLAY, fontSize: 26 }}>{detail.name}</h2>
              </div>
              <button
                onClick={() => setDetail(null)}
                style={{ color: C.dim, letterSpacing: "0.16em" }}
                className="text-[10px] uppercase"
              >
                schließen
              </button>
            </div>

            {detail.imagePath && (
              <div
                style={{ background: C.bg }}
                className="mt-4 aspect-square flex items-center justify-center overflow-hidden"
              >
                <img
                  src={imageUrl(detail.id)} alt={detail.name}
                  className="w-full h-full object-contain"
                />
              </div>
            )}

            <div className="mt-5 grid grid-cols-2 gap-3">
              <Field
                label="Kategorie" value={detail.category} options={CATEGORIES}
                onChange={(v) => updateItem(detail.id, { category: v })}
              />
              {detail.category === "Accessoire" ? (
                <Field
                  label="Art" value={detail.subcategory} options={ACCESSORY_TYPES}
                  onChange={(v) => updateItem(detail.id, { subcategory: v })}
                />
              ) : (
                <Field
                  label="Schnitt" value={detail.fit} options={FITS}
                  onChange={(v) => updateItem(detail.id, { fit: v })}
                />
              )}
              {detail.category !== "Accessoire" && detail.category !== "Schuhe" && (
                <Field
                  label="Länge" value={detail.length}
                  options={detail.category === "Unterteil" ? BOTTOM_LEN : TOP_LEN}
                  onChange={(v) => updateItem(detail.id, { length: v })}
                />
              )}
              {detail.category === "Unterteil" && (
                <Field
                  label="Bundhöhe" value={detail.rise} options={RISES}
                  onChange={(v) => updateItem(detail.id, { rise: v })}
                />
              )}
              {detail.category === "Schuhe" && (
                <Field
                  label="Gewicht" value={detail.shoeWeight} options={SHOE_WEIGHT}
                  onChange={(v) => updateItem(detail.id, { shoeWeight: v })}
                />
              )}
            </div>

            <div className="mt-5">
              <Label>
                Wärme {detail.warmth} von 5{detail.warmthManual ? " (von Hand)" : ""}
              </Label>
              <input
                type="range" min="0.5" max="5" step="0.5" value={detail.warmth ?? 3}
                onChange={(e) => updateItem(detail.id, { warmth: Number(e.target.value) })}
                className="w-full" style={{ accentColor: C.text }}
              />
            </div>
            <div className="mt-3">
              <Label>
                Formalität {detail.formality} von 5{detail.formalityManual ? " (von Hand)" : ""}
              </Label>
              <input
                type="range" min="1" max="5" step="0.5" value={detail.formality ?? 3}
                onChange={(e) => updateItem(detail.id, { formality: Number(e.target.value) })}
                className="w-full" style={{ accentColor: C.text }}
              />
            </div>
            {(detail.warmthManual || detail.formalityManual) && (
              <button
                onClick={() =>
                  updateItem(detail.id, { warmthManual: false, formalityManual: false })
                }
                style={{ color: C.dim, letterSpacing: "0.16em" }}
                className="mt-2 text-[10px] uppercase"
              >
                wieder berechnen lassen
              </button>
            )}

            <div className="mt-5 flex items-center justify-between">
              <Label>{detail.wearCount || 0} mal getragen</Label>
              <button
                onClick={() => updateItem(detail.id, { paused: !detail.paused })}
                style={{ color: detail.paused ? C.signal : C.dim, letterSpacing: "0.16em" }}
                className="text-[10px] uppercase"
              >
                {detail.paused ? "in der Wäsche" : "verfügbar"}
              </button>
            </div>

            <div className="mt-6 flex gap-2 pb-3">
              <button
                onClick={() => { setAnchor(detail.id); setDetail(null); setView("heute"); }}
                style={{ background: C.text, color: C.bg, letterSpacing: "0.16em" }}
                className="flex-1 py-4 text-[10px] uppercase"
              >
                Outfit hierzu
              </button>
              <button
                onClick={() => removeItem(detail.id)}
                style={{ borderColor: C.line, color: C.signal, letterSpacing: "0.16em" }}
                className="px-5 py-4 text-[10px] uppercase border"
              >
                Löschen
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ──────────────────────────── Profil ────────────────────────── */}
      {settings && (
        <div className="fixed inset-0 z-40 flex items-end" style={{ background: "#000000cc" }}>
          <div
            style={{ background: C.surface, borderColor: C.line }}
            className="w-full max-h-[92vh] overflow-y-auto border-t p-5"
          >
            <div className="flex justify-between items-start">
              <h2 style={{ fontFamily: DISPLAY, fontSize: 26 }}>Profil</h2>
              <button
                onClick={() => { setSettings(false); setBodyDraft(null); setAiStatus(null); }}
                style={{ color: C.dim, letterSpacing: "0.16em" }}
                className="text-[10px] uppercase"
              >
                schließen
              </button>
            </div>

            <div className="mt-5 flex flex-col gap-2">
              {SILHOUETTES.map((s) => (
                <button
                  key={s.key}
                  onClick={() => saveProfile({ silhouette: s.key })}
                  style={{
                    background: profile?.silhouette === s.key ? C.text : "transparent",
                    color: profile?.silhouette === s.key ? C.bg : C.text,
                    borderColor: profile?.silhouette === s.key ? C.text : C.line,
                  }}
                  className="border rounded-sm p-3 text-left"
                >
                  <span className="block text-sm">{s.label}</span>
                  <span style={{ opacity: 0.7 }} className="text-xs">{s.hint}</span>
                </button>
              ))}
            </div>

            <div className="mt-6">
              <Label>Körpergröße {profile?.height || 180} cm</Label>
              <input
                type="range" min="150" max="205" value={profile?.height || 180}
                onChange={(e) => saveProfile({ height: Number(e.target.value) })}
                className="w-full mt-1" style={{ accentColor: C.text }}
              />
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <Field
                label="Statur" value={profile?.build} options={BUILDS}
                onChange={(v) => saveProfile({ build: v })}
              />
              <Field
                label="Verhältnis" value={profile?.torso} options={TORSOS}
                onChange={(v) => saveProfile({ torso: v })}
              />
            </div>

            <div className="mt-4 flex items-center justify-between">
              <Label>Brille</Label>
              <button
                onClick={() => saveProfile({ glasses: !profile?.glasses })}
                style={{
                  borderColor: C.line, color: profile?.glasses ? C.text : C.faint,
                  letterSpacing: "0.16em",
                }}
                className="px-4 py-2 text-[10px] uppercase border"
              >
                {profile?.glasses ? "ja" : "nein"}
              </button>
            </div>

            <div style={{ borderColor: C.line }} className="mt-6 border-t pt-5">
              <Label>Statur automatisch bestimmen</Label>
              <p style={{ color: C.dim }} className="text-xs mt-2 leading-relaxed">
                Ganzkörperfoto, frontal, aufrecht vor einer möglichst leeren Wand, eng anliegende
                Kleidung, Arme leicht abgespreizt, Handy auf Bauchnabelhöhe und nicht von schräg
                oben. Das Foto wird nur zur Analyse übertragen und danach sofort verworfen. Es wird
                weder gespeichert noch protokolliert.
              </p>
              <input
                ref={bodyRef} type="file" accept="image/*"
                onChange={onBodyPhoto} className="hidden"
              />
              <button
                onClick={() => bodyRef.current?.click()} disabled={!!busy}
                style={{ borderColor: C.line, color: C.text, letterSpacing: "0.16em" }}
                className="mt-3 w-full py-3 text-[10px] uppercase border"
              >
                Foto auswählen
              </button>

              {bodyDraft && (
                <div
                  style={{ background: C.raised, borderColor: C.line }}
                  className="mt-4 border rounded-sm p-4"
                >
                  <Label>Erkannt, bitte prüfen</Label>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <Field
                      label="Statur" value={bodyDraft.build} options={BUILDS}
                      onChange={(v) => setBodyDraft({ ...bodyDraft, build: v })}
                    />
                    <Field
                      label="Verhältnis" value={bodyDraft.torso} options={TORSOS}
                      onChange={(v) => setBodyDraft({ ...bodyDraft, torso: v })}
                    />
                  </div>
                  {bodyDraft.hinweis && (
                    <p style={{ color: C.dim }} className="text-xs mt-3 leading-relaxed">
                      {bodyDraft.hinweis}
                    </p>
                  )}
                  {bodyDraft.confidence < 0.6 && (
                    <p style={{ color: C.signal }} className="text-xs mt-2">
                      Die Einschätzung ist unsicher. Prüfe sie besonders genau.
                    </p>
                  )}
                  <button
                    onClick={async () => {
                      await saveProfile({ build: bodyDraft.build, torso: bodyDraft.torso });
                      setBodyDraft(null);
                    }}
                    style={{ background: C.text, color: C.bg, letterSpacing: "0.16em" }}
                    className="mt-4 w-full py-3 text-[10px] uppercase"
                  >
                    Übernehmen
                  </button>
                </div>
              )}
            </div>

            <div className="mt-6">
              <Label>Eigene Vorgaben</Label>
              <textarea
                value={profile?.notes || ""}
                onChange={(e) => setProfile({ ...(profile || {}), notes: e.target.value })}
                onBlur={(e) => saveProfile({ notes: e.target.value })}
                placeholder="Hosen immer mit Stack über dem Schuh. Kein Braun zu Schwarz."
                style={{ background: C.raised, color: C.text, borderColor: C.line }}
                className="w-full mt-2 border rounded-sm p-3 text-sm h-24"
              />
            </div>

            <div style={{ borderColor: C.line }} className="mt-6 border-t pt-5">
              <Label>Server</Label>
              <p style={{ color: C.faint }} className="text-xs mt-2 leading-relaxed">
                {health?.teile ?? 0} Teile gespeichert.{" "}
                {health?.ki
                  ? `KI aktiv: ${health.modelle?.lesen} liest, ${health.modelle?.kuratieren} kuratiert.`
                  : "Kein API-Schlüssel, die Regel-Engine läuft trotzdem."}
              </p>
              <button
                onClick={async () => {
                  setBusy("Prüfe den Schlüssel");
                  try {
                    setAiStatus(await api.aiTest());
                  } catch (err) {
                    fail(err, "Der Test ist fehlgeschlagen.");
                  }
                  setBusy("");
                }}
                style={{ borderColor: C.line, color: C.dim, letterSpacing: "0.16em" }}
                className="mt-3 px-4 py-2 text-[10px] uppercase border"
              >
                Schlüssel prüfen
              </button>
              {aiStatus && (
                <p
                  style={{ color: aiStatus.ok ? C.dim : C.signal }}
                  className="text-xs mt-3 leading-relaxed"
                >
                  {aiStatus.ok
                    ? `Erreichbar. Schlüssel ${aiStatus.schluessel}, Modell ${aiStatus.modell}.`
                    : aiStatus.meldung}
                </p>
              )}
            </div>

            <div className="mt-6 flex gap-2 pb-3">
              <button
                onClick={exportAll}
                style={{ borderColor: C.line, color: C.text, letterSpacing: "0.16em" }}
                className="flex-1 py-4 text-[10px] uppercase border"
              >
                Export
              </button>
              <input
                ref={importRef} type="file" accept="application/json"
                onChange={importAll} className="hidden"
              />
              <button
                onClick={() => importRef.current?.click()}
                style={{ borderColor: C.line, color: C.text, letterSpacing: "0.16em" }}
                className="flex-1 py-4 text-[10px] uppercase border"
              >
                Import
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
