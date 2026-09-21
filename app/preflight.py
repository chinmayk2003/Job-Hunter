"""
preflight.py — System readiness checks
=======================================

Runs before the main pipeline to validate that all required systems
are operational. If a critical system fails, the pipeline aborts early
rather than wasting time collecting/matching thousands of jobs only to
fail at the very end.

Checks:
  1. DB — can we connect and read/write?
  2. Profile — does profile.json exist and parse correctly?
  3. Companies — does companies.json exist and have entries?
  4. Groq API — is the key set and at least one model usable?
  5. Email (SMTP) — can we authenticate to Gmail?

Each check returns a (ok: bool, message: str) tuple.
A WARNING does not block the pipeline. A CRITICAL failure does.
"""

import smtplib
import socket
import json
from pathlib import Path
from typing import NamedTuple


class CheckResult(NamedTuple):
    ok: bool
    level: str          # "OK" | "WARN" | "FAIL"
    system: str
    message: str


# ── Individual checks ─────────────────────────────────────────────────────────

def check_database() -> CheckResult:
    try:
        from app.database.db import get_connection
        with get_connection() as conn:
            conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
        return CheckResult(True, "OK", "Database", "Connected and readable")
    except Exception as e:
        return CheckResult(False, "FAIL", "Database", f"{type(e).__name__}: {e}")


def check_profile() -> CheckResult:
    try:
        from app.config import PROFILE_FILE
        if not Path(PROFILE_FILE).exists():
            return CheckResult(False, "FAIL", "Profile", f"profile.json not found at {PROFILE_FILE}")
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            profile = json.load(f)
        skills = profile.get("skills", {})
        skill_count = (
            sum(len(v) for v in skills.values() if isinstance(v, list))
            if isinstance(skills, dict)
            else len(skills)
        )
        return CheckResult(True, "OK", "Profile", f"Loaded — {skill_count} skills, {len(profile.get('target_roles', []))} target roles")
    except Exception as e:
        return CheckResult(False, "FAIL", "Profile", f"{type(e).__name__}: {e}")


def check_companies() -> CheckResult:
    try:
        from app.config import COMPANIES_FILE
        if not Path(COMPANIES_FILE).exists():
            return CheckResult(False, "FAIL", "Companies", f"companies.json not found")
        with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
            companies = json.load(f)
        return CheckResult(True, "OK", "Companies", f"{len(companies)} companies loaded")
    except Exception as e:
        return CheckResult(False, "FAIL", "Companies", f"{type(e).__name__}: {e}")


def check_groq() -> CheckResult:
    """
    Tests Groq API connectivity.
    Reuses the module-level probe so models are only checked once.
    """
    from app.config import GROQ_API_KEY, ENABLE_AI_ANALYSIS

    if not ENABLE_AI_ANALYSIS:
        return CheckResult(True, "WARN", "Groq API", "AI analysis disabled (ENABLE_AI_ANALYSIS=false)")

    if not GROQ_API_KEY:
        return CheckResult(True, "WARN", "Groq API", "No API key set — AI analysis will be skipped")

    try:
        from app.analysis.job_analyzer import _probe_models
        working = _probe_models()
        if working:
            return CheckResult(True, "OK", "Groq API", f"{len(working)} working model(s): {', '.join(working)}")
        else:
            return CheckResult(False, "FAIL", "Groq API", "API key set but no model responded. Check GROQ_MODELS in .env")
    except Exception as e:
        return CheckResult(False, "FAIL", "Groq API", f"{type(e).__name__}: {e}")


def check_email() -> CheckResult:
    """
    Verifies Gmail SMTP credentials with a login-only test (no email sent).
    """
    from app.config import GMAIL_ADDRESS, GMAIL_APP_PASS, ENABLE_EMAIL

    if not ENABLE_EMAIL:
        return CheckResult(True, "WARN", "Email", "Email disabled (ENABLE_EMAIL=false)")

    if not GMAIL_ADDRESS or not GMAIL_APP_PASS:
        return CheckResult(False, "FAIL", "Email",
                           "GMAIL_ADDRESS or GMAIL_APP_PASS not set in .env")

    try:
        # Quick network reachability check first
        socket.setdefaulttimeout(8)
        socket.create_connection(("smtp.gmail.com", 465))
    except OSError:
        return CheckResult(False, "FAIL", "Email", "Cannot reach smtp.gmail.com:465 — check network/firewall")

    try:
        app_pass = GMAIL_APP_PASS.replace(" ", "")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(GMAIL_ADDRESS, app_pass)
        return CheckResult(True, "OK", "Email", f"SMTP authenticated as {GMAIL_ADDRESS}")
    except smtplib.SMTPAuthenticationError:
        return CheckResult(False, "FAIL", "Email",
                           "Authentication failed — check App Password in .env (must be 16 chars, no spaces)")
    except Exception as e:
        return CheckResult(False, "FAIL", "Email", f"{type(e).__name__}: {e}")


# ── Runner ────────────────────────────────────────────────────────────────────

ICONS = {"OK": "[OK]  ", "WARN": "[WARN]", "FAIL": "[FAIL]"}


def run_preflight(
    skip_groq: bool = False,
    skip_email: bool = False,
    abort_on_fail: bool = True,
) -> bool:
    """
    Run all preflight checks and print a status table.

    Args:
        skip_groq:     Skip Groq check (e.g. --no-ai mode).
        skip_email:    Skip email check (e.g. --no-email mode).
        abort_on_fail: If True (default), return False on any FAIL so
                       the caller can abort the pipeline.

    Returns:
        True  — all critical checks passed, safe to proceed.
        False — at least one FAIL found, pipeline should abort.
    """
    print("\n[Preflight] Checking all systems...")
    print("-" * 54)

    checks = [
        check_database,
        check_profile,
        check_companies,
    ]
    if not skip_groq:
        checks.append(check_groq)
    if not skip_email:
        checks.append(check_email)

    results = [fn() for fn in checks]

    any_fail = False
    for r in results:
        icon = ICONS[r.level]
        print(f"  {icon}  {r.system:<14} {r.message}")
        if r.level == "FAIL":
            any_fail = True

    print("-" * 54)

    if any_fail:
        print("[Preflight] One or more systems FAILED. Fix issues above before running the pipeline.")
        return not abort_on_fail   # honour abort_on_fail flag

    print("[Preflight] All systems ready.\n")
    return True
