import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  api, etikettUrl, followIngest, followOutfits, imageUrl, person, setPerson,
  setToken, token,
} from "./api.js";
import {
  ACCESSORY_TYPES, BOTTOM_LEN, BUILDS, C, CARE_LABELS, CATEGORIES, DISPLAY,
  FITS, MATERIALS, PRINT_POSITIONS,
  OCCASIONS, PATTERN_SCALE, PATTERNS, PHOTO_GUIDE, RISES, SANS, SHOE_WEIGHT,
  SILHOUETTES, SLEEVES, TEXTURES, THICKNESS, TOP_LEN, TORSOS,
} from "./constants.js";

/* ═══════════════════════════════════════════════════════════════════
   RACK
   Die Oberflaeche des Prototypen, angebunden an den eigenen Server.
   Rechnen, Freistellen und Modellzugriff liegen jetzt im Backend; hier
   bleiben Darstellung und Bedienung.
   ═══════════════════════════════════════════════════════════════════ */

// Verbleibende Wäschetage eines Teils. Die Frist steht als Zeitpunkt im
// Datensatz, ausgerechnet wird sie hier — so stimmt die Anzeige auch,
// wenn die App lange offen liegt, ohne dass etwas nachgeladen wird.
function waescheTage(item) {
  if (!item?.laundryUntil) return 0;
  const bis = new Date(item.laundryUntil).getTime();
  if (Number.isNaN(bis)) return 0;
  return Math.max(0, (bis - Date.now()) / 86400000);
}

