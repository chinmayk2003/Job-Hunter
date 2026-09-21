"""
main.py — AI Job Agent orchestrator
====================================

Single entry point.

Usage:

    python app/main.py

    python app/main.py --dry-run

    python app/main.py --email-only

    python app/main.py --collect-only

    python app/main.py --match-only

    python app/main.py --no-ai

    python app/main.py --no-resume

Pipeline:

    1. Initialize DB
    2. Collect jobs
    3. Match jobs
    4. AI analysis
    5. Resume generation
    6. Email digest
"""

import sys
import io
import json
import argparse
from datetime import datetime
from pathlib import Path


# ============================================================
# UTF-8 WINDOWS OUTPUT
# ============================================================

if (
    sys.stdout.encoding
    and sys.stdout.encoding.lower() != "utf-8"
):

    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding="utf-8",
        errors="replace",
    )


# ============================================================
# PROJECT PATH
# ============================================================

project_root = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

if str(project_root) not in sys.path:

    sys.path.insert(
        0,
        str(project_root)
    )


# ============================================================
# CONFIG
# ============================================================

from app.config import (
    COMPANIES_FILE,
    ENABLE_AI_ANALYSIS,
    ENABLE_RESUME_GEN,
    ENABLE_EMAIL,
)

from app.preflight import run_preflight


# ============================================================
# DATABASE
# ============================================================

from app.database.db import (
    init_db,
    get_stats,
)


# ============================================================
# COLLECTORS
# ============================================================

from app.collectors import (
    greenhouse,
    lever,
    career_pages,
)


# ============================================================
# MATCHER
# ============================================================

from app.matching.matcher import (
    run_matching,
)


# ============================================================
# EMAIL
# ============================================================

from app.notifications.email import (
    send_digest,
)


# ============================================================
# LOAD COMPANIES
# ============================================================

