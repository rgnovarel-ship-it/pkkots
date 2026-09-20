import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS } from "../brand";
import { loopWave } from "./motion";
import { Paper } from "./parts/Paper";
import { Ticker } from "./parts/Ticker";
import { Description, Eyebrow, HeadlineMark, HeadlineOne, HeadlineTurn } from "./parts/Copy";
import { Panel } from "./parts/Panel";
import { Cta, Logo, Signature } from "./parts/Footer";
import { Grain } from "./parts/Grain";

/**
 * Pub Pinterest NOVAREL — 1000 × 1500, 30 fps, 7,5 s.
 *
 * Pas d'objet dessiné : un bandeau d'encre où les douze mois défilent sans
 * jamais s'arrêter, et un titre qui se révèle au masque juste en dessous.
 * La lumière est une lumière d'imprimé — chaleur qui respire, balayage
 * brillant qui traverse la page, grain.
 *
 * Bandeau, sur-titre et logo sont permanents et leur mouvement reboucle
 * exactement sur la durée : la dernière frame est la première.
 */
export const PubNovarel: React.FC = () => {
  const frame = useCurrentFrame();

  // Micro-travelling : une image parfaitement fixe trahit le rendu.
  const push = 1 + 0.008 * loopWave(frame);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.paper, overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `scale(${push})`, transformOrigin: "50% 42%" }}>
        <Paper />
        <Ticker />

        <Eyebrow />
        <HeadlineOne />
        <HeadlineMark />
        <HeadlineTurn />
        <Description />
        <Panel />
        <Cta />
        <Signature />
        <Logo />
      </AbsoluteFill>

      <Grain />
    </AbsoluteFill>
  );
};
