#!/usr/bin/env python3
"""Fetch and parse RSS feeds from sources.yml, output TSV sorted by date."""

import sys
import os
import re
import html
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

DURATION_MULTIPLIERS = {
    "day": 1, "jour": 1,
    "week": 7, "semaine": 7,
    "month": 30, "mois": 30,
    "year": 365, "an": 365, "annee": 365,
}


def parse_days(arg):
    """Parse a day count from an int string or a duration string like '12 months'."""
    if not arg:
        return 7
    arg = arg.strip()
    try:
        return int(arg)
    except ValueError:
        pass
    match = re.match(r"(\d+)\s*([a-zA-Zéà]+)", arg)
    if match:
        n = int(match.group(1))
        unit = normalize_slug(match.group(2)).rstrip("s")
        if unit in DURATION_MULTIPLIERS:
            return n * DURATION_MULTIPLIERS[unit]
    print(f"WARNING: could not parse duration '{arg}', defaulting to 7 days", file=sys.stderr)
    return 7


def normalize_slug(text):
    """Lowercase, strip accents, replace spaces with hyphens for tolerant matching."""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.replace(" ", "-")


def load_sources():
    """Load sources from sources.yml next to this script (no PyYAML needed)."""
    sources_path = Path(__file__).parent / "sources.yml"
    sources = []
    current = None
    with open(sources_path) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("#") or not stripped or stripped == "sources:":
                continue
            if stripped.startswith("- name:"):
                if current:
                    sources.append(current)
                current = {"name": stripped.split(":", 1)[1].strip()}
            elif current and ":" in stripped:
                key, val = stripped.split(":", 1)
                val = val.split("#")[0].strip()
                current[key.strip()] = val
    if current:
        sources.append(current)
    return sources


def strip_html(text):
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = " ".join(text.split())
    return text[:150]


