---
title: "Router plusieurs fournisseurs d'IA dans T3 Code"
date: 2026-09-13
tags: [ia, devops, opencode, t3code, cliproxy, claude-code-router]
---

# Router plusieurs fournisseurs d'IA dans T3 Code

Je paie 20 € par mois pour Claude Pro. J'ai aussi quelques dollars sur OpenRouter, et le tier gratuit d'OpenCode Zen. L'idée de départ était simple : utiliser T3 Code, mon client de code IA sur Mac, avec tous ces modèles à la fois, et choisir le bon modèle selon la tâche plutôt que d'envoyer chaque prompt à Sonnet par réflexe.

Ça a pris plus de détours que prévu. Ce billet raconte le chemin : Claude Code Router (CCR) d'abord, ses limites, puis le passage à CLIProxyAPI (cliproxy).

## Le problème avec T3 Code et l'agent Claude

T3 Code sait piloter Claude Code, mais son sélecteur de modèle est figé : une liste de noms Claude officiels (Sonnet 5, Opus 5, Haiku 4.5…), mise en cache dans `~/.t3/caches/claudeAgent_*.json`. Peu importe ce que le serveur en face expose réellement, T3 Code n'affiche que cette liste. Le même problème existait déjà avec un autre proxy, avant même d'ajouter OpenRouter : ce n'est pas un défaut de CCR, c'est le pilote « Claude Agent » de T3 Code qui ne va jamais interroger le backend pour connaître ses modèles disponibles.

Heureusement, T3 Code a un second pilote : OpenCode. Contrairement à Claude Agent, OpenCode expose la liste de modèles telle que définie dans son fichier de config (`opencode.json`), avec un `provider` personnalisé qui pointe vers n'importe quel serveur compatible OpenAI ou Anthropic. Ce détail a débloqué tout le reste.

## Premier essai : Claude Code Router

CCR tourne en service systemd sur mon serveur maison (Proxmox, exposé en Tailscale). Il centralise plusieurs providers — Codex API, Claude Code API (Anthropic direct), Google Gemini, OpenRouter — derrière une seule passerelle HTTP compatible Anthropic (`/v1/messages`).

Deux ajustements côté infra ont été nécessaires :

- **Accès à l'interface web via Tailscale.** CCR vérifie le header `Host` de chaque requête et ne laisse passer que `localhost` par défaut, une protection anti-DNS-rebinding classique. Il manquait une option pour autoriser un nom d'hôte externe, donc j'ai ajouté une variable d'environnement `CCR_WEB_ALLOWED_HOSTS` pour accepter le nom Tailscale.
- **Config OpenCode dédiée.** Un `opencode.json` avec un provider `ccr`, chaque modèle adressé en `<provider>/<model>` (par exemple `openrouter/qwen/qwen3.8-flash`), pointé sur `http://127.0.0.1:3456/v1`.

Jusque-là, tout allait bien. Les problèmes sont arrivés à l'usage.

## Les risques que j'ai rencontrés avec CCR

### Des modèles inaccessibles, pour de mauvaises raisons

L'adressage `provider/model` de CCR casse dès que l'identifiant du modèle commence par un segment qui ressemble lui-même à un nom de provider connu. `openai/gpt-5.3-codex` et `openrouter/free` en sont deux exemples concrets : CCR retire deux fois le préfixe au lieu d'une, et la requête échoue à l'étape de résolution, avant même d'atteindre le fournisseur. Le provider Codex API, lui, est carrément absent du routage générique : il n'est joignable que via le wrapper OAuth dédié à Codex CLI, pas via la passerelle Anthropic classique.

Résultat concret : sur les neuf modèles que je voulais exposer dans OpenCode, deux étaient structurellement injoignables, quelle que soit l'orthographe testée.

### Des 429 sur l'abonnement Claude Pro

Après une ré-authentification OAuth (le jeton de CCR pour Claude Code API expire de temps en temps), cinq requêtes `claude-sonnet-5` d'affilée sont revenues en `429 Too Many Requests`, en moins d'une minute. La connexion OAuth d'un abonnement Pro a des limites de débit bien plus basses qu'une vraie clé API, et CCR, en enchaînant les tentatives, tombe dedans plus vite qu'un usage manuel.

### De la lenteur inexpliquée

