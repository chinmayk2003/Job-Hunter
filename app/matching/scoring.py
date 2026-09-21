"""
matching/scoring.py
===================

Deterministic job scoring.

Pipeline:
    1. Role relevance
    2. Seniority / experience compatibility
    3. Skill overlap
    4. Domain compatibility
    5. Location

Important:
    A job must first be a plausible target role.
    Generic technical keywords in a description must NOT turn an
    unrelated job into a high match.
"""

import re
from typing import Optional


# ============================================================
# Normalization
# ============================================================

def _normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[^\w\s+#.-]", " ", text.lower())


def _tokenize(text: str) -> set[str]:
    return set(_normalize(text).split())


# ============================================================
# Candidate skill synonyms
# ============================================================

# Keep these conservative.
# Do NOT map broad concepts to unrelated technologies.

SKILL_SYNONYMS = {
    "python": {"python3"},
    "sql": {"mysql", "postgresql", "postgres", "sqlite", "t-sql"},
    "pandas": set(),
    "numpy": set(),
    "scikit-learn": {"sklearn", "scikit learn"},
    "tensorflow": {"tensorflow 2"},
    "power bi": {"powerbi", "power-bi"},
    "mongodb": {"mongo", "mongo db"},
    "machine learning": {"ml"},
    "deep learning": {"dl"},
    "natural language processing": {"nlp"},
    "computer vision": {"cv"},
    "data analysis": {"data analytics"},
    "artificial intelligence": {"ai"},
}


def _expand_skill(skill: str) -> set[str]:
    """Return conservative normalized variants of one skill."""

    normalized = _normalize(skill)
    variants = {normalized}

    for canonical, synonyms in SKILL_SYNONYMS.items():
        canonical_norm = _normalize(canonical)

        if normalized == canonical_norm:
            variants.add(canonical_norm)
            variants.update(_normalize(s) for s in synonyms)

        elif normalized in {_normalize(s) for s in synonyms}:
            variants.add(canonical_norm)
            variants.update(_normalize(s) for s in synonyms)

    return variants


def _skill_present(skill: str, description: str) -> bool:
    """
    Check whether a candidate skill is genuinely mentioned.

    Uses word boundaries rather than naive substring matching.
    """

    desc = _normalize(description)

    for variant in _expand_skill(skill):
        if not variant:
            continue

        pattern = r"(?<!\w)" + re.escape(variant) + r"(?!\w)"

        if re.search(pattern, desc):
            return True

    return False


# ============================================================
# Role classification
# ============================================================

TARGET_ROLE_PATTERNS = {
    "Data Analyst": [
        r"\bdata analyst\b",
        r"\banalyst\b",
        r"\banalytics analyst\b",
        r"\bbusiness analyst\b",
        r"\breporting analyst\b",
        r"\bbi analyst\b",
    ],

    "Data Engineer": [
        r"\bdata engineer\b",
        r"\bdata engineering\b",
        r"\banalytics engineer\b",
    ],

    "Data Scientist": [
        r"\bdata scientist\b",
        r"\bdata science\b",
    ],

    "ML Engineer": [
        r"\bmachine learning engineer\b",
        r"\bml engineer\b",
        r"\bmachine learning developer\b",
    ],

    "AI Engineer": [
        r"\bai engineer\b",
        r"\bartificial intelligence engineer\b",
        r"\bai developer\b",
        r"\bgenai engineer\b",
        r"\bgenerative ai engineer\b",
    ],

    "Software Engineer": [
        r"\bsoftware engineer\b",
        r"\bsoftware developer\b",
        r"\bsoftware development engineer\b",
        r"\bsde\b",
    ],

    "Python Developer": [
        r"\bpython developer\b",
        r"\bpython engineer\b",
    ],

    "Backend Developer": [
        r"\bbackend developer\b",
        r"\bbackend engineer\b",
    ],

    "Cloud / AWS": [
        r"\bcloud engineer\b",
        r"\baws engineer\b",
        r"\bcloud developer\b",
        r"\bdevops engineer\b",
    ],

    "Technical Data Role": [
        r"\bdata operations\b",
        r"\bdata specialist\b",
        r"\bdata associate\b",
        r"\bdata trainee\b",
        r"\banalytics associate\b",
        r"\bdata intern\b",
        r"\banalytics intern\b",
        r"\bmachine learning intern\b",
        r"\bai intern\b",
        r"\bsoftware engineer intern\b",
        r"\bsoftware developer intern\b",
    ],
}


NON_TARGET_ROLE_PATTERNS = [
    r"\baccountant\b",
    r"\baccounting\b",
    r"\baudit\b",
    r"\bsales\b",
    r"\bsalesforce\b",
    r"\bmarketing\b",
    r"\brecruiter\b",
    r"\brecruitment\b",
    r"\bhuman resources\b",
    r"\bhr\b",
    r"\blegal\b",
    r"\bparalegal\b",
    r"\bcommunity\b",
    r"\bcustomer support\b",
    r"\bcustomer service\b",
    r"\btechnical support\b",
    r"\bit support\b",
    r"\bsupport administrator\b",
    r"\bsupport admin\b",
    r"\bfinance\b",
    r"\bfinancial analyst\b",
    r"\bprocurement\b",
    r"\boperations manager\b",
]


def detect_role_type(title: str, description: str = "") -> str:
    """
    Determine role primarily from the TITLE.

    Description is intentionally not used for primary classification.
    This prevents unrelated jobs mentioning Python/data/AI from becoming
    technical roles.
    """

    title_norm = _normalize(title)

    for role_type, patterns in TARGET_ROLE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, title_norm):
                return role_type

    return "Other"


