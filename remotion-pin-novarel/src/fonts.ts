/**
 * Polices de marque : Archivo (500–800) et IBM Plex Mono (500–700).
 *
 * Fichiers issus de Google Fonts (dépôt google/fonts, licence OFL — copies dans
 * public/fonts/) et servis en local : le rendu ne dépend d'aucun accès réseau et
 * le jeu de glyphes est complet (« ≈ », « → », « € », accents, tirets longs),
 * ce que les sous-ensembles « latin » de l'API Google Fonts ne couvrent pas.
 *
 * loadFont() pose un delayRender() : la première frame attend les polices.
 */

import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

export const FONT_SANS = "Archivo, system-ui, sans-serif";
export const FONT_MONO = '"IBM Plex Mono", ui-monospace, monospace';

// Archivo est variable : une seule fontface couvre 100→900.
loadFont({
  family: "Archivo",
  url: staticFile("fonts/Archivo-Variable.ttf"),
  weight: "100 900",
  style: "normal",
});

const PLEX: { file: string; weight: string }[] = [
  { file: "IBMPlexMono-Medium.ttf", weight: "500" },
  { file: "IBMPlexMono-SemiBold.ttf", weight: "600" },
  { file: "IBMPlexMono-Bold.ttf", weight: "700" },
];

for (const { file, weight } of PLEX) {
  loadFont({
    family: "IBM Plex Mono",
    url: staticFile(`fonts/${file}`),
    weight,
    style: "normal",
  });
}