Un appel DeepSeek v4.1 Flash via OpenRouter, passé par CCR, a mis plus de 30 secondes à répondre à un simple « dis bonjour ». Passé directement par cliproxy, la même requête revient en quelques secondes. Rien dans la config n'explique l'écart, juste une couche de traduction en plus dans CCR (`openai_chat_completions` → routage interne → upstream) qui semble ajouter de la latence sous charge.

Trois problèmes indépendants, mais un seul point commun : ils viennent tous de la couche de routage de CCR, pas des fournisseurs derrière.

## Le changement : cliproxy (CLIProxyAPI)

Cliproxy tournait déjà sur le serveur, pour une tout autre raison : relayer des sessions OAuth de CLI (Claude Code, Codex, Gemini) sans dupliquer les logins. Son fichier de config supporte aussi des providers `openai-compatibility` : un bloc suffit pour brancher OpenRouter, avec un préfixe explicite (`openrouter/`) et un alias par modèle.

Différence de fond avec CCR : cliproxy adresse les modèles par alias plat, pas par découpage récursif d'une chaîne `provider/model`. Aucun des deux bugs de CCR ne s'est reproduit, `openrouter/gpt-5.3-codex` et `openrouter/free` fonctionnent du premier coup. Sa session OAuth Claude est indépendante de celle de CCR : elle n'avait pas expiré, aucun `429` rencontré depuis.

Deux providers OpenCode suffisent pour couvrir tout ça :

- `cliproxy-claude` (protocole Anthropic) pour les trois modèles Claude natifs
- `cliproxy-openrouter` (protocole OpenAI) pour les neuf alias OpenRouter

## Les modèles utilisés, par fournisseur

Trois comptes, trois façons de payer. C'est le point important pour la suite : choisir un modèle, c'est aussi choisir quel compte débiter.

| Fournisseur | Facturation | Modèles exposés |
| --- | --- | --- |
| Claude (via cliproxy, OAuth) | Abonnement Pro, 20 €/mois, forfaitaire | `claude-sonnet-5`, `claude-opus-5`, `claude-haiku-4-5-20251001` |
| OpenRouter (via cliproxy, clé API) | Solde prépayé, au token | `qwen/qwen3.8-flash` (alias `qwen-flash`), `deepseek/deepseek-v4.1-flash` (`deepseek-flash`), `deepseek/deepseek-v4-pro` (`deepseek-pro`), `google/gemini-3.8-flash` (`gemini-flash`), `openai/gpt-5.6-terra` (`gpt-terra`), `openai/gpt-5.6-luna` (`gpt-luna`), `moonshotai/kimi-k3` (`kimi`), `openai/gpt-5.3-codex`, `openrouter/free` |
| OpenCode Zen (natif, direct) | Tier gratuit | Modèles gratuits du catalogue Zen, accès direct sans passer par CCR ni cliproxy |

## Tableau de décision

La question n'est jamais « quel est le meilleur modèle ». C'est « quel est le bon modèle pour cette tâche, sur le compte que je veux débiter ».

| Complexité de la tâche | Option 1 | Option 2 | Option 3 |
| --- | --- | --- | --- |
| Tâche complexe (architecture, refonte, debug difficile) | Claude Sonnet 5 — Claude Pro | GPT Terra — OpenRouter | DeepSeek v4 Pro — OpenRouter |
| Usage courant | Claude Sonnet 5 — Claude Pro | Gemini 3.8 Flash — OpenRouter | Kimi (latest) — OpenRouter |
| Tâche simple | Qwen 3.8 Flash — OpenRouter | — | — |
| Tâche bon marché / volume | Claude Haiku 4.5 — Claude Pro | DeepSeek v4.1 Flash — OpenRouter | Modèle Zen gratuit — OpenCode Zen |

Le forfait Claude Pro n'a pas de coût marginal tant qu'on reste sous ses limites de débit, donc pour l'usage courant, il reste le premier réflexe. OpenRouter prend le relais quand Claude est occupé, en rate limit, ou pour distribuer la charge sur des tâches parallèles. Zen couvre ce qui ne justifie même pas de dépenser un crédit OpenRouter.

## Ce qui reste ouvert

CCR n'est pas mauvais dans l'absolu, son catalogue de providers est plus large, et sa gestion des credentials OAuth pour Codex est plus poussée que ce que fait cliproxy. Mais pour le cas précis « OpenCode + T3 Code + facturation multi-comptes », cliproxy s'est montré plus fiable, sans les deux bugs de routage décrits plus haut, et sans latence anormale. CCR reste installé sur le serveur, au cas où.
