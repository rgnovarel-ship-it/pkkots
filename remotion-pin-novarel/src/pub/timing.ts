/**
 * Minutage — en frames à 30 fps.
 *
 * Principe de boucle : le mur, la lumière, la caméra et le logo sont présents du
 * début à la fin et leur animation est **périodique sur la durée totale** (sinus
 * de période DURATION). Seuls les textes entrent puis ressortent. Résultat : la
 * dernière frame est identique à la première — plan produit + logo, jamais du
 * noir ni du vide — et la boucle ne coupe pas.
 */

export const FPS = 30;
export const DURATION = 225; // 7,5 s

const s = (seconds: number) => Math.round(seconds * FPS);

export const T = {
  /** Arrivées. Le titre est à l'écran avant 1,2 s. */
  eyebrow: s(0),
  headline1: s(0.35),
  headline2: s(0.6),
  headline3: s(0.95),
  description: s(1.35),
  panel: s(1.75),
  panelStagger: s(0.22),
  cta: s(2.8),
  signature: s(3.1),

  /** Durée d'une arrivée et d'une sortie. */
  enter: s(0.55),
  exit: s(0.4),

  /** Sortie des textes : cascade inverse, le bas part en premier. */
  exitStart: s(6.55),
  exitStagger: s(0.05),

  /** Pulsation du bouton. */
  ctaPulse: s(2.2),
} as const;
