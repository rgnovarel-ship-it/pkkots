import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../../brand";
import { FONT_MONO, FONT_SANS } from "../../fonts";
import { DESCRIPTION, EYEBROW, HEADLINE } from "../content";
import { revealOut, siteEase } from "../motion";
import { Y } from "../positions";
import { T } from "../timing";

/**
 * Rangs de sortie : la cascade repart du bas, le bas s'en va en premier.
 * (Le bandeau, le sur-titre et le logo ne sortent jamais — ils tiennent la
 * première et la dernière frame.)
 */
export const EXIT_RANK = {
  signature: 0,
  cta: 1,
  panel: 2,
  description: 5,
  headline3: 6,
  headline2: 7,
  headline1: 8,
} as const;

/**
 * Révélation au masque : le texte glisse derrière un cadre qui le coupe net,
 * il ne « s'allume » pas en fondu. C'est le geste d'affiche imprimée, et c'est
 * ce qui distingue une animation soignée d'un fondu générique.
 */
const MaskLine: React.FC<{
  from: number;
  rank: number;
  top: number;
  height: number;
  children: React.ReactNode;
}> = ({ from, rank, top, height, children }) => {
  const frame = useCurrentFrame();
  const { enter, leave } = revealOut(frame, from, rank);
  const y = (1 - enter) * height - leave * height;

  return (
    <div
      style={{
        position: "absolute",
        left: LAYOUT.gutter,
        width: LAYOUT.contentWidth,
        top,
        height,
        overflow: "hidden",
      }}
    >
      <div style={{ transform: `translateY(${y}px)` }}>{children}</div>
    </div>
  );
};

/** Bloc qui arrive en fondu et translation — pour ce qui n'est pas le titre. */
export const Line: React.FC<{
  from: number;
  rank: number;
  top: number;
  children: React.ReactNode;
}> = ({ from, rank, top, children }) => {
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
        transform: `translateY(${(1 - enter) * 24 - leave * 20}px)`,
      }}
    >
      {children}
    </div>
  );
};

/** Sur-titre : le `.eyebrow` du site, carré signal compris. Permanent. */
export const Eyebrow: React.FC = () => (
  <div
    style={{
      position: "absolute",
      left: LAYOUT.gutter,
      top: Y.eyebrow,
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
  </div>
);

const titleStyle: React.CSSProperties = {
  fontFamily: FONT_SANS,
  fontWeight: 800,
  fontSize: 76,
  lineHeight: 1,
  letterSpacing: -2,
  color: COLORS.ink,
  margin: 0,
};

export const HeadlineOne: React.FC = () => (
  <MaskLine from={T.headline1} rank={EXIT_RANK.headline1} top={Y.headline} height={92}>
    <div style={{ ...titleStyle, paddingTop: 8 }}>{HEADLINE.line1}</div>
  </MaskLine>
);

/**
 * La ligne surlignée : le `<mark>` du site. Le bloc signal se déroule d'abord
 * depuis la gauche, le mot monte ensuite derrière le masque. Deux temps.
 */
export const HeadlineMark: React.FC = () => {
  const frame = useCurrentFrame();
  const wipe = interpolate(frame, [T.headline2, T.headline2 + T.enter], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: siteEase,
  });

  return (
    <MaskLine
      from={T.headline2 + 6}
      rank={EXIT_RANK.headline2}
      top={Y.headline + 96}
      height={104}
    >
      <div style={{ ...titleStyle, position: "relative", paddingTop: 10 }}>
        <span style={{ position: "relative", display: "inline-block" }}>
          <span
            style={{
              position: "absolute",
              inset: "-8px -14px -14px -14px",
              background: COLORS.signal,
              transform: `scaleX(${wipe})`,
              transformOrigin: "left center",
              boxShadow: `0 12px 30px -22px ${alpha(COLORS.inkSoft, 0.9)}`,
            }}
          />
          <span style={{ position: "relative" }}>{HEADLINE.mark}</span>
        </span>
      </div>
    </MaskLine>
  );
};

/** La chute, plus basse en hiérarchie : c'est une remarque, pas un cri. */
export const HeadlineTurn: React.FC = () => (
  <MaskLine from={T.headline3} rank={EXIT_RANK.headline3} top={Y.headline + 206} height={64}>
    <div
      style={{
        fontFamily: FONT_SANS,
        fontWeight: 600,
        fontSize: 42,
        lineHeight: 1.12,
        letterSpacing: -0.8,
        color: COLORS.inkSoft,
        paddingTop: 4,
      }}
    >
      {HEADLINE.line3}
    </div>
  </MaskLine>
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
