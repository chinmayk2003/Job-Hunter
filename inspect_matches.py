import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "jobs.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

query = """
SELECT
    j.company,
    j.title,
    j.location,
    j.url,
    a.final_score,
    a.recommendation,
    a.role_type,
    a.matched_skills,
    a.missing_skills,
    a.experience_required
FROM jobs j
JOIN analysis a ON j.id = a.job_id
WHERE a.recommendation IN ('strong', 'stretch')
ORDER BY a.final_score DESC
"""

rows = cur.execute(query).fetchall()

print("=" * 100)
print(f"TOTAL MATCHES: {len(rows)}")
print("=" * 100)

for i, r in enumerate(rows, 1):
    print(f"\n[{i}] {r['final_score'] * 100:.1f}% | {r['recommendation'].upper()}")
    print(f"Company:     {r['company']}")
    print(f"Title:       {r['title']}")
    print(f"Role Type:   {r['role_type']}")
    print(f"Location:    {r['location']}")
    print(f"Experience:  {r['experience_required']}")
    print(f"Matched:     {r['matched_skills']}")
    print(f"Missing:     {r['missing_skills']}")
    print(f"URL:         {r['url']}")
    print("-" * 100)

conn.close()