/**
 * Tous les textes de la pub, au même endroit.
 * Prix = fourchettes constatées. Aucune note, aucun avis, aucun classement.
 */

export const EYEBROW = "COMPARATIF CAMÉRAS · 2026";

/** Les douze mois : c'est le bandeau qui défile, rien d'autre à y lire. */
export const MONTHS = [
  "JANVIER",
  "FÉVRIER",
  "MARS",
  "AVRIL",
  "MAI",
  "JUIN",
  "JUILLET",
  "AOÛT",
  "SEPTEMBRE",
  "OCTOBRE",
  "NOVEMBRE",
  "DÉCEMBRE",
] as const;

/** Titre en trois temps : le constat, le mot surligné, la chute. */
export const HEADLINE = {
  line1: "Vous payez déjà",
  mark: "tous les mois.",
  line3: "Ça s'appelle une assurance.",
} as const;

export const DESCRIPTION =
  "Une caméra, ça s'achète une fois. Chez NOVAREL, aucun abonnement pour accéder à vos propres images : vous payez le matériel, et c'est tout.";

/** En-tête du panneau comparatif — libellé, pas une affirmation chiffrée. */
export const PANEL_TITLE = "CAMÉRAS EXTÉRIEURES · SANS ABONNEMENT";

export type Product = { name: string; price: string; tag?: string };

export const PRODUCTS: Product[] = [
  { name: "Reolink Argus 4 Pro", price: "≈ 150–180 €", tag: "MEILLEUR CHOIX" },
  { name: "Reolink RLC-810A", price: "≈ 90–120 €" },
  { name: "Blink Outdoor 4", price: "≈ 100 € (kit)" },
];

export const CTA = "Voir le comparatif →";

export const SIGNATURE = "On ne joue pas avec votre sécurité.";

export const LOGO = { mark: "N", word: "NOVAREL" } as const;
