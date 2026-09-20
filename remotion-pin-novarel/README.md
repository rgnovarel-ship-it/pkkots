# Vidéos Pinterest NOVAREL — projet Remotion

Projet **séparé du site** : rien ici ne touche à Flask.

Deux compositions :

| id | ce que c'est | sortie |
|---|---|---|
| **`PubNovarel`** | version courante — bandeau des mois + titre au masque, monde clair du site | `out/pub-novarel.mp4` (7,5 s) |
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
| Fond papier, chaleur, balayage brillant | `src/pub/parts/Paper.tsx` |
| Le bandeau des mois (hauteur, vitesse, largeur des cellules) | `src/pub/parts/Ticker.tsx` |
| Le titre, sa révélation au masque, le bloc signal | `src/pub/parts/Copy.tsx` |
| Le panneau comparatif | `src/pub/parts/Panel.tsx` |
| Intensité du grain | `src/pub/parts/Grain.tsx` |

## Le parti pris visuel

Aucun objet dessiné. Le visuel principal est un **bandeau d'encre où les douze
mois défilent sans jamais s'arrêter** — c'est ça, « tous les mois » — et le
titre répond juste en dessous. Un faux objet en volume est le marqueur numéro un
d'un visuel généré : il n'y en a plus.

La lumière est une lumière d'imprimé, pas une lumière de scène 3D :

- une chaleur qui respire dans l'angle haut droit, une retombée plus froide en
  bas à gauche ;
- un **balayage brillant** très large et très doux qui traverse la page une fois
  par boucle, comme la lumière qui glisse sur une dorure (`Paper.tsx`) ;
- un grain en deux passes : `multiply` mord dans les ombres, `overlay` réveille
  les hautes lumières ;
- un micro-travelling permanent, parce qu'une image parfaitement fixe trahit le
  rendu.

Le titre se révèle **au masque** : chaque ligne glisse derrière un cadre qui la
coupe net, elle ne s'allume pas en fondu. La ligne surlignée se fait en deux
temps — le bloc signal se déroule depuis la gauche, puis le mot monte derrière
son masque.

## La boucle

Le bandeau, le sur-titre et le logo sont présents du début à la fin, et **toute
leur animation est périodique sur la durée totale**. Le défilement des mois est
exact : chaque cellule fait une largeur fixe (`CELL` dans `Ticker.tsx`), le
motif se répète donc tous les 12 × CELL pixels, et on translate d'un cycle
entier sur `DURATION` — le raccord est mathématiquement invisible. Le balayage
brillant et le micro-travelling suivent la même règle (`loopWave()` dans
`motion.ts`).

Seuls les textes entrent puis ressortent, en cascade inverse. Conséquence : la
dernière frame est identique à la première — bandeau, sur-titre et logo — donc
la boucle ne coupe pas, et aucune frame n'est noire ni vide.

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
- Aucune image ni vidéo téléchargée : tout est typographie, aplats et filets.
- Les douze mois sont les douze mois de l'année, rien d'autre à y lire : ni
  montant, ni durée d'engagement, ni promesse.
- Tout le mouvement dérive de `useCurrentFrame()`, avec l'easing du site.
