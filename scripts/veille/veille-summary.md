---
name: veille-summary
description: >
  Génère le récap IA de la veille tech francophone pour le dashboard Glance.
  Récupère les articles RSS depuis le dernier récap (réutilise le fetcher de
  /veille), en produit une synthèse en français bien écrite, groupée par
  sections thématiques, avec citations, puis la publie dans digests/ sur ce
  dépôt. Mots-clés : veille, récap IA, synthèse, digest, glance.
user-invokable: true
argument-hint: ""
allowed-tools:
  - Read
  - Bash
  - Edit
  - Skill
---

# Récap IA — Veille tech francophone

Tu produis **une** synthèse de la veille RSS tech francophone et tu la publies
dans `digests/` sur ce dépôt, où le fork Glance (`Gloweet/glance`) la lit
directement (`raw.githubusercontent.com/PheonBest/blogs/main/digests/...`,
ce dépôt est public, pas d'auth nécessaire pour la lecture).

Le style prime : c'est un texte que quelqu'un lit chaque matin. Court, vivant,
avec un point de vue. Pas une liste d'items reformulés.

## Procédure

### Étape 1 — Récupérer les articles

```bash
python3 scripts/veille/fetch_feeds.py <step_days> all
```

`<step_days>` vient de `digests/config.json` (`step_days`, défaut 1) — c'est la
fenêtre depuis le dernier récap, pas toujours 1 jour. Toutes catégories.
Sortie TSV, une ligne par article :
`DATE \t TITRE \t LIEN \t CATÉGORIE \t DESCRIPTION \t SOURCE`.

- Ignore les lignes `ERROR:` / `WARNING:` / `NOTE:` sur stderr (flux
  indisponibles) — n'en parle pas dans le récap.
- **Si zéro article** : passe directement à l'étape 4 avec une entrée minimale
  (voir plus bas).

### Étape 2 — Rédiger la synthèse (en français), groupée par sections

À partir du TSV, écris un digest groupé en **2 à 4 sections thématiques
nommées** (ex : "Dev & Ops", "Culture", "Société", "Cinéma" — nomme-les selon
ce que le TSV contient réellement ce jour-là, pas une liste fixe). Chaque
section a 1 à 2 paragraphes de ~120–200 mots.

Règles :

- **Un vrai fil narratif par section.** Relie les articles entre eux, dégage
  ce qui compte, dis pourquoi c'est intéressant. Si rien ne sort du lot dans
  une catégorie, ne force pas une section pour elle.
- **Un point de vue.** Tu as le droit de trouver une annonce tiède, une
  reprise de hype fatigante, un billet excellent. Nuance quand c'est nuancé.
- **Citations.** Chaque fait rattaché à un article porte un appel de citation.
  Numérote dans l'ordre d'apparition. Un même article = un seul numéro,
  réutilisable.
- **Titre** : une ligne, accrocheuse, qui résume l'angle du jour.
- Pas de méta ("dans ce récap, nous verrons…"), pas de conclusion générique.
- N'invente rien qui ne soit pas dans le TSV. Si une description est vide
  (`N/A`), fie-toi au titre et à la source, ne brode pas.

### Étape 3 — Passe Boileau

Invoque le guide `scripts/veille/boileau.md` sur ton brouillon (titre +
sections) pour retirer les tics d'écriture IA et donner du relief. Applique
ses corrections. Si la skill `boileau` n'est pas disponible, fais la passe
toi-même : phrases de longueurs variées, pas de "Par ailleurs / En outre /
Ainsi" en enfilade, pas de "véritable", "crucial", "s'impose comme", "permet
de", "à l'ère de".

### Étape 4 — Construire l'entrée et publier

Construis l'objet JSON de l'entrée. Chaque paragraphe est un **tableau de
runs** : `{"t": "texte"}` pour du texte, `{"cite": n}` pour un appel de
citation (numéro seul, pas de `[n]` en texte brut — le rendu ajoute le style).

```json
{
  "date": "<YYYY-MM-DD d'aujourd'hui>",
  "label": "<jour de la semaine + date longue, ex: dimanche 7 septembre 2026>",
  "title": "<titre de l'étape 2>",
  "sections": [
    {
      "name": "Dev & Ops",
      "paragraphs": [
        [
          {"t": "Dalibo sort la 1.0 de PostgreSQL Migrator"},
          {"cite": 1},
          {"t": ", et la newsletter de RudeOps est dense cette semaine"},
          {"cite": 2},
          {"t": "."}
        ]
      ]
    },
    { "name": "Culture", "paragraphs": [ [ {"t": "..."} ] ] }
  ],
  "sources": [
    {"n": 1, "title": "<titre exact de l'article>", "url": "<lien>", "feed": "<SOURCE du TSV>"}
  ]
}
```

- `sources` ne contient **que** les articles réellement cités, dans l'ordre
  des numéros.
- **Zéro article dans la fenêtre** : `title` = `"Rien de neuf côté veille"`,
  `sections` = `[{"name": "", "paragraphs": [[{"t": "Les flux n'ont rien publié depuis le dernier récap."}]]}]`,
  `sources` = `[]`.

Publie (le script écrit `digests/<date>.json`, met à jour
`digests/index.json`, commit et push — pas de branche orpheline ici,
contrairement à `gitops-demo`, ce dépôt n'a pas de contrainte GitOps) :

```bash
printf '%s' "$ENTRY_JSON" | python3 scripts/veille/update_archive.py <chemin-du-dépôt-blogs>
```

`<chemin-du-dépôt-blogs>` = la racine du checkout `PheonBest/blogs` (en
général le répertoire de travail courant).

### Étape 5 — Rendre compte

Affiche : le titre de l'entrée, le nombre d'articles cités, et la ligne de
sortie du script (`pushed digest <date>`). Rien d'autre — pas besoin de
recopier le récap.
