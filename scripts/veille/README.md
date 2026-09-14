# scripts/veille — Récap IA de veille tech pour Glance

Runs daily via `.github/workflows/veille-summary.yaml` as a single OpenRouter
chat completion (`OPENROUTER_API_KEY` repo secret, model configurable via the
`OPENROUTER_MODEL` repo variable, defaults to `anthropic/claude-sonnet-5`).
Publishes into `digests/` on this repo's `main` branch, which the
`Gloweet/glance` fork reads directly and unauthenticated (this repo is
public): `https://raw.githubusercontent.com/PheonBest/blogs/main/digests/<date>.json`.

Moved here from `Gloweet/gitops-demo` on 2026-09-11 — that repo is GitOps-only
(Flux reconciles it into the cluster), not a place for daily content commits.
This repo has no such constraint, so the pipeline runs and publishes directly
on `main`.

Originally ran on the agentic Claude Code GitHub Action with a
`CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`). Dropped 2026-09-14:
that token is tied to whichever session last authenticated the same Claude
account, and kept getting invalidated by local `claude` logins (401 "OAuth
access token is invalid", twice in a week). `generate_digest.py` now does the
same job — fetch, write, Boileau pass, structured JSON out — as one
non-agentic call, independent of any local session.

Canonical source of the fetcher/Boileau tooling: `Gloweet/gloweet-meta`
(`skills/veille/`, `skills/veille-summary/`). Keep this copy in sync when the
originals change. `veille-summary.md` there still documents the manual/local
`/veille-summary` skill flow; the CI workflow no longer reads it directly —
its rules are inlined in `generate_digest.py`'s prompt instead.

| File | Role |
| ---- | ---- |
| `fetch_feeds.py` | Pulls the francophone tech RSS feeds. `python3 fetch_feeds.py <days> <categories>` → TSV on stdout. Pure stdlib. |
| `sources.yml` | Feed list + categories, read by `fetch_feeds.py`. |
| `generate_digest.py` | Runs `fetch_feeds.py`, sends the articles + the Boileau guide to OpenRouter in one call, prints the entry JSON on stdout. `python3 generate_digest.py <repo-root> <step_days>` |
| `veille-summary.md` | The procedure `generate_digest.py`'s prompt is based on. Used directly by the manual `/veille-summary` skill locally; not read by the CI workflow. |
| `boileau.md` | AI-tic removal guide, embedded in `generate_digest.py`'s prompt. Vendored from `alxbd/boileau` (MIT — see `boileau.LICENSE`). |
| `update_archive.py` | Writes `digests/<date>.json` + updates `digests/index.json`, commits and pushes to the current branch (rebase + one retry). `printf '%s' "$JSON" \| python3 update_archive.py <repo-root>` |

## Layout

```
digests/
  config.json    # {"step_days": N} — cadence; the workflow's guard job reads
                 # this to decide whether to run today and how wide a fetch
                 # window to use. Edit the number to change cadence.
  index.json     # {date,label,title} per entry, newest first — cheap listing
                 # for search without fetching every digest file.
  latest.json    # full content of the newest 20 entries — what the Glance
                 # widget actually fetches (raw.githubusercontent.com, no
                 # auth, no Flux/ConfigMap plumbing needed).
  <date>.json    # one full digest per day (schema: see veille-summary.md)
```