function waescheText(tage) {
  if (tage <= 0) return "";
  if (tage < 1) return `noch ${Math.max(1, Math.round(tage * 24))} h`;
  return `noch ${Math.ceil(tage)} ${Math.ceil(tage) === 1 ? "Tag" : "Tage"}`;
}

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
  const slowPatch = useRef(null);
  // Auswahllisten kommen vom Server (/api/vocab). Die Konstanten in
  // constants.js bleiben als Rückfallebene, damit die Oberfläche auch
  // bedienbar ist, wenn der Aufruf scheitert — sie sind dann aber
  // womöglich veraltet, deshalb ist der Server die Wahrheit.
  const [vocab, setVocab] = useState(null);
  const [stats, setStats] = useState(null);
  const [suche, setSuche] = useState("");
  const [filterKat, setFilterKat] = useState("");
  const [zeigeArchiv, setZeigeArchiv] = useState(false);
  const [plaene, setPlaene] = useState([]);
  const [gemerkte, setGemerkte] = useState([]);
  const [packListe, setPackListe] = useState(null);
  const [packTage, setPackTage] = useState(5);
  const [packTemp, setPackTemp] = useState(16);
  const [ausmisten, setAusmisten] = useState(null);
  const [trends, setTrends] = useState(null);
  const [personen, setPersonen] = useState([]);
  const aktivePerson = person();
  const [diagnose, setDiagnose] = useState(null);
  const [wiederholungen, setWiederholungen] = useState({});
  // Regen und Wind aus dem letzten Wetterabruf. Gehen in die
  // Materialbewertung ein — ohne sie zählt nur die Temperatur, und dann
  // steht man mit Wildleder im Regen.
  const [wetter, setWetter] = useState({ regen: 0, wind: 0 });
  // Was zuletzt geholt wurde, für die Anzeige unter der Temperatur.
  const [wetterlage, setWetterlage] = useState(null);
  const [waschgaenge, setWaschgaenge] = useState(null);
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

  // Für jeden Vorschlag prüfen, ob dieselbe Zusammenstellung kürzlich
  // schon einmal dran war — vor allem beim selben Anlass. Läuft still im
  // Hintergrund; scheitert der Aufruf, fehlt eben der Hinweis.
  useEffect(() => {
    if (!outfits?.length) return;
    let aktuell = true;
    Promise.all(
      outfits.map((o) =>
        api.wiederholung({ teile: o.teile.map((p) => p.id), anlass: occasion })
          .then((r) => r.warnung)
          .catch(() => null),
      ),
    ).then((res) => {
      if (!aktuell) return;
      const map = {};
      res.forEach((w, i) => { if (w) map[i] = w; });
      setWiederholungen(map);
    });
    return () => { aktuell = false; };
  }, [outfits, occasion]);

  // Pläne und gemerkte Outfits beim Öffnen der Ansicht laden.
  useEffect(() => {
    if (view !== "planen") return;
    const heute = new Date().toISOString().slice(0, 10);
    const in14 = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10);
    Promise.all([api.plan(heute, in14), api.gespeicherteOutfits()])
      .then(([p, g]) => { setPlaene(p); setGemerkte(g); })
      .catch((err) => fail(err, "Die Planung war nicht abrufbar."));
    api.waschgaenge().then(setWaschgaenge).catch(() => {});
  }, [view, fail]);

  // Die Bilanz wird bei jedem Aufruf frisch geholt: sie hängt am
  // Trageprotokoll, das sich zwischen zwei Blicken geändert haben kann.
  useEffect(() => {
    if (view !== "bilanz") return;
    api.stats().then(setStats).catch((err) => fail(err, "Die Bilanz war nicht abrufbar."));
    api.aussortieren().then(setAusmisten).catch(() => {});
    // Nur lesend: der Endpunkt liefert den Zwischenspeicher und holt
    // nichts nach. Neu geholt wird beim Kuratieren, wenn er zu alt ist.
    api.trends().then(setTrends).catch(() => {});
  }, [view, items, fail]);

  // Wetter beim Start holen, aber nur wenn der Standort schon freigegeben
  // ist. Sonst käme die Erlaubnisabfrage ungefragt beim Öffnen — die
  // gehört an den Knopf, den man selbst gedrückt hat.
  //
  // Der Zweig ohne Permissions-API (ältere Safari-Fassungen) fragt gar
  // nicht: lieber einmal von Hand tippen als eine Abfrage aus dem Nichts.
  useEffect(() => {
    if (!navigator.permissions?.query || !navigator.geolocation) return;
    let aktuell = true;
    navigator.permissions
      .query({ name: "geolocation" })
      .then((p) => {
        if (aktuell && p.state === "granted") holeWetter({ still: true });
      })
      .catch(() => {});
    return () => { aktuell = false; };
    // Nur einmal beim Start.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Das Vokabular ändert sich nur mit einer neuen Fassung des Servers,
  // deshalb einmal beim Start und bewusst ohne Fehlerbehandlung: schlägt
  // es fehl, greifen die eingebauten Listen und die App bleibt bedienbar.
  useEffect(() => {
    api.vocab().then(setVocab).catch(() => {});
    api.personen().then(setPersonen).catch(() => {});
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
      job = await api.startOutfits({
        anlass: occasion, temp, anker: anchor, ...wetter,
      });
    } catch (err) {
      setSuggesting(null);
      // Der Vorgangsweg fehlt vielleicht, etwa nach einem Teilupdate.
      // Dann eben in einem Rutsch, nur ohne Fortschritt.
      try {
        setBusy("Kuratiere");
        zeigeErgebnis(await api.outfits({
          anlass: occasion, temp, anker: anchor, ...wetter,
        }));
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

  // still: der Aufruf beim Start soll weder einen Fortschritt anzeigen
  // noch mit einer Fehlermeldung dazwischenfahren, wenn gerade kein
  // Standort zu bekommen ist.
  async function holeWetter({ still = false } = {}) {
    if (!navigator.geolocation) {
      if (!still) {
        setError("Dieses Gerät gibt den Standort nicht heraus. "
          + "Stell die Temperatur von Hand ein.");
      }
      return;
    }
    if (!still) setBusy("Hole das Wetter");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          // Zwei Nachkommastellen sind rund ein Kilometer genau — fürs
          // Wetter reicht das, und der Server-Zwischenspeicher trifft
          // dadurch häufiger.
          const w = await api.weather(
            pos.coords.latitude.toFixed(2),
            pos.coords.longitude.toFixed(2)
          );
          if (typeof w.temp === "number") setTemp(Math.round(w.temp));
          setWetter({ regen: w.regen || 0, wind: w.wind || 0 });
          setWetterlage({ ...w, geholt: Date.now() });
        } catch (err) {
          if (!still) fail(err, "Das Wetter war nicht abrufbar.");
        }
        if (!still) setBusy("");
      },
      () => {
        if (!still) {
          setBusy("");
          setError("Der Standort wurde nicht freigegeben. "
            + "Stell die Temperatur von Hand ein.");
        }
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
      const res = await api.worn({
        teile: parts.map((p) => p.id), anlass: occasion, temp, punkte,
      });
      setItems(await api.items());
      merke(i, { getragen: true, laeuft: null, logId: res?.id });
      // Die Wäsche passiert automatisch — dann soll sie auch dastehen,
      // sonst wundert man sich, warum ein Teil plötzlich fehlt.
      const w = res?.waesche || [];
      if (w.length) {
        const namen = w.map((x) => x.name).filter(Boolean);
        const liste = namen.length > 2
          ? `${namen.slice(0, 2).join(", ")} und ${namen.length - 2} weitere`
          : namen.join(" und ");
        const tage = res?.waescheTage || 3;
        setNotice(
          `Vermerkt. ${liste} ${namen.length === 1 ? "geht" : "gehen"} für `
          + `${tage % 1 ? tage : Math.round(tage)} Tage in die Wäsche.`,
        );
      } else {
        setNotice("Als getragen vermerkt. Diese Teile kommen ein paar Tage seltener dran.");
      }
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

  // Farbwähler und Textfeld feuern bei jeder Mausbewegung bzw. jedem
  // Tastendruck. Ohne Verzögerung wären das Dutzende PATCH-Anfragen für
  // eine einzige Farbänderung — die Auswahlfelder daneben brauchen das
  // nicht und schicken weiterhin sofort.
  function updateItemLater(id, patch) {
    setDetail((d) => (d && d.id === id ? { ...d, ...patch } : d));
    clearTimeout(slowPatch.current);
    slowPatch.current = setTimeout(() => updateItem(id, patch), 400);
  }

  // Was der Schrank gerade zeigt. Eingemottetes ist standardmäßig aus dem
  // Weg — es soll den Blick auf das nicht verstellen, was man tragen kann.
  const sichtbareTeile = items.filter((it) => {
    if (Boolean(it.archived) !== zeigeArchiv) return false;
    if (filterKat && it.category !== filterKat) return false;
    const q = suche.trim().toLowerCase();
    if (!q) return true;
    return [it.name, it.brand, it.material, it.materialSecondary, it.colorName,
            it.category, it.subcategory, it.size, it.tags, it.care]
      .filter(Boolean)
      .some((feld) => String(feld).toLowerCase().includes(q));
  });

  // Liste aus dem Server-Vokabular, sonst die eingebaute.
  function V(key, fallback) {
    const list = vocab?.[key];
    return Array.isArray(list) && list.length ? list : fallback;
  }

  // Die Diagnose wird beim Öffnen eines Teils geholt. Sie beantwortet
  // die Frage, die keine der kommerziellen Apps beantwortet: warum taucht
  // dieses Stück nie in einem Vorschlag auf?
  useEffect(() => {
    if (!detail?.id) { setDiagnose(null); return; }
    let aktuell = true;
    setDiagnose(null);
    api.diagnose(detail.id, occasion, temp, wetter)
      .then((d) => { if (aktuell) setDiagnose(d); })
      .catch(() => {});
    return () => { aktuell = false; };
  }, [detail?.id, occasion, temp]);

  // Nach dem Wechsel wird neu geladen statt jeden Zustand einzeln
  // umzuhängen: Teile, Profil, Planung, Protokoll und Vorschläge hängen
  // alle an der Person, und ein halb umgeschalteter Zustand wäre die
  // schlechtere Variante.
  function personWechseln(id) {
    if (id === aktivePerson) return;
    setPerson(id);
    window.location.reload();
  }

  async function personAnlegen() {
    const name = window.prompt("Name der Person?");
    if (!name?.trim()) return;
    try {
      const p = await api.personAnlegen(name.trim());
      setPersonen(await api.personen());
      personWechseln(p.id);
    } catch (err) {
      fail(err, "Die Person ließ sich nicht anlegen.");
    }
  }

  async function personLoeschen(id) {
    if (!window.confirm("Diese Person und alle ihre Teile endgültig löschen?")) return;
    try {
      await api.personLoeschen(id);
      setPerson(1);
      window.location.reload();
    } catch (err) {
      fail(err, "Die Person ließ sich nicht löschen.");
    }
  }

  async function teilKlonen(id) {
    try {
      const kopie = await api.klonen(id);
      setItems(await api.items());
      setDetail(kopie);
      setNotice("Kopie angelegt. Foto und Farbe fehlen noch.");
    } catch (err) {
      fail(err, "Die Kopie ließ sich nicht anlegen.");
    }
  }

  async function aufraeumen() {
    try {
      const stand = await api.verwaisteBilder();
      if (!stand.anzahl) {
        setNotice("Keine verwaisten Bilder gefunden.");
        return;
      }
      const mb = (stand.bytes / 1048576).toFixed(1);
      if (!window.confirm(
        `${stand.anzahl} Bilddateien gehören zu keinem Teil mehr (${mb} MB). Löschen?`
      )) return;
      const res = await api.verwaisteBilderLoeschen();
      setNotice(`${res.geloescht} Dateien entfernt.`
        + (res.fehlgeschlagen ? ` ${res.fehlgeschlagen} ließen sich nicht löschen.` : ""));
    } catch (err) {
      fail(err, "Das Aufräumen ist gescheitert.");
    }
  }

  async function etikettHochladen(id, file) {
    if (!file) return;
    setBusy("Speichere das Etikett");
    try {
      const res = await api.etikettHochladen(id, file);
      setItems((list) => list.map((i) => (i.id === id ? { ...i, labelPath: res.labelPath } : i)));
      setDetail((d) => (d && d.id === id ? { ...d, labelPath: res.labelPath } : d));
      setNotice("Etikettfoto gespeichert.");
    } catch (err) {
      fail(err, "Das Etikett ließ sich nicht speichern.");
    }
    setBusy("");
  }

  async function wiederVerfuegbar(id) {
    try {
      const updated = await api.wiederVerfuegbar(id);
      setItems((list) => list.map((i) => (i.id === id ? updated : i)));
      setDetail((d) => (d && d.id === id ? updated : d));
    } catch (err) {
      fail(err, "Das Teil konnte nicht freigegeben werden.");
    }
  }

  // Die nächsten sieben Tage. Mehr braucht niemand im Voraus, und der
  // Blick bleibt auf eine Bildschirmhöhe beschränkt.
  function naechsteTage() {
    const heute = new Date();
    return Array.from({ length: 7 }, (_, n) => {
      const d = new Date(heute.getTime() + n * 86400000);
      return {
        iso: d.toISOString().slice(0, 10),
        kurz: n === 0
          ? "heute"
          : d.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" }),
        heute: n === 0,
      };
    });
  }

  async function ladePlanung() {
    const heute = new Date().toISOString().slice(0, 10);
    const in14 = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10);
    const [p, g] = await Promise.all([api.plan(heute, in14), api.gespeicherteOutfits()]);
    setPlaene(p);
    setGemerkte(g);
  }

  async function planLoeschen(datum) {
    try {
      await api.planLoeschen(datum);
      await ladePlanung();
    } catch (err) {
      fail(err, "Der Eintrag ließ sich nicht entfernen.");
    }
  }

  async function gemerktesLoeschen(id) {
    try {
      await api.outfitLoeschen(id);
      await ladePlanung();
    } catch (err) {
      fail(err, "Das Outfit ließ sich nicht entfernen.");
    }
  }

  async function packlisteBauen() {
    setBusy("Rechne die Packliste");
    try {
      setPackListe(await api.packliste({
        tage: packTage, temp: packTemp, anlass: occasion, ...wetter,
      }));
    } catch (err) {
      fail(err, "Die Packliste ließ sich nicht berechnen.");
    }
    setBusy("");
  }

  async function ootdHochladen(i, logId, file) {
    if (!file) return;
    setBusy("Speichere das Foto");
    try {
      await api.ootdHochladen(logId, file);
      merke(i, { foto: true });
      setNotice("Foto zum Outfit gespeichert.");
    } catch (err) {
      fail(err, "Das Foto ließ sich nicht speichern.");
    }
    setBusy("");
  }

  async function outfitMerken(parts) {
    const name = window.prompt("Wie soll das Outfit heißen?");
    if (!name?.trim()) return;
    try {
      await api.outfitSpeichern({
        name: name.trim(), teile: parts.map((p) => p.id), anlass: occasion,
      });
      setNotice(`„${name.trim()}" gemerkt.`);
    } catch (err) {
      fail(err, "Das Outfit konnte nicht gemerkt werden.");
    }
  }

  async function outfitEinplanen(parts) {
    // Vorgabe ist morgen — der häufigste Fall ist "was ziehe ich morgen an".
    const morgen = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
    const datum = window.prompt("Für welchen Tag? (JJJJ-MM-TT)", morgen);
    if (!datum?.trim()) return;
    try {
      await api.planSetzen(datum.trim(), {
        teile: parts.map((p) => p.id), anlass: occasion,
      });
      setNotice(`Für den ${datum.trim()} eingeplant. Diese Teile bleiben bis dahin verfügbar.`);
    } catch (err) {
      fail(err, "Das konnte nicht eingeplant werden.");
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
          {[["heute", "Heute"], ["schrank", `Schrank ${items.length}`],
            ["planen", "Planen"], ["fehlt", "Fehlt"], ["bilanz", "Bilanz"]].map(
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
              onClick={() => holeWetter()}
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

          {/* Was das Wetter beigetragen hat, bleibt stehen. Vorher blitzte
              es nur kurz als Meldung auf, und Regen und Wind tauchten gar
              nicht auf, wenn sie unter der Schwelle lagen — dann sah es
              aus, als zähle nur die Temperatur. */}
          {wetterlage && (
            <div className="mt-2">
              <p style={{ color: C.faint }} className="text-xs leading-relaxed">
                An deinem Standort
                {typeof wetterlage.gefuehlt === "number"
                  ? `, gefühlt ${Math.round(wetterlage.gefuehlt)} Grad` : ""}
                {" · "}
                {wetterlage.regen >= 0.2
                  ? `${wetterlage.regen} mm Regen`
                  : "kein Regen"}
                {" · "}
                {Math.round(wetterlage.wind)} km/h Wind
                {typeof wetterlage.min === "number" && typeof wetterlage.max === "number"
                  ? ` · heute ${Math.round(wetterlage.min)} bis ${Math.round(wetterlage.max)} Grad`
                  : ""}
                {wetterlage.gecacht ? " (gespeichert)" : ""}
              </p>
              {(wetterlage.regen >= 2 || wetterlage.wind >= 20) && (
                <p style={{ color: C.signal }} className="mt-1 text-xs leading-relaxed">
                  {wetterlage.regen >= 2
                    ? "Wildleder, Satin, Seide und Leinen werden bei dem Regen abgewertet."
                    : "Bei dem Wind werden Mesh, Leinen und Viskose abgewertet."}
                </p>
              )}
            </div>
          )}

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

              {Array.isArray(o.weglassen) && o.weglassen.length > 0 && (
                <p style={{ color: C.faint }} className="text-xs mt-4 leading-relaxed">
                  <Label>Kannst du dir sparen</Label>
                  <span className="block mt-1">
                    {o.weglassen.join(", ")} — sieht man in dieser Kombination nicht.
                  </span>
                </p>
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
                  <>
                  {wiederholungen[i] && (
                    <p
                      style={{ color: wiederholungen[i].selberAnlass ? C.signal : C.faint }}
                      className="mt-4 text-xs leading-relaxed"
                    >
                      {wiederholungen[i].selberAnlass
                        ? `Fast dasselbe hattest du vor ${wiederholungen[i].vorTagen} Tagen `
                          + `schon bei „${wiederholungen[i].anlass}" an.`
                        : `Ähnliche Zusammenstellung vor ${wiederholungen[i].vorTagen} Tagen`
                          + `${wiederholungen[i].anlass ? ` (${wiederholungen[i].anlass})` : ""}.`}
                    </p>
                  )}
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
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => outfitMerken(o.teile)}
                      style={{ borderColor: C.line, color: C.dim, letterSpacing: "0.16em" }}
                      className="flex-1 py-3 text-[10px] uppercase border"
                    >
                      Merken
                    </button>
                    <button
                      onClick={() => outfitEinplanen(o.teile)}
                      style={{ borderColor: C.line, color: C.dim, letterSpacing: "0.16em" }}
                      className="flex-1 py-3 text-[10px] uppercase border"
                    >
                      Einplanen
                    </button>
                  </div>
                  {/* Foto erst, wenn das Outfit vermerkt ist — vorher gibt
                      es keinen Protokolleintrag, an den es gehören könnte. */}
                  {z.logId && (
                    <label
                      style={{ borderColor: C.line, color: z.foto ? C.text : C.dim,
                               letterSpacing: "0.16em" }}
                      className="mt-2 block cursor-pointer border py-3 text-center text-[10px] uppercase"
                    >
                      {z.foto ? "Foto gespeichert ✓" : "Foto vom Outfit"}
                      <input
                        type="file" accept="image/*" capture="environment" className="hidden"
                        onChange={(e) => ootdHochladen(i, z.logId, e.target.files?.[0])}
                      />
                    </label>
                  )}
                  </>
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
          {items.length > 0 && (
            <div className="mb-4">
              <input
                value={suche}
                onChange={(e) => setSuche(e.target.value)}
                placeholder="Suchen: Name, Marke, Material, Farbe …"
                style={{ background: "transparent", color: C.text, borderColor: C.line }}
                className="w-full border-b pb-2 text-sm"
              />
              <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                {["", ...V("kategorien", CATEGORIES)].map((k) => (
                  <button
                    key={k || "alle"}
                    onClick={() => setFilterKat(k)}
                    style={{
                      borderColor: filterKat === k ? C.text : C.line,
                      color: filterKat === k ? C.text : C.faint,
                      letterSpacing: "0.14em",
                    }}
                    className="whitespace-nowrap border px-3 py-2 text-[10px] uppercase"
                  >
                    {k || "alle"}
                  </button>
                ))}
                <button
                  onClick={() => setZeigeArchiv((v) => !v)}
                  style={{
                    borderColor: zeigeArchiv ? C.text : C.line,
                    color: zeigeArchiv ? C.text : C.faint,
                    letterSpacing: "0.14em",
                  }}
                  className="whitespace-nowrap border px-3 py-2 text-[10px] uppercase"
                >
                  Eingemottet
                </button>
              </div>
            </div>
          )}
          <div className="grid grid-cols-3 gap-3">
            {sichtbareTeile.map((it) => (
              <button key={it.id} onClick={() => setDetail(it)} className="text-left">
                <div
                  style={{
                    background: C.surface,
                    opacity: it.paused || it.archived || waescheTage(it) > 0 ? 0.35 : 1,
                  }}
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
                <Label>
                  {waescheTage(it) > 0
                    ? `Wäsche · ${waescheText(waescheTage(it))}`
                    : it.archived
                      ? "eingemottet"
                      : [it.brand, it.material].filter(Boolean).join(" · ") || it.fit}
                </Label>
              </button>
            ))}
          </div>
          {items.length > 0 && sichtbareTeile.length === 0 && (
            <p style={{ color: C.faint }} className="py-10 text-center text-sm">
              Nichts gefunden.
            </p>
          )}
        </main>
      )}

      {/* ─────────────────────────── Planen ─────────────────────────── */}
      {view === "planen" && (
        <main className="px-5 pb-32 pt-5">
          <Label>die nächsten Tage</Label>
          <div className="mt-2">
            {naechsteTage().map(({ iso, kurz, heute }) => {
              const p = plaene.find((x) => x.datum === iso);
              const teile = (p?.itemIds || [])
                .map((id) => items.find((i) => i.id === id))
                .filter(Boolean);
              return (
                <div key={iso} style={{ borderColor: C.line }}
                     className="flex items-center gap-3 border-b py-3">
                  <div className="w-20 shrink-0">
                    <p style={{ color: heute ? C.text : C.dim }} className="text-sm">{kurz}</p>
                    {heute && <Label>heute</Label>}
                  </div>
                  {teile.length ? (
                    <>
                      <div className="flex flex-1 gap-1 overflow-hidden">
                        {teile.map((t) => (
                          <div key={t.id} style={{ background: C.surface }}
                               className="h-12 w-12 shrink-0 overflow-hidden">
                            {t.imagePath && (
                              <img src={imageUrl(t.id)} alt={t.name} loading="lazy"
                                   className="h-full w-full object-contain" />
                            )}
                          </div>
                        ))}
                      </div>
                      <button onClick={() => planLoeschen(iso)}
                              style={{ color: C.faint, letterSpacing: "0.14em" }}
                              className="shrink-0 text-[10px] uppercase">
                        weg
                      </button>
                    </>
                  ) : (
                    <p style={{ color: C.faint }} className="flex-1 text-xs">nichts geplant</p>
                  )}
                </div>
              );
            })}
          </div>
          <p style={{ color: C.faint }} className="mt-3 text-xs leading-relaxed">
            Eingeplante Teile bleiben verfügbar — die Wäsche nimmt dir nicht weg, was du für
            einen der nächsten Tage vorgesehen hast.
          </p>

          <section className="mt-8">
            <Label>gemerkte Outfits</Label>
            {gemerkte.length === 0 ? (
              <p style={{ color: C.faint }} className="mt-2 text-xs leading-relaxed">
                Noch keine. Unter „Heute" bei einem Vorschlag auf „Merken" tippen.
              </p>
            ) : (
              <div className="mt-2">
                {gemerkte.map((o) => {
                  const teile = o.itemIds
                    .map((id) => items.find((i) => i.id === id))
                    .filter(Boolean);
                  const fehlend = o.itemIds.length - teile.length;
                  return (
                    <div key={o.id} style={{ borderColor: C.line }} className="border-b py-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm">{o.name}</p>
                        <div className="flex gap-3">
                          <button onClick={() => outfitEinplanen(teile)}
                                  style={{ color: C.dim, letterSpacing: "0.14em" }}
                                  className="text-[10px] uppercase">
                            einplanen
                          </button>
                          <button onClick={() => gemerktesLoeschen(o.id)}
                                  style={{ color: C.faint, letterSpacing: "0.14em" }}
                                  className="text-[10px] uppercase">
                            weg
                          </button>
                        </div>
                      </div>
                      <div className="mt-2 flex gap-1">
                        {teile.map((t) => (
                          <div key={t.id} style={{ background: C.surface }}
                               className="h-12 w-12 shrink-0 overflow-hidden">
                            {t.imagePath && (
                              <img src={imageUrl(t.id)} alt={t.name} loading="lazy"
                                   className="h-full w-full object-contain" />
                            )}
                          </div>
                        ))}
                      </div>
                      {fehlend > 0 && (
                        <p style={{ color: C.faint }} className="mt-1 text-xs">
                          {fehlend} {fehlend === 1 ? "Teil" : "Teile"} nicht mehr im Schrank
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {waschgaenge?.ladungen?.length > 0 && (
            <section className="mt-8">
              <Label>Waschgänge</Label>
              <p style={{ color: C.faint }} className="mt-1 text-xs leading-relaxed">
                Was gerade in der Wäsche liegt, nach Pflegehinweis und hell/dunkel
                sortiert — so weit es Angaben dazu gibt.
              </p>
              {waschgaenge.ladungen.map((l) => (
                <div key={`${l.pflege}-${l.ton}`} className="mt-3">
                  <p style={{ color: C.dim }} className="text-sm">
                    {l.pflege} · {l.ton} · {l.anzahl}{" "}
                    {l.anzahl === 1 ? "Teil" : "Teile"}
                  </p>
                  <p style={{ color: C.faint }} className="text-xs">
                    {l.teile.map((t) => t.name).join(", ")}
                  </p>
                </div>
              ))}
              {waschgaenge.ohnePflegeangabe.length > 0 && (
                <p style={{ color: C.faint }} className="mt-3 text-xs leading-relaxed">
                  Ohne Pflegeangabe: {waschgaenge.ohnePflegeangabe.map((t) => t.name).join(", ")}.
                  Im Detail des Teils eintragen, dann landen sie in einer Ladung.
                </p>
              )}
            </section>
          )}

          <section className="mt-8">
            <Label>Koffer packen</Label>
            <p style={{ color: C.faint }} className="mt-1 text-xs leading-relaxed">
              Die kleinste Menge Teile, aus der sich für die Reise genug Outfits bauen lassen.
            </p>
            <div className="mt-3 flex items-end gap-3">
              <div className="w-20">
                <Label>Tage</Label>
                <input type="number" min="1" max="30" inputMode="numeric" value={packTage}
                       onChange={(e) => setPackTage(Number(e.target.value) || 1)}
                       style={{ background: "transparent", color: C.text, borderColor: C.line }}
                       className="w-full border-b pb-1 text-sm" />
              </div>
              <div className="w-24">
                <Label>Grad</Label>
                <input type="number" min="-20" max="45" inputMode="numeric" value={packTemp}
                       onChange={(e) => setPackTemp(Number(e.target.value))}
                       style={{ background: "transparent", color: C.text, borderColor: C.line }}
                       className="w-full border-b pb-1 text-sm" />
              </div>
              <button onClick={packlisteBauen} disabled={!!busy}
                      style={{ background: C.text, color: C.bg, letterSpacing: "0.16em" }}
                      className="flex-1 py-3 text-[10px] uppercase">
                Rechnen
              </button>
            </div>

            {packListe && (
              <div className="mt-4">
                <p style={{ color: C.dim }} className="text-sm">
                  {packListe.teile.length} {packListe.teile.length === 1 ? "Teil" : "Teile"} für{" "}
                  {packListe.outfits.length}{" "}
                  {packListe.outfits.length === 1 ? "Outfit" : "Outfits"}
                </p>
                {!packListe.genug && (
                  <p style={{ color: C.signal }} className="mt-1 text-xs leading-relaxed">
                    Für {packListe.tage} Tage reicht der Schrank nicht — mehr Kombinationen gibt
                    er bei dieser Temperatur nicht her.
                  </p>
                )}
                <ul className="mt-2">
                  {packListe.teile.map((t) => (
                    <li key={t.id} style={{ borderColor: C.line }}
                        className="flex items-center gap-3 border-b py-2">
                      <div style={{ background: C.surface }}
                           className="h-10 w-10 shrink-0 overflow-hidden">
                        {t.imagePath && (
                          <img src={imageUrl(t.id)} alt={t.name} loading="lazy"
                               className="h-full w-full object-contain" />
                        )}
                      </div>
                      <span className="flex-1 truncate text-sm">{t.name}</span>
                      <span style={{ color: C.faint }} className="text-xs">{t.fuerOutfits}×</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </main>
      )}

      {/* ─────────────────────────── Bilanz ─────────────────────────── */}
      {view === "bilanz" && (
        <main className="px-5 pb-32 pt-5">
          {!stats ? (
            <p style={{ color: C.dim }} className="text-sm">Wird geladen …</p>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3">
                {[
                  [stats.teile, "Teile"],
                  [stats.getragen, "schon getragen"],
                  [stats.protokollEintraege, "Outfits notiert"],
                ].map(([wert, text]) => (
                  <div key={text} style={{ borderColor: C.line }} className="border p-3">
                    <div style={{ fontFamily: DISPLAY, fontSize: 30 }}>{wert}</div>
                    <Label>{text}</Label>
                  </div>
                ))}
              </div>

              {stats.inDerWaesche?.length > 0 && (
                <section className="mt-7">
                  <Label>gerade in der Wäsche</Label>
                  <ul className="mt-2">
                    {stats.inDerWaesche.map((x) => (
                      <li
                        key={x.id}
                        style={{ borderColor: C.line, color: C.dim }}
                        className="flex justify-between border-b py-2 text-sm"
                      >
                        <span>{x.name}</span>
                        <span style={{ color: C.faint }}>
                          {x.restTage < 1
                            ? `noch ${Math.max(1, Math.round(x.restTage * 24))} h`
                            : `noch ${Math.ceil(x.restTage)} Tage`}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {stats.meistGetragen?.length > 0 && (
                <section className="mt-7">
                  <Label>am häufigsten getragen</Label>
                  <ul className="mt-2">
                    {stats.meistGetragen.map((x) => (
                      <li
                        key={x.id}
                        style={{ borderColor: C.line }}
                        className="flex justify-between border-b py-2 text-sm"
                      >
                        <span>{x.name}</span>
                        <span style={{ color: C.faint }}>
                          {x.getragen}×{x.proTragen != null ? ` · ${x.proTragen} €` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {stats.ladenhueter?.length > 0 && (
                <section className="mt-7">
                  <Label>liegt nur herum</Label>
                  <p style={{ color: C.faint }} className="mt-1 text-xs">
                    Seit mindestens einem Monat da und noch nie getragen.
                  </p>
                  <ul className="mt-2">
                    {stats.ladenhueter.map((x) => (
                      <li
                        key={x.id}
                        style={{ borderColor: C.line }}
                        className="flex justify-between border-b py-2 text-sm"
                      >
                        <span>{x.name}</span>
                        <span style={{ color: C.faint }}>seit {x.seitErfassung} Tagen</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {stats.waescheseit?.anzahl > 0 && (
                <p style={{ color: C.faint }} className="mt-5 text-xs leading-relaxed">
                  {stats.waescheseit.anzahl}{" "}
                  {stats.waescheseit.anzahl === 1 ? "Teil wartet" : "Teile warten"} auf die
                  Wäsche{stats.waescheseit.laengsteTage > 0
                    ? `, das älteste seit ${stats.waescheseit.laengsteTage} Tagen`
                    : ""}. Unter „Planen" steht, was zusammen in eine Maschine kann.
                </p>
              )}

              {stats.ausgaben?.jahre?.length > 0 && (
                <section className="mt-7">
                  <Label>Ausgaben</Label>
                  <ul className="mt-2">
                    {stats.ausgaben.jahre.map((j) => (
                      <li key={j.jahr} style={{ borderColor: C.line }}
                          className="flex justify-between border-b py-2 text-sm">
                        <span>{j.jahr}</span>
                        <span style={{ color: C.faint }}>{j.summe.toFixed(2)} €</span>
                      </li>
                    ))}
                  </ul>
                  {stats.ausgaben.kategorien.length > 0 && (
                    <p style={{ color: C.faint }} className="mt-2 text-xs leading-relaxed">
                      Nach Art: {stats.ausgaben.kategorien
                        .map((k) => `${k.kategorie} ${k.summe.toFixed(0)} €`)
                        .join(" · ")}
                    </p>
                  )}
                  {stats.ausgaben.ohneDatum > 0 && (
                    <p style={{ color: C.faint }} className="mt-1 text-xs">
                      {stats.ausgaben.ohneDatum} mit Preis, aber ohne Kaufdatum — die
                      fehlen in der Jahresliste.
                    </p>
                  )}
                </section>
              )}

              {ausmisten?.vorschlaege?.length > 0 && (
                <section className="mt-7">
                  <Label>könnte weg</Label>
                  <p style={{ color: C.faint }} className="mt-1 text-xs leading-relaxed">
                    Nur ein Vorschlag mit Begründung — was aus dem Schrank fliegt,
                    entscheidest du. „Einmotten" im Detail eines Teils ist der sanftere Weg.
                  </p>
                  <ul className="mt-2">
                    {ausmisten.vorschlaege.map((x) => (
                      <li key={x.id} style={{ borderColor: C.line }} className="border-b py-2">
                        <button
                          onClick={() => {
                            const teil = items.find((i) => i.id === x.id);
                            if (teil) { setDetail(teil); setView("schrank"); }
                          }}
                          className="w-full text-left"
                        >
                          <span className="text-sm">{x.name}</span>
                          <span style={{ color: C.faint }} className="block text-xs">
                            {x.gruende.join(" · ")}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section className="mt-7">
                <Label>aktuelle Einordnung</Label>
                {!trends ? (
                  <p style={{ color: C.faint }} className="mt-1 text-xs leading-relaxed">
                    Wird beim nächsten Vorschlag geholt und danach 30 Tage
                    weiterverwendet.
                  </p>
                ) : (
                  <>
                    <p style={{ color: C.faint }} className="mt-1 text-xs">
                      Stand {trends.trends?.stand || "unbekannt"}
                      {trends.geholt ? ` · geholt am ${trends.geholt.slice(0, 10)}` : ""}
                      {trends.alter != null ? ` · vor ${trends.alter} Tagen` : ""}
                    </p>
                    <ul className="mt-2">
                      {(trends.trends?.trends || []).map((t) => (
                        <li
                          key={t}
                          style={{ borderColor: C.line }}
                          className="border-b py-2 text-sm leading-relaxed"
                        >
                          {t}
                        </li>
                      ))}
                    </ul>
                    {(trends.trends?.ueberholt || []).length > 0 && (
                      <>
                        <Label style={{ display: "block", marginTop: 14 }}>gilt als überholt</Label>
                        <ul className="mt-1">
                          {trends.trends.ueberholt.map((t) => (
                            <li
                              key={t}
                              style={{ borderColor: C.line, color: C.dim }}
                              className="border-b py-2 text-sm leading-relaxed"
                            >
                              {t}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                    {trends.trends?.unsicherheit && (
                      <p style={{ color: C.faint }} className="mt-3 text-xs leading-relaxed">
                        {trends.trends.unsicherheit}
                      </p>
                    )}
                    <p style={{ color: C.faint }} className="mt-3 text-xs leading-relaxed">
                      Fließt als Hinweis in die Kuration ein, überstimmt die Auswahl aber
                      nicht. Wird nach 30 Tagen von selbst erneuert.
                    </p>
                  </>
                )}
              </section>

              <section className="mt-7">
                <Label>Preis pro Tragen</Label>
                {stats.teileMitPreis === 0 ? (
                  <p style={{ color: C.faint }} className="mt-2 text-xs leading-relaxed">
                    Noch kein Teil hat einen Preis. Trag ihn im Detail eines Teils ein — dann
                    rechnet die Bilanz aus, was dich jedes Tragen kostet.
                  </p>
                ) : (
                  <>
                    <p style={{ color: C.dim }} className="mt-2 text-sm">
                      {stats.investition.toFixed(2)} € über {stats.teileMitPreis}{" "}
                      {stats.teileMitPreis === 1 ? "Teil" : "Teile"}
                      {stats.teileOhnePreis > 0
                        ? ` · ${stats.teileOhnePreis} ohne Preisangabe`
                        : ""}
                    </p>
                    <ul className="mt-2">
                      {stats.besteProTragen.map((x) => (
                        <li
                          key={x.id}
                          style={{ borderColor: C.line }}
                          className="flex justify-between border-b py-2 text-sm"
                        >
                          <span>{x.name}</span>
                          <span style={{ color: C.faint }}>
                            {x.proTragen} € · {x.getragen}×
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </section>
            </>
          )}
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
                label="Kategorie" value={attrs.category} options={V("kategorien", CATEGORIES)}
                flagged={flagged("category")} onChange={(v) => patchQueue({ category: v })}
              />
              {attrs.category === "Accessoire" ? (
                <Field
                  label="Art" value={attrs.subcategory} options={V("accessoires", ACCESSORY_TYPES)}
                  flagged={flagged("subcategory")} onChange={(v) => patchQueue({ subcategory: v })}
                />
              ) : (
                <Field
                  label="Schnitt" value={attrs.fit} options={V("schnitte", FITS)}
                  flagged={flagged("fit")} onChange={(v) => patchQueue({ fit: v })}
                />
              )}
              {attrs.category !== "Accessoire" && attrs.category !== "Schuhe" && (
                <Field
                  label="Länge" value={attrs.length}
                  options={attrs.category === "Unterteil" ? V("laengenUnten", BOTTOM_LEN) : V("laengenOben", TOP_LEN)}
                  flagged={flagged("length")} onChange={(v) => patchQueue({ length: v })}
                />
              )}
              {attrs.category === "Unterteil" && (
                <Field
                  label="Bundhöhe" value={attrs.rise} options={V("bundhoehen", RISES)}
                  flagged={flagged("rise")} onChange={(v) => patchQueue({ rise: v })}
                />
              )}
              {attrs.category === "Schuhe" && (
                <Field
                  label="Gewicht" value={attrs.shoeWeight} options={V("schuhgewichte", SHOE_WEIGHT)}
                  flagged={flagged("shoeWeight")} onChange={(v) => patchQueue({ shoeWeight: v })}
                />
              )}
              {(attrs.category === "Oberteil" || attrs.category === "Jacke") && (
                <Field
                  label="Ärmel" value={attrs.sleeve} options={V("aermel", SLEEVES)}
                  flagged={flagged("sleeve")} onChange={(v) => patchQueue({ sleeve: v })}
                />
              )}
              <Field
                label="Material" value={attrs.material} options={V("materialien", MATERIALS)}
                flagged={flagged("material")} onChange={(v) => patchQueue({ material: v })}
              />
              <Field
                label="Dicke" value={attrs.thickness} options={V("dicken", THICKNESS)}
                flagged={flagged("thickness")} onChange={(v) => patchQueue({ thickness: v })}
              />
              <Field
                label="Oberfläche" value={attrs.texture} options={V("oberflaechen", TEXTURES)}
                flagged={flagged("texture")} onChange={(v) => patchQueue({ texture: v })}
              />
              <Field
                label="Muster" value={attrs.pattern} options={V("muster", PATTERNS)}
                flagged={flagged("pattern")} onChange={(v) => patchQueue({ pattern: v })}
              />
              {attrs.pattern && attrs.pattern !== "uni" && (
                <Field
                  label="Mustergröße" value={attrs.patternScale} options={V("musterGroessen", PATTERN_SCALE)}
                  flagged={flagged("patternScale")}
                  onChange={(v) => patchQueue({ patternScale: v })}
                />
              )}
              {attrs.category !== "Schuhe" && attrs.category !== "Accessoire" && (
                <Field
                  label="Aufdruck" value={attrs.printPosition}
                  options={V("printPositionen", PRINT_POSITIONS)}
                  flagged={flagged("printPosition")}
                  onChange={(v) => patchQueue({ printPosition: v })}
                />
              )}
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
              später im Detail überschreiben. Das Material entscheidet außerdem mit, ob ein Teil
              zur Temperatur passt — Leinen im Januar wird abgewertet, Wolle im Hochsommer auch.
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
                label="Kategorie" value={detail.category} options={V("kategorien", CATEGORIES)}
                onChange={(v) => updateItem(detail.id, { category: v })}
              />
              {detail.category === "Accessoire" ? (
                <Field
                  label="Art" value={detail.subcategory} options={V("accessoires", ACCESSORY_TYPES)}
                  onChange={(v) => updateItem(detail.id, { subcategory: v })}
                />
              ) : (
                <Field
                  label="Schnitt" value={detail.fit} options={V("schnitte", FITS)}
                  onChange={(v) => updateItem(detail.id, { fit: v })}
                />
              )}
              {detail.category !== "Accessoire" && detail.category !== "Schuhe" && (
                <Field
                  label="Länge" value={detail.length}
                  options={detail.category === "Unterteil" ? V("laengenUnten", BOTTOM_LEN) : V("laengenOben", TOP_LEN)}
                  onChange={(v) => updateItem(detail.id, { length: v })}
                />
              )}
              {detail.category === "Unterteil" && (
                <Field
                  label="Bundhöhe" value={detail.rise} options={V("bundhoehen", RISES)}
                  onChange={(v) => updateItem(detail.id, { rise: v })}
                />
              )}
              {detail.category === "Schuhe" && (
                <Field
                  label="Gewicht" value={detail.shoeWeight} options={V("schuhgewichte", SHOE_WEIGHT)}
                  onChange={(v) => updateItem(detail.id, { shoeWeight: v })}
                />
              )}
              {(detail.category === "Oberteil" || detail.category === "Jacke") && (
                <Field
                  label="Ärmel" value={detail.sleeve} options={V("aermel", SLEEVES)}
                  onChange={(v) => updateItem(detail.id, { sleeve: v })}
                />
              )}
              {/* Material, Dicke, Oberfläche und Mustergröße waren bis
                  29.08.2026 nur auf der Prüfkarte zu sehen. Wer sie dort
                  übersehen hatte, kam nie wieder an sie heran — obwohl
                  die Mustergröße über den harten Ausschluss "zwei laute
                  Muster" entscheidet. */}
              <Field
                label="Material" value={detail.material} options={V("materialien", MATERIALS)}
                onChange={(v) => updateItem(detail.id, { material: v })}
              />
              <Field
                label="Dicke" value={detail.thickness} options={V("dicken", THICKNESS)}
                onChange={(v) => updateItem(detail.id, { thickness: v })}
              />
              <Field
                label="Oberfläche" value={detail.texture} options={V("oberflaechen", TEXTURES)}
                onChange={(v) => updateItem(detail.id, { texture: v })}
              />
              <Field
                label="Muster" value={detail.pattern} options={V("muster", PATTERNS)}
                onChange={(v) => updateItem(detail.id, { pattern: v })}
              />
              {detail.pattern && detail.pattern !== "uni" && (
                <Field
                  label="Mustergröße" value={detail.patternScale} options={V("musterGroessen", PATTERN_SCALE)}
                  onChange={(v) => updateItem(detail.id, { patternScale: v })}
                />
              )}
              {detail.category !== "Schuhe" && detail.category !== "Accessoire" && (
                <Field
                  label="Aufdruck" value={detail.printPosition}
                  options={V("printPositionen", PRINT_POSITIONS)}
                  onChange={(v) => updateItem(detail.id, { printPosition: v })}
                />
              )}
            </div>

            {detail.materialSecondary && (
              <p style={{ color: C.faint }} className="mt-3 text-xs">
                Zweitmaterial: {detail.materialSecondary}
              </p>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <Label>Marke</Label>
                <input
                  value={detail.brand || ""}
                  placeholder="—"
                  onChange={(e) => updateItemLater(detail.id, { brand: e.target.value || null })}
                  style={{ background: "transparent", color: C.text, borderColor: C.line }}
                  className="w-full border-b text-sm pb-1"
                />
              </div>
              <div>
                <Label>Größe</Label>
                <input
                  value={detail.size || ""}
                  placeholder="—"
                  onChange={(e) => updateItemLater(detail.id, { size: e.target.value || null })}
                  style={{ background: "transparent", color: C.text, borderColor: C.line }}
                  className="w-full border-b text-sm pb-1"
                />
              </div>
            </div>
            <div className="mt-3">
              <Field
                label="Pflege" value={detail.care} options={V("pflege", CARE_LABELS)}
                onChange={(v) => updateItem(detail.id, { care: v })}
              />
            </div>

            {/* Preis und Kaufdatum sind freiwillig. Ohne sie funktioniert
                alles wie bisher; mit ihnen rechnet die Auswertung den
                Preis pro Tragen aus. */}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <Label>Preis (€)</Label>
                <input
                  type="number" min="0" step="0.01" inputMode="decimal"
                  value={detail.price ?? ""}
                  placeholder="—"
                  onChange={(e) =>
                    updateItemLater(detail.id, {
                      price: e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                  style={{ background: "transparent", color: C.text, borderColor: C.line }}
                  className="w-full border-b text-sm pb-1"
                />
              </div>
              <div>
                <Label>Gekauft am</Label>
                <input
                  type="date"
                  value={(detail.boughtAt || "").slice(0, 10)}
                  onChange={(e) =>
                    updateItemLater(detail.id, { boughtAt: e.target.value || null })
                  }
                  style={{ background: "transparent", color: C.text, borderColor: C.line }}
                  className="w-full border-b text-sm pb-1"
                />
              </div>
            </div>
            {detail.price != null && (detail.wearCount || 0) > 0 && (
              <p style={{ color: C.faint }} className="mt-2 text-xs">
                {(detail.price / detail.wearCount).toFixed(2)} € pro Tragen
              </p>
            )}

            <div className="mt-4 flex items-center gap-3">
              <span
                style={{ background: detail.colorHex || "#888", borderColor: C.line }}
                className="w-8 h-8 rounded-full border"
              />
              <div className="flex-1">
                <Label>Farbe</Label>
                <input
                  value={detail.colorName || ""}
                  onChange={(e) => updateItemLater(detail.id, { colorName: e.target.value })}
                  style={{ background: "transparent", color: C.text, borderColor: C.line }}
                  className="w-full border-b text-sm pb-1"
                />
              </div>
              <input
                type="color" value={detail.colorHex || "#888888"}
                onChange={(e) => updateItemLater(detail.id, { colorHex: e.target.value })}
                className="w-10 h-10 bg-transparent"
              />
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

            <div className="mt-4">
              <Label>Schlagworte</Label>
              <input
                value={detail.tags || ""}
                placeholder="z. B. urlaub, büro, lieblingsteil"
                onChange={(e) => updateItemLater(detail.id, { tags: e.target.value || null })}
                style={{ background: "transparent", color: C.text, borderColor: C.line }}
                className="w-full border-b pb-1 text-sm"
              />
              <p style={{ color: C.faint }} className="mt-1 text-xs">
                Frei wählbar, mit Komma getrennt. Die Suche im Schrank findet sie.
              </p>
            </div>

            <div className="mt-4">
              <Label>Waschetikett</Label>
              <div className="mt-2 flex items-center gap-3">
                {detail.labelPath && (
                  <div style={{ background: C.bg }} className="h-20 w-20 shrink-0 overflow-hidden">
                    <img
                      src={etikettUrl(detail.id)} alt="Waschetikett"
                      className="h-full w-full object-contain"
                    />
                  </div>
                )}
                <label
                  style={{ borderColor: C.line, color: C.dim, letterSpacing: "0.16em" }}
                  className="flex-1 cursor-pointer border py-3 text-center text-[10px] uppercase"
                >
                  {detail.labelPath ? "Etikett ersetzen" : "Etikett fotografieren"}
                  <input
                    type="file" accept="image/*" capture="environment" className="hidden"
                    onChange={(e) => etikettHochladen(detail.id, e.target.files?.[0])}
                  />
                </label>
              </div>
            </div>

            {/* Warum taucht dieses Teil (nicht) in Vorschlägen auf? */}
            {diagnose?.gefunden && (
              <div style={{ borderColor: C.line }} className="mt-5 border-t pt-4">
                <Label>in Vorschlägen</Label>
                {diagnose.sperre && (
                  <p style={{ color: C.signal }} className="mt-2 text-xs">
                    Zurzeit gesperrt: {diagnose.sperre}. Die folgenden Zahlen gelten
                    für den Fall, dass es wieder verfügbar ist.
                  </p>
                )}
                {diagnose.kombinationen === 0 ? (
                  <p style={{ color: C.faint }} className="mt-2 text-xs leading-relaxed">
                    Es fehlen andere Teile, um überhaupt eine Kombination zu bilden.
                  </p>
                ) : diagnose.zulaessig === 0 ? (
                  <>
                    <p style={{ color: C.signal }} className="mt-2 text-sm">
                      Fällt aus allen {diagnose.kombinationen} Kombinationen heraus.
                    </p>
                    <ul className="mt-2">
                      {diagnose.gruende.map((g) => (
                        <li
                          key={g.grund}
                          style={{ borderColor: C.line }}
                          className="flex justify-between border-b py-2 text-sm"
                        >
                          <span>{g.grund}</span>
                          <span style={{ color: C.faint }}>
                            {Math.round(g.anteil * 100)} %
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <>
                    <p style={{ color: C.dim }} className="mt-2 text-sm">
                      Passt in {diagnose.zulaessig} von {diagnose.kombinationen}{" "}
                      Kombinationen, beste {Math.round(diagnose.bestePunkte * 100)} Punkte.
                    </p>
                    {diagnose.gruende.length > 0 && (
                      <p style={{ color: C.faint }} className="mt-1 text-xs">
                        Scheitert sonst an: {diagnose.gruende
                          .map((g) => `${g.grund} (${Math.round(g.anteil * 100)} %)`)
                          .join(", ")}
                      </p>
                    )}
                    {diagnose.schwaechste.length > 0 && (
                      <p style={{ color: C.faint }} className="mt-1 text-xs">
                        Schwächster Wert: {diagnose.schwaechste
                          .map(([k, v]) => `${k} ${v}`)
                          .join(" · ")}
                      </p>
                    )}
                  </>
                )}
              </div>
            )}

            {diagnose?.abhilfe?.length > 0 && (
              <div className="mt-4">
                <Label>was hülfe</Label>
                <ul className="mt-1">
                  {diagnose.abhilfe.map((a) => (
                    <li key={a.name} style={{ borderColor: C.line }}
                        className="flex justify-between border-b py-2 text-sm">
                      <span className="flex-1 pr-3">{a.name}</span>
                      <span style={{ color: C.faint }} className="whitespace-nowrap text-xs">
                        {a.neueOutfits > 0 ? `+${a.neueOutfits} ` : ""}
                        {a.bestePunkteVorher}→{a.bestePunkteNachher}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-5 flex items-center justify-between">
              <Label>{detail.wearCount || 0} mal getragen</Label>
              {waescheTage(detail) > 0 ? (
                <button
                  onClick={() => wiederVerfuegbar(detail.id)}
                  style={{ color: C.signal, letterSpacing: "0.16em" }}
                  className="text-[10px] uppercase"
                  title="Wäschefrist vorzeitig beenden"
                >
                  Wäsche · {waescheText(waescheTage(detail))} · freigeben
                </button>
              ) : (
                <button
                  onClick={() =>
                    detail.paused
                      ? wiederVerfuegbar(detail.id)
                      : updateItem(detail.id, { paused: true })
                  }
                  style={{ color: detail.paused ? C.signal : C.dim, letterSpacing: "0.16em" }}
                  className="text-[10px] uppercase"
                >
                  {detail.paused ? "pausiert · freigeben" : "verfügbar"}
                </button>
              )}
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
                onClick={() => teilKlonen(detail.id)}
                style={{ borderColor: C.line, color: C.dim, letterSpacing: "0.16em" }}
                className="px-4 py-4 text-[10px] uppercase border"
                title="Zweites Exemplar: gleiche Eigenschaften, ohne Foto und Verlauf"
              >
                Kopie
              </button>
              <button
                onClick={() => updateItem(detail.id, { archived: !detail.archived })}
                style={{ borderColor: C.line, color: C.dim, letterSpacing: "0.16em" }}
                className="px-4 py-4 text-[10px] uppercase border"
                title="Eingemottet: bleibt im Bestand, wird aber nicht vorgeschlagen"
              >
                {detail.archived ? "Hervorholen" : "Einmotten"}
              </button>
              <button
                onClick={() => removeItem(detail.id)}
                style={{ borderColor: C.line, color: C.signal, letterSpacing: "0.16em" }}
                className="px-4 py-4 text-[10px] uppercase border"
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

            <div style={{ borderColor: C.line }} className="mb-5 border-b pb-5">
              <Label>Person</Label>
              <p style={{ color: C.faint }} className="mt-1 text-xs leading-relaxed">
                Jede Person hat ihren eigenen Schrank, ihr eigenes Protokoll und ihre
                eigene Planung. Der Wechsel lädt die App neu.
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {personen.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => personWechseln(p.id)}
                    style={{
                      borderColor: p.id === aktivePerson ? C.text : C.line,
                      color: p.id === aktivePerson ? C.text : C.faint,
                      letterSpacing: "0.14em",
                    }}
                    className="border px-3 py-2 text-[10px] uppercase"
                  >
                    {p.name || (p.id === 1 ? "ich" : `Person ${p.id}`)}
                  </button>
                ))}
                <button
                  onClick={personAnlegen}
                  style={{ borderColor: C.line, color: C.dim, letterSpacing: "0.14em" }}
                  className="border px-3 py-2 text-[10px] uppercase"
                >
                  + neu
                </button>
              </div>
              {aktivePerson !== 1 && (
                <button
                  onClick={() => personLoeschen(aktivePerson)}
                  style={{ color: C.signal, letterSpacing: "0.14em" }}
                  className="mt-2 text-[10px] uppercase"
                >
                  diese Person mit allen Teilen löschen
                </button>
              )}
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

            <button
              onClick={aufraeumen}
              style={{ color: C.dim, letterSpacing: "0.16em" }}
              className="mb-3 text-[10px] uppercase"
            >
              Verwaiste Bilder aufräumen
            </button>
            <p style={{ color: C.faint }} className="mb-3 text-xs leading-relaxed">
              Sucht Bilddateien, zu denen es kein Teil mehr gibt. Solche Reste stammen aus
              Löschungen von früher — neue hinterlassen keine.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
