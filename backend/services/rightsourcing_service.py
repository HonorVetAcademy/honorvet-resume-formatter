import anthropic
import json
import os
import re
from datetime import datetime

from services.resume_formatter_service import research_all_facilities, _parse_json_response

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


def extract_structured_resume_rightsourcing(resume_text: str) -> dict:
    """Parse raw resume text into the HonorVet standard submission structure."""
    prompt = f"""You are formatting a resume for submission to a healthcare staffing client. Parse the resume below into structured JSON.

Preserve the candidate's own wording and facts — do not invent or embellish content, and do not fabricate any facts not present in the source resume. But DO reformat for readability:
- If the source resume lists duties as a dense run of short comma/semicolon-separated fragments (e.g., "Sedation, Titrated drips, Ventilated patients, Belmont, RSI"), do not copy each fragment as its own one- or two-word bullet. Instead, group related fragments into a smaller number of complete, well-formed bullets (e.g., "Managed sedation, titrated drips, and ventilated patients" / "Performed RSI and utilized the Belmont rapid infuser"). Aim for roughly 4-8 substantive bullets per job, each a full phrase or sentence, not a single word or acronym standing alone.
- The "skills" list (separate from duties) is still fine as a flat list of short skill terms — this consolidation guidance is specifically about the per-job "duties" bullets, which should read like a professionally formatted resume, not a raw keyword dump.

RESUME TEXT:
{resume_text}

Return a JSON object with this exact schema:
{{
  "full_name": "<candidate's name in Firstname Lastname capitalization, no credentials>",
  "credentials_suffix": "<credentials after name if stated, e.g. 'BSN, RN, CNOR', else empty string>",
  "phone": "<phone number>",
  "email": "<email>",
  "permanent_address": "<full street address, city, state, zip if stated in the resume — else empty string>",
  "professional_summary": ["<bullet 1>", "<bullet 2>", ...],
  "skills": ["<skill 1>", "<skill 2>", ...],
  "education": [{{"degree": "<degree>", "school": "<school name>", "location": "<city, state>", "date": "<Month, Year format>"}}],
  "certifications": [{{"name": "<certification name/abbreviation>", "issuer": "<issuing body>", "id": "<license/id number if stated, else empty>", "expires": "<expiration date if stated, else empty>"}}],
  "experience": [
    {{
      "facility_name": "<employer/facility name as written>",
      "city": "<city>",
      "state": "<state>",
      "start_date": "<start date, e.g. 'Jan 2025'>",
      "end_date": "<end date or 'Present'>",
      "job_title": "<job title>",
      "emr_mentioned": "<EMR/charting system explicitly mentioned for this job in the resume, else empty string>",
      "duties": ["<duty bullet 1>", "<duty bullet 2>", ...]
    }}
  ]
}}

List experience most-recent-first. Return only valid JSON, no commentary."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    return _parse_json_response(message.content[0].text)


def build_formatted_resume_rightsourcing(structured: dict, facility_research: dict) -> dict:
    """Merge parsed resume with facility research and add client-submission fields."""
    experience = []
    for entry in structured.get("experience", []):
        research = facility_research.get(entry.get("facility_name", "").strip(), {})
        emr = entry.get("emr_mentioned") or research.get("emr_system")
        experience.append({
            **entry,
            "facility_type": research.get("type_of_facility"),
            "trauma_level": research.get("trauma_level"),
            "emr_system": emr,
            "emr_matches_resume": bool(entry.get("emr_mentioned")) and entry.get("emr_mentioned") == research.get("emr_system"),
            "position_type": "",
            "agency_name": "",
            "research_confidence": research.get("confidence", "low"),
            "research_sources": research.get("sources", []),
        })

    return {**structured, "experience": experience}


_MONTH_RE = re.compile(
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{4})",
    re.IGNORECASE,
)


def _parse_month_year(text: str):
    if not text:
        return None
    text = text.strip()
    if text.lower() in ("present", "current", "now"):
        return "present"
    match = _MONTH_RE.search(text)
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group(1)[:3]} {match.group(2)}", "%b %Y")
    except ValueError:
        return None


def _deterministic_checks(resume: dict) -> list:
    checks = []
    today = datetime.now()

    # Name format
    name = resume.get("full_name", "")
    name_ok = bool(re.match(r"^[A-Z][a-zA-Z'\-]*(\s+[A-Z][a-zA-Z'\-]*)+$", name.strip()))
    checks.append({
        "id": "name_format",
        "label": "Name is in Firstname Lastname format",
        "status": "pass" if name_ok else "fail",
        "detail": name if name_ok else f"'{name}' doesn't look like Firstname Lastname capitalization",
    })

    # Contact info
    has_contact = bool(resume.get("phone")) and bool(resume.get("email"))
    checks.append({
        "id": "contact_info",
        "label": "Phone and email present",
        "status": "pass" if has_contact else "fail",
        "detail": "" if has_contact else "Missing phone and/or email",
    })

    # Certifications not expired
    for cert in resume.get("certifications", []):
        expires = _parse_month_year(cert.get("expires", ""))
        if expires and expires != "present" and expires < today:
            checks.append({
                "id": f"cert_expired_{cert.get('name', '')}",
                "label": f"License/certification current: {cert.get('name', '')}",
                "status": "fail",
                "detail": f"Expired {cert.get('expires', '')} — mention renewal plans in selling points if candidate is renewing",
            })

    # Per-job required fields + future-date check
    required_fields = [
        ("facility_name", "Facility name"), ("city", "City"), ("state", "State"),
        ("start_date", "Start date"), ("end_date", "End date"), ("job_title", "Job title"),
    ]
    research_fields = [("trauma_level", "Trauma Level"), ("facility_type", "Facility Type"), ("emr_system", "EMR")]

    experience = resume.get("experience", [])
    for job in experience:
        label = job.get("facility_name") or "Unnamed facility"
        missing = [name for key, name in required_fields if not job.get(key)]
        missing += [name for key, name in research_fields if not job.get(key)]
        checks.append({
            "id": f"job_fields_{label}",
            "label": f"All required fields present: {label}",
            "status": "pass" if not missing else "warning",
            "detail": "" if not missing else f"Missing: {', '.join(missing)}",
        })

        start = _parse_month_year(job.get("start_date", ""))
        end = _parse_month_year(job.get("end_date", ""))
        for d, dl in [(start, "start date"), (end, "end date")]:
            if d and d != "present" and d > today:
                checks.append({
                    "id": f"future_date_{label}_{dl}",
                    "label": f"Dates are in the past: {label}",
                    "status": "fail",
                    "detail": f"{dl.capitalize()} '{job.get('start_date') if dl == 'start date' else job.get('end_date')}' appears to be in the future — check for a typo",
                })

    checks.append({
        "id": "position_type_agency",
        "label": "Position Type / Agency Name",
        "status": "info",
        "detail": "Not present in a candidate's own resume — recruiter fills these in per submission",
    })

    # Gap detection (chronological, most-recent-first list)
    parsed_jobs = []
    for job in experience:
        start = _parse_month_year(job.get("start_date", ""))
        end = _parse_month_year(job.get("end_date", ""))
        if end == "present":
            end = today
        if start and end:
            parsed_jobs.append((start, end, job.get("facility_name", "")))
    parsed_jobs.sort(key=lambda x: x[0], reverse=True)

    gaps = []
    for i in range(len(parsed_jobs) - 1):
        newer_start = parsed_jobs[i][0]
        older_end = parsed_jobs[i + 1][1]
        gap_days = (newer_start - older_end).days
        if gap_days > 45:
            gaps.append({
                "between": f"{parsed_jobs[i + 1][2]} → {parsed_jobs[i][2]}",
                "gap_days": gap_days,
            })

    if gaps:
        for g in gaps:
            checks.append({
                "id": f"gap_{g['between']}",
                "label": f"Employment gap: {g['between']}",
                "status": "warning",
                "detail": f"~{g['gap_days']} day gap — should be explained in the resume or selling points",
            })
    else:
        checks.append({
            "id": "no_gaps",
            "label": "No unexplained employment gaps detected",
            "status": "pass",
            "detail": "",
        })

    return checks


def _llm_qualitative_checks(resume_text: str, resume: dict) -> list:
    """Ask Claude to review the softer, judgment-based checklist items."""
    prompt = f"""You are QA-reviewing a healthcare staffing resume submission against a client checklist. Review the ORIGINAL resume text and the PARSED structure below.

