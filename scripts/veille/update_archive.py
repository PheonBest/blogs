#!/usr/bin/env python3
"""Publish a veille digest entry into digests/ on this repo's main branch.

Usage:
    <build the entry JSON> | python3 update_archive.py /path/to/blogs

Reads one JSON object (the entry) from stdin. Entry shape:
    {"date": "YYYY-MM-DD", "label": "...", "title": "...",
     "sections": [{"name": "...", "paragraphs": [[{"t": "..."}, {"cite": 1}, ...]]}],
     "sources": [{"n": 1, "title": "...", "url": "...", "feed": "..."}]}

Writes digests/<date>.json (one file per day, overwritten if the date already
has an entry), and updates digests/index.json (newest first, lightweight
{date,label,title} list used by search/listing without fetching every file).
Commits and pushes directly to the current branch (this repo has no GitOps
concerns, so no orphan-branch dance is needed like gitops-demo's `data`
branch) — rebase + one retry on push conflict.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DIGESTS_DIR = "digests"
INDEX_REL = "digests/index.json"


def run(*args, cwd=None, check=True):
    return subprocess.run(args, cwd=cwd, check=check, text=True,
                          capture_output=True)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    repo = Path(sys.argv[1]).resolve()
    if not (repo / ".git").exists():
        print(f"not a git repo: {repo}", file=sys.stderr)
        return 2

    entry = json.load(sys.stdin)
    for k in ("date", "title"):
        if k not in entry:
            print(f"entry missing key: {k}", file=sys.stderr)
            return 2
    if "sections" not in entry and "paragraphs" not in entry:
        print("entry missing key: sections (or legacy paragraphs)", file=sys.stderr)
        return 2

    digest_path = repo / DIGESTS_DIR / f"{entry['date']}.json"
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(json.dumps(entry, ensure_ascii=False, indent=1) + "\n")

    index_path = repo / INDEX_REL
    try:
        index = json.loads(index_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        index = {"updated_at": None, "entries": []}

    entries = [e for e in index.get("entries", []) if e.get("date") != entry["date"]]
    entries.insert(0, {"date": entry["date"], "label": entry.get("label", ""),
                        "title": entry["title"]})
    entries.sort(key=lambda e: e.get("date", ""), reverse=True)
    index["entries"] = entries
    index["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n")

    run("git", "add", str(digest_path.relative_to(repo)), INDEX_REL, cwd=repo)
    if not run("git", "diff", "--cached", "--quiet", cwd=repo, check=False).returncode:
        print("no change")
        return 0
    run("git", "-c", "user.name=veille-summary",
        "-c", "user.email=veille-summary@users.noreply.github.com",
        "commit", "-m", f"chore(veille): digest {entry['date']}", cwd=repo)

    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=repo).stdout.strip()
    for attempt in range(2):
        run("git", "fetch", "origin", branch, cwd=repo)
        run("git", "rebase", f"origin/{branch}", cwd=repo, check=False)
        push = run("git", "push", "origin", f"HEAD:{branch}", cwd=repo, check=False)
        if push.returncode == 0:
            print(f"pushed digest {entry['date']}")
            return 0
        print(f"push attempt {attempt + 1} failed: {push.stderr.strip()}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
