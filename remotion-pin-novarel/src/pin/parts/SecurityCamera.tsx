import React from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { alpha, COLORS } from "../tokens";
import { T } from "../timing";

/** Position du bloc caméra dans la frame (1000 × 1500). */
export const CAMERA_BOX = { left: 322, top: 34, width: 640, height: 360 } as const;
/** Centre de l'objectif dans le repère du SVG. */
export const LENS = { x: 214, y: 150, r: 38 } as const;
/** Centre de l'objectif en coordonnées de frame (la rotation se fait autour de ce point). */
export const LENS_PAGE = {
  x: CAMERA_BOX.left + LENS.x,
  y: CAMERA_BOX.top + LENS.y,
} as const;

/** Inclinaison de la caméra : elle regarde vers le bas à gauche. */
const TILT = 9;

/**
 * Caméra de vidéosurveillance extérieure montée au mur :
 * platine murale, bras, corps en tube, visière pare-soleil, objectif sombre,
 * voyant d'enregistrement. Volume donné par des dégradés + un liseré de lumière
 * sur l'arête supérieure.
 */
export const SecurityCamera: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entry = spring({
    frame: frame - T.cameraIn.from,
    fps,
    config: { damping: 18, mass: 0.9, stiffness: 90 },
    durationInFrames: T.cameraIn.duration,
  });
  const slide = interpolate(entry, [0, 1], [150, 0]);
  const opacity = interpolate(entry, [0, 0.4], [0, 1], { extrapolateRight: "clamp" });

  // Reflet qui traverse l'objectif (0,5 – 1,5 s)
  const flare = interpolate(
    frame,
    [T.lensFlare.from, T.lensFlare.from + T.lensFlare.duration],
    [-1.6, 1.6],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.quad) },
  );
  const flareOpacity = interpolate(
    frame,
    [
      T.lensFlare.from,
      T.lensFlare.from + T.lensFlare.duration * 0.35,
      T.lensFlare.from + T.lensFlare.duration,
    ],
    [0, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Voyant rouge : clignotement continu à partir de 1,0 s
  const ledPhase = Math.max(0, frame - T.led.from) % T.led.period;
  const ledOn = ledPhase < T.led.period * 0.42;
  const ledLevel = ledOn
    ? interpolate(ledPhase, [0, 3, T.led.period * 0.42], [0.25, 1, 0.55], {
        extrapolateRight: "clamp",
      })
    : 0.12;

  return (
    <svg
      width={CAMERA_BOX.width}
      height={CAMERA_BOX.height}
      viewBox={`0 0 ${CAMERA_BOX.width} ${CAMERA_BOX.height}`}
      style={{
        position: "absolute",
        left: CAMERA_BOX.left,
        top: CAMERA_BOX.top,
        opacity,
        transform: `translateX(${slide}px) rotate(${TILT}deg)`,
        transformOrigin: `${LENS.x}px ${LENS.y}px`,
        overflow: "visible",
      }}
    >
      <defs>
        {/* Corps : lumière chaude par le haut, retombée froide en bas */}
        <linearGradient id="nv-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6d6a57" />
          <stop offset="16%" stopColor="#434636" />
          <stop offset="58%" stopColor="#212619" />
          <stop offset="100%" stopColor="#101711" />
        </linearGradient>
        <linearGradient id="nv-visor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#837f69" />
          <stop offset="42%" stopColor="#494d3c" />
          <stop offset="100%" stopColor="#1c231a" />
        </linearGradient>
        <linearGradient id="nv-arm" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#4a4f42" />
          <stop offset="55%" stopColor="#262b20" />
          <stop offset="100%" stopColor="#12150f" />
        </linearGradient>
        <linearGradient id="nv-plate" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#3c4136" />
          <stop offset="100%" stopColor="#14170f" />
        </linearGradient>
        {/* Verre de l'objectif : presque noir */}
        <radialGradient id="nv-glass" cx="36%" cy="30%" r="78%">
          <stop offset="0%" stopColor="#1d221b" />
          <stop offset="45%" stopColor="#0b0e0a" />
          <stop offset="100%" stopColor="#030403" />
        </radialGradient>
        <radialGradient id="nv-led" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={COLORS.alert} stopOpacity="0.85" />
          <stop offset="100%" stopColor={COLORS.alert} stopOpacity="0" />
        </radialGradient>
        <filter id="nv-soft" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="9" />
        </filter>
        <filter id="nv-shadow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="16" />
        </filter>
        <clipPath id="nv-lens-clip">
          <circle cx={LENS.x} cy={LENS.y} r={LENS.r} />
        </clipPath>
      </defs>

      {/* Ombre portée sous l'ensemble */}
      <ellipse
        cx={330}
        cy={232}
        rx={185}
        ry={30}
        fill={alpha("#000000", 0.55)}
        filter="url(#nv-shadow)"
      />

      {/* Platine murale */}
      <rect x={566} y={74} width={36} height={152} rx={10} fill="url(#nv-plate)" />
      <rect
        x={566}
        y={74}
        width={36}
        height={152}
        rx={10}
        fill="none"
        stroke={alpha(COLORS.paper, 0.14)}
      />
      <circle cx={584} cy={98} r={4} fill={alpha("#000000", 0.5)} />
      <circle cx={584} cy={202} r={4} fill={alpha("#000000", 0.5)} />

      {/* Bras */}
      <rect x={462} y={130} width={112} height={40} rx={16} fill="url(#nv-arm)" />
      <path d={`M 470 134 L 566 134`} stroke={alpha(COLORS.paper, 0.22)} strokeWidth={2} />
      {/* Rotule */}
      <circle cx={468} cy={150} r={28} fill="url(#nv-arm)" />
      <circle cx={468} cy={150} r={28} fill="none" stroke={alpha("#000000", 0.55)} />
      <path
        d="M 448 132 A 28 28 0 0 1 486 130"
        fill="none"
        stroke={alpha(COLORS.paper, 0.2)}
        strokeWidth={2}
      />

      {/* Corps en tube */}
      <rect x={160} y={96} width={320} height={108} rx={54} fill="url(#nv-body)" />
      {/* Liseré de lumière sur l'arête supérieure */}
      <path
        d="M 214 98 L 452 98"
        stroke={alpha(COLORS.warnBg, 0.42)}
        strokeWidth={2.5}
        strokeLinecap="round"
      />
      {/* Nervure discrète sur le flanc */}
      <path d="M 250 186 L 440 186" stroke={alpha("#000000", 0.45)} strokeWidth={2} />
      {/* Rebond froid sous le corps : c'est la nuit qui remonte */}
      <path
        d="M 232 200 L 436 200"
        stroke={alpha(COLORS.good, 0.45)}
        strokeWidth={3}
        strokeLinecap="round"
        opacity={0.45}
      />

      {/* Visière pare-soleil au-dessus de l'objectif */}
      <path
        d="M 140 150 A 74 74 0 0 1 214 76 L 392 76 Q 412 76 412 90 Q 412 104 392 104 L 214 104 A 46 46 0 0 0 168 150 Z"
        fill="url(#nv-visor)"
      />
      <path
        d="M 141 146 A 72 72 0 0 1 214 78 L 392 78"
        fill="none"
        stroke={alpha(COLORS.warnBg, 0.5)}
        strokeWidth={2.5}
        strokeLinecap="round"
      />

      {/* Bague / bezel de l'objectif */}
      <circle cx={LENS.x} cy={LENS.y} r={50} fill="#191d16" />
      <circle cx={LENS.x} cy={LENS.y} r={50} fill="none" stroke={alpha("#000000", 0.6)} strokeWidth={3} />
      <path
        d={`M ${LENS.x - 36} ${LENS.y - 34} A 50 50 0 0 1 ${LENS.x + 22} ${LENS.y - 45}`}
        fill="none"
        stroke={alpha(COLORS.paper, 0.3)}
        strokeWidth={2}
      />

      {/* Verre */}
      <circle cx={LENS.x} cy={LENS.y} r={LENS.r} fill="url(#nv-glass)" />
      <g clipPath="url(#nv-lens-clip)">
        {/* Reflet vert, uniquement en haut à gauche */}
        <ellipse
          cx={LENS.x - 15}
          cy={LENS.y - 17}
          rx={11}
          ry={6.5}
          fill={alpha(COLORS.signal, 0.26)}
          transform={`rotate(-34 ${LENS.x - 15} ${LENS.y - 17})`}
          filter="url(#nv-soft)"
        />
        <ellipse
          cx={LENS.x - 17}
          cy={LENS.y - 19}
          rx={5}
          ry={3}
          fill={alpha(COLORS.paper, 0.6)}
          transform={`rotate(-34 ${LENS.x - 17} ${LENS.y - 19})`}
        />
        {/* Reflet qui traverse l'objectif */}
        <rect
          x={LENS.x - 16}
          y={LENS.y - 60}
          width={22}
          height={120}
          fill={alpha(COLORS.paper, 0.22)}
          opacity={flareOpacity}
          filter="url(#nv-soft)"
          transform={`translate(${flare * 58} 0) rotate(-22 ${LENS.x} ${LENS.y})`}
        />
      </g>
      {/* Anneau fin autour du verre */}
      <circle
        cx={LENS.x}
        cy={LENS.y}
        r={LENS.r}
        fill="none"
        stroke={alpha(COLORS.signalDeep, 0.22)}
        strokeWidth={1.5}
      />

      {/* Voyant d'enregistrement */}
      <circle cx={300} cy={176} r={18} fill="url(#nv-led)" opacity={ledLevel * 0.9} />
      <circle cx={300} cy={176} r={5.5} fill={COLORS.alert} opacity={0.35 + ledLevel * 0.65} />

      {/* Petite grille / micro, détail de volume */}
      <g opacity={0.5}>
        <circle cx={352} cy={178} r={2} fill={alpha("#000000", 0.7)} />
        <circle cx={362} cy={178} r={2} fill={alpha("#000000", 0.7)} />
        <circle cx={372} cy={178} r={2} fill={alpha("#000000", 0.7)} />
      </g>
    </svg>
  );
};
