#!/usr/bin/env python3
"""Generate a French tech digest entry via OpenRouter and print it as JSON.

Replaces the agentic Claude Code loop (which depended on a subscription
OAuth token that kept getting invalidated by concurrent local `claude`
logins — see git history) with a single non-agentic chat completion call,
billed per-token on OpenRouter instead of tied to a subscription session.

Usage:
    python3 generate_digest.py <repo_root> <days> > entry.json
    # then: cat entry.json | python3 update_archive.py <repo_root>

Reads from the environment:
    OPENROUTER_API_KEY  required.
    OPENROUTER_MODEL    optional, default "anthropic/claude-sonnet-5".

<days> is the look-back window. Up to CATCHUP_MIN_DAYS - 1 days it is one
call, as for a daily digest. Longer windows (catch-up after missed runs) are
split into chunks of at most CHUNK_MAX_ARTICLES articles, each written by its
own call so the cited-link ratio stays what a daily digest has, then merged
(citations renumbered). Any article the model left uncited is appended in an
"Aussi publié" section so no link of the window is lost.

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
from datetime import date, timedelta, timezone, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-sonnet-5"

CATCHUP_MIN_DAYS = 3
CHUNK_MAX_ARTICLES = 40

FR_WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FR_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
FR_MONTHS_SHORT = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
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

{window_rules}

À partir du TSV fourni (une ligne par article : DATE, TITRE, LIEN, CATEGORIE, \
DESCRIPTION, SOURCE), regroupe les articles en 2 à 4 sections thématiques \
nommées selon ce que le TSV contient réellement ce jour-là (ex: "Dev & Ops", \
"Culture" — pas une liste fixe). {length_rule}

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


DAILY_RULES = {
    "window_rules": "",
    "length_rule": "Chaque section a 1 à 2 paragraphes de ~120-200 mots.",
}


def catchup_rules(start: date, end: date, n_articles: int) -> dict:
    return {
        "window_rules": (
            f"Ce lot couvre du {french_label(start)} au {french_label(end)} "
            f"({n_articles} articles), pas seulement la veille. Cite au moins "
            "80 % des articles : regroupe-les par thème et cite plusieurs "
            "articles par phrase quand ils traitent du même sujet. N'écarte que "
            "le bruit manifeste (hors sujet, doublon, pub). Les articles sont "
            "classés du plus ancien au plus récent : respecte cet ordre quand "
            "la chronologie compte.\n"
        ),
        "length_rule": (
            "Chaque section a 2 à 4 paragraphes de ~120-200 mots, assez pour "
            "citer tous les articles qui comptent."
        ),
    }


def build_user_prompt(article_lines: list[str]) -> str:
    return "Articles (TSV) :\n\n" + "\n".join(article_lines)


def call_openrouter(model: str, system: str, user: str, max_tokens: int = 8000) -> str:
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
        "max_tokens": max_tokens,
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


def parse_articles(lines: list[str]) -> list[dict]:
    """TSV lines -> dicts; lines without a date/title/url are dropped."""
    articles = []
    for line in lines:
        f = line.split("\t")
        if len(f) < 3 or not f[2]:
            continue
        articles.append({
            "date": date.fromisoformat(f[0]), "title": f[1], "url": f[2],
            "feed": f[5] if len(f) > 5 else "", "line": line,
        })
    return articles


def chunk_articles(articles: list[dict]) -> list[list[dict]]:
    """Oldest-first chunks of at most CHUNK_MAX_ARTICLES, split on day boundaries."""
    by_day: dict[date, list[dict]] = {}
    for a in articles:
        by_day.setdefault(a["date"], []).append(a)
    chunks: list[list[dict]] = []
    current: list[dict] = []
    for day in sorted(by_day):
        if current and len(current) + len(by_day[day]) > CHUNK_MAX_ARTICLES:
            chunks.append(current)
            current = []
        current.extend(by_day[day])
    if current:
        chunks.append(current)
    return chunks


def period_label(start: date, end: date) -> str:
    def fmt(d: date) -> str:
        return f"{d.day} {FR_MONTHS_SHORT[d.month - 1]}"
    if start == end:
        return fmt(end)
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{fmt(end)}"
    return f"{fmt(start)}–{fmt(end)}"


def write_chunk(model: str, boileau: str, chunk: list[dict], rules: dict) -> dict:
    system = SYSTEM_PROMPT.format(boileau=boileau, **rules)
    user = build_user_prompt([a["line"] for a in chunk])
    for attempt in range(2):
        raw = call_openrouter(model, system, user, max_tokens=12000 if rules["window_rules"] else 8000)
        try:
            draft = extract_json(raw)
        except json.JSONDecodeError as e:
            print(f"model did not return valid JSON (attempt {attempt + 1}): {e}\n---\n{raw}", file=sys.stderr)
            continue
        missing = [k for k in ("title", "sections", "sources") if k not in draft]
        if not missing:
            # Drop sources the model invented: only URLs present in the TSV count.
            known = {a["url"] for a in chunk}
            draft["sources"] = [s for s in draft["sources"] if s.get("url") in known]
            return draft
        print(f"model output missing keys {missing}\n---\n{raw}", file=sys.stderr)
    raise SystemExit(1)


def merge_drafts(drafts: list[dict], periods: list[str]) -> tuple[list[dict], list[dict]]:
    """Concatenate chunk drafts, renumbering citations globally (one number per URL)."""
    sections: list[dict] = []
    sources: list[dict] = []
    n_by_url: dict[str, int] = {}
    for draft, period in zip(drafts, periods):
        local: dict[int, int] = {}
        for src in draft["sources"]:
            if src["url"] not in n_by_url:
                sources.append({**src, "n": len(sources) + 1})
                n_by_url[src["url"]] = len(sources)
            local[src["n"]] = n_by_url[src["url"]]
        for sec in draft["sections"]:
            paragraphs = [
                [{"cite": local[r["cite"]]} if "cite" in r else r
                 for r in para if "cite" not in r or r["cite"] in local]
                for para in sec["paragraphs"]
            ]
            name = sec.get("name", "")
            sections.append({
                "name": f"{period} · {name}" if period and name else (period or name),
                "paragraphs": paragraphs,
            })
    return sections, sources


def append_uncited(sections: list[dict], sources: list[dict], articles: list[dict]) -> int:
    """Safety net: list every article of the window the model did not cite."""
    cited = {s["url"] for s in sources}
    left = [a for a in sorted(articles, key=lambda a: a["date"], reverse=True) if a["url"] not in cited]
    paragraphs = []
    for a in left:
        sources.append({"n": len(sources) + 1, "title": a["title"], "url": a["url"], "feed": a["feed"]})
        paragraphs.append([{"t": f"{a['title']} ({a['feed']})" if a["feed"] else a["title"]},
                           {"cite": len(sources)}])
    if paragraphs:
        sections.append({"name": "Aussi publié", "paragraphs": paragraphs})
    return len(left)


def catchup_title(model: str, titles: list[str], start: date, end: date) -> str:
    fallback = f"Récap du {period_label(start, end)}"
    system = ("Tu titres un récap de veille tech francophone. Réponds par UN titre "
              "accrocheur en français (max 100 caractères), sans guillemets ni markdown, "
              "qui résume l'angle de la période à partir des titres des parties.")
    try:
        out = call_openrouter(model, system, "\n".join(f"- {t}" for t in titles), max_tokens=200)
    except SystemExit:
        return fallback
    return out.strip().strip('"«» ').splitlines()[0] if out.strip() else fallback


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    repo_root, days = sys.argv[1], int(sys.argv[2])
    today = datetime.now(timezone.utc).date()

    tsv = fetch_articles(str(days))
    article_lines, _sources_block = split_tsv(tsv)
    articles = parse_articles(article_lines)

    if not articles:
        print("no articles in window, emitting minimal entry", file=sys.stderr)
        print(json.dumps(minimal_entry(today), ensure_ascii=False))
        return 0

    boileau_text = (Path(repo_root) / "scripts/veille/boileau.md").read_text()
    # `.get(..., DEFAULT_MODEL)` only falls back when the key is absent, but
    # the workflow always sets OPENROUTER_MODEL (from an optional repo var)
    # so an unset var arrives here as "" rather than missing entirely.
    model = os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL

    catchup = days >= CATCHUP_MIN_DAYS
    start = today - timedelta(days=days)
    if not catchup:
        draft = write_chunk(model, boileau_text, articles, DAILY_RULES)
        title, sections, sources = draft["title"], draft["sections"], draft["sources"]
    else:
        chunks = chunk_articles(articles)
        print(f"catch-up: {len(articles)} articles over {days} days, {len(chunks)} chunk(s)", file=sys.stderr)
        drafts, periods = [], []
        for chunk in chunks:
            c_start, c_end = min(a["date"] for a in chunk), max(a["date"] for a in chunk)
            drafts.append(write_chunk(model, boileau_text, chunk, catchup_rules(c_start, c_end, len(chunk))))
            periods.append(period_label(c_start, c_end) if len(chunks) > 1 else "")
        sections, sources = merge_drafts(drafts, periods)
        title = drafts[0]["title"] if len(drafts) == 1 else catchup_title(
            model, [d["title"] for d in drafts], start, today)
        cited = len(sources)
        added = append_uncited(sections, sources, articles)
        print(f"coverage: {cited}/{len(articles)} cited by the model, {added} appended", file=sys.stderr)

    entry = {
        "date": today.isoformat(),
        "label": french_label(today),
        "title": title,
        "sections": sections,
        "sources": sources,
    }
    if catchup:
        entry["covers"] = {"from": start.isoformat(), "to": today.isoformat()}
    print(json.dumps(entry, ensure_ascii=False))
    print(f"generated: {entry['title']} ({len(entry['sources'])} sources)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
