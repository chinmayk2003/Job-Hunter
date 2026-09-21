# AI Job Agent

An automated job-hunting system that **collects**, **matches**, **analyzes**, and **emails** you relevant job postings every day — built in pure Python, runs free on GitHub Actions.

---

## What it does

```
Every morning at 9:00 AM IST
         ↓
GitHub Actions wakes up
         ↓
Collects jobs from Greenhouse + Lever APIs + career pages
         ↓
Matches them against your profile (rule-based + embeddings)
         ↓
AI agent does deep analysis (skills, gaps, keywords)
         ↓
Generates tailored resumes for strong matches
         ↓
Emails you a digest with scores, skill gaps, and apply links
```

---

## Project structure

```
AI-Job-Agent/
├── app/
│   ├── main.py                  ← Entry point (run this)
│   ├── config.py                ← All settings and paths
│   ├── collectors/
│   │   ├── greenhouse.py        ← Greenhouse public API
│   │   ├── lever.py             ← Lever public API
│   │   └── career_pages.py      ← Generic web scraper
│   ├── matching/
│   │   ├── matcher.py           ← Orchestrates matching
│   │   └── scoring.py           ← Rule-based + embedding scores
│   ├── analysis/
│   │   └── job_analyzer.py      ← OpenAI agent analysis
│   ├── resume/
│   │   ├── resume_data.py       ← Profile → resume content selector
│   │   └── resume_generator.py  ← Builds .docx files
│   ├── notifications/
│   │   └── email.py             ← Gmail digest sender
│   └── database/
│       └── db.py                ← All SQLite access
├── data/
│   ├── companies.json           ← Your 100 target companies
│   ├── profile.json             ← YOUR MASTER PROFILE (edit this!)
│   └── jobs.db                  ← SQLite database (auto-created)
├── resumes/
│   ├── master_resume.docx       ← Optional: style template
│   └── generated/               ← Auto-generated tailored resumes
├── .github/workflows/
│   └── job_agent.yml            ← GitHub Actions cron schedule
├── requirements.txt
├── .env                         ← Your secrets (never commit this)
└── .gitignore
```

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/AI-Job-Agent.git
cd AI-Job-Agent
pip install -r requirements.txt
```

### 2. Fill in your profile

Edit `data/profile.json` with your real information:
- Education details
- All your skills (be specific)
- Projects with descriptions and tech used
- Experience with bullet points
- Certifications

> ⚠️ **This is the single source of truth. The AI ONLY uses facts from this file when generating resumes. Never fabricate.**

### 3. Configure secrets

Edit `.env`:

```bash
OPENAI_API_KEY=sk-...          # Get from platform.openai.com
GMAIL_ADDRESS=you@gmail.com    # Your Gmail
GMAIL_APP_PASS=xxxx xxxx       # Gmail App Password (see below)
NOTIFY_EMAIL=you@gmail.com     # Where to send the digest
```

**Getting a Gmail App Password:**
1. Enable 2-Factor Authentication on your Google account
2. Go to: `myaccount.google.com` → Security → 2-Step Verification → App Passwords
3. Select app: "Mail" → Generate
4. Copy the 16-character code into `.env`

### 4. Run it

```bash
# Full run
python app/main.py

# Test without sending email
python app/main.py --dry-run

# Just collect jobs (no matching/email)
python app/main.py --collect-only

# Just match unanalyzed jobs
python app/main.py --match-only

# Skip AI analysis (faster, cheaper)
python app/main.py --no-ai

# Just send the digest from existing data
python app/main.py --email-only
```

---

## Customizing companies

Edit `data/companies.json`. For each company:

```json
{
  "name": "Company Name",
  "priority": "A",              // A = dream, B = strong, C = backup
  "greenhouse_slug": "slug",    // from greenhouse.io URL
  "lever_slug": "slug",         // from jobs.lever.co URL
  "career_page_url": "https://...",
  "notes": ""
}
```

**Finding slugs:**
- Greenhouse: if a company's jobs are at `company.greenhouse.io`, the slug is `company`
- Lever: if jobs are at `jobs.lever.co/company`, the slug is `company`

---

## Setting up GitHub Actions (automated daily runs)

### 1. Create a GitHub repository

```bash
git init
git remote add origin https://github.com/YOUR_USERNAME/AI-Job-Agent.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

