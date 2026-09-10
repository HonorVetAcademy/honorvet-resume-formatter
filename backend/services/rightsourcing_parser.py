import re

NOT_LISTED = "[TO BE CONFIRMED]"

BULLET_RE = re.compile(r"^[•\-*▪◦●‣∙○]\s*")
PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
# Tolerates a stray space before "@" — a common PDF-extraction artifact from
# justified/spaced-out header text (e.g. "name1008 @gmail.com").
EMAIL_RE = re.compile(r"[\w.+-]+\s?@\s?[\w-]+\.[\w.-]+")
ADDRESS_RE = re.compile(r"[A-Za-z .]+,\s*[A-Z]{2}(\s+\d{5})?\s*$")
# Header contact fields are commonly pipe-separated, but not always with the
# ASCII "|" — box-drawing/broken-bar Unicode variants show up too.
_HEADER_SEP_RE = re.compile(r"[|│¦]")

SECTION_ALIASES = {
    "professional summary": "summary",
    "summary": "summary",
    "summary statement": "summary",
    "professional summary statement": "summary",
    "professional profile": "summary",
    "career summary": "summary",
    "objective": "summary",
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
    "relevant work experience": "experience",
    "other work experience": "experience",
    "relevant experience": "experience",
    "additional work experience": "experience",
    "prior work experience": "experience",
    # Recognized so their content doesn't bleed into a real section, but the
    # standard output template has no slot for them — content here is dropped.
    "honors & awards": "ignored",
    "honors and awards": "ignored",
    "awards": "ignored",
    "professional memberships": "ignored",
    "memberships": "ignored",
    "affiliations": "ignored",
    "professional affiliations": "ignored",
    "community advocacy": "ignored",
    "volunteer experience": "ignored",
    "publications": "ignored",
    "references": "ignored",
    "leadership & core qualifications": "ignored",
    "leadership and core qualifications": "ignored",
    "core qualifications": "ignored",
    "qualifications": "ignored",
    "skills": "ignored",
    "key skills": "ignored",
    "clinical rotations": "ignored",
    "clinical rotation": "ignored",
}
_SQUASHED_ALIASES = {re.sub(r"[^a-z0-9]", "", k): v for k, v in SECTION_ALIASES.items()}

LABEL_ALIASES = {
    "emr": "emr",
    "ehr": "emr",
    "facility type": "facility_type",
    "type of facility": "facility_type",
    "trauma level": "trauma_level",
    "trauma designation": "trauma_level",
    "bed size": "bed_size",
    "associated hospital bed size": "bed_size",
    "patient ratio": "patient_ratio",
}

# An actual month-name alternation, not a generic 3-9 letter character class —
# the latter also matches things like "...etologist 2010" (the tail of
# "Cosmetologist" is coincidentally 9 letters) as if it were a month name.
_MONTH_NAMES = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?"
    r"|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
DATE_RANGE_RE = re.compile(
    rf"(?P<start>{_MONTH_NAMES}\.?,?\s*\d{{4}}|Present|Current)\s*(?:[–—-]|\bto\b)\s*(?P<end>{_MONTH_NAMES}\.?,?\s*\d{{4}}|Present|Current)",
    re.IGNORECASE,
)
_MONTH_YEAR_RE = re.compile(rf"^({_MONTH_NAMES})\.?,?\s*(\d{{4}})$", re.IGNORECASE)
_SINGLE_DATE_RE = re.compile(rf"({_MONTH_NAMES}\.?,?\s*\d{{4}})\s*$", re.IGNORECASE)
_BARE_YEAR_RE = re.compile(r"^\d{4}$")
# A bare year with no month at all, trailing some other text on the same line
# (e.g. "Licensed Cosmetologist 2010") — only used as a fallback in education
# parsing, after month-based date patterns have already had a chance to match.
_TRAILING_BARE_YEAR_RE = re.compile(r"\s(\d{4})\s*$")
FACILITY_TAIL_RE = re.compile(
    r"^(?P<name>.+)\s+[–—-]\s+(?P<city>[A-Za-z][A-Za-z .'&]*),\s*(?P<state>[A-Z]{2})$"
)
# Like FACILITY_TAIL_RE's comma form, but tolerates trailing text after the
# state code (e.g. "ECPI University, Charlotte, NC ADN Program") instead of
# requiring the state to end the line — some resumes tack a program/track
# name on after the location with no delimiter.
_SCHOOL_TAIL_LOOSE_RE = re.compile(
    r"^(?P<name>.+?),\s*(?P<city>[A-Za-z][A-Za-z .'&]*),\s*(?P<state>[A-Z]{2})\b\s*(?P<rest>.*)$"
)
LABEL_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z /&]{1,40}):\s*(.+)$")
ID_RE = re.compile(r"#\s*([A-Za-z0-9\-]+)")


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


