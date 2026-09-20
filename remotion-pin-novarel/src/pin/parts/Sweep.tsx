import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../tokens";
import { T } from "../timing";

/**
 * Bande lumineuse qui traverse le cadre pendant le maintien.
 * Elle entre et sort hors champ : rien ne coupe à la boucle.
 */
export const Sweep: React.FC = () => {
  const frame = useCurrentFrame();
  const end = T.sweep.from + T.sweep.duration;

  const progress = interpolate(frame, [T.sweep.from, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });
  const opacity = interpolate(
    frame,
    [T.sweep.from, T.sweep.from + 12, end - 16, end],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const travel = interpolate(progress, [0, 1], [-820, LAYOUT.height + 520]);

  return (
    <AbsoluteFill style={{ opacity, mixBlendMode: "screen", pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: -300,
          top: travel,
          width: LAYOUT.width + 600,
          height: 260,
          transform: "rotate(-14deg)",
          background: `linear-gradient(180deg, transparent 0%, ${alpha(
            COLORS.paper,
            0.05,
          )} 38%, ${alpha(COLORS.paper, 0.11)} 50%, ${alpha(
            COLORS.paper,
            0.05,
          )} 62%, transparent 100%)`,
          filter: "blur(18px)",
        }}
      />
    </AbsoluteFill>
  );
};
