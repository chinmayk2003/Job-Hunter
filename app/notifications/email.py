"""
notifications/email.py — Daily job digest via Gmail SMTP
=========================================================
Sends a rich HTML email digest with:
  🔥 Strong matches
  🟡 Stretch opportunities
  ⚪ Low matches

Each job shows: company, title, match score, matched/missing skills,
and the name of the generated resume (if any).

Setup:
  1. Enable 2FA on your Google account
  2. Go to: myaccount.google.com → Security → App Passwords
  3. Generate an "App Password" for "Mail"
  4. Add to .env: GMAIL_ADDRESS=you@gmail.com, GMAIL_APP_PASS=xxxx xxxx xxxx xxxx
"""

import smtplib
import json
import csv
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import date
from typing import Optional

from app.config import GMAIL_ADDRESS, GMAIL_APP_PASS, NOTIFY_EMAIL, ENABLE_EMAIL
from app.database.db import get_digest_jobs, get_todays_jobs, get_stats


# ── HTML email template ────────────────────────────────────────────────────────

def _build_job_card(job: dict, is_strong: bool = False) -> str:
    """Build an HTML card for a single job posting."""
    company     = job.get("company", "Unknown")
    title       = job.get("title", "Unknown Role")
    url         = job.get("url", "#")
    score       = job.get("final_score") or 0
    rec         = job.get("recommendation", "low")
    matched     = json.loads(job.get("matched_skills") or "[]")
    missing     = json.loads(job.get("missing_skills") or "[]")
    location    = job.get("location", "")

    # Color scheme per recommendation
    colors = {
        "strong":  {"border": "#22c55e", "badge_bg": "#dcfce7", "badge_fg": "#166534", "emoji": "🔥"},
        "stretch": {"border": "#f59e0b", "badge_bg": "#fef3c7", "badge_fg": "#92400e", "emoji": "🟡"},
        "low":     {"border": "#94a3b8", "badge_bg": "#f1f5f9", "badge_fg": "#475569", "emoji": "⚪"},
    }
    c = colors.get(rec, colors["low"])

    matched_html = "".join(
        f'<span style="background:#dcfce7;color:#166534;padding:2px 8px;'
        f'border-radius:4px;font-size:12px;margin:2px;">{s}</span>'
        for s in matched[:8]
    )
    missing_html = "".join(
        f'<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;'
        f'border-radius:4px;font-size:12px;margin:2px;">{s}</span>'
        for s in missing[:5]
    )

    summary_html = ""
    ai_summary = job.get("ai_summary", "")
    if ai_summary:
        summary_html = f'<div style="margin-top:10px;font-size:13px;color:#475569;border-top:1px solid #f1f5f9;padding-top:8px;">{ai_summary[:300]}</div>'

    return f"""
    <div style="border-left:4px solid {c['border']};background:#ffffff;
                padding:16px 20px;margin:12px 0;border-radius:4px;
                box-shadow:0 1px 3px rgba(0,0,0,0.08);">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          <span style="font-size:16px;font-weight:700;color:#1e293b;">{c['emoji']} {company}</span>
          <span style="color:#64748b;font-size:14px;"> &mdash; </span>
          <a href="{url}" style="color:#2563eb;font-size:15px;font-weight:600;text-decoration:none;">{title}</a>
          {f'<span style="color:#94a3b8;font-size:12px;margin-left:8px;">&#128205; {location}</span>' if location else ''}
        </div>
        <span style="background:{c['badge_bg']};color:{c['badge_fg']};
                     padding:4px 12px;border-radius:20px;font-weight:700;font-size:14px;
                     white-space:nowrap;margin-left:12px;">
          {score:.0%}
        </span>
      </div>

      {f'<div style="margin-top:10px;"><span style="font-size:12px;color:#64748b;font-weight:600;">&#10003; MATCHED:</span> {matched_html}</div>' if matched else ''}
      {f'<div style="margin-top:6px;"><span style="font-size:12px;color:#64748b;font-weight:600;">&#9888; MISSING:</span> {missing_html}</div>' if missing else ''}
      {summary_html}

      <div style="margin-top:12px;">
        <a href="{url}" style="background:#2563eb;color:#ffffff;padding:6px 16px;
                               border-radius:4px;text-decoration:none;font-size:13px;font-weight:600;">
          View Job &rarr;
        </a>
      </div>
    </div>
    """


