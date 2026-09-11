# scripts/veille — Récap IA de veille tech pour Glance

Runs daily via `.github/workflows/veille-summary.yaml` on a Claude subscription
(`CLAUDE_CODE_OAUTH_TOKEN` repo secret, from `claude setup-token`). Publishes
into `digests/` on this repo's `main` branch, which the `Gloweet/glance` fork
reads directly and unauthenticated (this repo is public):
`https://raw.githubusercontent.com/PheonBest/blogs/main/digests/<date>.json`.

Moved here from `Gloweet/gitops-demo` on 2026-09-11 — that repo is GitOps-only
(Flux reconciles it into the cluster), not a place for daily content commits.
This repo has no such constraint, so the pipeline runs and publishes directly
on `main`.

Canonical source of the fetcher/Boileau tooling: `Gloweet/gloweet-meta`
(`skills/veille/`, `skills/veille-summary/`). Keep this copy in sync when the
originals change.

| File | Role |
| ---- | ---- |
| `fetch_feeds.py` | Pulls the francophone tech RSS feeds. `python3 fetch_feeds.py <days> <categories>` → TSV on stdout. Pure stdlib. |
| `sources.yml` | Feed list + categories, read by `fetch_feeds.py`. |
| `veille-summary.md` | The procedure: fetch → write French digest (sectioned, run-based citations) → Boileau pass → publish. |
| `boileau.md` | AI-tic removal guide applied to the draft. Vendored from `alxbd/boileau` (MIT — see `boileau.LICENSE`). |
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
