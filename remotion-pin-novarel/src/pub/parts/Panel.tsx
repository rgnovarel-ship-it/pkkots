import React from "react";
import { Sequence, useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../../brand";
import { FONT_MONO, FONT_SANS } from "../../fonts";
import { PANEL_TITLE, PRODUCTS, type Product } from "../content";
import { revealOut } from "../motion";
import { Y } from "../positions";
import { T } from "../timing";
import { EXIT_RANK } from "./Copy";

const HEADER_H = 54;
const FEATURED_H = 108;
const ROW_H = 86;

/**
 * Le panneau comparatif : c'est le `.hero__panel` du site — cadre sur surface,
 * barre d'en-tête avec un point à droite, lignes séparées par des filets, nom à
 * gauche, prix et flèche à droite. Pas trois cartes identiques : la ligne
 * « meilleur choix » est la seule à porter un liseré et une pastille.
 */
export const Panel: React.FC = () => {
  const frame = useCurrentFrame();
  const { enter, leave } = revealOut(frame, T.panel, EXIT_RANK.panel);

  return (
    <div
      style={{
        position: "absolute",
        left: LAYOUT.gutter,
        top: Y.panel,
        width: LAYOUT.contentWidth,
        background: COLORS.surface,
        border: `1px solid ${COLORS.line}`,
        borderRadius: 4,
        boxShadow: `0 14px 34px -22px ${alpha(COLORS.ink, 0.55)}`,
        opacity: enter * (1 - leave),
        transform: `translateY(${(1 - enter) * 30 - leave * 22}px)`,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          height: HEADER_H,
          padding: "0 22px",
          borderBottom: `1px solid ${COLORS.line}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontFamily: FONT_MONO,
          fontWeight: 600,
          fontSize: 14,
          letterSpacing: 2,
          color: COLORS.muted,
        }}
      >
        <span>{PANEL_TITLE}</span>
        <span style={{ width: 9, height: 9, borderRadius: "50%", background: COLORS.signal }} />
      </div>

      {PRODUCTS.map((product, index) => (
        <Sequence
          key={product.name}
          from={T.panel + index * T.panelStagger}
          layout="none"
        >
          <Row product={product} index={index} featured={index === 0} />
        </Sequence>
      ))}
    </div>
  );
};

const Arrow: React.FC = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden>
    <path
      d="M7 17 L17 7 M9 7 h8 v8"
      stroke={COLORS.muted}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const Row: React.FC<{ product: Product; index: number; featured: boolean }> = ({
  product,
  index,
  featured,
}) => {
  const frame = useCurrentFrame();
  // Frame relative à la <Sequence> : chaque ligne arrive après la précédente
  const slide = Math.min(1, Math.max(0, frame / T.enter));
  const last = index === PRODUCTS.length - 1;

  return (
    <div
      style={{
        height: featured ? FEATURED_H : ROW_H,
        boxSizing: "border-box",
        padding: featured ? "16px 22px 16px 24px" : "0 22px 0 24px",
        borderBottom: last ? "none" : `1px solid ${COLORS.line}`,
        borderLeft: featured ? `3px solid ${COLORS.signal}` : "3px solid transparent",
        background: featured ? alpha(COLORS.signal, 0.08) : "transparent",
        display: "flex",
        flexDirection: featured ? "column" : "row",
        alignItems: featured ? "stretch" : "center",
        justifyContent: featured ? "space-between" : "space-between",
        opacity: slide,
        transform: `translateX(${(1 - slide) * 18}px)`,
      }}
    >
      {featured ? (
        <>
          <span
            style={{
              alignSelf: "flex-start",
              fontFamily: FONT_MONO,
              fontWeight: 700,
              fontSize: 13,
              letterSpacing: 1.8,
              color: COLORS.ink,
              background: COLORS.signal,
              padding: "4px 9px 3px",
              borderRadius: 3,
            }}
          >
            {product.tag}
          </span>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
            <span
              style={{
                fontFamily: FONT_SANS,
                fontWeight: 700,
                fontSize: 30,
                letterSpacing: -0.5,
                color: COLORS.ink,
              }}
            >
              {product.name}
            </span>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 12,
                fontFamily: FONT_MONO,
                fontWeight: 700,
                fontSize: 24,
                color: COLORS.ink,
              }}
            >
              {product.price}
              <Arrow />
            </span>
          </div>
        </>
      ) : (
        <>
          <span
            style={{
              fontFamily: FONT_SANS,
              fontWeight: 600,
              fontSize: 27,
              letterSpacing: -0.3,
              color: COLORS.inkSoft,
            }}
          >
            {product.name}
          </span>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 12,
              fontFamily: FONT_MONO,
              fontWeight: 500,
              fontSize: 22,
              color: COLORS.muted,
            }}
          >
            {product.price}
            <Arrow />
          </span>
        </>
      )}
    </div>
  );
};