def build_html_email(jobs: list[dict], stats: dict) -> str:
    """Build the full HTML email body."""
    today   = date.today().strftime("%B %d, %Y")
    total   = len(jobs)
    strong  = [j for j in jobs if j.get("recommendation") == "strong"]
    stretch = [j for j in jobs if j.get("recommendation") == "stretch"]
    low     = [j for j in jobs if j.get("recommendation") == "low"]

    strong_cards  = "".join(_build_job_card(j, is_strong=True) for j in strong)
    stretch_cards = "".join(_build_job_card(j) for j in stretch)
    low_cards     = "".join(_build_job_card(j) for j in low) if low else ""

    strong_section  = f"""
    <h2 style="color:#166534;font-size:16px;margin:24px 0 8px;">🔥 Strong Matches ({len(strong)})</h2>
    {strong_cards}
    """ if strong else ""

    stretch_section = f"""
    <h2 style="color:#92400e;font-size:16px;margin:24px 0 8px;">🟡 Stretch Opportunities ({len(stretch)})</h2>
    {stretch_cards}
    """ if stretch else ""

    low_section = f"""
    <h2 style="color:#475569;font-size:16px;margin:24px 0 8px;">⚪ Low Matches ({len(low)})</h2>
    {low_cards}
    """ if low else ""

    no_jobs_msg = """
    <div style="text-align:center;padding:40px;color:#94a3b8;">
      <p style="font-size:18px;">No new jobs found today.</p>
      <p style="font-size:14px;">The agent will check again tomorrow.</p>
    </div>
    """ if not jobs else ""

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f8fafc;margin:0;padding:0;">
  <div style="max-width:680px;margin:0 auto;padding:20px;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);
                border-radius:12px;padding:28px 32px;margin-bottom:24px;color:#ffffff;">
      <h1 style="margin:0;font-size:24px;font-weight:800;">🤖 AI Job Agent</h1>
      <p style="margin:4px 0 0;font-size:14px;opacity:0.85;">Daily Digest — {today}</p>
    </div>

    <!-- Stats row -->
    <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap;">
      <div style="flex:1;min-width:120px;background:#ffffff;padding:16px;border-radius:8px;
                  border:1px solid #e2e8f0;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#1e293b;">{total}</div>
        <div style="font-size:12px;color:#64748b;">New Today</div>
      </div>
      <div style="flex:1;min-width:120px;background:#ffffff;padding:16px;border-radius:8px;
                  border:1px solid #e2e8f0;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#22c55e;">{len(strong)}</div>
        <div style="font-size:12px;color:#64748b;">Strong</div>
      </div>
      <div style="flex:1;min-width:120px;background:#ffffff;padding:16px;border-radius:8px;
                  border:1px solid #e2e8f0;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#f59e0b;">{len(stretch)}</div>
        <div style="font-size:12px;color:#64748b;">Stretch</div>
      </div>
      <div style="flex:1;min-width:120px;background:#ffffff;padding:16px;border-radius:8px;
                  border:1px solid #e2e8f0;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#64748b;">{stats.get('total_jobs', 0)}</div>
        <div style="font-size:12px;color:#64748b;">All Time</div>
      </div>
    </div>

    <!-- Job listings -->
    {no_jobs_msg}
    {strong_section}
    {stretch_section}
    {low_section}

    <!-- Footer -->
    <div style="text-align:center;padding:24px 0 0;color:#94a3b8;font-size:12px;
                border-top:1px solid #e2e8f0;margin-top:24px;">
      <p>Generated by your AI Job Agent · Running on GitHub Actions</p>
      <p>Reply to this email to adjust your preferences</p>
    </div>

  </div>
