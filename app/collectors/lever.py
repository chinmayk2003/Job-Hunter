"""
collectors/lever.py — Lever public postings collector
======================================================
Lever exposes a public JSON endpoint for every company using it:

    https://api.lever.co/v0/postings/{company}?mode=json&limit=250

No API key required. The `limit=250` is the maximum per request.
For companies with >250 jobs, pagination via `offset` is supported.
"""

import time
from typing import Optional

import requests

from app.config import REQUEST_TIMEOUT, REQUEST_DELAY
from app.database.db import upsert_job

LEVER_API = "https://api.lever.co/v0/postings/{slug}?mode=json&limit=250"
LEVER_JOB_URL = "https://jobs.lever.co/{slug}/{id}"


# ── Fetching ───────────────────────────────────────────────────────────────────

def fetch_lever_jobs(company_name: str, slug: str) -> list[dict]:
    """
    Hit the Lever public API for one company.
    Returns list of raw posting dicts, or [] on error.
    """
    url = LEVER_API.format(slug=slug)
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        jobs = resp.json()  # Lever returns a plain list at top level
        if isinstance(jobs, dict):
            # Some slugs return {"data": [...]} format
            jobs = jobs.get("data", [])
        print(f"  [Lever] {company_name}: {len(jobs)} postings found")
        return jobs
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            print(f"  [Lever] {company_name}: slug '{slug}' not found — check companies.json")
        else:
            print(f"  [Lever] {company_name}: HTTP error — {e}")
    except requests.RequestException as e:
        print(f"  [Lever] {company_name}: request failed — {e}")
    return []


# ── Parsing ────────────────────────────────────────────────────────────────────

def _extract_description(posting: dict) -> str:
    """
    Lever postings have structured 'lists' and 'additional' fields.
    Flatten them into plain text for matching.
    """
    parts = []

    # Lever 'descriptionPlain' field (if present)
    plain = posting.get("descriptionPlain", "")
    if plain:
        parts.append(plain)

    # 'lists' field: [{"text": "Requirements", "content": "..."}, ...]
    for lst in posting.get("lists", []):
        header  = lst.get("text", "")
        content = lst.get("content", "")
        if header:
            parts.append(header)
        if content:
            # content can contain <li> tags
            parts.append(
                content.replace("<li>", "\n• ")
                       .replace("</li>", "")
                       .replace("<br>", "\n")
            )

    # 'additional' field
    additional = posting.get("additionalPlain", "") or posting.get("additional", "")
    if additional:
        parts.append(additional)

    return "\n".join(parts).strip()


def _extract_location(posting: dict) -> str:
    """Return location string from a Lever posting."""
    categories = posting.get("categories", {})
    if isinstance(categories, dict):
        return categories.get("location", "") or categories.get("allLocations", [""])[0]
    return ""


def _extract_posted_date(posting: dict) -> str:
    """Return ISO date from Lever unix timestamp (milliseconds)."""
    ts = posting.get("createdAt", 0)
    if ts:
        from datetime import datetime
        return datetime.utcfromtimestamp(ts / 1000).date().isoformat()
    return ""


# ── Saving ─────────────────────────────────────────────────────────────────────

def collect(company_name: str, slug: str) -> int:
    """
    Full pipeline for one Lever company:
      fetch → parse → save to DB
    Returns the number of NEW jobs inserted.
    """
    raw_jobs = fetch_lever_jobs(company_name, slug)
    new_count = 0

    for posting in raw_jobs:
        uid         = posting.get("id", "")
        title       = posting.get("text", "").strip()
        url         = posting.get("hostedUrl", "") or LEVER_JOB_URL.format(slug=slug, id=uid)
        description = _extract_description(posting)
        location    = _extract_location(posting)
        posted_date = _extract_posted_date(posting)

        if not url or not title:
            continue

        upsert_job(
            company=company_name,
            title=title,
            url=url,
            location=location,
            description=description,
            source="lever",
            posted_date=posted_date,
        )
        new_count += 1

    time.sleep(REQUEST_DELAY)
    return new_count


def collect_all(companies: list[dict]) -> int:
    """
    Run Lever collection for every company that has a lever_slug.
    Returns total new jobs across all companies.
    """
    total_new = 0
    lever_companies = [c for c in companies if c.get("lever_slug")]

    print(f"[Lever] Collecting from {len(lever_companies)} companies...")
    for company in lever_companies:
        new = collect(company["name"], company["lever_slug"])
        total_new += new

    print(f"[Lever] Done. {total_new} new jobs saved.\n")
    return total_new
