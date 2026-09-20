import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { LAYOUT } from "../tokens";

/**
 * Grain léger en surimpression. Le motif est fixe (déterministe) : c'est sa
 * translation, dérivée de la frame, qui le fait vibrer.
 */
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.16 }) => {
  const frame = useCurrentFrame();
  const dx = (frame % 5) * 13 - 26;
  const dy = (frame % 7) * 11 - 33;

  return (
    <AbsoluteFill style={{ opacity, mixBlendMode: "overlay", pointerEvents: "none" }}>
      <svg width={LAYOUT.width} height={LAYOUT.height}>
        <defs>
          <filter id="nv-grain" x="0" y="0" width="100%" height="100%">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.85"
              numOctaves={3}
              stitchTiles="stitch"
              result="noise"
            />
            <feColorMatrix
              in="noise"
              type="matrix"
              values="0 0 0 0 0.55 0 0 0 0 0.55 0 0 0 0 0.5 0 0 0 1 0"
            />
          </filter>
        </defs>
        <rect
          x={-60}
          y={-60}
          width={LAYOUT.width + 120}
          height={LAYOUT.height + 120}
          filter="url(#nv-grain)"
          transform={`translate(${dx} ${dy})`}
        />
      </svg>
    </AbsoluteFill>
  );
};
