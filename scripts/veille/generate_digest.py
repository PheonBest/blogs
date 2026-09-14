#!/usr/bin/env python3
"""Generate a French tech digest entry via OpenRouter and print it as JSON.

Replaces the agentic Claude Code loop (which depended on a subscription
OAuth token that kept getting invalidated by concurrent local `claude`
logins — see git history) with a single non-agentic chat completion call,
billed per-token on OpenRouter instead of tied to a subscription session.

Usage:
    python3 generate_digest.py <repo_root> <step_days> > entry.json
    # then: cat entry.json | python3 update_archive.py <repo_root>

Reads from the environment:
    OPENROUTER_API_KEY  required.
    OPENROUTER_MODEL    optional, default "anthropic/claude-sonnet-5".

Output on stdout: one JSON object matching the schema update_archive.py
expects (date, label, title, sections, sources). Nothing else goes to
stdout — logs and errors go to stderr.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import date, timezone, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-sonnet-5"

FR_WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FR_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def french_label(d: date) -> str:
    return f"{FR_WEEKDAYS[d.weekday()]} {d.day} {FR_MONTHS[d.month - 1]} {d.year}"


def fetch_articles(step_days: str) -> str:
    """Run fetch_feeds.py, return its stdout TSV. Forwards stderr notes/errors."""
    proc = subprocess.run(
        ["python3", str(SCRIPT_DIR / "fetch_feeds.py"), step_days, "all"],
        capture_output=True, text=True, check=True,
    )
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return proc.stdout


def split_tsv(tsv: str) -> tuple[list[str], str]:
    """Split fetch_feeds.py output into (article lines, sources block)."""
    lines = tsv.splitlines()
    if "SOURCES:" in lines:
        idx = lines.index("SOURCES:")
        return lines[:idx], "\n".join(lines[idx:])
    return lines, ""


SYSTEM_PROMPT = """Tu écris le récap quotidien de veille tech francophone pour \
un dashboard perso. Le texte est lu chaque matin par une seule personne : \
court, vivant, avec un point de vue. Pas une liste d'items reformulés.

## Rédaction (2 à 4 sections thématiques)

À partir du TSV fourni (une ligne par article : DATE, TITRE, LIEN, CATEGORIE, \
DESCRIPTION, SOURCE), regroupe les articles en 2 à 4 sections thématiques \
nommées selon ce que le TSV contient réellement ce jour-là (ex: "Dev & Ops", \
"Culture" — pas une liste fixe). Chaque section a 1 à 2 paragraphes de \
~120-200 mots.

Règles :
- Un vrai fil narratif par section : relie les articles entre eux, dégage ce \
qui compte, dis pourquoi c'est intéressant. Si rien ne sort du lot dans une \
catégorie, ne force pas une section pour elle.
- Un point de vue : le droit de trouver une annonce tiède, une reprise de \
hype fatigante, un billet excellent. Nuance quand c'est nuancé.
- Citations : chaque fait rattaché à un article porte un appel de citation \
(voir schéma JSON plus bas). Numérote dans l'ordre d'apparition. Un même \
article = un seul numéro, réutilisable.
- Titre : une ligne, accrocheuse, qui résume l'angle du jour.
- Pas de méta ("dans ce récap, nous verrons…"), pas de conclusion générique.
- N'invente rien qui ne soit pas dans le TSV. Si une description est vide \
(N/A), fie-toi au titre et à la source, ne brode pas.

## Passe de style (obligatoire, avant de finaliser)

Applique au brouillon (titre + sections) le guide anti-tics-IA suivant. Ne \
livre jamais un texte qui contient encore ces marqueurs.

{boileau}

## Format de sortie

Réponds UNIQUEMENT avec un objet JSON, sans texte avant/après, sans balises \
markdown, correspondant exactement à ce schéma :

{{
  "title": "<titre accrocheur>",
  "sections": [
    {{
      "name": "Dev & Ops",
      "paragraphs": [
        [
          {{"t": "Dalibo sort la 1.0 de PostgreSQL Migrator"}},
          {{"cite": 1}},
          {{"t": ", et la newsletter de RudeOps est dense cette semaine"}},
          {{"cite": 2}},
          {{"t": "."}}
        ]
      ]
    }}
  ],
  "sources": [
    {{"n": 1, "title": "<titre exact de l'article>", "url": "<lien>", "feed": "<SOURCE du TSV>"}}
  ]
}}

Chaque paragraphe est un tableau de "runs" : {{"t": "texte"}} pour du texte, \
{{"cite": n}} pour un appel de citation (numéro seul, pas de "[n]" en texte \
brut). "sources" ne contient que les articles réellement cités, dans l'ordre \
des numéros."""


def build_user_prompt(article_lines: list[str]) -> str:
    return "Articles (TSV) :\n\n" + "\n".join(article_lines)


def call_openrouter(model: str, system: str, user: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        sys.exit(2)
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
        "max_tokens": 8000,
        # Reasoning models (Claude Sonnet 5 included) can spend the entire
        # max_tokens budget on hidden thinking tokens and return content:
        # null with finish_reason: length. This is a one-shot structured
        # JSON write, not a task that benefits from extended thinking.
        "reasoning": {"enabled": False},
    }).encode()
    req = urllib.request.Request(
        OPENROUTER_URL, data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"OpenRouter API error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    choice = data["choices"][0]
    content = choice.get("message", {}).get("content")
    if not content:
        print(
            f"OpenRouter returned no content (finish_reason={choice.get('finish_reason')}): "
            f"{json.dumps(choice)[:2000]}",
            file=sys.stderr,
        )
        sys.exit(1)
    return content


def extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


def minimal_entry(today: date) -> dict:
    return {
        "date": today.isoformat(),
        "label": french_label(today),
        "title": "Rien de neuf côté veille",
        "sections": [{"name": "", "paragraphs": [[
            {"t": "Les flux n'ont rien publié depuis le dernier récap."}
        ]]}],
        "sources": [],
    }


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    repo_root, step_days = sys.argv[1], sys.argv[2]
    today = datetime.now(timezone.utc).date()

    tsv = fetch_articles(step_days)
    article_lines, _sources_block = split_tsv(tsv)

    if not article_lines:
        print("no articles in window, emitting minimal entry", file=sys.stderr)
        print(json.dumps(minimal_entry(today), ensure_ascii=False))
        return 0

    boileau_text = (Path(repo_root) / "scripts/veille/boileau.md").read_text()
    # `.get(..., DEFAULT_MODEL)` only falls back when the key is absent, but
    # the workflow always sets OPENROUTER_MODEL (from an optional repo var)
    # so an unset var arrives here as "" rather than missing entirely.
    model = os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL
    system = SYSTEM_PROMPT.format(boileau=boileau_text)
    user = build_user_prompt(article_lines)

    raw = call_openrouter(model, system, user)
    try:
        draft = extract_json(raw)
    except json.JSONDecodeError as e:
        print(f"model did not return valid JSON: {e}\n---\n{raw}", file=sys.stderr)
        return 1

    for key in ("title", "sections", "sources"):
        if key not in draft:
            print(f"model output missing key: {key}\n---\n{raw}", file=sys.stderr)
            return 1

    entry = {
        "date": today.isoformat(),
        "label": french_label(today),
        "title": draft["title"],
        "sections": draft["sections"],
        "sources": draft["sources"],
    }
    print(json.dumps(entry, ensure_ascii=False))
    print(f"generated: {entry['title']} ({len(entry['sources'])} sources)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
