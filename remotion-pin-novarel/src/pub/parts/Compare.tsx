import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../../brand";
import { FONT_MONO } from "../../fonts";
import { COMPARE, MONTHS } from "../content";
import { siteEase } from "../motion";
import { Y } from "../positions";

/**
 * Le comparateur : douze cases contre une.
 *
 * Deux rangées strictement identiques, douze emplacements chacune. En haut,
 * l'abonnement mensuel les remplit tous, un par un, puis l'année recommence. En
 * bas, NOVAREL n'en remplit qu'une, et les onze autres restent vides pour
 * toujours. Rien à expliquer : on voit la différence avant de lire.
 *
 * Les leviers sont honnêtes — on montre l'année entière d'un coup au lieu du
 * « petit prix mensuel », et on met les deux modèles côte à côte. Aucun compte
 * à rebours, aucune rareté fabriquée, aucun montant inventé.
 */

const CELL = 52;
const GAP = 6;
const ROW_W = MONTHS.length * CELL + (MONTHS.length - 1) * GAP;

/** Un cycle = une année. 75 frames × 3 = 225 : la boucle tombe juste. */
const CYCLE = 75;
/** Écart entre deux cases qui s'allument. */
const STEP = 5;

export const COMPARE_H = 200;

export const Compare: React.FC = () => {
  const frame = useCurrentFrame();
  const cycle = frame % CYCLE;

  // L'année se vide d'un coup à la fin du cycle, puis tout recommence
  const clear = interpolate(cycle, [CYCLE - 9, CYCLE - 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: siteEase,
  });

  const fill = (index: number) =>
    interpolate(cycle, [index * STEP, index * STEP + STEP], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: siteEase,
    }) * clear;

  return (
    <div
      style={{
        position: "absolute",
        left: LAYOUT.gutter,
        top: Y.compare,
        width: LAYOUT.contentWidth,
      }}
    >
      <Row
        label={COMPARE.subscription.label}
        tally={COMPARE.subscription.tally}
        tone="ink"
        cells={MONTHS.map((month, i) => ({ text: month, level: fill(i) }))}
      />
      <div style={{ height: 26 }} />
      <Row
        label={COMPARE.oneShot.label}
        tally={COMPARE.oneShot.tally}
        tone="signal"
        cells={MONTHS.map((_, i) => ({ text: "", level: i === 0 ? 1 : 0 }))}
      />
    </div>
  );
};

const Row: React.FC<{
  label: string;
  tally: string;
  tone: "ink" | "signal";
  cells: { text: string; level: number }[];
}> = ({ label, tally, tone, cells }) => {
  const strong = tone === "signal";

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          width: ROW_W + 150,
          marginBottom: 10,
          fontFamily: FONT_MONO,
          fontWeight: strong ? 700 : 600,
          fontSize: 15,
          letterSpacing: 2,
          color: strong ? COLORS.ink : COLORS.muted,
        }}
      >
        <span>{label}</span>
        <span style={{ color: strong ? COLORS.ink : COLORS.inkSoft }}>{tally}</span>
      </div>

      <div style={{ display: "flex", gap: GAP }}>
        {cells.map((cell, i) => (
          <Cell key={i} text={cell.text} level={cell.level} tone={tone} />
        ))}
      </div>
    </div>
  );
};

const Cell: React.FC<{ text: string; level: number; tone: "ink" | "signal" }> = ({
  text,
  level,
  tone,
}) => {
  const filled = tone === "signal" ? COLORS.signal : COLORS.ink;
  const label = tone === "signal" ? COLORS.ink : COLORS.paper;

  return (
    <div
      style={{
        position: "relative",
        width: CELL,
        height: CELL,
        border: `1px solid ${alpha(COLORS.lineStrong, 0.85)}`,
        borderRadius: 3,
        overflow: "hidden",
      }}
    >
      {/* L'emplacement rempli : il apparaît par un coup de tampon */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: filled,
          opacity: level,
          transform: `scale(${interpolate(level, [0, 1], [0.78, 1])})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: FONT_MONO,
          fontWeight: 600,
          fontSize: 13,
          letterSpacing: 0.4,
          color: level > 0.5 ? label : alpha(COLORS.muted, 0.55),
        }}
      >
        {text}
      </div>
    </div>
  );
};
