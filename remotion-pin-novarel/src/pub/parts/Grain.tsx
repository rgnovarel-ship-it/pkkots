import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { LAYOUT } from "../../brand";

/**
 * Grain photo. Deux passes : `multiply` mord surtout dans les ombres,
 * `overlay` réveille très légèrement les hautes lumières. Le motif est fixe,
 * c'est sa translation, dérivée de la frame, qui le fait vibrer.
 */
export const Grain: React.FC = () => {
  const frame = useCurrentFrame();
  const dx = (frame % 5) * 13 - 26;
  const dy = (frame % 7) * 11 - 33;

  const sheet = (blend: "multiply" | "overlay", opacity: number) => (
    <AbsoluteFill style={{ mixBlendMode: blend, opacity, pointerEvents: "none" }}>
      <svg width={LAYOUT.width} height={LAYOUT.height}>
        <defs>
          <filter id={`nv-grain-${blend}`} x="0" y="0" width="100%" height="100%">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.9"
              numOctaves={3}
              stitchTiles="stitch"
              result="noise"
            />
            <feColorMatrix
              in="noise"
              type="matrix"
              values="0 0 0 0 0.52 0 0 0 0 0.52 0 0 0 0 0.48 0 0 0 1 0"
            />
          </filter>
        </defs>
        <rect
          x={-60}
          y={-60}
          width={LAYOUT.width + 120}
          height={LAYOUT.height + 120}
          filter={`url(#nv-grain-${blend})`}
          transform={`translate(${dx} ${dy})`}
        />
      </svg>
    </AbsoluteFill>
  );

  return (
    <>
      {sheet("multiply", 0.1)}
      {sheet("overlay", 0.07)}
    </>
  );
};
