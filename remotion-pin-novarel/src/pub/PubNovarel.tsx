import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS } from "../brand";
import { loopWave } from "./motion";
import { Paper } from "./parts/Paper";
import { Compare } from "./parts/Compare";
import { Description, Eyebrow, HeadlineMark, HeadlineOne, HeadlineTurn } from "./parts/Copy";
import { Panel } from "./parts/Panel";
import { Cta, Logo, Signature } from "./parts/Footer";
import { Grain } from "./parts/Grain";

/**
 * Pub Pinterest NOVAREL — 1000 × 1500, 30 fps, 7,5 s.
 *
 * Pas d'objet dessiné. Le visuel principal est un comparateur : douze cases que
 * l'abonnement mensuel remplit une par une, année après année, contre une seule
 * case pour NOVAREL. Le titre se révèle au masque juste en dessous.
 * La lumière est une lumière d'imprimé — chaleur qui respire, balayage
 * brillant qui traverse la page, grain.
 *
 * Comparateur, sur-titre et logo sont permanents et leur mouvement reboucle
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
        <Compare />

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