# Job-board exports (Monster, CareerBuilder, etc.) sometimes inject their own
# contact-relay boilerplate into the plain-text body of a downloaded resume —
# it's real text in the file, but it's platform noise, not resume content, and
# without filtering it lands wherever it happens to fall (a fake certification,
# a fake job-detail line, whatever section is open at that point in the file).
_PLATFORM_NOISE_RE = re.compile(r"you can contact this candidate at", re.IGNORECASE)


def _lines(resume_text: str):
    return [_clean(line) for line in resume_text.splitlines() if not _PLATFORM_NOISE_RE.search(line)]


def _section_key(line: str):
    normalized = line.rstrip(":").strip().lower()
    key = SECTION_ALIASES.get(normalized)
    if key:
        return key
    # OCR and glued-header templates sometimes drop the spaces/ampersands
    # entirely (e.g. "LICENSURE&CERTIFICATIONS") — compare with those stripped too.
    return _SQUASHED_ALIASES.get(re.sub(r"[^a-z0-9]", "", normalized))


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
        for segment in _HEADER_SEP_RE.split(line):
            segment = _clean(segment)
            if not segment:
                continue
            email_match = EMAIL_RE.search(segment)
            phone_match = PHONE_RE.search(segment)
            if email_match:
                header["email"] = header["email"] or email_match.group(0).replace(" ", "")
            elif phone_match:
                header["phone"] = header["phone"] or phone_match.group(0)
            elif ADDRESS_RE.search(segment):
                header["permanent_address"] = header["permanent_address"] or segment
            elif not header["professional_headline"]:
                header["professional_headline"] = segment
    return header


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _parse_bulleted_list(lines):
    content = [l for l in lines if l]
    if not any(BULLET_RE.match(l) for l in content):
        # No recognizable bullet marker anywhere — this is prose, not a list with an
        # unusual glyph. Split on sentence boundaries so it still becomes one bullet
        # per sentence rather than one run-on paragraph; this only chooses where to
        # break, it doesn't add, remove, or reword anything.
        joined = _clean(" ".join(content))
        return [s.strip() for s in _SENTENCE_SPLIT_RE.split(joined) if s.strip()] if joined else []

    items = []
    for line in content:
        if BULLET_RE.match(line):
            items.append(BULLET_RE.sub("", line))
        elif items:
            items[-1] += " " + line
    return items


def _split_school_location(text: str):
    """Like _split_facility_city_state, but also tolerates trailing text after
    the state code (e.g. "ECPI University, Charlotte, NC ADN Program") instead
    of requiring the state to end the line — some resumes tack a program/track
    name on after the location with no delimiter. Returns a 4th "extra" value
    (that trailing text, or "") so the caller can decide where it belongs."""
    school, city, state = _split_facility_city_state(text)
    if city and state:
        return school, city, state, ""

    loose = _SCHOOL_TAIL_LOOSE_RE.match(text)
    if loose:
        return _clean(loose.group("name")), _clean(loose.group("city")), loose.group("state"), _clean(loose.group("rest"))

    # No location at all (e.g. an online-only school) — the text may still end
    # in a dangling comma that was meant to introduce one, so strip it rather
    # than leaving it stuck to the end of the school name.
    return text.rstrip(" ,"), "", "", ""


