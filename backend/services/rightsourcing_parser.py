import re

NOT_LISTED = "Not Listed"

BULLET_RE = re.compile(r"^[•\-*▪]\s*")
PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ADDRESS_RE = re.compile(r"[A-Za-z .]+,\s*[A-Z]{2}(\s+\d{5})?\s*$")

SECTION_ALIASES = {
    "professional summary": "summary",
    "summary": "summary",
    "leadership & core qualifications": "qualifications",
    "leadership and core qualifications": "qualifications",
    "core qualifications": "qualifications",
    "qualifications": "qualifications",
    "skills": "qualifications",
    "education": "education",
    "licensure & certification": "licenses_certs",
    "licensure & certifications": "licenses_certs",
    "licensure and certifications": "licenses_certs",
    "licenses & certifications": "licenses_certs",
    "licenses and certifications": "licenses_certs",
    "certifications": "certifications_only",
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
    r"(?P<start>[A-Za-z]{3,9}\.?\s+\d{4}|Present|Current)\s*[–—-]\s*(?P<end>[A-Za-z]{3,9}\.?\s+\d{4}|Present|Current)",
    re.IGNORECASE,
)
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


def _lines(resume_text: str):
    return [_clean(line) for line in resume_text.splitlines()]


def _section_key(line: str):
    if not line.endswith(":"):
        return None
    return SECTION_ALIASES.get(line[:-1].strip().lower())


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
        if not line:
            continue
        if PHONE_RE.search(line) and not EMAIL_RE.search(line):
            header["phone"] = line
        elif EMAIL_RE.search(line):
            header["email"] = EMAIL_RE.search(line).group(0)
        elif ADDRESS_RE.search(line):
            header["permanent_address"] = line
        elif not header["professional_headline"]:
            header["professional_headline"] = line
    return header


def _parse_bulleted_list(lines):
    items = []
    for line in lines:
        if not line:
            continue
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
    entries = []
    for line in lines:
        if not line:
            continue
        date = ""
        rest = line
        if "|" in line:
            rest, _, date = line.rpartition("|")
            rest, date = _clean(rest), _clean(date)

        parts = re.split(r"\s{2,}|\s+–\s+", rest, maxsplit=1)
        degree = _clean(parts[0]) if parts else rest
        tail = _clean(parts[1]) if len(parts) > 1 else ""

        school, location = tail, ""
        if " - " in tail:
            school, _, location = tail.partition(" - ")
            school, location = _clean(school), _clean(location)
        elif tail.count(",") >= 2:
            segments = [s.strip() for s in tail.split(",")]
            school = ", ".join(segments[:-2])
            location = ", ".join(segments[-2:])

        entries.append({"degree": degree, "school": school, "location": location, "date": date})
    return entries


def _parse_licenses_certs(lines, force_bucket=None):
    licenses, certifications = [], []
    for line in lines:
        if not line:
            continue
        line = BULLET_RE.sub("", line)
        name, expires = line, ""
        if "|" in line:
            name, _, expires_part = line.partition("|")
            name = _clean(name)
            expires_match = re.search(r"Expires:\s*(.+)", expires_part, re.IGNORECASE)
            expires = _clean(expires_match.group(1)) if expires_match else _clean(expires_part)

        id_match = ID_RE.search(name)
        cert_id = id_match.group(1) if id_match else ""
        if id_match:
            name = _clean(name.replace(id_match.group(0), ""))

        entry = {"name": name, "id": cert_id, "expires": expires}
        is_license = bool(cert_id) or bool(re.match(r"^(RN\b|Registered Nurse\b|Licensed|License)", name, re.IGNORECASE))
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


def _match_job_header(line):
    if "|" not in line:
        return None
    facility_part, _, dates_part = line.rpartition("|")
    facility_part, dates_part = _clean(facility_part), _clean(dates_part)
    date_match = DATE_RANGE_RE.search(dates_part)
    if not date_match:
        return None

    job = _new_job()
    job["start_date"] = date_match.group("start")
    job["end_date"] = date_match.group("end")

    tail_match = FACILITY_TAIL_RE.match(facility_part)
    if tail_match:
        job["facility_name"] = _clean(tail_match.group("name"))
        job["city"] = _clean(tail_match.group("city"))
        job["state"] = tail_match.group("state")
    else:
        job["facility_name"] = facility_part
    return job


def _extract_position_type(title: str) -> str:
    match = POSITION_TYPE_RE.search(title)
    return match.group(1) if match else NOT_LISTED


def _parse_experience(lines):
    jobs = []
    current = None
    awaiting_title = False

    for line in lines:
        if not line:
            continue

        job = _match_job_header(line)
        if job:
            if current:
                jobs.append(current)
            current = job
            awaiting_title = True
            continue

        if current is None:
            continue

        label_match = LABEL_LINE_RE.match(line) if not BULLET_RE.match(line) else None
        if label_match:
            awaiting_title = False
            label, value = _clean(label_match.group(1)).lower(), _clean(label_match.group(2))
            field = LABEL_ALIASES.get(label)
            if field:
                current[field] = value
            else:
                current["additional_details"].append({"label": _clean(label_match.group(1)), "value": value})
            continue

        if BULLET_RE.match(line):
            awaiting_title = False
            current["duties"].append(BULLET_RE.sub("", line))
            continue

        if awaiting_title:
            if current["job_title"]:
                current["job_title"] += " " + line
            else:
                current["job_title"] = line
        elif current["duties"]:
            current["duties"][-1] += " " + line

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
