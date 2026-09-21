"""
analysis/job_analyzer.py — Groq-powered job analysis agent
=============================================================
Uses the Groq API (OpenAI-compatible) to analyze job descriptions against the
candidate profile. The agent has access to Python tools (functions)
and returns structured analysis.

HARD GUARDRAIL — The agent is instructed to NEVER invent:
  ✗ Skills the candidate doesn't have
  ✗ Employment history
  ✗ Projects or certifications
  ✗ Years of experience
  ✗ Technologies
  ✗ Metrics or achievements

This is enforced both in the system prompt AND via output validation.

If GROQ_API_KEY is not set, this module falls back gracefully
and the matcher's rule-based results are used instead.

Model probe strategy:
  Each model is tested ONCE at startup. Models that fail the probe are
  permanently skipped for the rest of the run — we never retry a dead model.
"""

import json
from datetime import datetime
from typing import Optional

from app.config import GROQ_API_KEY, GROQ_MODELS, PROFILE_FILE, ENABLE_AI_ANALYSIS
from app.database.db import get_job, get_analysis, save_analysis


# ── Tool functions (called by the agent) ───────────────────────────────────────

def get_candidate_profile() -> str:
    """
    Tool: Return the candidate's full profile as a JSON string.
    The agent calls this to understand who the candidate is.
    """
    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        profile = json.load(f)
    # Remove internal instructions key before sending to LLM
    profile.pop("_instructions", None)
    return json.dumps(profile, indent=2)


def get_job_description(job_id: int) -> str:
    """
    Tool: Return the full job posting (title, company, description) for a job_id.
    """
    job = get_job(job_id)
    if not job:
        return f"No job found with id={job_id}"
    return json.dumps({
        "company":     job.get("company"),
        "title":       job.get("title"),
        "location":    job.get("location"),
        "description": job.get("description", "")[:4000],  # cap tokens
        "url":         job.get("url"),
    }, indent=2)


def get_existing_match_scores(job_id: int) -> str:
    """
    Tool: Return the rule-based and embedding scores already computed.
    The agent uses these as a starting point for its deeper analysis.
    """
    analysis = get_analysis(job_id)
    if not analysis:
        return "No preliminary analysis found."
    return json.dumps({
        "rule_based_score":  analysis.get("match_score"),
        "embedding_score":   analysis.get("embedding_score"),
        "matched_skills":    analysis.get("matched_skills"),
        "missing_skills":    analysis.get("missing_skills"),
        "experience_required": analysis.get("experience_required"),
    }, indent=2)


# ── Agent setup ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are an expert job-matching analyst. Your job is to evaluate a job description from the perspective of the candidate's profile. You must determine how well the job aligns with the candidate's core strengths, experience level, and career goals.

════ CRITICAL GUARDRAIL ════
NEVER INVENT OR EXAGGERATE:
  ✗ Skills the candidate has not listed
  ✗ Work experience or employment history
  ✗ Projects or certifications not in the profile
  ✗ Years of experience the candidate doesn't have
  ✗ Technologies the candidate hasn't used
  ✗ Metrics, achievements, or numbers

You may only:
  ✓ Identify which of the candidate's REAL skills match the JD
  ✓ Explicitly list the critical skills required by the JD that the candidate is missing
  ✓ Assess if the job's required experience level matches the candidate's actual experience
  ✓ Extract JD keywords relevant for resume tailoring
  ✓ Provide resume suggestions that SELECT and REPHRASE real evidence to fit the job
  ✓ Give a realistic recommendation (strong/stretch/low) based on how well the job fits the candidate
════════════════════════════

Always use the tools to get real data — do not rely on memory.

