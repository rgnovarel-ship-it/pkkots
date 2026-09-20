/**
 * Tous les textes de la vidéo, au même endroit.
 * Prix = fourchettes constatées. Aucune note, aucun classement fabriqué.
 */

export const BADGE = "COMPARATIF CAMÉRAS · 2026";

export const HEADLINE = {
  line1: { before: "Payez-la ", accent: "une fois", after: "." },
  line2: "Pas tous les mois.",
} as const;

export const DESCRIPTION = [
  "NOVAREL : prix juste, qualité durable, payée une seule fois — même en plusieurs fois.",
  "Pas d'abonnement caché, pas de rançon mensuelle pour garder l'accès à VOS images.",
] as const;

export type Product = {
  name: string;
  price: string;
  tag?: string;
};

export const PRODUCTS: Product[] = [
  { name: "Reolink Argus 4 Pro", price: "≈ 150–180 €", tag: "MEILLEUR CHOIX" },
  { name: "Reolink RLC-810A", price: "≈ 90–120 €" },
  { name: "Blink Outdoor 4", price: "≈ 100 € (kit)" },
];

export const CTA = "Voir le comparatif →";

export const SIGNATURE = "On ne joue pas avec votre sécurité.";

export const LOGO = { mark: "N", word: "NOVAREL" } as const;
