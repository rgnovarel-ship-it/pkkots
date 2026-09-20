import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS } from "../brand";
import { loopWave } from "./motion";
import { Wall } from "./parts/Wall";
import { Camera } from "./parts/Camera";
import { Description, Eyebrow, HeadlineMark, HeadlineOne, HeadlineTurn } from "./parts/Copy";
import { Panel } from "./parts/Panel";
import { Cta, Logo, Signature } from "./parts/Footer";
import { Grain } from "./parts/Grain";

/**
 * Pub Pinterest NOVAREL — 1000 × 1500, 30 fps, 7,5 s.
 *
 * Monde clair du site : mur papier, soleil bas hors champ en haut à droite,
 * caméra en plan produit, ombre portée réelle, poussière dans le rai.
 * Le décor et le logo sont permanents et leur animation reboucle exactement sur
 * la durée : la dernière frame est la première, et elle n'est ni noire ni vide.
 */
export const PubNovarel: React.FC = () => {
  const frame = useCurrentFrame();

  // Micro-travelling : une image parfaitement fixe trahit le rendu.
  // Périodique, donc invisible au raccord de boucle.
  const push = 1 + 0.012 * loopWave(frame);
  const drift = loopWave(frame, Math.PI) * 6;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.paper, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          transform: `scale(${push}) translate(${-drift * 0.5}px, ${drift * 0.3}px)`,
          transformOrigin: "58% 40%",
        }}
      >
        <Wall />
        <Camera />

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
