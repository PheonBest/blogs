# Planifier des prompts Claude Code ou OpenCode avec GitHub Actions

J'ai un dashboard perso qui affiche chaque matin un résumé de ma veille tech, écrit en français, par une IA. Pas un cron qui recrache des flux RSS bruts : un vrai prompt, exécuté chaque jour, qui lit les articles, rédige une synthèse et la publie tout seul. Pour en arriver là, il a fallu brancher un agent de code — Claude Code dans mon cas — sur un cron GitHub Actions. Le principe marche tout aussi bien avec OpenCode. Voici ce que j'ai appris en le faisant tourner pour de vrai, pas en suivant un tuto.

## Pourquoi un cron plutôt qu'un déclenchement manuel

Un agent de code branché en CI n'est pas qu'un chatbot planifié. C'est un processus qui a accès à un checkout du repo, qui peut lancer des scripts, committer, pousser. Ça ouvre des usages récurrents : un digest quotidien (mon cas), du triage d'issues, des petites corrections routinières comme un changelog ou une vérification de liens morts. La recette est toujours la même : `on: schedule` combiné à `workflow_dispatch`, pour pouvoir tester à la main sans attendre le prochain créneau du cron.

## Claude Code : `anthropics/claude-code-action`

L'action officielle s'utilise comme n'importe quelle autre action GitHub.

```yaml
on:
  schedule:
    - cron: "37 5 * * *"
  workflow_dispatch:

permissions:
  contents: write
  id-token: write

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          claude_args: |
            --allowedTools Bash,Read,Edit,Write,Glob,Grep
            --max-turns 40
          prompt: |
            Récupère les articles des dernières 24h, rédige une synthèse,
            publie-la. Toutes les instructions détaillées sont dans le repo.
```

Deux détails ne sautent pas aux yeux en lisant la doc en diagonale.

Le token n'est pas une clé API. `CLAUDE_CODE_OAUTH_TOKEN` vient d'un abonnement Claude Pro ou Max, généré en local avec `claude setup-token`, puis collé comme secret du repo. Pas besoin de clé Anthropic API séparée : c'est votre abonnement qui paie l'exécution. Pratique si vous l'avez déjà et ne voulez pas ouvrir une deuxième facturation à l'usage.

Et `id-token: write` est obligatoire, sans que l'erreur le dise clairement. J'ai laissé tourner ce workflow trois jours avant de remarquer qu'il échouait à chaque fois. Le job passait le checkout, passait le setup Python, puis mourait sur l'étape `claude-code-action` avec : *Could not fetch an OIDC token. Did you remember to add id-token: write to your workflow permissions?* L'action fait un échange OIDC en interne pour s'authentifier, et sans cette permission dans le bloc `permissions:`, l'échange échoue. Le seul signal, c'est ce message dans les logs du job — que je n'étais pas allé lire, puisque le workflow avait juste l'air de ne rien faire. Un seul digest avait été généré, à la main, avant que j'active le cron. Les trois exécutions automatiques suivantes avaient toutes échoué sans que rien ne me prévienne.

## OpenCode : `anomalyco/opencode/github`

Même logique côté OpenCode, avec une action maintenue par le projet lui-même.

```yaml
on:
  schedule:
    - cron: "0 9 * * 1"
  workflow_dispatch:

permissions:
  id-token: write
  contents: write
  pull-requests: write
  issues: write

jobs:
  weekly-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anomalyco/opencode/github@latest
        with:
          prompt: "Analyse les issues ouvertes cette semaine et propose un résumé."
```

Sur un déclenchement `schedule`, il n'y a personne pour donner des instructions dans un commentaire de PR comme sur les autres triggers de cette action, donc le champ `prompt` devient obligatoire. Si vous comptiez sur un comportement « par défaut » observé sur `pull_request`, il ne s'applique pas ici. Côté authentification, deux options : une `ANTHROPIC_API_KEY` classique, ou `use_github_token: true`, qui réutilise le token GitHub Actions — dans ce second cas, `id-token: write` devient inutile, l'échange OIDC est sauté. La commande `opencode github install`, lancée en local, automatise toute l'installation (app GitHub, secrets, fichier de workflow) pour qui préfère ne pas écrire le YAML à la main.

## Ce qui compte une fois que ça tourne

Une fois le premier run vert, trois réglages font la différence entre « ça tourne » et « ça tourne sans me réveiller à 3 h du matin ».

D'abord, un `concurrency.group`. Un cron qui se chevauche avec le run précédent — parce qu'une exécution a traîné, ou qu'on a relancé à la main pendant que le schedule tournait — peut produire deux commits concurrents sur la même branche. `concurrency: { group: mon-job, cancel-in-progress: false }` sérialise sans annuler le run en cours.

Ensuite, une garde de cadence plutôt qu'un cron plus lent. Si un jour vous voulez passer d'un digest quotidien à un digest tous les deux jours, ne touchez pas au cron : ajoutez une étape en début de job qui lit une valeur de configuration et sort en `should_run=false` si ce n'est pas le bon jour. Le cron reste simple, tous les jours, et la cadence réelle devient une donnée qu'on peut changer sans toucher au YAML.

Enfin, le toolchain doit être vendored dans le repo. L'action checkout le repo courant, pas votre machine locale. Si le prompt dépend de scripts — fetch de flux RSS, appel d'API, post-traitement — ces scripts doivent vivre dans le repo que le workflow checkout, pas dans un `~/.claude/skills/` local qui n'existe pas sur le runner.

Rien de tout ça n'est sorcier une fois qu'on l'a fait une fois. Mais la première fois, c'est exactement ce genre de détail (une permission manquante, un `prompt` qui devient obligatoire sur un trigger différent) qui fait la différence entre un cron qui tourne et un cron qui échoue en silence pendant trois jours.
