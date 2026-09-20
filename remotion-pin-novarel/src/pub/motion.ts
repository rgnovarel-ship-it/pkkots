/**
 * Outils de mouvement communs.
 * Tout dérive de la frame : rien n'est aléatoire au rendu, rien n'est en CSS.
 */

import { Easing, interpolate } from "remotion";
import { EASE } from "../brand";
import { DURATION, T } from "./timing";

/** L'easing du site, prêt à passer à interpolate(). */
export const siteEase = Easing.bezier(EASE[0], EASE[1], EASE[2], EASE[3]);

/**
 * Phase de boucle : 0 → 2π sur la durée totale.
 * Toute animation de fond construite avec sin/cos de cette phase revient
 * exactement à son état de départ sur la dernière frame.
 */
export const loopPhase = (frame: number) => (frame / DURATION) * Math.PI * 2;

/** Va-et-vient périodique dans [0, 1], sans discontinuité à la boucle. */
export const loopWave = (frame: number, offset = 0) =>
  (1 - Math.cos(loopPhase(frame) + offset)) / 2;

/** Générateur déterministe (mulberry32) : même seed = mêmes valeurs à chaque rendu. */
export const seeded = (seed: number) => {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

/**
 * Entrée puis sortie d'un élément de texte, en frames absolues.
 * `index` décale la sortie : la cascade repart du bas.
 */
export const revealOut = (frame: number, from: number, index = 0) => {
  const outAt = T.exitStart + index * T.exitStagger;

  const enter = interpolate(frame, [from, from + T.enter], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: siteEase,
  });
  const leave = interpolate(frame, [outAt, outAt + T.exit], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: siteEase,
  });

  return {
    /** 0 avant l'entrée, 1 pendant le maintien, 0 après la sortie. */
    progress: enter * (1 - leave),
    enter,
    leave,
  };
};
