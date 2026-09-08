import re

NOT_LISTED = "Not Listed"

BULLET_RE = re.compile(r"^[•\-*▪]\s*")
PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ADDRESS_RE = re.compile(r"[A-Za-z .]+,\s*[A-Z]{2}(\s+\d{5})?\s*$")

SECTION_ALIASES = {
    "professional summary": "summary",
    "summary": "summary",
    "summary statement": "summary",
    "professional summary statement": "summary",
    "career summary": "summary",
    "objective": "summary",
    "leadership & core qualifications": "qualifications",
    "leadership and core qualifications": "qualifications",
    "core qualifications": "qualifications",
    "qualifications": "qualifications",
    "skills": "qualifications",
    "key skills": "qualifications",
    "education": "education",
    "licensure & certification": "licenses_certs",
    "licensure & certifications": "licenses_certs",
    "licensure and certifications": "licenses_certs",
    "licenses & certifications": "licenses_certs",
    "licenses and certifications": "licenses_certs",
    "licensure": "licenses_certs",
    "licenses": "licenses_certs",
    "certifications": "certifications_only",
    "certification": "certifications_only",
    "professional experience": "experience",
    "experience": "experience",
    "work experience": "experience",
    "employment history": "experience",
}

LABEL_ALIASES = {
    "emr": "emr",
    "ehr": "emr",
    "facility type": "facility_type",
    "type of facility": "facility_type",
    "trauma level": "trauma_level",
    "trauma designation": "trauma_level",
    "position type": "position_type",
    "employment type": "position_type",
    "agency name": "agency_name",
    "agency": "agency_name",
    "staffing agency": "agency_name",
}

