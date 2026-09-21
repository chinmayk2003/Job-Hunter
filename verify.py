import sys, json
sys.path.insert(0, '.')

print("--- Import check ---")
from app.config import PROFILE_FILE, COMPANIES_FILE, DB_PATH
print(f"[OK] config loaded")
print(f"     Profile:   {PROFILE_FILE}")
print(f"     Companies: {COMPANIES_FILE}")
print(f"     DB:        {DB_PATH}")

from app.database.db import init_db, get_stats
init_db()
print(f"[OK] DB initialized")

with open(COMPANIES_FILE) as f:
    companies = json.load(f)
gh = [c for c in companies if c.get("greenhouse_slug")]
lv = [c for c in companies if c.get("lever_slug")]
cp = [c for c in companies if c.get("career_page_url") and not c.get("greenhouse_slug") and not c.get("lever_slug")]
print(f"[OK] Companies: {len(companies)} total | GH:{len(gh)} | Lever:{len(lv)} | Pages:{len(cp)}")

from app.matching.scoring import rule_based_score, get_recommendation
skills = ["Python", "SQL", "Power BI", "Pandas"]
fake_jd = "Looking for Data Analyst with Python, SQL, Power BI, Tableau. 2+ years experience."
score, req, matched, missing = rule_based_score(fake_jd, skills)
rec = get_recommendation(score)
print("")
print("--- Matcher self-test ---")
print(f"Matched:  {matched}")
print(f"Missing:  {missing}")
print(f"Score:    {score:.0%}  ({rec})")

stats = get_stats()
print("")
print(f"--- DB Stats: {stats}")
print("")
print("[ALL CHECKS PASSED]")