def _parse_education(lines):
    """Handles a single "Degree – School, City, ST | Date" line, or a degree
    line and a school/location line as two separate lines (in either order,
    since some resumes put the date next to the degree and others next to the
    school) — and the case where one program has no separate degree line at
    all, just a school/location line with the program name tacked on after
    the state and a date of its own."""
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

        if _BARE_YEAR_RE.match(line):
            # Some templates put just the year on its own line, with no month —
            # attach it to whatever degree is pending rather than treating a bare
            # "2022" as its own degree/school entry.
            if pending_degree:
                pending_date = pending_date or line
            continue

        if "|" in line:
            flush_pending()
            rest, _, date = line.rpartition("|")
            rest, date = _clean(rest), _normalize_date(date)
            parts = re.split(r"\s{2,}|\s+[–—-]\s+", rest, maxsplit=1)
            degree = _clean(parts[0]) if parts else rest
            tail = _clean(parts[1]) if len(parts) > 1 else ""
            school, city, state, extra = _split_school_location(tail)
            location = f"{city}, {state}" if city and state else ""
            if extra:
                degree = f"{degree} – {extra}" if degree else extra
            entries.append({"degree": degree, "school": school, "location": location, "date": date})
            continue

        date_value, remainder, date_found = "", line, False
        range_match = DATE_RANGE_RE.search(line)
        if range_match:
            date_value = _normalize_date(range_match.group("end"))
            remainder = _clean(line[:range_match.start()] + " " + line[range_match.end():]).strip(" |,-–—")
            date_found = True
        else:
            single_match = _SINGLE_DATE_RE.search(line)
            if single_match:
                date_value = _normalize_date(single_match.group(1))
                remainder = _clean(line[:single_match.start()])
                date_found = True
            else:
                bare_match = _TRAILING_BARE_YEAR_RE.search(line)
                if bare_match:
                    date_value = bare_match.group(1)
                    remainder = _clean(line[:bare_match.start()])
                    date_found = True

        school, city, state, extra = _split_school_location(remainder)

        if city and state:
            if pending_degree and extra:
                degree = f"{pending_degree} – {extra}"
            else:
                degree = pending_degree or extra
            entries.append({
                "degree": degree, "school": school, "location": f"{city}, {state}",
                "date": date_value if date_found else pending_date,
            })
            pending_degree, pending_date = None, ""
        elif date_found:
            flush_pending()
            pending_degree, pending_date = remainder, date_value
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

        pipe_segments = [s for s in line.split("|")]
        if re.search(r"Expires:", line, re.IGNORECASE):
            entries = [_parse_single_cert_line(line)]
        elif len(pipe_segments) > 1 and not any(_SINGLE_DATE_RE.search(s) for s in pipe_segments):
            # Several short cert names sharing one line with "|" between them and no
            # date anywhere (e.g. "ACLS | BLS | PALS | NRP") — not a single cert whose
            # name and expiry happen to be pipe-separated.
            entries = [{"name": _clean(s), "id": "", "expires": ""} for s in pipe_segments if _clean(s)]
        elif "|" in line:
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
        "emr": NOT_LISTED, "facility_type": NOT_LISTED, "trauma_level": NOT_LISTED,
        "bed_size": NOT_LISTED, "patient_ratio": NOT_LISTED,
        "additional_details": [], "duties": [],
    }


def _split_facility_city_state(text: str):
    """Facility/location line comes in at least three conventions across resumes:
    "Name – City, ST" (dash-separated), "Name, City, ST" (comma-separated), or
    "Name; City, ST" (semicolon-separated). Try the least ambiguous form first."""
    tail_match = FACILITY_TAIL_RE.match(text)
    if tail_match:
        return _clean(tail_match.group("name")), _clean(tail_match.group("city")), tail_match.group("state")

    if ";" in text:
        name, _, tail = text.rpartition(";")
        tail_parts = [p.strip() for p in tail.split(",")]
        if len(tail_parts) == 2 and re.match(r"^[A-Z]{2}$", tail_parts[-1]):
            return _clean(name), tail_parts[0], tail_parts[1]

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
    if not text or len(text.split()) > 12 or text.endswith((".", ":")):
        return False
    if "=" in text or re.search(r"\d+\s*(hours?|weeks?)\b", text, re.IGNORECASE):
        return False
    return True


def _is_real_job(job: dict) -> bool:
    return bool(job["facility_name"] or job["job_title"] or job["start_date"])