DATE_RANGE_RE = re.compile(
    r"(?P<start>[A-Za-z]{3,9}\.?,?\s*\d{4}|Present|Current)\s*[–—-]\s*(?P<end>[A-Za-z]{3,9}\.?,?\s*\d{4}|Present|Current)",
    re.IGNORECASE,
)
_MONTH_YEAR_RE = re.compile(r"^([A-Za-z]{3,9})\.?,?\s*(\d{4})$")
_SINGLE_DATE_RE = re.compile(r"([A-Za-z]{3,9}\.?,?\s*\d{4})\s*$", re.IGNORECASE)
FACILITY_TAIL_RE = re.compile(
    r"^(?P<name>.+)\s+[–—-]\s+(?P<city>[A-Za-z][A-Za-z .'&]*),\s*(?P<state>[A-Z]{2})$"
)
LABEL_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z /&]{1,40}):\s*(.+)$")
ID_RE = re.compile(r"#\s*([A-Za-z0-9\-]+)")
POSITION_TYPE_RE = re.compile(
    r"\b(Staff|PRN|Per\s*Diem|Travel(?:\s+Contract)?|Contract|Locums?|Agency|Float|Casual|Registry|Part[- ]Time|Full[- ]Time)\b",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_date(text: str) -> str:
    text = _clean(text)
    if text.lower() in ("present", "current"):
        return "Present"
    match = _MONTH_YEAR_RE.match(text.replace(",", ""))
    if match:
        month, year = match.groups()
        return f"{month[:3].capitalize()} {year}"
    return text


def _lines(resume_text: str):
    return [_clean(line) for line in resume_text.splitlines()]


def _section_key(line: str):
    normalized = line.rstrip(":").strip().lower()
    return SECTION_ALIASES.get(normalized)


def _parse_header(lines):
    header = {
        "full_name": "", "credentials_suffix": "", "professional_headline": "",
        "phone": "", "email": "", "permanent_address": "",
    }
    name_line = lines[0] if lines else ""
    if "," in name_line:
        first, rest = name_line.split(",", 1)
        header["full_name"], header["credentials_suffix"] = _clean(first), _clean(rest)
    else:
        header["full_name"] = name_line

    for line in lines[1:]:
        for segment in line.split("|"):
            segment = _clean(segment)
            if not segment:
                continue
            email_match = EMAIL_RE.search(segment)
            phone_match = PHONE_RE.search(segment)
            if email_match:
                header["email"] = header["email"] or email_match.group(0)
            elif phone_match:
                header["phone"] = header["phone"] or phone_match.group(0)
            elif ADDRESS_RE.search(segment):
                header["permanent_address"] = header["permanent_address"] or segment
            elif not header["professional_headline"]:
                header["professional_headline"] = segment
    return header


def _parse_bulleted_list(lines):
    content = [l for l in lines if l]
    if not any(BULLET_RE.match(l) for l in content):
        # Prose with no bullet markers at all — treat the whole block as one item
        # rather than inventing bullet points the resume doesn't have.
        return [_clean(" ".join(content))] if content else []

    items = []
    for line in content:
        if BULLET_RE.match(line):
            items.append(BULLET_RE.sub("", line))
        elif items:
            items[-1] += " " + line
    return items


def _parse_qualifications(lines):
    bulleted = [l for l in lines if l]
    if any(BULLET_RE.match(l) for l in bulleted):
        return _parse_bulleted_list(lines)
    joined = " ".join(bulleted)
    return [_clean(x) for x in joined.split(",") if _clean(x)]


def _parse_education(lines):
    """Handles two conventions: a single "Degree – School, City, ST | Date" line,
    or a degree line and a school/location line as two separate lines (in either
    order, since some resumes put the date next to the degree and others next
    to the school)."""
    entries = []
    pending_degree, pending_date = None, ""

    def flush_pending():
        nonlocal pending_degree, pending_date
        if pending_degree:
            entries.append({"degree": pending_degree, "school": "", "location": "", "date": pending_date})
        pending_degree, pending_date = None, ""

    for line in lines:
        if not line:
            continue

        if "|" in line:
            flush_pending()
            rest, _, date = line.rpartition("|")
            rest, date = _clean(rest), _normalize_date(date)
            parts = re.split(r"\s{2,}|\s+–\s+", rest, maxsplit=1)
            degree = _clean(parts[0]) if parts else rest
            tail = _clean(parts[1]) if len(parts) > 1 else ""
            school, city, state = _split_facility_city_state(tail)
            location = f"{city}, {state}" if city and state else ""
            entries.append({"degree": degree, "school": school if location else tail, "location": location, "date": date})
            continue

        date_match = _SINGLE_DATE_RE.search(line)
        remainder = _clean(line[:date_match.start()]) if date_match else line
        school, city, state = _split_facility_city_state(remainder)

        if city and state:
            entries.append({
                "degree": pending_degree or "", "school": school, "location": f"{city}, {state}",
                "date": _normalize_date(date_match.group(1)) if date_match else pending_date,
            })
            pending_degree, pending_date = None, ""
        elif date_match:
            flush_pending()
            pending_degree, pending_date = remainder, _normalize_date(date_match.group(1))
        else:
            flush_pending()
            pending_degree = remainder

    flush_pending()
    return entries


def _parse_single_cert_line(line: str) -> dict:
    name, expires_part = line, ""
    if "|" in line:
        name, _, expires_part = line.partition("|")
    else:
        expires_idx = line.lower().find("expires:")
        if expires_idx != -1:
            name, expires_part = line[:expires_idx], line[expires_idx:]

    name = _clean(name)
    expires_match = re.search(r"Expires:\s*(.+)", expires_part, re.IGNORECASE)
    expires = _clean(expires_match.group(1)) if expires_match else _clean(expires_part)

    id_match = ID_RE.search(name)
    cert_id = id_match.group(1) if id_match else ""
    if id_match:
        name = _clean(name.replace(id_match.group(0), ""))
    return {"name": name, "id": cert_id, "expires": expires}


def _split_multi_cert_line(line: str) -> list:
    """A line listing several short cert names with no per-item delimiter at all
    (e.g. "BLS, NRP, ACLS, Allentown, PA October 2025") — pull off a trailing
    date and "City, ST" fragment, then treat the rest as comma-separated names
    sharing that one expiry, rather than one garbled certification entry."""
    date_match = _SINGLE_DATE_RE.search(line)
    expires = _normalize_date(date_match.group(1)) if date_match else ""
    remainder = _clean(line[:date_match.start()]) if date_match else line

    _, city, state = _split_facility_city_state(remainder)
    if city and state:
        remainder = re.sub(rf",\s*{re.escape(city)},\s*{state}\s*$", "", remainder).strip()

    names = [_clean(n) for n in remainder.split(",") if _clean(n)]
    return [{"name": n, "id": "", "expires": expires} for n in names] or [{"name": remainder, "id": "", "expires": expires}]


def _parse_licenses_certs(lines, force_bucket=None):
    licenses, certifications = [], []
    for line in lines:
        if not line:
            continue
        line = BULLET_RE.sub("", line)

        if "|" in line or re.search(r"Expires:", line, re.IGNORECASE):
            entries = [_parse_single_cert_line(line)]
        else:
            entries = _split_multi_cert_line(line)

        for entry in entries:
            is_license = bool(entry["id"]) or bool(re.match(r"^(RN\b|Registered Nurse\b|Licensed|License)", entry["name"], re.IGNORECASE))
            if force_bucket == "certifications_only" or (force_bucket is None and not is_license):
                certifications.append(entry)
            else:
                licenses.append(entry)
    return licenses, certifications


def _new_job():
    return {
        "facility_name": "", "city": "", "state": "",
        "start_date": "", "end_date": "", "job_title": "",
        "emr": NOT_LISTED, "position_type": NOT_LISTED, "agency_name": NOT_LISTED,
        "trauma_level": NOT_LISTED, "facility_type": NOT_LISTED,
        "additional_details": [], "duties": [],
    }


def _split_facility_city_state(text: str):
    """Facility/location line comes in at least two conventions across resumes:
    "Name – City, ST" (dash-separated) or plain "Name, City, ST" (comma-separated).
    Try the dash form first since it's less ambiguous, then fall back to treating
    the last two comma segments as city/state if the last one is a state code."""
    tail_match = FACILITY_TAIL_RE.match(text)
    if tail_match:
        return _clean(tail_match.group("name")), _clean(tail_match.group("city")), tail_match.group("state")

    parts = [p.strip() for p in text.split(",")]
    if len(parts) >= 3 and re.match(r"^[A-Z]{2}$", parts[-1]):
        return ", ".join(parts[:-2]), parts[-2], parts[-1]
    return text, "", ""


def _strip_date(line: str):
    """Pull a date range out of a line that may also carry the facility or job
    title on the same line, in either order — resumes aren't consistent about
    which piece of the job header the date is attached to."""
    match = DATE_RANGE_RE.search(line)
    if not match:
        return None, None, line
    remainder = _clean(line[:match.start()] + " " + line[match.end():]).strip(" |,-–—")
    return _normalize_date(match.group("start")), _normalize_date(match.group("end")), remainder


def _looks_like_title(text: str) -> bool:
    return bool(text) and len(text.split()) <= 12 and not text.endswith((".", ":"))


def _extract_position_type(title: str) -> str:
    match = POSITION_TYPE_RE.search(title)
    return match.group(1) if match else NOT_LISTED


def _parse_experience(lines):
    jobs = []
    current = None
    need_title = False
    need_facility = False

    for line in lines:
        if not line:
            continue

        is_bullet = bool(BULLET_RE.match(line))
        label_match = LABEL_LINE_RE.match(line) if not is_bullet else None
        date_start, date_end, remainder = (None, None, line) if label_match else _strip_date(line)

        if date_start:
            if current:
                jobs.append(current)
            current = _new_job()
            current["start_date"], current["end_date"] = date_start, date_end
            name, city, state = _split_facility_city_state(remainder)
            if city and state:
                current["facility_name"], current["city"], current["state"] = name, city, state
                # The job title may have already been misread as the previous
                # job's last duty, if it appeared before this line with no
                # marker to tell them apart — reclaim it when it looks right.
                if jobs and jobs[-1]["duties"] and _looks_like_title(jobs[-1]["duties"][-1]):
                    current["job_title"] = jobs[-1]["duties"].pop()
                need_title = not current["job_title"]
                need_facility = False
            else:
                current["job_title"] = remainder
                need_title = False
                need_facility = True
            continue

        if current is None:
            continue

        if need_facility and not label_match:
            name, city, state = _split_facility_city_state(remainder)
            current["facility_name"], current["city"], current["state"] = name, (city or ""), (state or "")
            need_facility = False
            continue

        if need_title and not label_match and not is_bullet:
            current["job_title"] = remainder
            need_title = False
            continue

        if label_match:
            label, value = _clean(label_match.group(1)).lower(), _clean(label_match.group(2))
            field = LABEL_ALIASES.get(label)
            if field:
                current[field] = value
            else:
                current["additional_details"].append({"label": _clean(label_match.group(1)), "value": value})
            continue

        current["duties"].append(BULLET_RE.sub("", line))

    if current:
        jobs.append(current)

    for job in jobs:
        if job["position_type"] == NOT_LISTED:
            job["position_type"] = _extract_position_type(job["job_title"])

    return jobs


def extract_structured_resume_rightsourcing_deterministic(resume_text: str) -> dict:
    """Parse a resume that already follows the HonorVet labeled-field convention
    (section headers ending in ':', per-job 'Label: Value' lines, bulleted lists)
    into the standard structure — no AI calls, no inference beyond literal parsing."""
    lines = _lines(resume_text)

    first_section_idx = next((i for i, l in enumerate(lines) if _section_key(l)), len(lines))
    result = _parse_header(lines[:first_section_idx])
    result.update({
        "professional_summary": [], "core_qualifications": [], "education": [],
        "licenses": [], "certifications": [], "experience": [],
    })

    section = None
    section_lines = []
    certifications_only_lines = []

    def flush(sec, sec_lines):
        if sec == "summary":
            result["professional_summary"] = _parse_bulleted_list(sec_lines)
        elif sec == "qualifications":
            result["core_qualifications"] = _parse_qualifications(sec_lines)
        elif sec == "education":
            result["education"] = _parse_education(sec_lines)
        elif sec == "licenses_certs":
            licenses, certifications = _parse_licenses_certs(sec_lines)
            result["licenses"].extend(licenses)
            result["certifications"].extend(certifications)
        elif sec == "certifications_only":
            certifications_only_lines.extend(sec_lines)
        elif sec == "experience":
            result["experience"] = _parse_experience(sec_lines)

    for line in lines[first_section_idx:]:
        key = _section_key(line)
        if key:
            flush(section, section_lines)
            section, section_lines = key, []
        else:
            section_lines.append(line)
    flush(section, section_lines)

    if certifications_only_lines:
        _, certifications = _parse_licenses_certs(certifications_only_lines, force_bucket="certifications_only")
        result["certifications"].extend(certifications)

    return result