ORIGINAL RESUME TEXT:
{resume_text}

PARSED STRUCTURE:
{json.dumps(resume, indent=2)}

Check these specific items and return a JSON array, one object per item, in this exact order:
1. "summary_bullets" — Is the professional summary in bullet points and does it clearly highlight why this candidate is a strong match for their field?
2. "hospital_settings_consistent" — Are the candidate's hospital/facility settings across jobs consistent with each other (no contradictions in acuity level, unit type, etc.)?
3. "gaps_explained_in_text" — For any employment gaps, does the resume text itself explain them anywhere (e.g., mentions of leave, education, relocation)? If there are no gaps, mark this "pass".
4. "license_state_matches" — Does the state license mentioned match the state(s) the candidate worked in or lists as their address?

Return a JSON array of exactly 4 objects, in the order above:
[
  {{"id": "summary_bullets", "label": "Summary is bulleted and highlights fit", "status": "pass|fail|warning", "detail": "<one sentence>"}},
  {{"id": "hospital_settings_consistent", "label": "Hospital settings consistent across experience", "status": "pass|fail|warning", "detail": "<one sentence>"}},
  {{"id": "gaps_explained_in_text", "label": "Employment gaps explained in resume text", "status": "pass|fail|warning", "detail": "<one sentence>"}},
  {{"id": "license_state_matches", "label": "License state matches candidate location/work history", "status": "pass|fail|warning", "detail": "<one sentence>"}}
]

Return only valid JSON, no commentary."""

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return _parse_json_response(message.content[0].text)
    except Exception as e:
        return [{"id": "qualitative_review_error", "label": "Qualitative checklist review", "status": "warning", "detail": f"Could not complete: {e}"}]


def run_checklist(resume_text: str, resume: dict) -> list:
    """Run the HonorVet standard submission checklist against a formatted resume. Resume-content checks only — items requiring separate documents (interview availability, reference check sheet) aren't covered here."""
    return _deterministic_checks(resume) + _llm_qualitative_checks(resume_text, resume)
