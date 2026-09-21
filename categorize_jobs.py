"""
categorize_jobs.py
==================

Reads ALL jobs from the database and splits them into:

  1. India jobs      — location clearly points to India or India-remote
  2. Remote jobs     — location says "Remote" or "WFH" with no country, or
                       explicitly remote with no India or foreign country lock
  3. International   — everything else (US, EU, Singapore, etc.)

Prints a summary and saves three CSV files in the project root:
  jobs_india.csv
  jobs_remote.csv
  jobs_international.csv

Usage:
    python categorize_jobs.py
"""

import sqlite3
import csv
import re
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "jobs.db"
OUT_DIR  = Path(__file__).parent

# ── India signals ────────────────────────────────────────────────────────────
INDIA_CITIES = {
    "india", "pune", "mumbai", "bengaluru", "bangalore",
    "hyderabad", "chennai", "delhi", "new delhi", "gurugram",
    "gurgaon", "noida", "kolkata", "ahmedabad", "jaipur",
    "surat", "lucknow", "bhopal", "indore", "kochi",
    "thiruvananthapuram", "coimbatore", "nagpur", "vadodara",
    "visakhapatnam", "chandigarh", "patna", "bhubaneswar",
    "mysuru", "mysore", "mangaluru", "mangalore", "nashik",
    "aurangabad", "rajasthan", "maharashtra", "karnataka",
    "andhra", "telangana", "tamilnadu", "tamil nadu",
    "kerala", "gujarat", "punjab", "haryana", "up",
    "uttar pradesh", "west bengal", "jharkhand", "odisha",
}

# Explicit India-remote strings
INDIA_REMOTE_PHRASES = [
    "remote - india",
    "remote, india",
    "india remote",
    "india - remote",
    "remote (india",
    "india (remote",
    "work from home india",
    "wfh india",
    "india wfh",
]

# ── "Generic remote" signals (no country lock) ───────────────────────────────
BARE_REMOTE_PHRASES = [
    "remote",
    "work from home",
    "wfh",
    "anywhere",
    "fully remote",
    "100% remote",
    "globally remote",
    "remote-first",
    "remote first",
]

# ── Strong international signals ─────────────────────────────────────────────
INTL_SIGNALS = [
    # United States — explicit
    "usa", "united states", ", us", " us-", "us remote",
    "remote from the us", "remote (us", "remote - us",
    "remote, us", "remote, usa",
    # US state abbreviations (", CA", ", TX", etc.) — space+comma avoids "Sca"
    ", al", ", ak", ", az", ", ar", ", ca", ", co", ", ct",
    ", de", ", fl", ", ga", ", hi", ", id", ", il", ", in",
    ", ia", ", ks", ", ky", ", la", ", me", ", md", ", ma",
    ", mi", ", mn", ", ms", ", mo", ", mt", ", ne", ", nv",
    ", nh", ", nj", ", nm", ", ny", ", nc", ", nd", ", oh",
    ", ok", ", or", ", pa", ", ri", ", sc", ", sd", ", tn",
    ", tx", ", ut", ", vt", ", va", ", wa", ", wv", ", wi",
    ", wy", ", dc",
    # Common US cities that appear without state
    "new york", "los angeles", "san francisco", "seattle",
    "chicago", "boston", "austin", "denver", "atlanta",
    "dallas", "houston", "miami", "phoenix", "portland",
    "minneapolis", "nashville", "philadelphia", "pittsburgh",
    "washington dc", "washington, dc", "silicon valley",
    "palo alto", "menlo park", "mountain view", "santa clara",
    # Canada
    "canada", "ontario", "british columbia", "alberta", "toronto",
    "vancouver", "montreal", "quebec", "calgary", "ottawa",
    # UK / Ireland / Europe
    "uk", "united kingdom", "london", "england", "scotland",
    "ireland", "dublin",
    "germany", "berlin", "munich", "frankfurt", "hamburg",
    "france", "paris", "lyon",
    "netherlands", "amsterdam", "rotterdam",
    "spain", "madrid", "barcelona",
    "italy", "rome", "milan",
    "portugal", "lisbon",
    "belgium", "brussels",
    "sweden", "stockholm",
    "norway", "oslo",
    "denmark", "copenhagen",
    "finland", "helsinki",
    "switzerland", "zurich", "geneva",
    "austria", "vienna",
    "poland", "warsaw",
    "romania", "bucharest",
    "europe", "emea",
    # APAC
    "singapore",
    "australia", "sydney", "melbourne", "brisbane", "perth",
    "new zealand", "auckland",
    "japan", "tokyo", "osaka",
    "china", "beijing", "shanghai",
    "hong kong",
    "south korea", "seoul",
    "taiwan", "taipei",
    "apac",
    # Other regions
    "israel", "tel aviv",
    "argentina", "brazil", "mexico", "latam",
    "amer",
]


