import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS } from "./tokens";
import { T } from "./timing";
import { Backdrop } from "./parts/Backdrop";
import { Beam } from "./parts/Beam";
import { SecurityCamera } from "./parts/SecurityCamera";
import { Badge, Description, HeadlineOne, HeadlineTwo } from "./parts/Copy";
import { Products } from "./parts/Products";
import { Cta } from "./parts/Cta";
import { Logo, Signature } from "./parts/Footer";
import { Sweep } from "./parts/Sweep";
import { Grain } from "./parts/Grain";

/**
 * Épingle Pinterest NOVAREL — 1000 × 1500, 30 fps.
 *
 * Empilement : fond (deux températures de lumière) → faisceau → caméra →
 * textes → bande lumineuse → voile de faisceau → grain.
 * Tout le mouvement dérive de useCurrentFrame().
 */
export const PinNovarel: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Fondu final vers l'obscurité du début : la boucle ne coupe pas.
  const loopOut = interpolate(
    frame,
    [durationInFrames - T.loopFade, durationInFrames - 1],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.quad) },
  );

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.night.paper }}>
      <Backdrop />

      <AbsoluteFill style={{ opacity: loopOut }}>
        <Beam />
        <SecurityCamera />

        <Sequence from={T.badge.from} layout="none">
          <Badge />
        </Sequence>
        <Sequence from={T.headline1.from} layout="none">
          <HeadlineOne />
        </Sequence>
        <Sequence from={T.headline2.from} layout="none">
          <HeadlineTwo />
        </Sequence>
        <Sequence from={T.description.from} layout="none">
          <Description />
        </Sequence>

        <Products />

        <Sequence from={T.cta.from} layout="none">
          <Cta />
        </Sequence>
        <Sequence from={T.signature.from} layout="none">
          <Signature />
        </Sequence>
        <Sequence from={T.logo.from} layout="none">
          <Logo />
        </Sequence>

        <Sweep />
        {/* Voile de faisceau par-dessus le texte : le texte est DANS la lumière */}
        <Beam overlay />
      </AbsoluteFill>

      <Grain />
    </AbsoluteFill>
  );
};
