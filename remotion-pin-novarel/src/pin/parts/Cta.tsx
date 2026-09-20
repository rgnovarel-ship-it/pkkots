import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { alpha, COLORS, LAYOUT } from "../tokens";
import { FONT_SANS } from "../fonts";
import { CTA } from "../content";
import { Y } from "../positions";
import { T } from "../timing";

/** Bouton d'action : arrivée en spring, puis pulsation douce et continue. */
export const Cta: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entry = spring({
    frame,
    fps,
    config: { damping: 16, mass: 0.6, stiffness: 120 },
    durationInFrames: T.cta.duration,
  });

  const pulse = Math.sin(
    (Math.max(0, frame - T.cta.duration) / T.ctaPulsePeriod) * Math.PI * 2,
  );
  const scale = interpolate(entry, [0, 1], [0.93, 1]) * (1 + 0.012 * pulse);
  const glow = 0.28 + 0.16 * (pulse * 0.5 + 0.5);

  return (
    <div
      style={{
        position: "absolute",
        left: LAYOUT.gutter,
        top: Y.cta,
        opacity: interpolate(entry, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
        transform: `translateY(${interpolate(entry, [0, 1], [24, 0])}px) scale(${scale})`,
        transformOrigin: "left center",
      }}
    >
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          height: 92,
          padding: "0 44px",
          background: COLORS.signal,
          borderRadius: 4,
          boxShadow: `0 18px 50px -18px ${alpha(COLORS.signal, glow)}`,
          fontFamily: FONT_SANS,
          fontWeight: 700,
          fontSize: 34,
          letterSpacing: -0.4,
          color: COLORS.ink,
        }}
      >
        {CTA}
      </div>
    </div>
  );
};
