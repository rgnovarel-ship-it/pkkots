import React from "react";
import { useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../../brand";
import { FONT_MONO, FONT_SANS } from "../../fonts";
import { DESCRIPTION, EYEBROW, HEADLINE } from "../content";
import { revealOut } from "../motion";
import { Y } from "../positions";
import { T } from "../timing";

/**
 * Rangs de sortie : la cascade repart du bas, le bas s'en va en premier.
 * (Le logo, lui, ne sort jamais — il tient la dernière frame.)
 */
export const EXIT_RANK = {
  signature: 0,
  cta: 1,
  panel: 2,
  description: 5,
  headline3: 6,
  headline2: 7,
  headline1: 8,
  eyebrow: 9,
} as const;

/** Bloc de texte qui entre par le bas et ressort par le haut. */
export const Line: React.FC<{
  from: number;
  rank: number;
  top: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ from, rank, top, children, style }) => {
  const frame = useCurrentFrame();
  const { enter, leave } = revealOut(frame, from, rank);

  return (
    <div
      style={{
        position: "absolute",
        left: LAYOUT.gutter,
        width: LAYOUT.contentWidth,
        top,
        opacity: enter * (1 - leave),
        transform: `translateY(${(1 - enter) * 26 - leave * 22}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/** Sur-titre : le `.eyebrow` du site, carré signal compris. */
export const Eyebrow: React.FC = () => (
  <Line from={T.eyebrow} rank={EXIT_RANK.eyebrow} top={Y.eyebrow}>
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 12,
        fontFamily: FONT_MONO,
        fontWeight: 600,
        fontSize: 19,
        letterSpacing: 2.6,
        color: COLORS.muted,
      }}
    >
      <span style={{ width: 10, height: 10, background: COLORS.signal }} />
      {EYEBROW}
    </span>
  </Line>
);

const titleStyle: React.CSSProperties = {
  fontFamily: FONT_SANS,
  fontWeight: 800,
  fontSize: 70,
  lineHeight: 1.02,
  letterSpacing: -1.8,
  color: COLORS.ink,
  margin: 0,
};

export const HeadlineOne: React.FC = () => (
  <Line from={T.headline1} rank={EXIT_RANK.headline1} top={Y.headline}>
    <div style={titleStyle}>{HEADLINE.line1}</div>
  </Line>
);

/** Le `<mark>` du site : fond signal, encre dessus. */
export const HeadlineMark: React.FC = () => (
  <Line from={T.headline2} rank={EXIT_RANK.headline2} top={Y.headline + 78}>
    <div style={titleStyle}>
      <span
        style={{
          display: "inline-block",
          background: COLORS.signal,
          color: COLORS.ink,
          padding: "4px 14px 10px",
          boxShadow: `0 10px 26px -18px ${alpha(COLORS.inkSoft, 0.9)}`,
        }}
      >
        {HEADLINE.mark}
      </span>
    </div>
  </Line>
);

/** La chute, plus basse en hiérarchie : c'est une remarque, pas un cri. */
export const HeadlineTurn: React.FC = () => (
  <Line from={T.headline3} rank={EXIT_RANK.headline3} top={Y.headline + 176}>
    <div
      style={{
        fontFamily: FONT_SANS,
        fontWeight: 600,
        fontSize: 42,
        lineHeight: 1.1,
        letterSpacing: -0.8,
        color: COLORS.inkSoft,
      }}
    >
      {HEADLINE.line3}
    </div>
  </Line>
);

export const Description: React.FC = () => (
  <Line from={T.description} rank={EXIT_RANK.description} top={Y.description}>
    <p
      style={{
        margin: 0,
        maxWidth: 790,
        fontFamily: FONT_SANS,
        fontWeight: 500,
        fontSize: 24,
        lineHeight: 1.5,
        color: COLORS.muted,
      }}
    >
      {DESCRIPTION}
    </p>
  </Line>
);
