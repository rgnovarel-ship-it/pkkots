import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Arrivée standard : translation vers le haut + fondu, pilotée par spring().
 * À utiliser dans une <Sequence>, la frame y est déjà relative.
 */
export const Reveal: React.FC<{
  duration?: number;
  distance?: number;
  delay?: number;
  style?: React.CSSProperties;
  children: React.ReactNode;
}> = ({ duration = 16, distance = 28, delay = 0, style, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - delay,
    fps,
    config: { damping: 22, mass: 0.7, stiffness: 110 },
    durationInFrames: duration,
  });

  return (
    <div
      style={{
        ...style,
        opacity: interpolate(progress, [0, 0.45], [0, 1], { extrapolateRight: "clamp" }),
        transform: `translateY(${interpolate(progress, [0, 1], [distance, 0])}px)`,
      }}
    >
      {children}
    </div>
  );
};
