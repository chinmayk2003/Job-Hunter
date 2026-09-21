"""
matching/matcher.py
===================

Matches collected jobs against the candidate profile.

Pipeline:

    Raw jobs
        ↓
    Generic/garbage filter
        ↓
    Location filter
        ↓
    Target-role title gate
        ↓
    Seniority filter
        ↓
    Rule-based scoring
        ↓
    Recommendation
        ↓
    Save analysis

Important:
    A job must first be a plausible target role.
    Generic words such as "Python", "data", "SQL", etc. inside an
    unrelated JD must NOT make the job a strong match.
"""


import json

from app.config import PROFILE_FILE

from app.database.db import (
    get_unanalyzed_jobs,
    save_analysis,
)

from app.matching.scoring import (
    calculate_composite_score,
    combined_score,
    get_recommendation,
    extract_experience_required,
    is_senior_role,
    is_garbage_job,
    is_valid_location,
    is_relevant_role_title,
    detect_role_type,
)


# ============================================================
# PROFILE LOADING
# ============================================================

def load_candidate_skills() -> list[str]:
    """
    Load candidate skills from profile.json.

    Supports:
        "skills": ["Python", "SQL", ...]
    and:
        "skills": {
            "programming": [...],
            "ml": [...],
            ...
        }
    """

    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        profile = json.load(f)

    skills = profile.get("skills", [])

    # New/list format
    if isinstance(skills, list):
        return [
            str(skill).strip()
            for skill in skills
            if str(skill).strip()
        ]

    # Dict-of-lists format
    if isinstance(skills, dict):
        flattened = []

        for values in skills.values():
            if isinstance(values, list):
                flattened.extend(values)
            elif isinstance(values, str):
                flattened.append(values)

        return [
            str(skill).strip()
            for skill in flattened
            if str(skill).strip()
        ]

    return []



def get_profile_roles() -> list[str]:
    """
    Load target roles from profile.json.

    Supports:
        "target_roles": [...]
        "roles": [...]
    """

    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        profile = json.load(f)

    roles = profile.get(
        "target_roles",
        profile.get("roles", [])
    )

    if isinstance(roles, str):
        return [roles]

    if isinstance(roles, list):
        return [
            str(role).strip()
            for role in roles
            if str(role).strip()
        ]

    return []


# ============================================================
# MATCHING
# ============================================================

def run_matching() -> int:
    """
    Match all currently unanalyzed jobs.

    Returns:
        Number of jobs analyzed.
    """

    print("\n[Matcher] Starting job matching...")

    jobs = get_unanalyzed_jobs()

    if not jobs:
        print("[Matcher] No unanalyzed jobs found.")
        return 0

    print(
        f"[Matcher] Processing {len(jobs)} unanalyzed jobs..."
    )

    candidate_skills = load_candidate_skills()
    profile_roles = get_profile_roles()

    print(
        f"[Matcher] Candidate skills loaded: "
        f"{len(candidate_skills)}"
    )

    print(
        f"[Matcher] Target roles loaded: "
        f"{len(profile_roles)}"
    )

    analyzed_count = 0
    skipped_garbage = 0
    skipped_location = 0
    skipped_role = 0
    skipped_senior = 0

    # --------------------------------------------------------
    # Process jobs
    # --------------------------------------------------------

    for job in jobs:

        job_id = job["id"]

        title = (job["title"] or "").strip()
        description = (job["description"] or "").strip()
        location = (job["location"] or "").strip()

        company = (
            job["company"]
            if "company" in job.keys()
            else ""
        )

        # ----------------------------------------------------
        # HARD FILTER 1 — garbage / generic career pages
        # ----------------------------------------------------

        if is_garbage_job(title, description):

            skipped_garbage += 1

            print(
                f"  [Skip: Generic] "
                f"{company} | {title}"
            )

            continue

        # ----------------------------------------------------
        # HARD FILTER 2 — location
        # ----------------------------------------------------

        if not is_valid_location(location):

            skipped_location += 1

            print(
                f"  [Skip: Location] "
                f"{company} | {title} | {location}"
            )

            continue

        # ----------------------------------------------------
        # HARD FILTER 3 — TITLE MUST BE RELEVANT
        # ----------------------------------------------------

        if not is_relevant_role_title(title):

            skipped_role += 1

            print(
                f"  [Skip: Role] "
                f"{company} | {title}"
            )

            continue

        # ----------------------------------------------------
        # HARD FILTER 4 — SENIORITY
        # ----------------------------------------------------

        exp_required = extract_experience_required(
            description
        )

        if is_senior_role(
            title,
            description
        ):

            skipped_senior += 1

            print(
                f"  [Skip: Senior] "
                f"{company} | {title} | "
                f"{exp_required or 'unknown experience'}"
            )

            continue

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        (
            rule_score,
            required_found,
            matched_skills,
            missing_skills,
        ) = calculate_composite_score(
            title=title,
            description=description,
            location=location,
            candidate_skills=candidate_skills,
            profile_roles=profile_roles,
        )

        # Embeddings intentionally disabled in current design.
        embedding_score = 0.0

        final_score = combined_score(
            rule_score,
            embedding_score
        )

        recommendation = get_recommendation(
            final_score
        )

        role_type = detect_role_type(
            title,
            description
        )

        # ----------------------------------------------------
        # Additional safety gate
        # ----------------------------------------------------

        if final_score < 0.30:
            recommendation = "low"

        # ----------------------------------------------------
        # Save analysis
        # ----------------------------------------------------

        try:

            save_analysis(
                job_id=job_id,
                match_score=rule_score,
                embedding_score=embedding_score,
                final_score=final_score,
                required_skills=required_found,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                experience_required=exp_required,
                role_type=role_type,
                recommendation=recommendation,
            )

            analyzed_count += 1

            print(
                f"  [{recommendation.upper():7}] "
                f"{final_score:.1%} | "
                f"{role_type:22} | "
                f"{company} | "
                f"{title}"
            )

        except Exception as e:
            print(
                f"  [ERROR] Could not save analysis "
                f"for job {job_id}: {type(e).__name__}: {e}"
            )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n[Matcher] Matching complete.")

    print(
        f"  Analyzed:          {analyzed_count}"
    )

    print(
        f"  Generic skipped:   {skipped_garbage}"
    )

    print(
        f"  Location skipped:  {skipped_location}"
    )

    print(
        f"  Role skipped:      {skipped_role}"
    )

    print(
        f"  Senior skipped:    {skipped_senior}"
    )

    return analyzed_count