Return your analysis as valid JSON matching this exact schema:
{
  "match_score_adjusted": 0.0,           // your refined score 0.0-1.0 representing how well the job fits the candidate
  "recommendation": "strong|stretch|low",
  "role_type": "Data Analyst|Data Engineer|ML Engineer|AI Engineer|Software Engineer|Other",
  "experience_required": "0-2 years",    // extracted from JD, "" if not mentioned
  "matched_skills": ["Python", "SQL"],   // candidate's skills that match the JD
  "missing_skills": ["Spark", "dbt"],    // CRITICAL: skills required by JD that candidate lacks
  "jd_keywords": ["ETL", "pipeline"],    // important keywords for resume
  "summary": "...",                      // 3-4 sentence honest assessment of why this job is or isn't a good fit for the candidate
  "resume_suggestions": [                // ONLY using real candidate evidence
    "Emphasize your SQL projects in the opening bullet",
    "Lead with Power BI experience in the tools section"
  ],
  "red_flags": []                        // concerns: overqualified, missing critical skills, location mismatch, etc.
}
"""


# ── Model probe: check once, skip permanently if dead ─────────────────────────

# Cached at module level so the probe only runs once per process.
_WORKING_MODELS: Optional[list[str]] = None


def _probe_models() -> list[str]:
    """
    Send a minimal chat test to each configured model.
    Returns only models that can genuinely respond to a text generation request.

    Explicitly rejects:
      - Models that return empty content (whisper, some audio models)
      - Safety classifiers like llama-prompt-guard that return only SAFE/UNSAFE
        and have a hard 512-token limit incompatible with job analysis.

    Called once at the start of run_ai_analysis(). Result is cached.
    """
    global _WORKING_MODELS
    if _WORKING_MODELS is not None:
        return _WORKING_MODELS

    if not GROQ_API_KEY:
        _WORKING_MODELS = []
        return _WORKING_MODELS

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        print("[AI Agent] groq package not installed. Run: pip install groq")
        _WORKING_MODELS = []
        return _WORKING_MODELS

    working = []
    print(f"[AI Agent] Probing {len(GROQ_MODELS)} model(s) for chat capability...")

    # Safety-classifier responses that indicate the model is NOT a chat model
    CLASSIFIER_RESPONSES = {"safe", "unsafe", "jailbreak", "benign", "injection"}

    for model in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say the word hello."}],
                max_tokens=200,   # reasoning models need budget beyond their think tokens
                timeout=15,
            )
            content = (resp.choices[0].message.content or "").strip().lower()
            finish = resp.choices[0].finish_reason

            if not content:
                # Reasoning model used all tokens thinking but produced no output
                print(f"  [SKIP] {model} — no visible output (finish={finish}); may need higher token budget")
                continue

            # Reject prompt-guard / safety classifiers
            if content in CLASSIFIER_RESPONSES or content.startswith("safe") or content.startswith("unsafe"):
                print(f"  [SKIP] {model} — safety classifier, not a chat model (returned: {content!r})")
                continue

            working.append(model)
            print(f"  [OK]   {model} — responded: {content[:40]!r}")

        except Exception as e:
            err = str(e)
            if "512" in err or "max_tokens" in err.lower():
                print(f"  [SKIP] {model} — token limit error (likely a safety classifier, not chat model)")
            else:
                print(f"  [SKIP] {model} — {type(e).__name__}: {err[:100]}")

    if not working:
        print("[AI Agent] WARNING: No working chat models found. AI analysis will be skipped.")
    else:
        print(f"[AI Agent] {len(working)}/{len(GROQ_MODELS)} model(s) ready: {', '.join(working)}")

    _WORKING_MODELS = working
    return _WORKING_MODELS


# ── Single-job Groq call ───────────────────────────────────────────────────────

def _call_groq_agent(job_id: int, working_models: list[str]) -> Optional[dict]:
    """
    Call the Groq API using only pre-validated working models.
    Returns parsed JSON dict, or None if all fail.
    """
    if not working_models:
        return None

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        return None

    profile_data = get_candidate_profile()
    job_data     = get_job_description(job_id)
    scores_data  = get_existing_match_scores(job_id)

    user_message = f"""
Please analyze this job posting against the candidate profile.

=== CANDIDATE PROFILE ===
{profile_data}

=== JOB POSTING ===
{job_data}

=== PRELIMINARY SCORES (rule-based + embedding) ===
{scores_data}