> ⚠️ **Make sure `.gitignore` is committed first so `.env` and `jobs.db` are excluded.**

### 2. Add secrets to GitHub

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:
| Secret name | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `GMAIL_ADDRESS` | your@gmail.com |
| `GMAIL_APP_PASS` | Your 16-char App Password |
| `NOTIFY_EMAIL` | Where to receive the digest |

### 3. Enable Actions

Go to your repo → **Actions** tab → Enable workflows if prompted.

The workflow runs automatically at **9:00 AM IST every day**.

To trigger it manually: Actions → "AI Job Agent" → "Run workflow".

---

## How matching works

### Layer 1 — Rule-based (Phase 6)
Exact + synonym keyword matching between the job description and your skills.

```
Job says: Python, SQL, Power BI, 2 years experience
You have: Python, SQL, Power BI, 0 years

Python    ✓
SQL       ✓
Power BI  ✓
2 years   ⚠

Match = 75%
```

### Layer 2 — Embeddings (Phase 7)
`sentence-transformers` (all-MiniLM-L6-v2, runs locally, free) converts both the JD and your profile into vectors. Cosine similarity catches semantic matches:

```
"ETL developer" ≈ "data pipeline engineer"  →  recognized as related
```

**Final score = 60% rule-based + 40% embedding**

### Match tiers
| Score | Label | Emoji |
|---|---|---|
| ≥ 70% | Strong | 🔥 |
| 45–70% | Stretch | 🟡 |
| < 45% | Low | ⚪ |

---

## AI guardrails

The resume generation agent has a hard rule — it will **NEVER**:
- ❌ Add skills you don't have
- ❌ Invent work experience
- ❌ Fabricate projects or certifications
- ❌ Create fake metrics or achievements
- ❌ Claim years of experience you don't have

It **CAN**:
- ✓ Reorder your real bullet points for relevance
- ✓ Rephrase your real experience using JD keywords
- ✓ Select the most relevant subset of your real projects
- ✓ Write a tailored summary from your real facts
- ✓ Incorporate JD keywords where factually accurate

This is enforced in the system prompt **and** validated in code (any skills not in your profile are stripped from the AI's output).

---

## Database schema

```sql
-- All collected job postings
jobs (id, company, title, location, url, description,
      source, posted_date, first_seen, last_checked)

-- Match analysis results
analysis (job_id, match_score, embedding_score, final_score,
          required_skills, matched_skills, missing_skills,
          experience_required, role_type, recommendation,
          ai_summary, keywords, analyzed_at)

-- Application tracking (manual)
applications (job_id, resume_version, applied_date, status, notes)
```

---

## Costs

| Component | Cost |
|---|---|
| Job collection (Greenhouse + Lever APIs) | Free |
| Embedding model (sentence-transformers) | Free (local) |
| SQLite database | Free |
| GitHub Actions (2000 min/month free) | Free |
| OpenAI analysis (gpt-4o-mini) | ~$0.002 per job analyzed |
| Gmail SMTP | Free |

**Estimated monthly cost: < $1 for 500 jobs/month analyzed by AI**

---

## Troubleshooting

**`404` errors from Greenhouse/Lever:**
The company slug is wrong. Check `companies.json` and verify the slug against the actual job board URL.

**Email not sending:**
- Check `GMAIL_APP_PASS` is the App Password (not your main password)
- Make sure 2FA is enabled on your Google account
- Check your Gmail isn't blocking less secure apps

**`sentence-transformers` taking long to load:**
The model (`all-MiniLM-L6-v2`, ~80MB) downloads once and is cached. First run will be slow.

**`ModuleNotFoundError`:**
Run `pip install -r requirements.txt` again in your virtual environment.

---

## Next steps

After everything is working:
1. Fill in your real profile in `profile.json`
2. Add/remove companies in `companies.json`  
3. Push to GitHub and add secrets
4. Watch the daily digest land in your inbox
