import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { alpha, COLORS } from "../tokens";
import { T } from "../timing";

/**
 * Deux températures de lumière :
 *  - une source chaude (éclairage extérieur de maison) en haut à droite,
 *    derrière la caméra, qui « respire » ;
 *  - une ambiance nuit froide, plus verte/olive, en bas à gauche.
 * Plus une vignette, pour éviter l'aplat numérique.
 */
export const Backdrop: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // La lumière monte dans la scène au tout début
  const rise = interpolate(
    frame,
    [T.lightRise.from, T.lightRise.from + T.lightRise.duration],
    [0.12, 1],
    { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) },
  );

  // Respiration lente, dérivée du temps Remotion (jamais d'animation CSS)
  const breath = 0.88 + 0.12 * Math.sin((frame / T.breathPeriod) * Math.PI * 2);

  // Fin = état du début : la lumière redescend au même niveau qu'à la frame 0,
  // la boucle se referme sans coupure.
  const fall = interpolate(
    frame,
    [durationInFrames - T.loopFade, durationInFrames - 1],
    [1, 0.12],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.quad) },
  );
  const warm = rise * breath * fall;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.night.paper }}>
      {/* Nuit froide : les ombres tirent vers le vert profond, pas vers le noir */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(130% 95% at 4% 92%, ${alpha(
            COLORS.good,
            0.2,
          )} 0%, ${alpha(COLORS.good, 0.08)} 42%, transparent 78%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `linear-gradient(200deg, transparent 30%, ${alpha(
            COLORS.night.surface,
            0.9,
          )} 100%)`,
        }}
      />
      {/* Halo chaud principal : l'éclairage extérieur, derrière la caméra */}
      <AbsoluteFill
        style={{
          opacity: warm,
          mixBlendMode: "screen",
          background: `radial-gradient(66% 40% at 66% 6%, ${alpha(
            COLORS.warnBg,
            0.4,
          )} 0%, ${alpha(COLORS.warnBg, 0.15)} 28%, ${alpha(
            COLORS.warn,
            0.13,
          )} 52%, ${alpha(COLORS.warn, 0.05)} 70%, transparent 88%)`,
        }}
      />
      {/* Nappe chaude large : la profondeur vient de là */}
      <AbsoluteFill
        style={{
          opacity: warm * 0.85,
          mixBlendMode: "screen",
          background: `radial-gradient(115% 66% at 86% 0%, ${alpha(
            COLORS.warnBg,
            0.12,
          )} 0%, ${alpha(COLORS.warn, 0.085)} 36%, transparent 76%)`,
        }}
      />
      {/* Sol de lumière sous le bloc texte, là où le faisceau retombe */}
      <AbsoluteFill
        style={{
          opacity: rise,
          mixBlendMode: "screen",
          background: `radial-gradient(72% 28% at 34% 62%, ${alpha(
            COLORS.warnBg,
            0.085,
          )} 0%, transparent 70%)`,
        }}
      />
      {/* Vignette */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(82% 62% at 52% 40%, transparent 58%, ${alpha(
            "#000000",
            0.42,
          )} 100%)`,
        }}
      />
      {/* Filet intérieur « dossier technique » */}
      <AbsoluteFill
        style={{
          margin: 30,
          border: `1px solid ${alpha(COLORS.paper, 0.1)}`,
          opacity:
            interpolate(frame, [0, fps], [0, 1], { extrapolateRight: "clamp" }) * fall,
        }}
      />
    </AbsoluteFill>
  );
};
