import React from "react";
import { useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../tokens";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { BADGE, DESCRIPTION, HEADLINE } from "../content";
import { Y } from "../positions";
import { T } from "../timing";
import { Reveal } from "./Reveal";

const block: React.CSSProperties = {
  position: "absolute",
  left: LAYOUT.gutter,
  width: LAYOUT.contentWidth,
};

/** Pastille du haut. Le seul vert ici : le point. */
export const Badge: React.FC = () => {
  const frame = useCurrentFrame();
  // Le point respire avec le voyant de la caméra
  const pulse = 0.7 + 0.3 * Math.sin((frame / (T.led.period * 2)) * Math.PI * 2);

  return (
    <Reveal style={{ ...block, top: Y.badge }} distance={16} duration={14}>
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 12,
          padding: "11px 20px 10px",
          border: `1px solid ${alpha(COLORS.night.line, 1)}`,
          background: alpha(COLORS.night.surface, 0.72),
          borderRadius: 4,
        }}
      >
        <span
          style={{
            width: 9,
            height: 9,
            borderRadius: "50%",
            background: COLORS.signal,
            opacity: pulse,
            boxShadow: `0 0 12px ${alpha(COLORS.signal, 0.6 * pulse)}`,
          }}
        />
        <span
          style={{
            fontFamily: FONT_MONO,
            fontWeight: 600,
            fontSize: 19,
            letterSpacing: 2.4,
            color: COLORS.night.ink,
          }}
        >
          {BADGE}
        </span>
      </div>
    </Reveal>
  );
};

const headlineStyle: React.CSSProperties = {
  fontFamily: FONT_SANS,
  fontWeight: 800,
  fontSize: 84,
  lineHeight: 1.02,
  letterSpacing: -2,
  color: COLORS.night.ink,
  textShadow: `0 10px 40px ${alpha("#000000", 0.45)}`,
};

/** Titre, ligne 1. « une fois » en couleur signal. */
export const HeadlineOne: React.FC = () => (
  <Reveal style={{ ...block, top: Y.headline }} distance={34} duration={18}>
    <div style={headlineStyle}>
      {HEADLINE.line1.before}
      <span style={{ color: COLORS.signal }}>{HEADLINE.line1.accent}</span>
      {HEADLINE.line1.after}
    </div>
  </Reveal>
);

/** Titre, ligne 2. */
export const HeadlineTwo: React.FC = () => (
  <Reveal style={{ ...block, top: Y.headline + 88 }} distance={34} duration={18}>
    <div style={headlineStyle}>{HEADLINE.line2}</div>
  </Reveal>
);

/** Texte de description. */
export const Description: React.FC = () => (
  <Reveal style={{ ...block, top: Y.description }} distance={20} duration={15}>
    <p
      style={{
        margin: 0,
        fontFamily: FONT_SANS,
        fontWeight: 500,
        fontSize: 25,
        lineHeight: 1.46,
        color: alpha(COLORS.night.ink, 0.86),
        maxWidth: 780,
      }}
    >
      {DESCRIPTION[0]}
    </p>
    <p
      style={{
        margin: "10px 0 0",
        fontFamily: FONT_SANS,
        fontWeight: 500,
        fontSize: 25,
        lineHeight: 1.46,
        color: COLORS.night.muted,
        maxWidth: 780,
      }}
    >
      {DESCRIPTION[1]}
    </p>
  </Reveal>
);
