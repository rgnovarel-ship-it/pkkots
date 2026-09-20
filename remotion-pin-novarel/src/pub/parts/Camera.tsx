import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { alpha, COLORS } from "../../brand";
import { loopWave } from "../motion";

/** Bloc caméra dans la frame (1000 × 1500). Le viewBox reste en 640 × 360. */
export const CAMERA_BOX = { left: 58, top: 46, width: 700, height: 394 } as const;
/** Centre de l'objectif, dans le repère du SVG avant inclinaison. */
export const LENS = { x: 448, y: 151, r: 38 } as const;
/** Centre de la rotule : c'est autour d'elle que la tête s'incline. */
const JOINT = { x: 180, y: 151 } as const;
/** Inclinaison de la tête : elle regarde vers le bas à droite. */
const TILT = 8;
/** Période du voyant : 45 frames, soit 5 cycles exacts sur 225 — la boucle reste propre. */
const LED_PERIOD = 45;

// Visière courte, coupée en biais vers l'arrière, comme une vraie casquette pare-soleil
const VISOR_PATH =
  "M 530 151 A 82 82 0 0 0 448 69 L 356 69 L 322 118 L 448 118 A 50 50 0 0 1 498 151 Z";

/**
 * Silhouette complète — sert deux fois : une fois en ombre portée, une fois en
 * objet. La platine et le bras restent dans le plan du mur ; seule la tête
 * pivote autour de la rotule, comme sur une vraie caméra.
 */
const Silhouette: React.FC<{ shadow?: boolean }> = ({ shadow = false }) => {
  const fill = (id: string) => (shadow ? undefined : `url(#${id})`);
  return (
    <>
      <rect x={40} y={76} width={34} height={150} rx={10} fill={fill("nv-d-plate")} />
      <rect x={64} y={132} width={120} height={38} rx={15} fill={fill("nv-d-arm")} />
      <circle cx={JOINT.x} cy={JOINT.y} r={27} fill={fill("nv-d-arm")} />
      <g transform={`rotate(${TILT} ${JOINT.x} ${JOINT.y})`}>
        <rect x={182} y={97} width={320} height={108} rx={54} fill={fill("nv-d-body")} />
        <path d={VISOR_PATH} fill={fill("nv-d-visor")} />
      </g>
    </>
  );
};

/**
 * Caméra de vidéosurveillance extérieure montée au mur, traitée en plan produit.
 * Source unique en haut à droite : hautes lumières en haut et à droite, flancs
 * bas-gauche dans l'ombre, ombre portée vers le bas à gauche — dense au contact,
 * de plus en plus floue en s'éloignant.
 */