def is_relevant_role_title(title: str) -> bool:
    """
    Hard gate.

    Returns True only if the title itself looks like a plausible
    target role.
    """

    title_norm = _normalize(title)

    # Explicitly reject obvious non-target roles.
    for pattern in NON_TARGET_ROLE_PATTERNS:
        if re.search(pattern, title_norm):
            return False

    for patterns in TARGET_ROLE_PATTERNS.values():
        for pattern in patterns:
            if re.search(pattern, title_norm):
                return True

    return False


# ============================================================
# Generic / garbage job detection
# ============================================================

def is_garbage_job(title: str, description: str = "") -> bool:
    text = f"{title} {description[:500]}".lower()

    garbage_patterns = [
        "life at ",
        "working at ",
        "career opportunities",
        "career opportunity",
        "job search",
        "search jobs",
        "jobs search",
        "expression of interest",
        "talent pool",
        "talent community",
        "future opportunities",
        "general application",
        "open application",
        "open positions",
        "internship programs",
        "working with us",
        "events:",
        "webinar",
    ]

    title_lower = title.lower().strip()

    if any(p in text for p in garbage_patterns):
        return True

    generic_titles = {
        "jobs",
        "careers",
        "career",
        "job search",
        "search",
        "opportunities",
        "open positions",
        "work with us",
    }

    if title_lower in generic_titles:
        return True

    return False


# ============================================================
# Location
# ============================================================

def is_valid_location(location: str) -> bool:
    """
    Location is NOT a strong scoring signal.

    Many company APIs omit location or say 'Remote'.
    Do not reject a job merely because location is blank.
    """

    if not location:
        return True

    loc = location.lower()

    valid_terms = [
        "india",
        "pune",
        "mumbai",
        "bangalore",
        "bengaluru",
        "hyderabad",
        "chennai",
        "delhi",
        "gurgaon",
        "gurugram",
        "noida",
        "kolkata",
        "ahmedabad",
        "remote",
        "work from home",
        "wfh",
        "anywhere",
    ]

    return any(term in loc for term in valid_terms)


# ============================================================
# Experience extraction
# ============================================================

def extract_experience_required(description: str) -> str:
    """
    Extract the first clear years-of-experience requirement.

    Examples:
        2+ years
        2-5 years
        1 year
    """

    if not description:
        return ""

    desc = description.lower()

    patterns = [
        r"(\d+)\s*(?:to|-)\s*(\d+)\s*years?",
        r"(\d+)\s*\+\s*years?",
        r"(\d+)\s*years?\s+of\s+experience",
        r"minimum\s+of\s+(\d+)\s*years?",
        r"at\s+least\s+(\d+)\s*years?",
    ]

    for pattern in patterns:
        match = re.search(pattern, desc)

        if not match:
            continue

        groups = match.groups()

        if len(groups) == 2:
            return f"{groups[0]}-{groups[1]} years"

        return f"{groups[0]}+ years"

    return ""