def parse_rss_date(date_str):
    """Parse RFC 2822 or ISO 8601 date string to datetime."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str.strip())
    except Exception:
        pass
    # Try ISO 8601 (Atom feeds)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def fetch_feed(source, cutoff_date):
    """Fetch a single RSS/Atom feed and return parsed articles."""
    url = source["url"]
    name = source["name"]
    articles = []

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "veille-techno/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
    except Exception as e:
        return articles, f"ERROR: {name} - {e}"

    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        return articles, f"ERROR: {name} - XML parse error: {e}"

    # Fallback category when the feed itself doesn't tag entries: use the
    # source's own configured category so the recap never shows a bare "N/A".
    src_cats = sorted(source_categories(source))
    fallback_category = src_cats[0] if src_cats else "N/A"

    # Handle RSS 2.0
    ns = {"dc": "http://purl.org/dc/elements/1.1/", "atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item")

    if items:
        # RSS 2.0
        for item in items:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            date_str = item.findtext("pubDate", "")
            raw_desc = strip_html(item.findtext("description", ""))
            # JDH uses description for comment links — filter those out
            desc = "" if raw_desc.startswith("Comments") or raw_desc.startswith("http") else raw_desc
            categories = [c.text for c in item.findall("category") if c.text]
            category = categories[0] if categories else fallback_category

            pub_date = parse_rss_date(date_str)
            if pub_date and pub_date.date() >= cutoff_date:
                articles.append({
                    "date": pub_date,
                    "title": title,
                    "link": link,
                    "category": category,
                    "description": desc,
                    "source": name,
                })
    else:
        # Try Atom format
        atom_ns = "http://www.w3.org/2005/Atom"
        entries = root.findall(f".//{{{atom_ns}}}entry")
        for entry in entries:
            title = (entry.findtext(f"{{{atom_ns}}}title") or "").strip()
            link_el = entry.find(f"{{{atom_ns}}}link[@href]")
            link = link_el.get("href", "") if link_el is not None else ""
            date_str = entry.findtext(f"{{{atom_ns}}}updated") or entry.findtext(f"{{{atom_ns}}}published") or ""
            raw_content = entry.findtext(f"{{{atom_ns}}}summary") or entry.findtext(f"{{{atom_ns}}}content") or ""
            desc = strip_html(raw_content[:2000])
            cat_el = entry.find(f"{{{atom_ns}}}category")
            category = cat_el.get("term", fallback_category) if cat_el is not None else fallback_category

            pub_date = parse_rss_date(date_str)
            if pub_date and pub_date.date() >= cutoff_date:
                articles.append({
                    "date": pub_date,
                    "title": title,
                    "link": link,
                    "category": category,
                    "description": desc,
                    "source": name,
                })

    return articles, None


def source_categories(source):
    """Parse the comma-separated 'categories' field of a source into a set of normalized slugs."""
    raw = source.get("categories", "")
    return {normalize_slug(c) for c in raw.split(",") if c.strip()}


def parse_requested_categories(category_arg):
    """Turn a raw 'category_arg' CLI value into a set of normalized slugs (empty = all)."""
    if not category_arg or normalize_slug(category_arg) == "all":
        return set()
    return {normalize_slug(c) for c in category_arg.split(",") if c.strip()}


def filter_sources_by_category(sources, requested_categories):
    """Keep only sources matching requested_categories, warning on unrecognized slugs."""
    if not requested_categories:
        return sources
    known_categories = set().union(*(source_categories(s) for s in sources)) if sources else set()
    unknown = requested_categories - known_categories
    if unknown:
        print(
            f"WARNING: unknown categories: {', '.join(sorted(unknown))} "
            f"(valid: {', '.join(sorted(known_categories))})",
            file=sys.stderr,
        )
    return [s for s in sources if requested_categories & source_categories(s)]


def dedupe_articles(all_articles):
    """Deduplicate by URL (keep first occurrence, merge source names), sorted newest first."""
    seen = {}
    for a in all_articles:
        url = a["link"]
        if url in seen:
            if a["source"] not in seen[url]["source"]:
                seen[url]["source"] += f", {a['source']}"
        else:
            seen[url] = a
    return sorted(seen.values(), key=lambda a: a["date"], reverse=True)


def coverage_note(unique_articles, days):
    """Flag when requested duration far exceeds what the fetched feeds actually cover.

    RSS/Atom feeds only retain their most recent entries, not a full history, so asking
    for e.g. 365 days rarely yields a full year of articles.
    """
    if not unique_articles or days < 60:
        return None
    span_days = (unique_articles[0]["date"].date() - unique_articles[-1]["date"].date()).days
    if span_days < days * 0.3:
        return (
            f"NOTE: requested {days} days but retrieved articles only span {span_days} days -- "
            "RSS feeds typically retain only their most recent entries, not a full historical archive."
        )
    return None


def print_tsv(unique_articles):
    for a in unique_articles:
        date_str = a["date"].strftime("%Y-%m-%d")
        desc = a["description"] or "N/A"
        # Sanitize tabs/newlines in fields
        title = a["title"].replace("\t", " ").replace("\n", " ")
        desc = desc.replace("\t", " ").replace("\n", " ")
        cat = a["category"].replace("\t", " ")
        src = a["source"].replace("\t", " ")
        print(f"{date_str}\t{title}\t{a['link']}\t{cat}\t{desc}\t{src}")


def main():
    days = parse_days(sys.argv[1] if len(sys.argv) > 1 else "")
    category_arg = sys.argv[2] if len(sys.argv) > 2 else ""
    requested_categories = parse_requested_categories(category_arg)
    cutoff_date = (datetime.now().date() - timedelta(days=days))

    sources = filter_sources_by_category(load_sources(), requested_categories)
    all_articles = []
    errors = []

    # Fetch all feeds in parallel
    if sources:
        with ThreadPoolExecutor(max_workers=min(len(sources), 10)) as pool:
            futures = {pool.submit(fetch_feed, s, cutoff_date): s for s in sources}
            for future in as_completed(futures):
                articles, error = future.result()
                all_articles.extend(articles)
                if error:
                    errors.append(error)

    unique_articles = dedupe_articles(all_articles)

    # Output errors/notes to stderr so stdout stays clean TSV
    for err in errors:
        print(err, file=sys.stderr)
    note = coverage_note(unique_articles, days)
    if note:
        print(note, file=sys.stderr)

    print_tsv(unique_articles)

    # Output sources section
    print("SOURCES:")
    for s in sources:
        print(f"  {s['name']}\t{s.get('site', s['url'])}\t{s.get('description', '')}")


if __name__ == "__main__":
    main()
