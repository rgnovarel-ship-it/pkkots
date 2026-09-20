import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../../brand";
import { loopWave, seeded } from "../motion";
import { DURATION } from "../timing";

/**
 * Le mur et sa lumière.
 *
 * Une seule source : un soleil bas, hors champ en haut à droite. Tout le reste
 * en découle — le côté éclairé des objets, la direction des ombres, la zone
 * froide en bas à gauche. Un rai de lumière traverse le cadre, une ombre de
 * fenêtre glisse lentement sur le mur, de la poussière dérive dans le rai.
 *
 * Tout est périodique sur la durée totale : l'image de fin est celle du début.
 */

/** Source lumineuse, hors cadre. */
const SUN = { x: 1150, y: -260 };
/** Axe du rai et son ouverture (degrés). */
const SHAFT = { heading: 128.1, spread: 9, reach: 2300 };

const rayPoint = (deg: number) => {
  const rad = (deg * Math.PI) / 180;
  return `${SUN.x + SHAFT.reach * Math.cos(rad)},${SUN.y + SHAFT.reach * Math.sin(rad)}`;
};

const SHAFT_POLY = [
  `${SUN.x},${SUN.y}`,
  rayPoint(SHAFT.heading - SHAFT.spread),
  rayPoint(SHAFT.heading + SHAFT.spread),
].join(" ");

/** Poussière : positions tirées d'un seed fixe, dérive qui reboucle sur la durée. */
const DUST = (() => {
  const rand = seeded(20260219);
  return Array.from({ length: 46 }, () => ({
    x: 120 + rand() * 1000,
    y: -160 + rand() * 1500,
    r: 1.2 + rand() * 2.4,
    phase: rand(),
    speed: 90 + rand() * 210,
    opacity: 0.22 + rand() * 0.42,
  }));
})();

export const Wall: React.FC = () => {
  const frame = useCurrentFrame();

  // Dérive lente de l'ombre de fenêtre : le soleil bouge, pas le mur
  const drift = loopWave(frame);
  const shadowX = -18 + drift * 36;
  const shadowY = 6 + drift * 22;

  // Respiration très faible de l'intensité, comme un ciel qui varie
  const light = 0.9 + 0.1 * loopWave(frame, Math.PI * 0.5);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.paper }}>
      {/* Le mur : plus clair et plus chaud près de la source, plus froid à l'opposé */}
      <AbsoluteFill
        style={{
          background: `linear-gradient(218deg, ${COLORS.surface} 0%, ${COLORS.paper} 42%, ${COLORS.surface2} 78%, ${alpha(
            COLORS.lineStrong,
            0.55,
          )} 100%)`,
        }}
      />
      {/* Nappe chaude là où le soleil frappe le mur */}
      <AbsoluteFill
        style={{
          opacity: light,
          background: `radial-gradient(70% 42% at 92% -6%, ${alpha(
            COLORS.warnBg,
            0.95,
          )} 0%, ${alpha(COLORS.warnBg, 0.42)} 34%, transparent 72%)`,
        }}
      />
      {/* Zone d'ombre, plus froide, en bas à gauche */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(85% 55% at 2% 104%, ${alpha(
            COLORS.inkSoft,
            0.16,
          )} 0%, ${alpha(COLORS.inkSoft, 0.05)} 46%, transparent 78%)`,
        }}
      />

      <svg
        width={LAYOUT.width}
        height={LAYOUT.height}
        viewBox={`0 0 ${LAYOUT.width} ${LAYOUT.height}`}
        style={{ position: "absolute", inset: 0 }}
      >
        <defs>
          <filter id="nv-window-blur" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="15" />
          </filter>
          <filter id="nv-shaft-blur" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="34" />
          </filter>
          <linearGradient
            id="nv-shaft"
            gradientUnits="userSpaceOnUse"
            x1={SUN.x}
            y1={SUN.y}
            x2={SUN.x - 880}
            y2={SUN.y + 1320}
          >
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.85" />
            <stop offset="34%" stopColor={COLORS.warnBg} stopOpacity="0.55" />
            <stop offset="78%" stopColor={COLORS.warnBg} stopOpacity="0.18" />
            <stop offset="100%" stopColor={COLORS.warnBg} stopOpacity="0" />
          </linearGradient>
          <clipPath id="nv-shaft-clip">
            <polygon points={SHAFT_POLY} />
          </clipPath>
        </defs>

        {/* Ombre portée d'une fenêtre : quatre carreaux, très flous, qui glissent */}
        <g
          filter="url(#nv-window-blur)"
          opacity={0.9}
          transform={`translate(${shadowX} ${shadowY}) rotate(-11 480 160) skewX(-15)`}
        >
          {[0, 1, 2].map((col) =>
            [0, 1].map((row) => (
              <rect
                key={`${col}-${row}`}
                x={210 + col * 272}
                y={-140 + row * 322}
                width={240}
                height={290}
                rx={5}
                fill={alpha(COLORS.inkSoft, 0.13)}
              />
            )),
          )}
        </g>

        {/* Le rai de lumière */}
        <polygon points={SHAFT_POLY} fill="url(#nv-shaft)" filter="url(#nv-shaft-blur)" opacity={light} />

        {/* Poussière en suspension, uniquement dans le rai */}
        <g clipPath="url(#nv-shaft-clip)">
          {DUST.map((d, i) => {
            const t = (frame / DURATION + d.phase) % 1;
            return (
              <circle
                key={i}
                cx={d.x - t * d.speed * 0.8}
                cy={d.y + t * d.speed}
                r={d.r}
                fill="#ffffff"
                opacity={d.opacity * Math.sin(Math.PI * t)}
              />
            );
          })}
        </g>
      </svg>

      {/* Vignette légère, jamais noire : c'est un mur clair */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(84% 64% at 56% 42%, transparent 60%, ${alpha(
            COLORS.inkSoft,
            0.16,
          )} 100%)`,
        }}
      />
    </AbsoluteFill>
  );
};