def _parse_experience(lines):
    jobs = []
    # Starts as a placeholder so a title line that appears before the very
    # first job's date-anchor (rather than after it) has somewhere to land —
    # it's discarded at the end if it never picks up any real content.
    current = _new_job()
    need_title = False
    need_facility = False

    for line in lines:
        if not line:
            continue

        is_bullet = bool(BULLET_RE.match(line))
        label_match = LABEL_LINE_RE.match(line) if not is_bullet else None
        date_start, date_end, remainder = (None, None, line) if label_match else _strip_date(line)

        if date_start:
            closing = current
            current = _new_job()
            current["start_date"], current["end_date"] = date_start, date_end

            name, city, state = _split_facility_city_state(remainder) if remainder else ("", "", "")
            if city and state:
                current["facility_name"], current["city"], current["state"] = name, city, state
            elif remainder:
                current["job_title"] = remainder

            # The title may have landed on the closing job's last duty line,
            # if it appeared with no marker to tell it apart from a duty.
            if not current["job_title"] and closing["duties"] and _looks_like_title(closing["duties"][-1]):
                current["job_title"] = closing["duties"].pop()

            need_title = not current["job_title"]
            need_facility = not current["facility_name"]
            if _is_real_job(closing):
                jobs.append(closing)
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

        # A duty that word-wraps across two lines in the source (common once a
        # bullet runs longer than one line) has no bullet marker on its second
        # line — that's what tells it apart from a genuinely new duty, so it
        # gets appended to the previous one instead of starting a new entry.
        if is_bullet or not current["duties"]:
            current["duties"].append(BULLET_RE.sub("", line))
        else:
            current["duties"][-1] += " " + line

    if _is_real_job(current):
        jobs.append(current)

    return jobs


def _strip_running_header(lines, header):
    """A scanned multi-page resume's name/title/contact block often repeats verbatim
    at the top of every page — without a real page break to signal that, it would
    otherwise get swept into whatever section/job happens to be open at that point."""
    known = set()
    if header["full_name"]:
        known.add(header["full_name"].lower())
        if header["credentials_suffix"]:
            known.add(f"{header['full_name']}, {header['credentials_suffix']}".lower())
    if header["professional_headline"]:
        known.add(header["professional_headline"].lower())

    phone_digits = re.sub(r"\D", "", header["phone"] or "")
    email = (header["email"] or "").lower()

    filtered = []
    for line in lines:
        low = line.lower()
        if low in known:
            continue
        if phone_digits and len(phone_digits) >= 7 and re.sub(r"\D", "", line) == phone_digits:
            continue
        if email and email in low:
            continue
        filtered.append(line)
    return filtered


_MONTH_NUM = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}


def _date_sort_key(date_str: str):
    """Sort key for reverse-chronological ordering. "Present"/unparseable dates
    sort first/last respectively via a stable fallback rather than raising."""
    if not date_str:
        return (0, 0)
    if date_str.strip().lower() in ("present", "current"):
        return (9999, 12)
    match = _MONTH_YEAR_RE.match(date_str.replace(",", ""))
    if match:
        month, year = match.groups()
        return (int(year), _MONTH_NUM.get(month[:3].capitalize(), 0))
    return (0, 0)


def extract_structured_resume_rightsourcing_deterministic(resume_text: str) -> dict:
    """Parse a resume that already follows the HonorVet labeled-field convention
    (section headers ending in ':', per-job 'Label: Value' lines, bulleted lists)
    into the standard structure — no AI calls, no inference beyond literal parsing."""
    lines = _lines(resume_text)

    first_section_idx = next((i for i, l in enumerate(lines) if _section_key(l)), len(lines))
    result = _parse_header(lines[:first_section_idx])
    result.update({
        "professional_summary": [], "education": [],
        "licenses": [], "certifications": [], "experience": [],
    })

    remaining_lines = _strip_running_header(lines[first_section_idx:], result)

    section = None
    section_lines = []
    certifications_only_lines = []

    def flush(sec, sec_lines):
        if sec == "summary":
            result["professional_summary"] = _parse_bulleted_list(sec_lines)
        elif sec == "education":
            result["education"] = _parse_education(sec_lines)
        elif sec == "licenses_certs":
            licenses, certifications = _parse_licenses_certs(sec_lines)
            result["licenses"].extend(licenses)
            result["certifications"].extend(certifications)
        elif sec == "certifications_only":
            certifications_only_lines.extend(sec_lines)
        elif sec == "experience":
            # A resume can split employment history across more than one
            # section header (e.g. "Relevant Work Experience" + "Other Work
            # Experience") — accumulate rather than let the second one
            # silently overwrite the first.
            result["experience"].extend(_parse_experience(sec_lines))

    for line in remaining_lines:
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

    result["experience"].sort(key=lambda j: _date_sort_key(j.get("start_date", "")), reverse=True)
    result["education"].sort(key=lambda e: _date_sort_key(e.get("date", "")), reverse=True)

    return result