def is_entry_level_role(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()

    patterns = [
        "intern",
        "internship",
        "fresher",
        "entry level",
        "entry-level",
        "graduate",
        "new grad",
        "recent graduate",
        "trainee",
        "campus",
        "0-1 years",
        "0 - 1 years",
        "0-2 years",
        "0 - 2 years",
    ]

    return any(p in text for p in patterns)


def is_senior_role(title: str, description: str) -> bool:
    title_lower = title.lower()

    senior_title_patterns = [
        r"\bsenior\b",
        r"\bsr\.?\b",
        r"\blead\b",
        r"\bprincipal\b",
        r"\bstaff\b",
        r"\bmanager\b",
        r"\bdirector\b",
        r"\bhead\b",
        r"\bvp\b",
        r"\bvice president\b",
    ]

    if any(re.search(p, title_lower) for p in senior_title_patterns):
        return True

    # Entry-level language overrides ambiguous description requirements.
    if is_entry_level_role(title, description):
        return False

    exp = extract_experience_required(description)

    if not exp:
        return False

    numbers = [int(x) for x in re.findall(r"\d+", exp)]

    if numbers and max(numbers) >= 3:
        return True

    return False


# ============================================================
# Composite score
# ============================================================

def calculate_composite_score(
    title: str,
    description: str,
    location: str,
    candidate_skills: list[str],
    profile_roles: list[str],
) -> tuple[float, list[str], list[str], list[str]]:
    """
    Score a plausible job.

    Maximum:
        Role relevance       35%
        Skill compatibility  35%
        Experience           20%
        Location             10%

    IMPORTANT:
        This function assumes the caller has already passed the
        garbage-job and role-relevance gates.
    """

    title_norm = _normalize(title)
    description_norm = _normalize(description)

    # --------------------------------------------------------
    # 1. Role relevance — 35%
    # --------------------------------------------------------

    role_type = detect_role_type(title, description)

    role_score = 0.0

    if role_type != "Other":
        role_score = 0.35

    # Additional match against user's declared target roles.
    if profile_roles:
        for role in profile_roles:
            role_norm = _normalize(role)

            if role_norm and role_norm in title_norm:
                role_score = 0.35
                break

    # --------------------------------------------------------
    # 2. Skill compatibility — 35%
    # --------------------------------------------------------

    matched_skills = []
    missing_skills = []

    for skill in candidate_skills:
        if _skill_present(skill, description_norm):
            matched_skills.append(skill)

    # Skill coverage rather than arbitrary +5% per skill.
    #
    # 0 skills  -> 0
    # 25%       -> partial
    # 50%       -> decent
    # 75%       -> strong
    # 100%      -> full

    if candidate_skills:
        skill_coverage = len(matched_skills) / len(candidate_skills)
    else:
        skill_coverage = 0.0

    skill_score = 0.35 * skill_coverage

    # --------------------------------------------------------
    # 3. Detect important missing technical skills
    # --------------------------------------------------------

    known_technical_skills = [
        "python",
        "sql",
        "pandas",
        "numpy",
        "scikit-learn",
        "tensorflow",
        "pytorch",
        "spark",
        "airflow",
        "dbt",
        "aws",
        "azure",
        "gcp",
        "docker",
        "kubernetes",
        "java",
        "scala",
        "r",
        "tableau",
        "power bi",
        "snowflake",
        "databricks",
        "fastapi",
        "flask",
        "django",
        "react",
    ]

    candidate_normalized = {
        _normalize(skill)
        for skill in candidate_skills
    }

    for skill in known_technical_skills:
        if _skill_present(skill, description_norm):
            if _normalize(skill) not in candidate_normalized:
                missing_skills.append(skill)

    # --------------------------------------------------------
    # 4. Experience compatibility — 20%
    # --------------------------------------------------------

    exp_req = extract_experience_required(description)

    if is_entry_level_role(title, description):
        experience_score = 0.20

    elif not exp_req:
        # Unknown requirement = neutral, NOT full points.
        experience_score = 0.10

    else:
        numbers = [int(x) for x in re.findall(r"\d+", exp_req)]
        max_required = max(numbers) if numbers else 99

        if max_required <= 1:
            experience_score = 0.20
        elif max_required <= 2:
            experience_score = 0.15
        elif max_required <= 3:
            experience_score = 0.08
        else:
            experience_score = 0.0

    # --------------------------------------------------------
    # 5. Location — 10%
    # --------------------------------------------------------

    if not location:
        # Unknown location = neutral.
        location_score = 0.05

    elif is_valid_location(location):
        location_score = 0.10

    else:
        location_score = 0.0

    # --------------------------------------------------------
    # Final score
    # --------------------------------------------------------

    score = (
        role_score
        + skill_score
        + experience_score
        + location_score
    )

    score = max(0.0, min(1.0, score))

    return (
        round(score, 4),
        matched_skills,
        matched_skills,
        missing_skills,
    )


# ============================================================
# Final combined score
# ============================================================

def combined_score(rule_score: float, emb_score: float = 0.0) -> float:
    """
    Embeddings are currently disabled architecturally.

    Keep this function for API compatibility.
    """

    return round(rule_score, 4)


# ============================================================
# Recommendation
# ============================================================

def get_recommendation(score: float) -> str:
    from app.config import (
        STRONG_MATCH_THRESHOLD,
        STRETCH_MATCH_THRESHOLD,
    )

    if score >= STRONG_MATCH_THRESHOLD:
        return "strong"

    if score >= STRETCH_MATCH_THRESHOLD:
        return "stretch"

    return "low"