"""
collectors/greenhouse.py — Greenhouse public job board collector
================================================================
Greenhouse exposes a public, no-auth JSON endpoint for every company
that uses it as their ATS:

    https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true

The `content=true` parameter includes the full job description HTML.
No API key required — this is intentionally public.
"""

import time
import re
from html.parser import HTMLParser
from typing import Optional

import requests

from app.config import REQUEST_TIMEOUT, REQUEST_DELAY
from app.database.db import upsert_job

# Base URL pattern for the Greenhouse public API
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


# ── HTML stripping ─────────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    """Minimal HTML→plain-text converter (no external deps needed)."""
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self.text_parts)


def strip_html(html: str) -> str:
    """Return plain text from an HTML string."""
    if not html:
        return ""
    parser = _HTMLStripper()
    parser.feed(html)
    return parser.get_text()


# ── Fetching ───────────────────────────────────────────────────────────────────

def fetch_greenhouse_jobs(company_name: str, slug: str) -> list[dict]:
    """
    Hit the Greenhouse public API for one company.
    Returns a list of raw job dicts (API format), or [] on error.
    """
    url = GREENHOUSE_API.format(slug=slug)
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs", [])
        print(f"  [Greenhouse] {company_name}: {len(jobs)} postings found")
        return jobs
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            print(f"  [Greenhouse] {company_name}: slug '{slug}' not found (404) — check companies.json")
        else:
            print(f"  [Greenhouse] {company_name}: HTTP error — {e}")
    except requests.RequestException as e:
        print(f"  [Greenhouse] {company_name}: request failed — {e}")
    return []


# ── Parsing & saving ───────────────────────────────────────────────────────────

def _parse_location(job: dict) -> str:
    """Extract a human-readable location string from a Greenhouse job object."""
    location = job.get("location", {})
    if isinstance(location, dict):
        return location.get("name", "")
    return str(location)


def _parse_posted_date(job: dict) -> str:
    """Return ISO date string, or empty string if missing."""
    updated = job.get("updated_at", "")
    if updated:
        # Greenhouse uses ISO 8601: "2024-01-15T12:00:00.000Z"
        return updated[:10]
    return ""


def collect(company_name: str, slug: str) -> int:
    """
    Full pipeline for one Greenhouse company:
      fetch → parse → save to DB
    Returns the number of NEW jobs inserted.
    """
    raw_jobs = fetch_greenhouse_jobs(company_name, slug)
    new_count = 0

    for job in raw_jobs:
        title       = job.get("title", "").strip()
        url         = job.get("absolute_url", "").strip()
        description = strip_html(job.get("content", ""))
        location    = _parse_location(job)
        posted_date = _parse_posted_date(job)

        if not url or not title:
            continue  # skip malformed entries

        job_id = upsert_job(
            company=company_name,
            title=title,
            url=url,
            location=location,
            description=description,
            source="greenhouse",
            posted_date=posted_date,
        )

        if job_id:
            new_count += 1

    time.sleep(REQUEST_DELAY)   # be polite to Greenhouse servers
    return new_count


def collect_all(companies: list[dict]) -> int:
    """
    Run Greenhouse collection for every company that has a greenhouse_slug.
    `companies` is the parsed companies.json list.
    Returns total new jobs across all companies.
    """
    total_new = 0
    greenhouse_companies = [c for c in companies if c.get("greenhouse_slug")]

    print(f"\n[Greenhouse] Collecting from {len(greenhouse_companies)} companies...")
    for company in greenhouse_companies:
        new = collect(company["name"], company["greenhouse_slug"])
        total_new += new

    print(f"[Greenhouse] Done. {total_new} new jobs saved.\n")
    return total_new
