# Vidéos Pinterest NOVAREL — projet Remotion

Projet **séparé du site** : rien ici ne touche à Flask.

Deux compositions :

| id | ce que c'est | sortie |
|---|---|---|
| **`PubNovarel`** | version courante — pub en lumière naturelle, monde clair du site | `out/pub-novarel.mp4` (7,5 s) |
| `PinNovarel` | première version, gardée en archive — scène de nuit | `out/pin-novarel.mp4` (6,5 s) |

Format commun : 1000 × 1500 (2:3 Pinterest), 30 fps, MP4 / H.264 / yuv420p,
sans son, bouclable.

## Lancer

```bash
npm install
npm run dev          # studio Remotion sur http://localhost:3000
```

## Rendre

```bash
npm run build:pub    # -> out/pub-novarel.mp4
npm run cover        # -> out/pub-novarel-cover.png (image de couverture)
npm run build:pin    # -> out/pin-novarel.mp4 (l'archive)
```

Si Remotion ne trouve pas de navigateur : `npx remotion browser ensure`. Si un
Chromium est déjà là, pointe-le — attention, un Chrome récent refuse l'ancien
mode headless, il faut un `headless_shell` :

```bash
REMOTION_BROWSER_EXECUTABLE=/chemin/vers/headless_shell npm run build:pub
```

`remotion.config.ts` lit cette variable et la passe à `Config.setBrowserExecutable`.

## Où toucher quoi (`PubNovarel`)

| Ce que tu veux changer | Fichier |
|---|---|
| Textes, produits, prix, signature | `src/pub/content.ts` |
| Minutage, durée totale, ordre des arrivées et des sorties | `src/pub/timing.ts` |
| Position verticale des blocs | `src/pub/positions.ts` |
| Couleurs et easing de marque (partagés) | `src/brand.ts` |
| Mur, soleil, ombre de fenêtre, rai, poussière | `src/pub/parts/Wall.tsx` |
| La caméra (platine, bras, visière, objectif, voyant) | `src/pub/parts/Camera.tsx` |
| Le panneau comparatif | `src/pub/parts/Panel.tsx` |
| Intensité du grain | `src/pub/parts/Grain.tsx` |

## Comment la lumière est construite

Une seule source : un soleil bas, hors champ en haut à droite (`SUN` dans
`Wall.tsx`). Tout en découle.

- Le mur reçoit une nappe chaude côté source et une zone froide en bas à gauche.
- Une ombre de fenêtre, très floue, glisse lentement en haut du cadre.
- Un rai de lumière traverse la scène en diagonale ; de la poussière y dérive.
- La caméra est éclairée en haut et à droite, ses flancs bas-gauche sont dans
  l'ombre, et elle projette une ombre penchée vers le bas à gauche — dense au
  contact de la platine, de plus en plus floue en s'éloignant.
- La visière porte une ombre sur le corps : c'est ce qui les désolidarise.
- Grain en deux passes : `multiply` mord dans les ombres, `overlay` réveille les
  hautes lumières.

## La boucle

Le décor, la caméra et le logo sont présents du début à la fin, et **toute leur
animation est périodique sur la durée totale** (`loopWave()` dans `motion.ts`,
un sinus de période `DURATION`). Le voyant clignote sur 45 frames, soit 5 cycles
exacts sur 225. Seuls les textes entrent puis ressortent, en cascade inverse.

Conséquence : la dernière frame est identique à la première — plan produit +
logo sur le mur éclairé — donc la boucle ne coupe pas, et aucune frame n'est
noire.

**Couverture Pinterest :** la première frame ne porte pas encore le message.
Choisis l'image de couverture au moment de l'upload, ou utilise
`out/pub-novarel-cover.png` (frame 150, la composition complète).

## Polices

Archivo (500–800) et IBM Plex Mono (500–700), depuis Google Fonts (dépôt
`google/fonts`, licence OFL — copies dans `public/fonts/`), servies en local.
Le rendu ne dépend d'aucun accès réseau et le jeu de glyphes est complet
(`≈`, `→`, `€`, accents, tirets longs), ce que les sous-ensembles « latin » de
l'API Google Fonts ne couvrent pas. Chargement via `@remotion/fonts`
(`src/fonts.ts`), qui pose un `delayRender()`.

## Ce qui vient du site

Les jetons de `src/brand.ts` sont copiés de `novarel/static/css/novarel.css`, y
compris l'easing `--ease` `cubic-bezier(0.22, 0.61, 0.36, 1)`, utilisé comme
easing par défaut (`siteEase` dans `motion.ts`). Les composants repris :
`.eyebrow` et son carré signal, le `<mark>` du `.hero__title`, le `.hero__panel`
(barre d'en-tête + point, lignes sur filets, nom à gauche, prix et flèche à
droite), le `.badge`, le `.btn--signal`, le `.brand`.

## Règles respectées

- Aucun chiffre, aucune note, aucun avis, aucun classement inventé. Les prix
  sont les fourchettes fournies, recopiées telles quelles dans `content.ts`.
- Aucune image ni vidéo téléchargée : la caméra est dessinée en SVG, la lumière
  et le grain sont générés.
- Tout le mouvement dérive de `useCurrentFrame()`. La poussière utilise un
  générateur à seed fixe (`seeded()`), jamais `Math.random()` au rendu : sans
  ça, l'image scintillerait d'une frame à l'autre.