Return your analysis as valid JSON matching the schema in your instructions.
IMPORTANT: Return ONLY the JSON object, no markdown fences or extra text.
"""

    for model in working_models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
                temperature=0.2,
                max_tokens=1500,
                timeout=30,
            )

            content = response.choices[0].message.content or ""
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            return json.loads(content)

        except json.JSONDecodeError as e:
            print(f"  [AI Agent] Model {model} returned invalid JSON: {e}")
            continue
        except Exception as e:
            err_str = str(e).lower()
            # Rate limit / overload → try next model
            if any(x in err_str for x in ("rate limit", "429", "overloaded", "capacity")):
                print(f"  [AI Agent] Model {model} rate-limited. Trying next...")
                continue
            # Any other error → log and stop trying this job
            print(f"  [AI Agent] Model {model} error: {type(e).__name__}: {str(e)[:120]}")
            return None

    print(f"  [AI Agent] All working models failed for job_id={job_id}.")
    return None


def _validate_analysis(analysis: dict, profile_skills: list[str]) -> dict:
    """
    Guardrail validation: ensure the AI didn't hallucinate skills.
    Remove any 'matched_skills' that aren't in the candidate's real profile.
    """
    profile_skills_lower = {s.lower() for s in profile_skills}
    validated_matched = [
        s for s in analysis.get("matched_skills", [])
        if s.lower() in profile_skills_lower
    ]
    analysis["matched_skills"] = validated_matched

    # Clamp score to [0, 1]
    score = analysis.get("match_score_adjusted", 0.5)
    analysis["match_score_adjusted"] = max(0.0, min(1.0, float(score)))

    return analysis


# ── Main analysis function ─────────────────────────────────────────────────────

def analyze_job(job_id: int, working_models: Optional[list[str]] = None) -> Optional[dict]:
    """
    Run AI analysis on a single job.
    Updates the DB analysis record with AI-enriched data.
    Returns the analysis dict.
    """
    if not ENABLE_AI_ANALYSIS:
        return None
    if not GROQ_API_KEY:
        return None

    # Use pre-probed models if provided, otherwise probe now
    if working_models is None:
        working_models = _probe_models()
    if not working_models:
        return None

    print(f"  [AI Agent] Analyzing job_id={job_id}...", end=" ", flush=True)
    result = _call_groq_agent(job_id, working_models)
    if not result:
        print("FAILED")
        return None

    print(f"OK  ({result.get('recommendation','?').upper()} {result.get('match_score_adjusted', 0):.0%})")

    # Validate — enforce the guardrail
    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        profile = json.load(f)
    skills = []
    raw_skills = profile.get("skills", [])
    if isinstance(raw_skills, list):
        skills = raw_skills
    elif isinstance(raw_skills, dict):
        for v in raw_skills.values():
            skills.extend(v)

    result = _validate_analysis(result, skills)

    # Update DB with AI-enriched analysis (merge with existing)
    existing = get_analysis(job_id)
    if existing:
        save_analysis(
            job_id=job_id,
            match_score=existing.get("match_score", 0),
            embedding_score=existing.get("embedding_score", 0),
            final_score=result.get("match_score_adjusted", existing.get("final_score", 0)),
            required_skills=result.get("matched_skills", existing.get("matched_skills", [])),
            matched_skills=result.get("matched_skills", []),
            missing_skills=result.get("missing_skills", []),
            experience_required=result.get("experience_required", ""),
            role_type=result.get("role_type", ""),
            recommendation=result.get("recommendation", "low"),
            ai_summary=result.get("summary", ""),
            keywords=result.get("jd_keywords", []),
        )

    return result


def run_ai_analysis(job_ids: Optional[list[int]] = None) -> int:
    """
    Run AI analysis on a list of job IDs (or all strong/stretch matches).
    Probes models ONCE at the start — dead models are never retried.
    Returns count of jobs successfully analyzed.
    """
    if not ENABLE_AI_ANALYSIS or not GROQ_API_KEY:
        print("[AI Agent] Skipping — API key not configured or feature disabled.")
        return 0

    # ── Probe models once ──────────────────────────────────────────────────────
    working_models = _probe_models()
    if not working_models:
        print("[AI Agent] No usable models. Skipping AI analysis.")
        return 0

    # ── Determine which jobs to analyze ───────────────────────────────────────
    if job_ids is not None:
        jobs = [{"id": jid} for jid in job_ids]
    else:
        # Only analyze jobs that passed rule-based matching (strong or stretch).
        # Do NOT run AI on every unanalyzed job — that would be thousands of rows.
        from app.database.db import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT j.id FROM jobs j
                JOIN analysis a ON j.id = a.job_id
                WHERE a.recommendation IN ('strong', 'stretch')
                  AND (a.ai_summary IS NULL OR a.ai_summary = '')
                ORDER BY a.final_score DESC
                """
            ).fetchall()
        jobs = [{"id": row["id"]} for row in rows]

    if not jobs:
        print("[AI Agent] No jobs to analyze (no strong/stretch matches without AI summary).")
        return 0

    print(f"\n[AI Agent] Deep-analyzing {len(jobs)} strong/stretch job(s) with {len(working_models)} model(s)...")

    count = 0
    for job in jobs:
        result = analyze_job(job["id"], working_models=working_models)
        if result:
            count += 1

    print(f"[AI Agent] Done. {count}/{len(jobs)} jobs analyzed.\n")
    return count
