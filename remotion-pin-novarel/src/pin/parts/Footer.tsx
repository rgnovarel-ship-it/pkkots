import React from "react";
import { alpha, COLORS, LAYOUT } from "../tokens";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { LOGO, SIGNATURE } from "../content";
import { Y } from "../positions";
import { Reveal } from "./Reveal";

/** Signature de marque. */
export const Signature: React.FC = () => (
  <Reveal
    duration={14}
    distance={16}
    style={{ position: "absolute", left: LAYOUT.gutter, top: Y.rule, width: LAYOUT.contentWidth }}
  >
    <div style={{ height: 1, background: alpha(COLORS.night.line, 1) }} />
    <div
      style={{
        marginTop: 22,
        fontFamily: FONT_SANS,
        fontWeight: 600,
        fontSize: 27,
        letterSpacing: -0.3,
        color: alpha(COLORS.night.ink, 0.78),
      }}
    >
      {SIGNATURE}
    </div>
  </Reveal>
);

/** Logo : carré arrondi + mot-marque en mono. */
export const Logo: React.FC = () => (
  <Reveal
    duration={14}
    distance={14}
    style={{ position: "absolute", left: LAYOUT.gutter, top: Y.logo }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
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
          color: COLORS.night.ink,
        }}
      >
        {LOGO.word}
      </span>
    </div>
  </Reveal>
);
