"""
collectors/career_pages.py — Generic career page scraper
=========================================================
Fallback for companies that don't use Greenhouse or Lever.
Uses requests + BeautifulSoup to pull job listings from custom career pages.

Because every company's career page is different, this module provides:
  1. A generic extractor that tries common patterns
  2. Company-specific override functions when the generic one fails

To add a custom scraper for a new company:
  1. Write a function: def scrape_<company_key>(url) -> list[dict]
  2. Register it in CUSTOM_SCRAPERS at the bottom of this file
"""

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.config import REQUEST_TIMEOUT, REQUEST_DELAY
from app.database.db import upsert_job

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ── Generic extractor ──────────────────────────────────────────────────────────

def _fetch_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [CareerPages] Failed to fetch {url}: {e}")
        return None


def _generic_scrape(company_name: str, url: str) -> list[dict]:
    """
    Try common patterns to extract job listings from a career page.
    Returns list of {title, url, location, description} dicts.
    """
    soup = _fetch_page(url)
    if not soup:
        return []

    jobs = []

    # Pattern 1: <a> tags containing "job" or "position" in href
    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True)

        if not text or len(text) < 5 or len(text) > 150:
            continue

        href_lower = href.lower()
        # Skip navigation, privacy, social links
        if any(skip in href_lower for skip in ["linkedin", "twitter", "facebook", "privacy", "#"]):
            continue

        # Look for job-like links
        if any(kw in href_lower for kw in ["job", "position", "career", "opening", "role", "apply"]):
            full_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
            jobs.append({
                "title":       text,
                "url":         full_url,
                "location":    "",
                "description": "",
            })

    # Deduplicate by URL
    seen = set()
    unique_jobs = []
    for j in jobs:
        if j["url"] not in seen:
            seen.add(j["url"])
            unique_jobs.append(j)

    print(f"  [CareerPages] {company_name}: {len(unique_jobs)} links found (generic scrape)")
    return unique_jobs[:50]   # cap to avoid scraping 1000 irrelevant links


# ── Company-specific scrapers ──────────────────────────────────────────────────
# Add custom scrapers here when the generic one fails.
# Each function receives (company_name, url) and returns list[dict].

def _scrape_google(company_name: str, url: str) -> list[dict]:
    """
    Google careers uses a JS-heavy SPA — we can't scrape it directly.
    Instead, use the public Google Jobs search API workaround via serpapi
    or simply return empty and rely on user's manual check.
    """
    print(f"  [CareerPages] {company_name}: JS-rendered SPA, cannot scrape directly.")
    print(f"    → Tip: Use https://careers.google.com/jobs/results/?q=data+analyst&location=India")
    return []


def _scrape_amazon(company_name: str, url: str) -> list[dict]:
    """Amazon jobs requires JS. Return placeholder."""
    print(f"  [CareerPages] {company_name}: JS-rendered, cannot scrape directly.")
    print(f"    → Tip: Check https://www.amazon.jobs/en/search?base_query=data+analyst")
    return []


# Registry: maps company name (lowercase, no spaces) → custom scraper function
CUSTOM_SCRAPERS = {
    "google":  _scrape_google,
    "amazon":  _scrape_amazon,
}


# ── Main collect function ──────────────────────────────────────────────────────

def collect(company_name: str, career_url: str) -> int:
    """
    Scrape one company's career page and save jobs to DB.
    Returns count of new jobs saved.
    """
    # Check for custom scraper
    key = company_name.lower().replace(" ", "").replace(".", "")
    scraper = CUSTOM_SCRAPERS.get(key, _generic_scrape)

    raw_jobs = scraper(company_name, career_url)
    new_count = 0

    for job in raw_jobs:
        title       = job.get("title", "").strip()
        url         = job.get("url", "").strip()
        location    = job.get("location", "")
        description = job.get("description", "")

        if not title or not url:
            continue

        upsert_job(
            company=company_name,
            title=title,
            url=url,
            location=location,
            description=description,
            source="career_page",
        )
        new_count += 1

    time.sleep(REQUEST_DELAY)
    return new_count


def collect_all(companies: list[dict]) -> int:
    """
    Run career page scraping for companies that have no Greenhouse/Lever slug
    but have a career_page_url.
    Returns total new jobs.
    """
    total_new = 0
    # Only run for companies without ATS slugs (Greenhouse/Lever already handled them)
    career_page_companies = [
        c for c in companies
        if c.get("career_page_url")
        and not c.get("greenhouse_slug")
        and not c.get("lever_slug")
    ]

    print(f"[CareerPages] Scraping {len(career_page_companies)} company career pages...")
    for company in career_page_companies:
        new = collect(company["name"], company["career_page_url"])
        total_new += new

    print(f"[CareerPages] Done. {total_new} new jobs saved.\n")
    return total_new