def load_companies() -> list[dict]:
    """
    Load companies.json.
    """

    with open(
        COMPANIES_FILE,
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(f)


# ============================================================
# BANNER
# ============================================================

def print_banner():

    print(
        """
╔══════════════════════════════════════════════╗
║             AI JOB AGENT v1.0                ║
║   Automated job collection + matching        ║
╚══════════════════════════════════════════════╝
"""
    )


# ============================================================
# COLLECTION
# ============================================================

def run_collection(
    companies: list[dict],
) -> int:

    """
    Run all collectors.
    """

    total = 0

    print(
        "\n[Main] Starting job collection..."
    )

    # --------------------------------------------------------
    # Greenhouse
    # --------------------------------------------------------

    try:

        count = greenhouse.collect_all(
            companies
        )

        total += count

    except Exception as e:

        print(
            f"[Greenhouse] Collector failed: "
            f"{type(e).__name__}: {e}"
        )

    # --------------------------------------------------------
    # Lever
    # --------------------------------------------------------

    try:

        count = lever.collect_all(
            companies
        )

        total += count

    except Exception as e:

        print(
            f"[Lever] Collector failed: "
            f"{type(e).__name__}: {e}"
        )

    # --------------------------------------------------------
    # Career pages
    # --------------------------------------------------------

    try:

        count = career_pages.collect_all(
            companies
        )

        total += count

    except Exception as e:

        print(
            f"[CareerPages] Collector failed: "
            f"{type(e).__name__}: {e}"
        )

    return total


# ============================================================
# AI PHASE
# ============================================================

def run_ai_phase():

    if not ENABLE_AI_ANALYSIS:

        print(
            "[Main] AI analysis disabled."
        )

        return

    try:

        from app.analysis.job_analyzer import (
            run_ai_analysis
        )

        run_ai_analysis()

    except Exception as e:

        print(
            f"[AI Agent] Analysis failed: "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# RESUME PHASE
# ============================================================

def run_resume_phase():

    if not ENABLE_RESUME_GEN:

        print(
            "[Main] Resume generation disabled."
        )

        return

    try:

        from app.resume.resume_generator import (
            generate_resumes_for_strong_matches
        )

        generate_resumes_for_strong_matches()

    except ImportError as e:

        print(
            f"[Resume] Import error: {e}"
        )

        print(
            "[Resume] This is a Python import/config "
            "problem, not necessarily a missing package."
        )

    except Exception as e:

        print(
            f"[Resume] Generation failed: "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# SUMMARY
# ============================================================

def print_summary(stats: dict):
    w = 36
    print("\n" + "-" * w)
    print(f"  Run Summary")
    print("-" * w)
    print(f"  Total jobs in DB : {stats.get('total_jobs', 0)}")
    print(f"  Analyzed         : {stats.get('analyzed', 0)}")
    print(f"  Strong matches   : {stats.get('strong_matches', 0)}")
    print(f"  Stretch matches  : {stats.get('stretch_matches', 0)}")
    print(f"  Applied          : {stats.get('applied', 0)}")
    print("-" * w)


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "AI Job Agent — automated job hunting system"
        ),
        formatter_class=(
            argparse.RawDescriptionHelpFormatter
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run everything but don't send email",
    )

    parser.add_argument(
        "--email-only",
        action="store_true",
        help="Only send email digest",
    )

    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Only collect jobs",
    )

    parser.add_argument(
        "--match-only",
        action="store_true",
        help="Only match unanalyzed jobs",
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip AI analysis",
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Skip resume generation",
    )

    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip email digest",
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():

    start_time = datetime.now()

    print_banner()

    args = parse_args()

    # --------------------------------------------------------
    # DB initialization (must come before preflight)
    # --------------------------------------------------------

    print("[Main] Initializing database...")
    init_db()

    # --------------------------------------------------------
    # Preflight — verify all systems before spending time on work
    # --------------------------------------------------------

    skip_groq  = args.no_ai  or not ENABLE_AI_ANALYSIS
    skip_email = getattr(args, 'no_email', False) or not ENABLE_EMAIL

    ok = run_preflight(
        skip_groq=skip_groq,
        skip_email=skip_email,
        abort_on_fail=True,
    )

    if not ok:
        print("[Main] Aborting — fix the issues above and re-run.")
        return

    # --------------------------------------------------------
    # Email-only
    # --------------------------------------------------------

    if args.email_only:

        print(
            "\n[Main] Email-only mode."
        )

        if ENABLE_EMAIL and not args.no_email:

            send_digest(
                dry_run=args.dry_run
            )

        else:

            print(
                "[Main] Email disabled."
            )

        return

    # --------------------------------------------------------
    # Load companies
    # --------------------------------------------------------

    try:

        companies = load_companies()

    except Exception as e:

        print(
            f"[Main] Failed to load companies.json: "
            f"{type(e).__name__}: {e}"
        )

        return

    print(
        f"[Main] Loaded "
        f"{len(companies)} companies."
    )

    # --------------------------------------------------------
    # Collection
    # --------------------------------------------------------

    if not args.match_only:

        new_jobs = run_collection(
            companies
        )

        print(
            f"\n[Main] Collection complete. "
            f"{new_jobs} new jobs found."
        )

    # --------------------------------------------------------
    # Collect-only
    # --------------------------------------------------------

    if args.collect_only:

        print(
            "\n[Main] Collect-only mode."
        )

        print_summary(
            get_stats()
        )

        return

    # --------------------------------------------------------
    # Matching
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        " PHASE 3 — JOB MATCHING"
    )

    print(
        "========================================"
    )

    analyzed = run_matching()

    print(
        f"\n[Main] Matcher analyzed "
        f"{analyzed} jobs."
    )

    # --------------------------------------------------------
    # Match-only
    # --------------------------------------------------------

    if args.match_only:

        print_summary(
            get_stats()
        )

        return

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    if not args.no_ai:

        print(
            "\n========================================"
        )

        print(
            " PHASE 4 — AI ANALYSIS"
        )

        print(
            "========================================"
        )

        run_ai_phase()

    else:

        print(
            "\n[Main] AI analysis skipped "
            "(--no-ai)."
        )

    # --------------------------------------------------------
    # Resume
    # --------------------------------------------------------

    if not args.no_resume:

        print(
            "\n========================================"
        )

        print(
            " PHASE 5 — RESUME GENERATION"
        )

        print(
            "========================================"
        )

        run_resume_phase()

    else:

        print(
            "\n[Main] Resume generation skipped."
        )

    # --------------------------------------------------------
    # Email
    # --------------------------------------------------------

    if (
        ENABLE_EMAIL
        and not args.no_email
    ):

        print(
            "\n========================================"
        )

        print(
            " PHASE 6 — EMAIL DIGEST"
        )

        print(
            "========================================"
        )

        try:

            send_digest(
                dry_run=args.dry_run
            )

        except Exception as e:

            print(
                f"[Email] Failed: "
                f"{type(e).__name__}: {e}"
            )

    else:

        print(
            "\n[Main] Email disabled/skipped."
        )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    elapsed = (
        datetime.now() - start_time
    ).total_seconds()

    stats = get_stats()

    print_summary(
        stats
    )

    print(
        f"\n[Main] Done in "
        f"{elapsed:.1f}s"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()