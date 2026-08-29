/* Vokabulare und Farben, unveraendert aus rack.jsx uebernommen.
   Die Engine auf dem Server kennt dieselben Listen; hier stehen sie nur
   fuer die Auswahlfelder der Oberflaeche. */

export const C = {
  bg: "#121212",
  surface: "#1a1a1a",
  raised: "#232323",
  line: "#2f2f2f",
  text: "#ece8e2",
  dim: "#8f8981",
  faint: "#5c5852",
  signal: "#c8542f",
};
export const DISPLAY = "'Bodoni Moda', Didot, Georgia, serif";
export const SANS = "'Archivo', 'Helvetica Neue', Arial, sans-serif";

export const CATEGORIES = ["Oberteil", "Unterteil", "Kleid", "Jacke", "Schuhe", "Accessoire"];
export const ACCESSORY_TYPES = ["Uhr", "Schmuck", "Mütze", "Cap", "Schal", "Gürtel", "Tasche", "Brille"];
export const FITS = ["oversize", "weit", "regular", "slim", "cropped"];
export const TOP_LEN = ["cropped", "hüftlang", "longline"];
export const BOTTOM_LEN = ["shorts", "sieben-achtel", "knöchel", "lang", "stacked"];
export const RISES = ["high", "mid", "low"];
export const THICKNESS = ["dünn", "mittel", "dick"];
export const PATTERNS = ["uni", "gestreift", "kariert", "gemustert", "meliert", "logo"];
export const SHOE_WEIGHT = ["filigran", "normal", "chunky"];
// Muss mit engine.MATERIALS uebereinstimmen: das Backend bildet jede
// Eingabe darauf ab, ein hier erfundener Wert landet als leeres Feld.
export const MATERIALS = [
  "Baumwolle", "Cord", "Denim", "Leinen", "Jersey", "Strick", "Wolle",
  "Kaschmir", "Fleece", "Daune", "Leder", "Wildleder", "Kunstleder",
  "Seide", "Satin", "Viskose", "Synthetik", "Mesh",
];
export const TEXTURES = ["glatt", "strukturiert", "glänzend", "flauschig", "robust"];
export const PATTERN_SCALE = ["klein", "mittel", "groß"];
export const SLEEVES = ["ärmellos", "kurz", "dreiviertel", "lang"];
export const CARE_LABELS = ["30 Grad", "40 Grad", "60 Grad", "Handwäsche",
  "Reinigung", "nicht in den Trockner"];
export const BUILDS = ["schlank", "normal", "athletisch", "kräftig"];
export const TORSOS = ["langer Oberkörper", "ausgeglichen", "lange Beine"];

export const SILHOUETTES = [
  { key: "oversize", label: "Durchgehend weit", hint: "Enge Teile fallen raus" },
  { key: "mix", label: "Oben weit, unten gerade", hint: "Volumen oben, klare Linie unten" },
  { key: "frei", label: "Proportionsspiel", hint: "Weit zu schmal ist erwünscht" },
  { key: "offen", label: "Alles erlaubt", hint: "Keine Silhouettenvorgabe, nur Statur und Proportion entscheiden" },
];

export const OCCASIONS = [
  { key: "Alltag", f: 2 },
  { key: "Arbeit", f: 4 },
  { key: "Abends", f: 3 },
  { key: "Anlass", f: 5 },
  { key: "Sport", f: 1 },
];

export const PHOTO_GUIDE = [
  ["Grundsatz", "Tageslicht, kein Blitz. Heller einfarbiger Untergrund, etwa ein Bettlaken. Handy parallel über dem Teil, nicht schräg. Ganzes Teil im Bild mit etwas Rand."],
  ["Oberteile", "Flach hinlegen, Ärmel leicht abgespreizt, Schulternaht sichtbar. Nicht falten, sonst wird der Schnitt als enger gelesen als er ist."],
  ["Hosen", "Flach, Bund oben im Bild, ein Bein leicht versetzt. Nur so ist die Beinweite erkennbar."],
  ["Jacken", "Geschlossen und flach, Kragen sichtbar. Bei Steppjacken auf gleichmäßiges Licht achten."],
  ["Schuhe", "Nicht direkt von der Seite, sondern schräg von vorn im Dreiviertelwinkel. Beide Schuhe oder einer, aber immer die Sohle mit im Bild."],
  ["Accessoires", "Einzeln fotografieren, mit Abstand zum Rand. Uhren mit dem Zifferblatt zur Kamera."],
];
