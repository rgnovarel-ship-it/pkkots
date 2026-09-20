# Visuels Pinterest

Deux pins au format 2:3 (1000×1500 dessinés, exportés en 2000×3000), aux jetons
de `novarel.css`. Mêmes textes que la landing, rien d'inventé.

| Fichier | Angle |
|---|---|
| `novarel-pin-promesse.png` | « Payez-la une fois. Pas tous les mois. » + les trois caméras |
| `novarel-pin-avertissement.png` | L'avertissement consommateur + les trois caméras |

## Modifier

Tout est dans `pins.html` : un fichier, deux `<div class="pin">`, les couleurs
en variables CSS en haut. Ouvre-le dans un navigateur pour voir le rendu.

## Réexporter

Depuis `landing/` :

```bash
npx playwright screenshot --viewport-size=1100,1600 --selector="#pin-a" \
  --scale=css pins/pins.html pins/novarel-pin-promesse.png
```

Ou, pour les deux d'un coup avec la bonne densité, un court script Playwright
qui charge `pins.html` avec `deviceScaleFactor: 2` et capture `#pin-a` puis
`#pin-b`.

## Règles tenues

- Aucune marque concurrente citée dans l'avertissement, aucun chiffre inventé.
- Prix repris de `src/data/novarel.ts`, marqués « prix constatés ».
- Le vert signal uniquement sur le « meilleur choix », le pictogramme d'alerte
  et le soulignement de l'adresse.