</body>
</html>
"""


def build_subject(jobs: list[dict]) -> str:
    """Build the email subject line."""
    today    = date.today().strftime("%b %d")
    total    = len(jobs)
    strong   = sum(1 for j in jobs if j.get("recommendation") == "strong")
    stretch  = sum(1 for j in jobs if j.get("recommendation") == "stretch")

    if total == 0:
        return f"[Job Agent] {today} — No new jobs today"
    parts = []
    if strong:  parts.append(f"🔥 {strong} strong")
    if stretch: parts.append(f"🟡 {stretch} stretch")
    return f"[Job Agent] {today} — {total} new jobs | {', '.join(parts)}"


# ── CSV Report ─────────────────────────────────────────────────────────────────

def generate_csv_report(jobs: list[dict]) -> str:
    """Generate a CSV string containing all job details."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Company", "Title", "URL", "Score", "Recommendation", "Experience Required", "Role Type", "Matched Skills", "Missing Skills", "Summary"])
    
    for job in jobs:
        score = f"{(job.get('final_score') or 0):.0%}"
        matched = ", ".join(json.loads(job.get("matched_skills") or "[]"))
        missing = ", ".join(json.loads(job.get("missing_skills") or "[]"))
        
        writer.writerow([
            job.get("company", ""),
            job.get("title", ""),
            job.get("url", ""),
            score,
            job.get("recommendation", ""),
            job.get("experience_required", ""),
            job.get("role_type", ""),
            matched,
            missing,
            job.get("ai_summary", "")
        ])
    return output.getvalue()


# ── Sender ─────────────────────────────────────────────────────────────────────

def send_digest(dry_run: bool = False) -> bool:
    """
    Build and send the daily email digest.
    Returns True if email was sent successfully (or dry_run skipped).
    dry_run=True: print the email to console instead of sending.
    """
    if not ENABLE_EMAIL and not dry_run:
        print("[Email] Email disabled in config. Skipping.")
        return False

    # Use get_digest_jobs() — all strong/stretch matches, not just today's
    # (get_todays_jobs() is empty on re-runs if jobs were collected yesterday)
    jobs  = get_digest_jobs()
    today_jobs = get_todays_jobs()   # for "new today" counter
    stats = get_stats()

    html    = build_html_email(jobs, stats)
    subject = build_subject(jobs)

    if dry_run:
        print(f"\n{'='*60}")
        print(f"SUBJECT: {subject}")
        print(f"{'='*60}")
        print(f"Strong+Stretch matches: {len(jobs)}")
        print(f"  New today: {len(today_jobs)}")
        print(f"Stats: {stats}")
        print("[dry_run] Email not sent.")
        return True

    if not GMAIL_ADDRESS or not GMAIL_APP_PASS:
        print("[Email] Gmail credentials not configured. Add GMAIL_ADDRESS and GMAIL_APP_PASS to .env")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = NOTIFY_EMAIL

        # Plain text fallback
        plain_text = f"AI Job Agent — {date.today()}\n\n"
        for job in jobs:
            plain_text += f"{job.get('recommendation','').upper()}: {job.get('company')} — {job.get('title')} ({(job.get('final_score') or 0):.0%})\n"
            plain_text += f"  {job.get('url')}\n\n"

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html, "html"))

        # Attach CSV
        if jobs:
            csv_content = generate_csv_report(jobs)
            part = MIMEApplication(csv_content.encode("utf-8"), Name="jobs_report.csv")
            part["Content-Disposition"] = 'attachment; filename="jobs_report.csv"'
            msg.attach(part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            # Strip spaces — Gmail app passwords are sometimes stored with spaces
            # but must be passed as a continuous 16-character string
            app_pass = (GMAIL_APP_PASS or "").replace(" ", "")
            smtp.login(GMAIL_ADDRESS, app_pass)
            smtp.sendmail(GMAIL_ADDRESS, NOTIFY_EMAIL, msg.as_string())

        print(f"[Email] ✅ Digest sent to {NOTIFY_EMAIL} — {len(jobs)} jobs")
        return True

    except smtplib.SMTPAuthenticationError:
        print("[Email] ❌ Gmail auth failed. Check your App Password in .env")
    except smtplib.SMTPException as e:
        print(f"[Email] ❌ SMTP error: {e}")
    except Exception as e:
        print(f"[Email] ❌ Unexpected error: {e}")

    return False
