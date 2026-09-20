import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../tokens";
import { T } from "../timing";
import { LENS_PAGE } from "./SecurityCamera";

/** Ouverture du faisceau, en degrés. */
const SPREAD = 17;
/** Direction du faisceau : vers le bas à gauche. */
const HEADING = 108;
const REACH = 1750;

const edge = (deg: number) => {
  const rad = (deg * Math.PI) / 180;
  return `${LENS_PAGE.x + REACH * Math.cos(rad)},${LENS_PAGE.y + REACH * Math.sin(rad)}`;
};

const cone = (spread: number) =>
  `${LENS_PAGE.x},${LENS_PAGE.y} ${edge(HEADING - spread)} ${edge(HEADING + spread)}`;

/**
 * Le faisceau de la caméra : il descend en diagonale et éclaire le texte.
 * Il « s'établit » entre 0,5 et 1,5 s (révélation le long de l'axe),
 * puis respire avec le reste de la lumière.
 */
export const Beam: React.FC<{ overlay?: boolean }> = ({ overlay = false }) => {
  const frame = useCurrentFrame();

  const establish = interpolate(
    frame,
    [T.beam.from, T.beam.from + T.beam.duration],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) },
  );
  const breath = 0.86 + 0.14 * Math.sin((frame / T.breathPeriod) * Math.PI * 2 + 0.6);
  // Révélation le long de l'axe du faisceau, avec un bord dégradé (pas de coupe nette)
  const reveal = establish * 1.45;
  const revealEnd = Math.min(reveal, 1);
  const revealStart = Math.max(0, Math.min(reveal - 0.3, 1));

  return (
    <AbsoluteFill
      style={{
        opacity: establish * breath * (overlay ? 0.4 : 1),
        mixBlendMode: overlay ? "soft-light" : "screen",
      }}
    >
      <svg
        width={LAYOUT.width}
        height={LAYOUT.height}
        viewBox={`0 0 ${LAYOUT.width} ${LAYOUT.height}`}
      >
        <defs>
          <linearGradient
            id="nv-beam"
            gradientUnits="userSpaceOnUse"
            x1={LENS_PAGE.x}
            y1={LENS_PAGE.y}
            x2={LENS_PAGE.x - 430}
            y2={LENS_PAGE.y + 1330}
          >
            <stop offset="0%" stopColor={COLORS.warnBg} stopOpacity="0.3" />
            <stop offset="28%" stopColor={COLORS.warnBg} stopOpacity="0.15" />
            <stop offset="72%" stopColor={COLORS.paper} stopOpacity="0.055" />
            <stop offset="100%" stopColor={COLORS.paper} stopOpacity="0" />
          </linearGradient>
          <linearGradient
            id="nv-beam-mask"
            gradientUnits="userSpaceOnUse"
            x1={LENS_PAGE.x}
            y1={LENS_PAGE.y}
            x2={LENS_PAGE.x - 480}
            y2={LENS_PAGE.y + 1480}
          >
            <stop offset={revealStart} stopColor="#ffffff" />
            <stop offset={revealEnd} stopColor="#000000" />
          </linearGradient>
          <mask id="nv-beam-reveal" maskUnits="userSpaceOnUse" x={-400} y={-400} width={LAYOUT.width + 800} height={LAYOUT.height + 800}>
            <rect
              x={-400}
              y={-400}
              width={LAYOUT.width + 800}
              height={LAYOUT.height + 800}
              fill="url(#nv-beam-mask)"
            />
          </mask>
          <filter id="nv-beam-blur" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="26" />
          </filter>
          <filter id="nv-core-blur" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="12" />
          </filter>
        </defs>

        <g mask="url(#nv-beam-reveal)">
          <polygon points={cone(SPREAD)} fill="url(#nv-beam)" filter="url(#nv-beam-blur)" />
          <polygon
            points={cone(SPREAD * 0.42)}
            fill="url(#nv-beam)"
            filter="url(#nv-core-blur)"
            opacity={0.65}
          />
          {/* Départ du faisceau, juste devant l'objectif */}
          <circle
            cx={LENS_PAGE.x}
            cy={LENS_PAGE.y}
            r={54}
            fill={alpha(COLORS.paper, 0.14)}
            filter="url(#nv-beam-blur)"
          />
        </g>
      </svg>
    </AbsoluteFill>
  );
};
