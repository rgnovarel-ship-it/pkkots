import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { alpha, COLORS, LAYOUT } from "../../brand";
import { loopWave } from "../motion";
import { DURATION } from "../timing";

/**
 * Le fond : du papier, pas une scène.
 *
 * La lumière est une lumière d'imprimé — une chaleur qui respire dans un angle,
 * et un balayage brillant qui traverse la page, comme la lumière qui glisse sur
 * une dorure. Pas de faux volume, pas de rai de soleil simulé : c'est ce qui
 * faisait « image générée ».
 *
 * Tout est périodique sur la durée totale : la dernière frame est la première.
 */
export const Paper: React.FC = () => {
  const frame = useCurrentFrame();

  const breath = loopWave(frame, Math.PI * 0.5);
  // Le balayage traverse la page une fois par boucle, hors champ aux deux bouts
  const sweep = (frame / DURATION) * (LAYOUT.height + 1600) - 800;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.paper }}>
      {/* Grain de papier : une chaleur légère en haut à droite, plus froid en bas */}
      <AbsoluteFill
        style={{
          background: `linear-gradient(206deg, ${COLORS.surface} 0%, ${COLORS.paper} 46%, ${COLORS.surface2} 100%)`,
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.55 + breath * 0.45,
          background: `radial-gradient(58% 34% at 88% 2%, ${alpha(
            COLORS.warnBg,
            0.9,
          )} 0%, transparent 68%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(70% 44% at 4% 100%, ${alpha(
            COLORS.lineStrong,
            0.42,
          )} 0%, transparent 72%)`,
        }}
      />

      {/* Le balayage brillant : une bande large, très douce, qui descend */}
      <AbsoluteFill style={{ mixBlendMode: "soft-light", opacity: 0.9 }}>
        <div
          style={{
            position: "absolute",
            left: -400,
            top: sweep,
            width: LAYOUT.width + 800,
            height: 620,
            transform: "rotate(-16deg)",
            background: `linear-gradient(180deg, transparent 0%, ${alpha(
              "#ffffff",
              0.5,
            )} 42%, ${alpha("#ffffff", 0.85)} 50%, ${alpha(
              "#ffffff",
              0.5,
            )} 58%, transparent 100%)`,
            filter: "blur(40px)",
          }}
        />
      </AbsoluteFill>

      {/* Vignette de papier, jamais noire */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(86% 66% at 50% 44%, transparent 62%, ${alpha(
            COLORS.inkSoft,
            0.13,
          )} 100%)`,
        }}
      />
    </AbsoluteFill>
  );
};