def classify_location(location: str) -> str:
    """
    Returns one of: 'india' | 'remote' | 'international'

    Order of precedence:
      1. India city / India-remote phrase  → 'india'
      2. Any international signal present  → 'international'
         (catches "Atlanta, GA (Remote)", "US-Remote", etc.)
      3. Bare remote / WFH, no country     → 'remote'
      4. Blank or unrecognised             → 'international' (safe default)
    """
    if not location:
        return "international"

    loc = location.lower().strip()

    # ── 1. India check (highest priority) ────────────────────────────────────
    for phrase in INDIA_REMOTE_PHRASES:
        if phrase in loc:
            return "india"

    for city in INDIA_CITIES:
        if re.search(r"\b" + re.escape(city) + r"\b", loc):
            return "india"

    # ── 2. International check (BEFORE bare-remote) ───────────────────────────
    for signal in INTL_SIGNALS:
        if signal in loc:
            return "international"

    # ── 3. Bare remote / WFH (no country lock found above) ───────────────────
    for phrase in BARE_REMOTE_PHRASES:
        if phrase in loc:
            return "remote"

    # ── 4. Fallback ───────────────────────────────────────────────────────────
    return "international"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            j.id,
            j.company,
            j.title,
            j.location,
            j.url,
            j.source,
            j.posted_date,
            j.first_seen
        FROM jobs j
        ORDER BY j.first_seen DESC
    """)

    rows = cur.fetchall()
    conn.close()

    india_jobs, remote_jobs, intl_jobs = [], [], []

    for row in rows:
        cat = classify_location(row["location"] or "")
        data = dict(row)
        data["category"] = cat

        if cat == "india":
            india_jobs.append(data)
        elif cat == "remote":
            remote_jobs.append(data)
        else:
            intl_jobs.append(data)

    # ── Print summary ─────────────────────────────────────────────────────────
    total = len(rows)
    print("=" * 60)
    print("JOB CATEGORIZATION SUMMARY")
    print("=" * 60)
    print(f"  Total jobs in DB   : {total:,}")
    print(f"  India              : {len(india_jobs):,}  ({len(india_jobs)/total*100:.1f}%)")
    print(f"  Remote (no country): {len(remote_jobs):,}  ({len(remote_jobs)/total*100:.1f}%)")
    print(f"  International      : {len(intl_jobs):,}  ({len(intl_jobs)/total*100:.1f}%)")
    print("=" * 60)

    FIELDS = ["id", "company", "title", "location", "url",
              "source", "posted_date", "first_seen", "category"]

    # ── Save CSVs ─────────────────────────────────────────────────────────────
    def save_csv(jobs: list, filename: str):
        path = OUT_DIR / filename
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(jobs)
        print(f"  Saved {len(jobs):>5} rows -> {filename}")

    print()
    save_csv(india_jobs,  "jobs_india.csv")
    save_csv(remote_jobs, "jobs_remote.csv")
    save_csv(intl_jobs,   "jobs_international.csv")
    print()

    # ── Preview top 15 India jobs ─────────────────────────────────────────────
    print("-" * 60)
    print(f"TOP {min(15, len(india_jobs))} INDIA JOBS")
    print("-" * 60)
    for j in india_jobs[:15]:
        print(f"  {j['company']:<30} | {j['title'][:45]:<45} | {j['location'][:35]}")

    # ── Preview top 15 Remote jobs ────────────────────────────────────────────
    print()
    print("-" * 60)
    print(f"TOP {min(15, len(remote_jobs))} REMOTE JOBS (country unknown)")
    print("-" * 60)
    for j in remote_jobs[:15]:
        print(f"  {j['company']:<30} | {j['title'][:45]:<45} | {j['location'][:35]}")

    print()
    print("Done. Open the CSV files to browse all results.")


if __name__ == "__main__":
    main()
