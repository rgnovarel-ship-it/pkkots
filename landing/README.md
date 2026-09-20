# NOVAREL — page de publicité

Projet **séparé** du site Flask (`novarel/`). React + Vite + TypeScript + Tailwind v4.
Rien de ce dossier n'est importé par `app_site.py` : la page n'est ni hébergée ni
routée pour l'instant, c'est une décision à prendre.

```bash
cd landing
npm install
npm run dev      # http://localhost:5173
npm run build    # dist/
```

## ⚠ Les composants 21st.dev n'ont pas pu être récupérés

La session tourne dans un conteneur distant dont la politique réseau **bloque
`21st.dev`** (`CONNECT tunnel failed, response 403` — un blocage d'egress, pas un
paywall). Ni le CLI shadcn, ni le registre `https://21st.dev/r/...`, ni les pages
publiques n'étaient joignables.

Les trois blocs ont donc été **réécrits à la main**, avec le même rôle et la même
API que les composants demandés :

| Demandé | Écrit ici | Écart |
|---|---|---|
| `@beratberkayg/shader-hero` | `src/components/ui/shader-hero.tsx` | Shader GLSL maison en WebGL2 brut (pas de `three`, pas de `@react-three/fiber`) |
| `@hirael/comparison-02` | `src/components/ui/comparison-table.tsx` | `<table>` sémantique sur desktop, fiches empilées sur mobile |
| `@sean0205/alert-1` (mono) | `src/components/ui/alert-banner.tsx` | Filet + pictogramme dessiné, aucune dépendance |

**Pour poser les vrais composants 21st.dev depuis ta machine**, où le réseau n'est
pas filtré :

```bash
cd landing
npx shadcn@latest add "https://21st.dev/r/beratberkayg/shader-hero"
npx shadcn@latest add "https://21st.dev/r/hirael/comparison-02"
npx shadcn@latest add "https://21st.dev/r/sean0205/alert-1"
```

Ils atterriront dans `src/components/ui/`. `src/Page.tsx` n'importe que trois
composants et leur passe des props explicites : remplacer un fichier par la
version 21st.dev ne touche ni la mise en page, ni les textes, ni les couleurs.
Il restera à refaire le passage à la palette NOVAREL (ils arrivent avec leurs
propres couleurs).

## Où ajuster

**Les textes** → `src/data/novarel.ts`, et nulle part ailleurs.
Titre, sous-titre, avertissement, produits, lignes du comparatif, signature,
mention d'affiliation, URL du bouton (`CTA_URL`).

**Les couleurs et la typo** → bloc `@theme` en haut de `src/index.css`.
Les jetons sont copiés à l'identique de `novarel/static/css/novarel.css` ; les
changer ici suffit, aucune couleur n'est écrite en dur dans les composants.
Les trois teintes sombres du shader sont en plus déclarées en `const` dans
`shader-hero.tsx` (GLSL ne lit pas les variables CSS) — si le thème sombre
bouge, ces trois lignes bougent aussi.

## Règles tenues

- Le **vert signal** (`--color-signal`) n'apparaît qu'à trois endroits : le
  « Meilleur choix » du comparatif, les boutons d'action, le pictogramme de
  l'avertissement. Le shader est volontairement monochrome.
- L'avertissement ne cite **aucune marque** et n'avance **aucun chiffre**.
- Aucune note, aucun avis, aucun pourcentage nulle part ; les prix sont ceux
  fournis, marqués « prix constaté ».
- Aucune image distante : uniquement du texte, des filets et un shader.
- Le shader s'arrête hors écran et se fige sur `prefers-reduced-motion`.
  Sans WebGL2, le hero reste un aplat sombre et la page est intacte.
