/* ==========================================================================
   NOVAREL — tous les textes de la page, au même endroit.
   ➜ POUR CHANGER UN TEXTE : c'est ici, et nulle part ailleurs.
   Règles de marque : aucun chiffre inventé, aucune marque concurrente
   nommée dans l'avertissement, aucun ton alarmiste.
   ========================================================================== */

export const CTA_URL =
  "https://novarel-site.onrender.com/cameras-exterieures-sans-abonnement";

export const hero = {
  eyebrow: "Comparatifs équipement de sécurité — sans abonnement",
  /* Titre imposé — ne pas réécrire. */
  titleLines: ["Payez-la une fois.", "Pas tous les mois."] as const,
  /* Sous-titre imposé — ne pas réécrire. */
  subtitle: [
    "NOVAREL : prix juste, qualité durable, payée une seule fois — même en plusieurs fois.",
    "Pas d'abonnement caché, pas de rançon mensuelle pour garder l'accès à VOS images.",
  ] as const,
  cta: "Voir le comparatif caméras extérieures",
  scrollHint: "Le comparatif",
};

/* Avertissement consommateur — texte imposé, ne pas réécrire. */
export const alert = {
  label: "Ce qu'on ne vous dit pas toujours",
  body: [
    "La plupart des caméras « gratuites » ou « à petit prix » facturent un abonnement mensuel pour accéder à l'enregistrement cloud de VOS propres images.",
    "Sans lui, l'appareil peut perdre une grande partie de son utilité. Vérifiez toujours si le stockage local (carte SD, disque local) est possible AVANT d'acheter.",
  ] as const,
};

export type Product = {
  id: string;
  name: string;
  price: string;
  priceNote: string;
  best?: boolean;
  bestLabel?: string;
  summary: string;
};

/* Prix constatés — ne pas modifier, ne pas en ajouter, ne rien noter. */
export const products: Product[] = [
  {
    id: "argus-4-pro",
    name: "Reolink Argus 4 Pro",
    price: "≈ 150–180 €",
    priceNote: "Prix constaté",
    best: true,
    bestLabel: "Meilleur choix",
    summary: "Sans fil, stockage sur carte SD, fonctionne sans abonnement.",
  },
  {
    id: "rlc-810a",
    name: "Reolink RLC-810A",
    price: "≈ 90–120 €",
    priceNote: "Prix constaté",
    summary: "Filaire PoE, stockage local, pensée pour une installation fixe.",
  },
  {
    id: "blink-outdoor-4",
    name: "Blink Outdoor 4",
    price: "≈ 100 €",
    priceNote: "Prix constaté (kit)",
    summary: "Kit sur piles ; le stockage local passe par un module dédié.",
  },
];

/* Lignes du comparatif. `values` suit l'ordre de `products`.
   Écrire ce qui est vérifiable, jamais une note ni un pourcentage. */
export type Row = {
  criterion: string;
  hint?: string;
  values: string[];
};

export const rows: Row[] = [
  {
    criterion: "Abonnement obligatoire",
    hint: "Pour que l'appareil garde son usage principal",
    values: ["Non", "Non", "Non"],
  },
  {
    criterion: "Stockage local",
    hint: "Vos images restent chez vous",
    values: [
      "Carte microSD intégrée",
      "Carte microSD + enregistreur réseau",
      "Module de synchronisation (vendu à part ou en kit)",
    ],
  },
  {
    criterion: "Alimentation",
    values: ["Batterie + panneau solaire en option", "Filaire PoE", "Piles"],
  },
  {
    criterion: "Installation",
    values: ["Sans câble", "Câble réseau à tirer", "Sans câble"],
  },
  {
    criterion: "Prix",
    hint: "Payé une fois",
    values: ["≈ 150–180 €", "≈ 90–120 €", "≈ 100 € (kit)"],
  },
];

export const closing = {
  /* Signature imposée — ne pas réécrire. */
  signature: "On ne joue pas avec votre sécurité.",
  body: "On compare du matériel qu'on paie une fois. Quand un abonnement est nécessaire pour qu'un appareil garde son usage, c'est écrit noir sur blanc dans le comparatif.",
  cta: "Voir le comparatif complet",
};

export const footer = {
  disclosure:
    "NOVAREL est financé par l'affiliation Amazon : un achat via nos liens peut nous rémunérer, sans surcoût pour vous. Cela ne change pas l'ordre des comparatifs.",
  note: "Prix constatés à titre indicatif, susceptibles d'évoluer.",
};
