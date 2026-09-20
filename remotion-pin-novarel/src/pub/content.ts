/**
 * Tous les textes de la pub, au même endroit.
 * Prix = fourchettes constatées. Aucune note, aucun avis, aucun classement.
 */

export const EYEBROW = "COMPARATIF CAMÉRAS · 2026";

/** Les douze mois de l'année, abrégés : les douze cases du comparateur. */
export const MONTHS = [
  "JAN",
  "FÉV",
  "MAR",
  "AVR",
  "MAI",
  "JUIN",
  "JUIL",
  "AOÛT",
  "SEP",
  "OCT",
  "NOV",
  "DÉC",
] as const;

/**
 * Le bloc de comparaison. Rien ici n'est un chiffre de produit : « ×12 / an »
 * est l'arithmétique d'un abonnement mensuel (douze mois dans une année), et
 * « ×1 » est la définition d'un achat unique.
 */
export const COMPARE = {
  subscription: { label: "AVEC UN ABONNEMENT MENSUEL", tally: "×12 / AN" },
  oneShot: { label: "AVEC NOVAREL", tally: "×1" },
} as const;

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
