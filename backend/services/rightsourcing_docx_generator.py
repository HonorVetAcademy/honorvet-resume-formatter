import os
import re
from datetime import datetime

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from services.resume_docx_generator import _section_header, _bullet, _plain_line

NOT_LISTED = "Not Listed"


def _line_or_not_listed(doc, label: str, value):
    """Always render a labeled line, defaulting to 'Not Listed' rather than skipping it."""
    _plain_line(doc, label, value if value else NOT_LISTED)


def _license_line(doc, entry: dict):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(entry.get("name", ""))
    run.font.size = Pt(10.5)
    extras = []
    if entry.get("id"):
        extras.append(f"#{entry['id']}")
    if entry.get("expires"):
        extras.append(f"Expires – {entry['expires']}")
    if extras:
        r2 = p.add_run(" " + " ".join(extras))
        r2.bold = True
        r2.font.size = Pt(10.5)


def generate_rightsourcing_docx(resume: dict, output_dir: str) -> str:
    """Render a structured resume into the HonorVet standard format: header, summary,
    core qualifications, education, licensure & certification, professional experience.
    Transcribes only what's present in `resume` — missing job metadata is shown as
    "Not Listed" rather than omitted."""
    os.makedirs(output_dir, exist_ok=True)
    doc = Document()

    for section in doc.sections:
        section.top_margin = Pt(50)
        section.bottom_margin = Pt(50)
        section.left_margin = Pt(60)
        section.right_margin = Pt(60)

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    # Header
    name_line = resume.get("full_name", "")
    if resume.get("credentials_suffix"):
        name_line += f", {resume['credentials_suffix']}"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(name_line)
    run.bold = True
    run.font.size = Pt(15)

    if resume.get("professional_headline"):
        hp = doc.add_paragraph()
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        hp.paragraph_format.space_after = Pt(0)
        hr = hp.add_run(resume["professional_headline"])
        hr.italic = True
        hr.font.size = Pt(11)

    contact_bits = [resume.get("permanent_address"), resume.get("phone")]
    for bit in contact_bits:
        if not bit:
            continue
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_after = Pt(0)
        r = cp.add_run(bit)
        r.font.size = Pt(10.5)

    if resume.get("email"):
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_after = Pt(0)
        r = cp.add_run(f"You can contact this candidate at: {resume['email']}")
        r.font.size = Pt(10.5)

    # Professional Summary
    if resume.get("professional_summary"):
        _section_header(doc, "Professional Summary:")
        for bullet in resume["professional_summary"]:
            _bullet(doc, bullet)

    # Leadership & Core Qualifications
    if resume.get("core_qualifications"):
        _section_header(doc, "Leadership & Core Qualifications:")
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(", ".join(resume["core_qualifications"]))
        run.font.size = Pt(10.5)

    # Education
    if resume.get("education"):
        _section_header(doc, "Education:")
        for edu in resume["education"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            tail = ", ".join(x for x in [edu.get("school", ""), edu.get("location", "")] if x)
            parts = [edu.get("degree", ""), tail, edu.get("date", "")]
            run = p.add_run(" | ".join(x for x in parts if x))
            run.font.size = Pt(10.5)

    # Licensure & Certification
    if resume.get("licenses"):
        _section_header(doc, "Licensure & Certification:")
        for lic in resume["licenses"]:
            _license_line(doc, lic)

    # Certifications
    if resume.get("certifications"):
        _section_header(doc, "Certifications:")
        for cert in resume["certifications"]:
            _license_line(doc, cert)

    # Professional Experience
    if resume.get("experience"):
        _section_header(doc, "Professional Experience:")
        for job in resume["experience"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(0)
            loc = ", ".join(x for x in [job.get("city", ""), job.get("state", "")] if x)
            facility_line = job.get("facility_name", "")
            if loc:
                facility_line += f" | {loc}"
            run = p.add_run(facility_line)
            run.bold = True
            run.font.size = Pt(10.5)
            dates = f"{job.get('start_date', '')} – {job.get('end_date', '')}"
            r2 = p.add_run(f" | {dates}")
            r2.bold = True
            r2.font.size = Pt(10.5)

            _line_or_not_listed(doc, "a. Job Title", job.get("job_title"))
            _line_or_not_listed(doc, "b. EMR", job.get("emr"))
            _line_or_not_listed(doc, "c. Position Type", job.get("position_type"))
            _line_or_not_listed(doc, "d. Agency Name", job.get("agency_name"))
            _line_or_not_listed(doc, "e. Trauma Level", job.get("trauma_level"))
            _line_or_not_listed(doc, "f. Facility Type", job.get("facility_type"))

            for duty in job.get("duties", []):
                _bullet(doc, duty)

    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", resume.get("full_name", "candidate"))
    filename = f"{safe_name}_HonorVet_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
    filepath = os.path.join(output_dir, filename)
    doc.save(filepath)
    return filepath
