"""
database/db.py — SQLite schema + all CRUD operations
======================================================
Single file for all database access.  Nothing else in the project
imports sqlite3 directly — everything goes through this module.
"""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from app.config import DB_PATH


# ── Schema ─────────────────────────────────────────────────────────────────────

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company      TEXT    NOT NULL,
    title        TEXT    NOT NULL,
    location     TEXT,
    url          TEXT    UNIQUE NOT NULL,
    description  TEXT,
    source       TEXT,               -- 'greenhouse' | 'lever' | 'career_page'
    posted_date  TEXT,
    first_seen   TEXT    NOT NULL,
    last_checked TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id              INTEGER NOT NULL REFERENCES jobs(id),
    match_score         REAL,        -- 0.0 – 1.0 (rule-based)
    embedding_score     REAL,        -- 0.0 – 1.0 (cosine similarity)
    final_score         REAL,        -- weighted combo
    required_skills     TEXT,        -- JSON array
    matched_skills      TEXT,        -- JSON array
    missing_skills      TEXT,        -- JSON array
    experience_required TEXT,
    role_type           TEXT,
    recommendation      TEXT,        -- 'strong' | 'stretch' | 'low'
    ai_summary          TEXT,        -- full AI analysis text
    keywords            TEXT,        -- JSON array of JD keywords
    analyzed_at         TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id         INTEGER NOT NULL REFERENCES jobs(id),
    resume_version TEXT,             -- filename of generated resume
    applied_date   TEXT,
    status         TEXT DEFAULT 'interested',
    notes          TEXT,
    updated_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_company    ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
CREATE INDEX IF NOT EXISTS idx_analysis_score  ON analysis(final_score DESC);
"""


# ── Connection ─────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Return a configured sqlite3 connection (row_factory set to Row)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't exist yet. Safe to call on every run."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    print(f"[DB] Initialized: {DB_PATH}")


# ── Jobs ───────────────────────────────────────────────────────────────────────

def upsert_job(
    company: str,
    title: str,
    url: str,
    location: str = "",
    description: str = "",
    source: str = "",
    posted_date: str = "",
) -> Optional[int]:
    """
    Insert a new job or update last_checked if it already exists.
    Returns the job_id (int), or None on error.
    """
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        # Check if already seen
        existing = conn.execute(
            "SELECT id FROM jobs WHERE url = ?", (url,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE jobs SET last_checked = ? WHERE url = ?",
                (now, url),
            )
            return existing["id"]

        cursor = conn.execute(
            """
            INSERT INTO jobs (company, title, location, url, description,
                              source, posted_date, first_seen, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (company, title, location, url, description,
             source, posted_date, now, now),
        )
        return cursor.lastrowid


def get_job(job_id: int) -> Optional[dict]:
    """Fetch a single job by id. Returns dict or None."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_unanalyzed_jobs() -> list[dict]:
    """Return jobs that have no analysis entry yet."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT j.* FROM jobs j
            LEFT JOIN analysis a ON j.id = a.job_id
            WHERE a.job_id IS NULL
            ORDER BY j.first_seen DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_todays_jobs() -> list[dict]:
    """Return all jobs first seen today."""
    today = date.today().isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT j.*, a.final_score, a.recommendation, a.matched_skills,
                   a.missing_skills, a.ai_summary, a.role_type, a.experience_required
            FROM jobs j
            LEFT JOIN analysis a ON j.id = a.job_id
            WHERE j.first_seen >= ?
            ORDER BY a.final_score DESC
            """,
            (today,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_digest_jobs() -> list[dict]:
    """
    Return all strong and stretch matches for the email digest.

    Unlike get_todays_jobs(), this is NOT limited to today — it returns every
    job that passed rule-based matching regardless of when it was collected.
    This ensures the digest is never empty on re-runs.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT j.*, a.final_score, a.recommendation, a.matched_skills,
                   a.missing_skills, a.ai_summary, a.role_type, a.experience_required
            FROM jobs j
            JOIN analysis a ON j.id = a.job_id
            WHERE a.recommendation IN ('strong', 'stretch')
            ORDER BY
                CASE a.recommendation WHEN 'strong' THEN 0 ELSE 1 END,
                a.final_score DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


# ── Analysis ───────────────────────────────────────────────────────────────────

def save_analysis(
    job_id: int,
    match_score: float,
    embedding_score: float,
    final_score: float,
    required_skills: list,
    matched_skills: list,
    missing_skills: list,
    experience_required: str,
    role_type: str,
    recommendation: str,
    ai_summary: str = "",
    keywords: list = None,
) -> int:
    """Insert or replace an analysis row for a job."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        # Delete old analysis for this job if it exists (re-run scenario)
        conn.execute("DELETE FROM analysis WHERE job_id = ?", (job_id,))
        cursor = conn.execute(
            """
            INSERT INTO analysis
                (job_id, match_score, embedding_score, final_score,
                 required_skills, matched_skills, missing_skills,
                 experience_required, role_type, recommendation,
                 ai_summary, keywords, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, match_score, embedding_score, final_score,
                json.dumps(required_skills), json.dumps(matched_skills),
                json.dumps(missing_skills), experience_required, role_type,
                recommendation, ai_summary,
                json.dumps(keywords or []), now,
            ),
        )
        return cursor.lastrowid


def get_analysis(job_id: int) -> Optional[dict]:
    """Return the analysis dict for a given job_id, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM analysis WHERE job_id = ?", (job_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        # Deserialize JSON fields
        for field in ("required_skills", "matched_skills", "missing_skills", "keywords"):
            result[field] = json.loads(result.get(field) or "[]")
        return result


# ── Applications ───────────────────────────────────────────────────────────────

def log_application(
    job_id: int,
    resume_version: str,
    status: str = "interested",
    notes: str = "",
) -> int:
    """Record that we've applied (or flagged) a job."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO applications
                (job_id, resume_version, applied_date, status, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, resume_version, now, status, notes, now),
        )
        return cursor.lastrowid


def get_stats() -> dict:
    """Return a summary dict for logging/email."""
    with get_connection() as conn:
        total     = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        analyzed  = conn.execute("SELECT COUNT(*) FROM analysis").fetchone()[0]
        strong    = conn.execute(
            "SELECT COUNT(*) FROM analysis WHERE recommendation='strong'"
        ).fetchone()[0]
        stretch   = conn.execute(
            "SELECT COUNT(*) FROM analysis WHERE recommendation='stretch'"
        ).fetchone()[0]
        applied   = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    return {
        "total_jobs": total,
        "analyzed": analyzed,
        "strong_matches": strong,
        "stretch_matches": stretch,
        "applied": applied,
    }
