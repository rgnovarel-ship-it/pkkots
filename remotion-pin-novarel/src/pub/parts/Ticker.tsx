import React from "react";
import { useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../../brand";
import { FONT_MONO } from "../../fonts";
import { MONTHS } from "../content";
import { Y } from "../positions";
import { DURATION } from "../timing";

/**
 * Le bandeau des mois.
 *
 * C'est le visuel principal de l'épingle : plus d'objet dessiné, un geste
 * typographique. Les douze mois défilent en continu sur un aplat d'encre — le
 * prélèvement mensuel qui ne s'arrête jamais. Le titre répond juste en dessous.
 *
 * Boucle : chaque cellule a une largeur fixe, donc le motif se répète
 * exactement tous les 12 × CELL pixels. On translate d'un cycle entier sur la
 * durée totale : le raccord est mathématiquement invisible.
 */

/** Largeur d'une cellule « mois ». Fixe, pour que le cycle soit exact. */
const CELL = 190;
const CYCLE = MONTHS.length * CELL;
/** Hauteur du bandeau. */
export const BAND_H = 168;

export const Ticker: React.FC = () => {
  const frame = useCurrentFrame();
  const offset = -((frame / DURATION) * CYCLE);

  const strip = (key: string) => (
    <div key={key} style={{ display: "flex", flexShrink: 0 }}>
      {MONTHS.map((month) => (
        <div
          key={month}
          style={{
            width: CELL,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontFamily: FONT_MONO,
            fontWeight: 600,
            fontSize: 24,
            letterSpacing: 1.6,
            color: COLORS.paper,
          }}
        >
          <span>{month}</span>
          <span style={{ color: alpha(COLORS.paper, 0.35) }}>·</span>
        </div>
      ))}
    </div>
  );

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        top: Y.band,
        width: LAYOUT.width,
        height: BAND_H,
        background: COLORS.ink,
        overflow: "hidden",
      }}
    >
      {/* Les mois qui défilent, avec les bords fondus */}
      <div
        style={{
          position: "absolute",
          top: 54,
          height: 40,
          display: "flex",
          transform: `translateX(${offset}px)`,
          maskImage: `linear-gradient(90deg, transparent 0%, #000 12%, #000 88%, transparent 100%)`,
          WebkitMaskImage: `linear-gradient(90deg, transparent 0%, #000 12%, #000 88%, transparent 100%)`,
        }}
      >
        {["a", "b", "c"].map(strip)}
      </div>

      {/* Filets du bandeau : un en haut discret, un en signal en bas */}
      <div
        style={{
          position: "absolute",
          inset: "0 0 auto 0",
          height: 1,
          background: alpha(COLORS.paper, 0.18),
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: "auto 0 0 0",
          height: 4,
          background: COLORS.signal,
        }}
      />
    </div>
  );
};
