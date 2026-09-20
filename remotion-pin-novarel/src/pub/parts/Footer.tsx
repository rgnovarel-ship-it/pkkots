import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../../brand";
import { FONT_MONO, FONT_SANS } from "../../fonts";
import { CTA, LOGO, SIGNATURE } from "../content";
import { revealOut, siteEase } from "../motion";
import { Y } from "../positions";
import { T } from "../timing";
import { EXIT_RANK, Line } from "./Copy";

/** Bouton `.btn--signal` : arrivée, puis pulsation douce et continue. */
export const Cta: React.FC = () => {
  const frame = useCurrentFrame();
  const { enter, leave } = revealOut(frame, T.cta, EXIT_RANK.cta);

  const pulse = Math.sin((Math.max(0, frame - T.cta) / T.ctaPulse) * Math.PI * 2);
  const scale = interpolate(enter, [0, 1], [0.94, 1], { easing: siteEase }) * (1 + 0.011 * pulse);

  return (
    <div
      style={{
        position: "absolute",
        left: LAYOUT.gutter,
        top: Y.cta,
        opacity: enter * (1 - leave),
        transform: `translateY(${(1 - enter) * 26 - leave * 22}px) scale(${scale})`,
        transformOrigin: "left center",
      }}
    >
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          height: 88,
          padding: "0 42px",
          background: COLORS.signal,
          borderRadius: 4,
          boxShadow: `0 16px 40px -20px ${alpha(COLORS.ink, 0.65 + 0.15 * pulse)}`,
          fontFamily: FONT_SANS,
          fontWeight: 700,
          fontSize: 32,
          letterSpacing: -0.4,
          color: COLORS.ink,
        }}
      >
        {CTA}
      </div>
    </div>
  );
};

export const Signature: React.FC = () => (
  <Line from={T.signature} rank={EXIT_RANK.signature} top={Y.signature}>
    <div style={{ height: 1, background: COLORS.line }} />
    <div
      style={{
        marginTop: 20,
        fontFamily: FONT_SANS,
        fontWeight: 600,
        fontSize: 26,
        letterSpacing: -0.3,
        color: COLORS.inkSoft,
      }}
    >
      {SIGNATURE}
    </div>
  </Line>
);

/**
 * Le logo ne bouge pas et ne sort jamais : il est là à la première comme à la
 * dernière frame. C'est lui qui garantit qu'une vignette prise n'importe où
 * porte la marque.
 */
export const Logo: React.FC = () => (
  <div
    style={{
      position: "absolute",
      left: LAYOUT.gutter,
      top: Y.logo,
      display: "flex",
      alignItems: "center",
      gap: 14,
    }}
  >
    <div
      style={{
        width: 44,
        height: 44,
        borderRadius: 9,
        background: COLORS.signal,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: FONT_SANS,
        fontWeight: 800,
        fontSize: 27,
        color: COLORS.ink,
      }}
    >
      {LOGO.mark}
    </div>
    <span
      style={{
        fontFamily: FONT_MONO,
        fontWeight: 700,
        fontSize: 30,
        letterSpacing: 4,
        color: COLORS.ink,
      }}
    >
      {LOGO.word}
    </span>
  </div>
);
