# Épingle Pinterest NOVAREL — vidéo Remotion

Vidéo d'animation 1000 × 1500 (2:3), 6,5 s, 30 fps, MP4 / H.264 / yuv420p, sans son,
pensée pour tourner en boucle. Projet **séparé du site** : rien ici ne touche à Flask.

## Lancer

```bash
npm install
npm run dev        # studio Remotion sur http://localhost:3000
```

## Rendre

```bash
npm run build:pin  # -> out/pin-novarel.mp4
```

Si Remotion ne trouve pas de navigateur :

```bash
npx remotion browser ensure
```

ou, si un Chromium est déjà installé sur la machine :

```bash
REMOTION_BROWSER_EXECUTABLE=/chemin/vers/chromium npm run build:pin
```

(`remotion.config.ts` lit cette variable d'environnement et la passe à
`Config.setBrowserExecutable`.)

## Où toucher quoi

| Ce que tu veux changer | Fichier |
|---|---|
| Les textes, les produits, les prix, la signature | `src/pin/content.ts` |
| Le minutage (qui arrive quand, durée totale, fps) | `src/pin/timing.ts` |
| Les couleurs de marque | `src/pin/tokens.ts` |
| La position verticale des blocs | `src/pin/positions.ts` |
| Le fond et les deux températures de lumière | `src/pin/parts/Backdrop.tsx` |
| Le dessin de la caméra (corps, visière, objectif, voyant) | `src/pin/parts/SecurityCamera.tsx` |
| Le faisceau lumineux | `src/pin/parts/Beam.tsx` |
| L'empilement des calques | `src/pin/PinNovarel.tsx` |

La durée totale se règle avec `DURATION` dans `src/pin/timing.ts` (en frames :
195 = 6,5 s). Les temps y sont écrits en secondes via l'aide `s()`, donc lisibles
tels quels.

## Polices

Archivo (500–800) et IBM Plex Mono (500–700), récupérées depuis Google Fonts
(dépôt `google/fonts`, licence OFL — copie des licences dans `public/fonts/`) et
servies en local depuis `public/fonts`. Le rendu ne dépend donc d'aucun accès
réseau, et le jeu de glyphes complet est disponible (`≈`, `→`, `€`, accents,
tirets longs) — ce que les sous-ensembles « latin » de l'API Google Fonts ne
couvrent pas. Le chargement passe par `@remotion/fonts` (`src/pin/fonts.ts`), qui
pose un `delayRender()` : la première frame n'est rendue qu'une fois les polices
prêtes.

## Règles respectées

- Aucun chiffre, aucune note, aucun avis, aucun classement inventé. Les prix sont
  les fourchettes fournies, recopiées telles quelles dans `content.ts`.
- Aucune image ni vidéo téléchargée : la caméra est dessinée en SVG, tout le reste
  est vectoriel ou généré (grain via `feTurbulence`).
- Tout le mouvement dérive de `useCurrentFrame()` (`spring()`, `interpolate()`,
  `<Sequence>`), jamais d'animation CSS parallèle au temps Remotion.
