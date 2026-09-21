"""
resume/resume_data.py — Profile-to-resume data mapper
======================================================
Reads profile.json (the single source of truth) and returns
clean, structured data objects that the resume generator can use.

The AI agent calls select_relevant_content() to choose which parts
of the master profile are most relevant for a specific job.
Everything returned here MUST come from profile.json — no fabrication.
"""

import json
from typing import Optional

from app.config import PROFILE_FILE, GROQ_API_KEY, GROQ_MODEL, ENABLE_RESUME_GEN


def load_full_profile() -> dict:
    """Load and return the full profile.json as a dict."""
    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_all_skills_flat(profile: dict) -> list[str]:
    """Return all skills as a flat list regardless of category structure."""
    skills_data = profile.get("skills", [])
    if isinstance(skills_data, list):
        return [s for s in skills_data if s]
    if isinstance(skills_data, dict):
        flat = []
        for v in skills_data.values():
            if isinstance(v, list):
                flat.extend([s for s in v if s])
        return flat
    return []


def select_relevant_content(
    job_title: str,
    job_description: str,
    matched_skills: list[str],
    keywords: list[str],
    profile: Optional[dict] = None,
) -> dict:
    """
    Select the most relevant subset of the profile for a specific job.

    If OpenAI is available: uses LLM to intelligently select + rephrase bullets.
    Otherwise: uses simple keyword-based selection.

    Returns a dict with these keys:
      - summary (str): tailored 2-3 sentence summary
      - skills (list[str]): relevant skills to highlight
      - projects (list[dict]): selected projects with relevant bullets
      - experience (list[dict]): selected experience entries
      - certifications (list[dict]): relevant certifications
    """
    if profile is None:
        profile = load_full_profile()

    all_skills   = get_all_skills_flat(profile)
    projects     = profile.get("projects", [])
    experience   = profile.get("experience", [])
    certs        = profile.get("certifications", [])
    # Support summary as dict {"text": "..."} or plain string
    summary_raw  = profile.get("summary", "")
    base_summary = summary_raw.get("text", "") if isinstance(summary_raw, dict) else summary_raw

    # Always use REAL skills — prioritize matched ones, then all others
    matched_set = {s.lower() for s in matched_skills}
    priority_skills = [s for s in all_skills if s.lower() in matched_set]
    other_skills    = [s for s in all_skills if s.lower() not in matched_set]
    ordered_skills  = priority_skills + other_skills

    if GROQ_API_KEY and ENABLE_RESUME_GEN:
        return _ai_select_content(
            job_title=job_title,
            job_description=job_description,
            keywords=keywords,
            profile=profile,
            ordered_skills=ordered_skills,
            base_summary=base_summary,
        )

    # Fallback: keyword-based selection (no AI)
    return _keyword_select_content(
        job_title=job_title,
        keywords=keywords,
        ordered_skills=ordered_skills,
        projects=projects,
        experience=experience,
        certs=certs,
        base_summary=base_summary,
    )


def _ai_select_content(
    job_title: str,
    job_description: str,
    keywords: list[str],
    profile: dict,
    ordered_skills: list[str],
    base_summary: str,
) -> dict:
    """Use Groq to select and rephrase relevant resume content."""
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        # Remove internal fields before sending
        clean_profile = {k: v for k, v in profile.items() if not k.startswith("_")}

        prompt = f"""
You are a professional resume writer. Given a job description and a candidate's profile,
select and lightly rephrase the most relevant content for this specific role.

═══ STRICT RULES ═══
✗ NEVER add skills, projects, experience, or metrics not in the profile
✗ NEVER invent numbers, technologies, or achievements
✓ You may reorder bullets for relevance
✓ You may rephrase using keywords from the JD (without changing meaning)
✓ You may write a tailored summary using ONLY facts from the profile
✓ You may omit irrelevant experience/projects
════════════════════

JOB TITLE: {job_title}

JD KEYWORDS TO INCORPORATE (where factually accurate): {', '.join(keywords[:15])}

JOB DESCRIPTION (excerpt):
{job_description[:2000]}

CANDIDATE PROFILE (source of truth):
{json.dumps(clean_profile, indent=2)[:3000]}

Return valid JSON:
{{
  "summary": "2-3 sentence tailored summary using only real facts",
  "skills": ["Skill1", "Skill2", ...],
  "projects": [
    {{
      "name": "Project name from profile",
      "description": "Rephrased description emphasizing relevance",
      "tech": ["tech1", "tech2"],
      "bullets": ["bullet using real metrics only"]
    }}
  ],
  "experience": [
    {{
      "company": "Company from profile",
      "role": "Role from profile",
      "start": "date",
      "end": "date",
      "bullets": ["rephrased but factual bullet"]
    }}
  ],
  "certifications": ["cert name from profile"]
}}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)

    except Exception as e:
        print(f"[ResumeData] AI selection failed: {e}. Falling back to keyword selection.")
        return _keyword_select_content(
            job_title=job_title,
            keywords=keywords,
            ordered_skills=ordered_skills,
            projects=profile.get("projects", []),
            experience=profile.get("experience", []),
            certs=profile.get("certifications", []),
            base_summary=base_summary,
        )


def _keyword_select_content(
    job_title: str,
    keywords: list[str],
    ordered_skills: list[str],
    projects: list[dict],
    experience: list[dict],
    certs: list[dict],
    base_summary: str,
) -> dict:
    """
    Simple fallback: select content based on keyword overlap.
    No AI — purely deterministic.
    """
    kw_lower = {k.lower() for k in keywords}

    # Score each project by keyword overlap in description/tech/technologies
    def project_score(proj):
        tech_list = proj.get("technologies", proj.get("tech", []))
        text = (proj.get("description", "") + " " + " ".join(tech_list)).lower()
        return sum(1 for kw in kw_lower if kw in text)

    scored_projects = sorted(projects, key=project_score, reverse=True)

    # Score experience entries — support both old (role/bullets) and new (title/facts) keys
    def exp_score(exp):
        role_text   = exp.get("title", exp.get("role", ""))
        bullet_text = " ".join(exp.get("facts", exp.get("bullets", [])))
        text = (role_text + " " + bullet_text).lower()
        return sum(1 for kw in kw_lower if kw in text)

    scored_exp = sorted(experience, key=exp_score, reverse=True)

    # Normalise experience to common schema
    normalised_exp = [
        {
            "company": e.get("company", ""),
            "role":    e.get("title", e.get("role", "")),
            "start":   e.get("start_date", e.get("start", "")),
            "end":     e.get("end_date",   e.get("end", "Present")),
            "bullets": e.get("facts",      e.get("bullets", [])),
        }
        for e in scored_exp
    ]

    # Normalise projects to common schema
    normalised_projects = [
        {
            "name":        p.get("name", ""),
            "description": p.get("description", ""),
            "tech":        p.get("technologies", p.get("tech", [])),
            "bullets":     p.get("facts", p.get("metrics", p.get("bullets", []))),
        }
        for p in scored_projects
    ]

    return {
        "summary": base_summary,
        "skills": ordered_skills,
        "projects": normalised_projects,
        "experience": normalised_exp,
        "certifications": [c.get("name", c) if isinstance(c, dict) else c for c in certs],
    }
