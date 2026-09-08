import re
from datetime import datetime

from services.rightsourcing_parser import extract_structured_resume_rightsourcing_deterministic

NOT_LISTED = "Not Listed"

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC",
}
US_STATE_ABBREVIATIONS = set(US_STATES.values())
# Longest names first, so "north carolina" matches before "carolina"-style partial overlaps.
_STATE_NAME_RE = re.compile(
    r"\b(" + "|".join(sorted(US_STATES, key=len, reverse=True)) + r")\b", re.IGNORECASE
)


def _find_states(text: str) -> set:
    found = {abbr for abbr in re.findall(r"\b([A-Z]{2})\b", text) if abbr in US_STATE_ABBREVIATIONS}
    found |= {US_STATES[name.lower()] for name in _STATE_NAME_RE.findall(text)}
    return found


def extract_structured_resume_rightsourcing(resume_text: str) -> dict:
    """Parse raw resume text into the HonorVet standard submission structure.

    Fully deterministic — no AI calls. Only information explicitly present in the
    resume is captured; anything not stated is marked "Not Listed" rather than
    inferred or researched. Assumes the upload is the resume itself (in the
    HonorVet labeled-field convention) and not a multi-document packet — a
    parser with no AI can't tell resume content apart from a bundled cover
    sheet, clearance form, or certificate scan in the same file."""
    structured = extract_structured_resume_rightsourcing_deterministic(resume_text)

    if not structured.get("experience") and not structured.get("phone") and not structured.get("email"):
        raise ValueError(
            "Couldn't find resume content in this file. Upload just the resume itself — "
            "not a packet bundling a cover sheet, clearance form, or certificate scans."
        )

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

    # Professional summary present
    has_summary = bool(resume.get("professional_summary"))
    checks.append({
        "id": "summary_bullets",
        "label": "Professional summary present",
        "status": "pass" if has_summary else "warning",
        "detail": "" if has_summary else "No professional summary bullets found",
    })

    # License state matches candidate's address/work history
    license_states = set()
    for lic in resume.get("licenses", []):
        license_states |= _find_states(lic.get("name", ""))
    work_states = {job.get("state", "") for job in resume.get("experience", []) if job.get("state")}
    address_states = _find_states(resume.get("permanent_address", ""))
    known_states = work_states | address_states
    if license_states and known_states:
        overlap = license_states & known_states
        checks.append({
            "id": "license_state_matches",
            "label": "License state matches candidate location/work history",
            "status": "pass" if overlap else "warning",
            "detail": "" if overlap else f"Licensed in {', '.join(sorted(license_states))} but address/work history shows {', '.join(sorted(known_states))}",
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


def run_checklist(resume: dict) -> list:
    """Run the HonorVet standard submission checklist against a formatted resume. Resume-content checks only — items requiring separate documents (interview availability, reference check sheet) aren't covered here."""
    return _deterministic_checks(resume)
