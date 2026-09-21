"""
config.py — Central configuration loader
=========================================

All secrets come from .env.

All project paths are defined here.

Environment variables are loaded once when this module is imported.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"

RESUMES_DIR = ROOT_DIR / "resumes"

GENERATED_DIR = RESUMES_DIR / "generated"

DB_PATH = DATA_DIR / "jobs.db"

COMPANIES_FILE = DATA_DIR / "companies.json"

PROFILE_FILE = DATA_DIR / "profile.json"

MASTER_RESUME = RESUMES_DIR / "master_resume.docx"


# Make sure generated resume directory exists.
GENERATED_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(ROOT_DIR / ".env")


# ============================================================
# GROQ
# ============================================================

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    ""
)

GROQ_MODELS = [
    model.strip()
    for model in os.getenv(
        "GROQ_MODELS",
        "openai/gpt-oss-20b"
    ).split(",")
    if model.strip()
]


# Backward compatibility.
#
# Some older modules may import GROQ_MODEL instead of
# GROQ_MODELS.
#
# This prevents:
#     cannot import name 'GROQ_MODEL'
#
GROQ_MODEL = (
    GROQ_MODELS[0]
    if GROQ_MODELS
    else "openai/gpt-oss-20b"
)


# ============================================================
# GMAIL
# ============================================================

GMAIL_ADDRESS = os.getenv(
    "GMAIL_ADDRESS",
    ""
)

GMAIL_APP_PASS = os.getenv(
    "GMAIL_APP_PASS",
    ""
)

NOTIFY_EMAIL = os.getenv(
    "NOTIFY_EMAIL",
    GMAIL_ADDRESS
)


# ============================================================
# SCRAPING
# ============================================================

REQUEST_TIMEOUT = int(
    os.getenv(
        "REQUEST_TIMEOUT",
        "15"
    )
)

REQUEST_DELAY = float(
    os.getenv(
        "REQUEST_DELAY",
        "1.5"
    )
)


# ============================================================
# MATCHING THRESHOLDS
# ============================================================

STRONG_MATCH_THRESHOLD = float(
    os.getenv(
        "STRONG_MATCH_THRESHOLD",
        "0.70"
    )
)

STRETCH_MATCH_THRESHOLD = float(
    os.getenv(
        "STRETCH_MATCH_THRESHOLD",
        "0.45"
    )
)


# ============================================================
# FEATURE FLAGS
# ============================================================

ENABLE_AI_ANALYSIS = (
    os.getenv(
        "ENABLE_AI_ANALYSIS",
        "true"
    ).lower()
    == "true"
)

ENABLE_RESUME_GEN = (
    os.getenv(
        "ENABLE_RESUME_GEN",
        "true"
    ).lower()
    == "true"
)

ENABLE_EMAIL = (
    os.getenv(
        "ENABLE_EMAIL",
        "true"
    ).lower()
    == "true"
)

ENABLE_EMBEDDINGS = (
    os.getenv(
        "ENABLE_EMBEDDINGS",
        "false"
    ).lower()
    == "true"
)


# ============================================================
# CONFIG VALIDATION
# ============================================================

def validate_config() -> list[str]:
    """
    Return configuration warnings.

    Empty list means no obvious configuration problems.
    """

    warnings = []

    if not GROQ_API_KEY and ENABLE_AI_ANALYSIS:
        warnings.append(
            "GROQ_API_KEY not set — AI analysis will be skipped"
        )

    if (
        not GMAIL_ADDRESS
        and ENABLE_EMAIL
    ):
        warnings.append(
            "GMAIL_ADDRESS not set — email digest disabled"
        )

    if (
        not GMAIL_APP_PASS
        and ENABLE_EMAIL
    ):
        warnings.append(
            "GMAIL_APP_PASS not set — email digest disabled"
        )

    if not PROFILE_FILE.exists():
        warnings.append(
            f"profile.json not found: {PROFILE_FILE}"
        )

    if not COMPANIES_FILE.exists():
        warnings.append(
            f"companies.json not found: {COMPANIES_FILE}"
        )

    return warnings