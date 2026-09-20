/**
 * Jetons de marque NOVAREL.
 * Extraits tels quels de novarel/static/css/novarel.css — ne pas inventer
 * d'autres couleurs ici, la vidéo doit rester raccord avec le site.
 */

export const COLORS = {
  // Thème clair du site (utilisé ici pour la lumière chaude / le texte clair)
  paper: "#f4f1ea",
  surface: "#fbf9f5",
  ink: "#10120f",
  inkSoft: "#33372f",
  muted: "#64685d",
  line: "#d9d4c7",

  signal: "#c8f04c",
  signalDeep: "#9cc021",
  alert: "#b8331c",
  good: "#1d6642",
  // --warn / --warn-bg du site : c'est la seule source de chaud du système,
  // elle sert ici de température d'éclairage (lumière extérieure ambrée).
  warn: "#8a6410",
  warnBg: "#f7efd9",

  // Variante sombre du site — c'est la base de la scène de nuit
  night: {
    paper: "#0c0e0b",
    surface: "#14170f",
    ink: "#f2efe6",
    muted: "#9aa08f",
    line: "#292e22",
  },
} as const;

/** #rrggbb -> rgba(r, g, b, a) */
export const alpha = (hex: string, a: number): string => {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
};

/** Marges de composition (1000 × 1500). */
export const LAYOUT = {
  width: 1000,
  height: 1500,
  gutter: 80,
  get contentWidth() {
    return this.width - this.gutter * 2;
  },
} as const;