export const Camera: React.FC = () => {
  const frame = useCurrentFrame();

  // Micro-vie : le reflet spéculaire glisse de quelques pixels
  const breath = loopWave(frame, Math.PI * 0.5);
  const specular = -5 + breath * 10;

  const ledPhase = frame % LED_PERIOD;
  const ledLevel =
    ledPhase < LED_PERIOD * 0.4
      ? interpolate(ledPhase, [0, 3, LED_PERIOD * 0.4], [0.3, 1, 0.6], {
          extrapolateRight: "clamp",
        })
      : 0.15;

  return (
    <svg
      width={CAMERA_BOX.width}
      height={CAMERA_BOX.height}
      viewBox="0 0 640 360"
      style={{
        position: "absolute",
        left: CAMERA_BOX.left,
        top: CAMERA_BOX.top,
        overflow: "visible",
      }}
    >
      <defs>
        {/* Corps clair : lumière en haut à droite, ombre en bas à gauche */}
        <linearGradient id="nv-d-body" x1="1" y1="0" x2="0.1" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="22%" stopColor={COLORS.surface} />
          <stop offset="58%" stopColor={COLORS.surface2} />
          <stop offset="86%" stopColor={COLORS.lineStrong} />
          <stop offset="100%" stopColor="#8a8677" />
        </linearGradient>
        <linearGradient id="nv-d-visor" x1="1" y1="0" x2="0.2" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="36%" stopColor={COLORS.surface} />
          <stop offset="80%" stopColor={COLORS.line} />
          <stop offset="100%" stopColor="#9a9586" />
        </linearGradient>
        <linearGradient id="nv-d-arm" x1="1" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={COLORS.surface} />
          <stop offset="50%" stopColor={COLORS.line} />
          <stop offset="100%" stopColor="#8a8677" />
        </linearGradient>
        <linearGradient id="nv-d-plate" x1="1" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={COLORS.surface2} />
          <stop offset="68%" stopColor={COLORS.lineStrong} />
          <stop offset="100%" stopColor="#7b776a" />
        </linearGradient>
        {/* Verre : sombre, mais il réfléchit le mur clair du côté de la source */}
        <radialGradient id="nv-d-glass" cx="68%" cy="26%" r="86%">
          <stop offset="0%" stopColor="#3b4038" />
          <stop offset="38%" stopColor="#1b1f19" />
          <stop offset="100%" stopColor="#0a0c09" />
        </radialGradient>
        <radialGradient id="nv-d-led" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={COLORS.alert} stopOpacity="0.8" />
          <stop offset="100%" stopColor={COLORS.alert} stopOpacity="0" />
        </radialGradient>
        <filter id="nv-d-cast" x="-70%" y="-70%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="15" />
        </filter>
        <filter id="nv-d-contact" x="-70%" y="-70%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="4" />
        </filter>
        <filter id="nv-d-soft" x="-70%" y="-70%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
        <clipPath id="nv-d-lens-clip">
          <circle cx={LENS.x} cy={LENS.y} r={LENS.r} />
        </clipPath>
      </defs>

      {/* Ombre portée sur le mur : penchée vers le bas à gauche, floue */}
      <g
        filter="url(#nv-d-cast)"
        opacity={0.42 + breath * 0.08}
        transform="translate(-30 96) skewX(-13) scale(1 0.9)"
        fill={alpha(COLORS.inkSoft, 0.34)}
      >
        <Silhouette shadow />
      </g>

      {/* Ombre de contact : serrée, dense, juste au pied de la platine */}
      <rect
        x={44}
        y={86}
        width={38}
        height={146}
        rx={10}
        fill={alpha(COLORS.inkSoft, 0.4)}
        filter="url(#nv-d-contact)"
      />

      <Silhouette />

      {/* La visière porte une ombre sur le corps : c'est ce qui les désolidarise */}
      <g transform={`rotate(${TILT} ${JOINT.x} ${JOINT.y})`}>
        <path
          d="M 330 122 L 446 122 A 50 50 0 0 1 496 152"
          fill="none"
          stroke={alpha(COLORS.inkSoft, 0.4)}
          strokeWidth={9}
          filter="url(#nv-d-soft)"
        />
        <path
          d="M 326 118 L 446 118"
          stroke={alpha(COLORS.lineStrong, 0.9)}
          strokeWidth={1.5}
        />
        {/* Filet de tôle sur le flanc */}
        <path d="M 236 190 L 430 190" stroke={alpha(COLORS.lineStrong, 0.5)} strokeWidth={1.5} />

        {/* Reflet spéculaire étroit sur l'arête de la visière, côté source */}
        <path
          d={`M ${370 + specular} 72 L ${474 + specular} 72`}
          stroke="#ffffff"
          strokeWidth={3}
          strokeLinecap="round"
          opacity={0.9}
        />
        <path
          d={`M ${374 + specular} 78 L ${466 + specular} 78`}
          stroke="#ffffff"
          strokeWidth={7}
          strokeLinecap="round"
          opacity={0.3}
          filter="url(#nv-d-soft)"
        />

        {/* Bague de l'objectif */}
        <circle cx={LENS.x} cy={LENS.y} r={50} fill={COLORS.surface2} />
        <circle
          cx={LENS.x}
          cy={LENS.y}
          r={50}
          fill="none"
          stroke={alpha(COLORS.inkSoft, 0.32)}
          strokeWidth={2}
        />
        <path
          d={`M ${LENS.x + 14} ${LENS.y - 48} A 50 50 0 0 1 ${LENS.x + 48} ${LENS.y - 12}`}
          fill="none"
          stroke="#ffffff"
          strokeWidth={2.5}
          strokeLinecap="round"
          opacity={0.9}
        />

        {/* Verre */}
        <circle cx={LENS.x} cy={LENS.y} r={LENS.r} fill="url(#nv-d-glass)" />
        <g clipPath="url(#nv-d-lens-clip)">
          <ellipse
            cx={LENS.x + 16}
            cy={LENS.y - 18}
            rx={13}
            ry={8}
            fill={alpha(COLORS.warnBg, 0.5)}
            transform={`rotate(32 ${LENS.x + 16} ${LENS.y - 18})`}
            filter="url(#nv-d-soft)"
          />
          <ellipse
            cx={LENS.x + 18}
            cy={LENS.y - 20}
            rx={4.5}
            ry={2.6}
            fill="#ffffff"
            opacity={0.78}
            transform={`rotate(32 ${LENS.x + 18} ${LENS.y - 20})`}
          />
          {/* Reflet secondaire, très faible, en bas à gauche */}
          <ellipse
            cx={LENS.x - 15}
            cy={LENS.y + 17}
            rx={9}
            ry={5}
            fill={alpha(COLORS.signal, 0.18)}
            filter="url(#nv-d-soft)"
          />
        </g>
        <circle
          cx={LENS.x}
          cy={LENS.y}
          r={LENS.r}
          fill="none"
          stroke={alpha(COLORS.signalDeep, 0.32)}
          strokeWidth={1.5}
        />

        {/* Voyant d'enregistrement */}
        <circle cx={392} cy={176} r={13} fill="url(#nv-d-led)" opacity={ledLevel * 0.8} />
        <circle cx={392} cy={176} r={4.5} fill={COLORS.alert} opacity={0.4 + ledLevel * 0.6} />

        {/* Micro */}
        <g opacity={0.3}>
          <circle cx={336} cy={176} r={2} fill={COLORS.inkSoft} />
          <circle cx={346} cy={176} r={2} fill={COLORS.inkSoft} />
          <circle cx={356} cy={176} r={2} fill={COLORS.inkSoft} />
        </g>
      </g>

      {/* Vis de la platine */}
      <circle cx={57} cy={99} r={4} fill={alpha(COLORS.inkSoft, 0.4)} />
      <circle cx={57} cy={203} r={4} fill={alpha(COLORS.inkSoft, 0.4)} />
    </svg>
  );
};
