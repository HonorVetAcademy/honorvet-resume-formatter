import anthropic
import json
import os
import re
from datetime import datetime

from services.resume_formatter_service import _parse_json_response

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


NOT_LISTED = "Not Listed"

_EXPERIENCE_DEFAULTS = ("emr", "position_type", "agency_name", "trauma_level", "facility_type")


def extract_structured_resume_rightsourcing(resume_text: str) -> dict:
    """Parse raw resume text into the HonorVet standard submission structure.

    Strict, non-inferring transcription only — no facts, research, or rewriting beyond
    what the candidate's own resume states. See rightsourcing formatting rules."""
    prompt = f"""You are transcribing a resume into a standardized structure for submission to a healthcare staffing client. Follow every rule below exactly.

RULES:
1. Do not add, assume, infer, fabricate, or rewrite any information that is not present in the raw resume.
2. Use only the information provided in the raw resume.
3. Preserve all employment dates exactly as provided, but format each as "Mon YYYY" (e.g. "Jan 2025") or "Present" so the duration can be rendered consistently as "Month Year – Month Year".
4. Maintain the same capitalization, spacing, punctuation, and overall wording shown in the raw resume wherever you transcribe text from it.
5. Do not omit any information from the raw resume — every job, bullet, credential, and detail must appear somewhere in the output.
6. If a required field is not provided in the raw resume, use the exact string "Not Listed".
7. Do not infer an EMR from a general skills section. Only report an EMR for a job if the raw resume explicitly associates that EMR with that specific facility/job.
8. Do not infer an agency name from the fact that a position is labeled "Travel". If the agency is not explicitly named, use "Not Listed".
9. Do not infer Trauma Level or Facility Type from the facility's name or reputation. If not explicitly stated in the resume, use "Not Listed".
10. Do not add phone number, email, license information, certification expiration dates, facility details, patient ratios, agency names, EMRs, trauma levels, facility types, or any other detail unless it is explicitly present in the raw resume.
11. Keep the candidate's original job titles and employment descriptions as close to the raw resume's wording as possible.
12. Do not create new bullet points, combine/rewrite duty fragments into new sentences, or add achievements that are not in the raw resume — transcribe each duty/bullet as the candidate wrote it, only cleaning up obvious spacing.
13. Do not change the meaning of any information.
14. Preserve certifications and licenses exactly as listed, only cleaning up minor spacing.

Classify each licensure/certification entry into exactly one of two buckets:
- "licenses": state RN (or other professional practice) licenses — typically has a license number.
- "certifications": things like ACLS, BLS, PALS, NIHSS, CNOR, etc. — typically no license number.

RESUME TEXT:
{resume_text}

Return a JSON object with this exact schema:
{{
  "full_name": "<candidate's name in Firstname Lastname capitalization, no credentials>",
  "credentials_suffix": "<credentials after name if stated, e.g. 'BSN, RN, CNOR', else empty string>",
  "professional_headline": "<a professional headline/title tagline ONLY if the resume states one, else empty string>",
  "phone": "<phone number, else empty string>",
  "email": "<email, else empty string>",
  "permanent_address": "<full street address / city, state as stated in the resume, else empty string>",
  "professional_summary": ["<bullet 1 transcribed from the resume's own summary>", ...],
  "core_qualifications": ["<skill/qualification 1, transcribed as listed>", ...],
  "education": [{{"degree": "<degree>", "school": "<school name>", "location": "<city, state>", "date": "<date as stated>"}}],
  "licenses": [{{"name": "<license name, e.g. 'RN Compact License (Georgia)'>", "id": "<license number if stated, else empty string>", "expires": "<expiration date if stated, else empty string>"}}],
  "certifications": [{{"name": "<certification name, e.g. 'ACLS (Advanced Cardiac Life Support)'>", "id": "<id if stated, else empty string>", "expires": "<expiration date if stated, else empty string>"}}],
  "experience": [
    {{
      "facility_name": "<employer/facility name as written>",
      "city": "<city, else empty string>",
      "state": "<state, else empty string>",
      "start_date": "<start date, e.g. 'Jan 2025'>",
      "end_date": "<end date or 'Present'>",
      "job_title": "<exact job title as stated>",
      "emr": "<EMR explicitly tied to THIS facility in the resume, else 'Not Listed'>",
      "position_type": "<Staff/PRN/Travel/Contract/etc. ONLY if explicitly stated, else 'Not Listed'>",
      "agency_name": "<staffing agency name ONLY if explicitly stated, else 'Not Listed'>",
      "trauma_level": "<ONLY if explicitly stated in the resume, else 'Not Listed'>",
      "facility_type": "<ONLY if explicitly stated in the resume, else 'Not Listed'>",
      "duties": ["<duty/bullet exactly as the candidate wrote it, minor spacing cleanup only>", ...]
    }}
  ]
}}

List experience most-recent-first. Return only valid JSON, no commentary."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    structured = _parse_json_response(message.content[0].text)

    experience = []
    for entry in structured.get("experience", []):
        entry = dict(entry)
        for field in _EXPERIENCE_DEFAULTS:
            if not entry.get(field):
                entry[field] = NOT_LISTED
        experience.append(entry)
    structured["experience"] = experience

    return structured


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

    # Licenses/certifications not expired
    for cert in resume.get("licenses", []) + resume.get("certifications", []):
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

    experience = resume.get("experience", [])
    for job in experience:
        label = job.get("facility_name") or "Unnamed facility"
        missing = [name for key, name in required_fields if not job.get(key)]
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
