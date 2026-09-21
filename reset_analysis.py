import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "jobs.db"

print("=" * 50)
print("RESETTING OLD JOB ANALYSIS")
print("=" * 50)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Count before
cur.execute("SELECT COUNT(*) FROM jobs")
job_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM analysis")
analysis_count = cur.fetchone()[0]

print(f"Jobs in DB:       {job_count}")
print(f"Analysis records: {analysis_count}")

confirm = input(
    "\nDelete ALL analysis records while keeping jobs? (yes/no): "
).strip().lower()

if confirm != "yes":
    print("Cancelled.")
    conn.close()
    raise SystemExit

cur.execute("DELETE FROM analysis")
deleted = cur.rowcount

conn.commit()

# Verify
cur.execute("SELECT COUNT(*) FROM analysis")
remaining = cur.fetchone()[0]

print("\nReset complete.")
print(f"Analysis records deleted: {deleted}")
print(f"Analysis records remaining: {remaining}")
print(f"Jobs preserved: {job_count}")

conn.close()