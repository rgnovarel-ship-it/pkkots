/**
 * Minutage — tout est en frames à 30 fps.
 * C'est le seul fichier à toucher pour réagencer le déroulé.
 */

export const FPS = 30;
export const DURATION = 195; // 6,5 s

const s = (seconds: number) => Math.round(seconds * FPS);

export const T = {
  /** Montée de lumière + arrivée de la caméra (0 – 0,9 s) */
  lightRise: { from: 0, duration: s(0.9) },
  cameraIn: { from: 0, duration: s(0.95) },

  /** Reflet qui traverse l'objectif + faisceau qui s'établit (0,5 – 1,5 s) */
  lensFlare: { from: s(0.5), duration: s(1.0) },
  beam: { from: s(0.5), duration: s(1.0) },

  /** Voyant d'enregistrement : clignote à partir de 1,0 s, en continu */
  led: { from: s(1.0), period: s(1.2) },

  /** Cascade du haut (1,0 – 1,9 s) */
  badge: { from: s(1.0), duration: s(0.5) },
  headline1: { from: s(1.25), duration: s(0.6) },
  headline2: { from: s(1.45), duration: s(0.6) },

  /** Description (1,7 – 2,1 s) */
  description: { from: s(1.7), duration: s(0.5) },

  /** Produits l'un après l'autre (2,1 – 2,8 s) */
  products: { from: s(2.1), stagger: s(0.25), duration: s(0.55) },

  /** Bouton (2,9 – 3,3 s) puis pulsation continue */
  cta: { from: s(2.9), duration: s(0.5) },
  ctaPulsePeriod: s(2.0),

  /** Signature puis logo (3,2 – 3,6 s) */
  signature: { from: s(3.2), duration: s(0.45) },
  logo: { from: s(3.4), duration: s(0.45) },

  /** Maintien : respiration de la lumière + bande lumineuse */
  breathPeriod: s(3.4),
  sweep: { from: s(4.0), duration: s(1.6) },

  /** Fondu final : on revient à l'obscurité du début, la boucle est propre */
  loopFade: s(0.55),
} as const;
