import React from "react";
import { Sequence } from "remotion";
import { alpha, COLORS, LAYOUT } from "../tokens";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { PRODUCTS, type Product } from "../content";
import { Y } from "../positions";
import { T } from "../timing";
import { Reveal } from "./Reveal";

const FEATURED_H = 122;
const ROW_H = 80;
const GAP = 14;

const rowTop = (index: number) =>
  index === 0 ? 0 : FEATURED_H + GAP + (index - 1) * (ROW_H + GAP);

/**
 * Les trois produits comparés.
 * Hiérarchie assumée : la ligne « meilleur choix » est traitée différemment,
 * les deux autres restent des lignes de tableau. Pas trois cartes identiques.
 */
export const Products: React.FC = () => (
  <div
    style={{
      position: "absolute",
      left: LAYOUT.gutter,
      top: Y.products,
      width: LAYOUT.contentWidth,
    }}
  >
    {PRODUCTS.map((product, index) => (
      <Sequence
        key={product.name}
        from={T.products.from + index * T.products.stagger}
        layout="none"
      >
        <Reveal
          duration={T.products.duration}
          distance={22}
          style={{ position: "absolute", top: rowTop(index), left: 0, right: 0 }}
        >
          {index === 0 ? <Featured product={product} /> : <Row product={product} />}
        </Reveal>
      </Sequence>
    ))}
  </div>
);

const Featured: React.FC<{ product: Product }> = ({ product }) => (
  <div
    style={{
      height: FEATURED_H,
      boxSizing: "border-box",
      padding: "16px 24px 16px 26px",
      borderLeft: `3px solid ${COLORS.signal}`,
      background: `linear-gradient(90deg, ${alpha(COLORS.signal, 0.09)} 0%, ${alpha(
        COLORS.night.surface,
        0.7,
      )} 55%, ${alpha(COLORS.night.surface, 0.3)} 100%)`,
      display: "flex",
      flexDirection: "column",
      justifyContent: "space-between",
    }}
  >
    <span
      style={{
        alignSelf: "flex-start",
        fontFamily: FONT_MONO,
        fontWeight: 700,
        fontSize: 14,
        letterSpacing: 2,
        color: COLORS.ink,
        background: COLORS.signal,
        padding: "4px 10px 3px",
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
          fontSize: 34,
          letterSpacing: -0.6,
          color: COLORS.night.ink,
        }}
      >
        {product.name}
      </span>
      <span
        style={{
          fontFamily: FONT_MONO,
          fontWeight: 700,
          fontSize: 27,
          color: COLORS.night.ink,
        }}
      >
        {product.price}
      </span>
    </div>
  </div>
);

const Row: React.FC<{ product: Product }> = ({ product }) => (
  <div
    style={{
      height: ROW_H,
      boxSizing: "border-box",
      padding: "0 24px 0 26px",
      borderLeft: `3px solid ${alpha(COLORS.night.line, 1)}`,
      borderBottom: `1px solid ${alpha(COLORS.night.line, 0.9)}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
    }}
  >
    <span
      style={{
        fontFamily: FONT_SANS,
        fontWeight: 600,
        fontSize: 29,
        letterSpacing: -0.3,
        color: alpha(COLORS.night.ink, 0.9),
      }}
    >
      {product.name}
    </span>
    <span
      style={{
        fontFamily: FONT_MONO,
        fontWeight: 500,
        fontSize: 24,
        color: COLORS.night.muted,
      }}
    >
      {product.price}
    </span>
  </div>
);
