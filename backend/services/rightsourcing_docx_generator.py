import os
import re
from datetime import datetime

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from services.resume_docx_generator import _section_header, _bullet, _plain_line

NOT_LISTED = "[TO BE CONFIRMED]"


def _line_or_placeholder(doc, label: str, value):
    """Always render a labeled line, defaulting to the placeholder rather than skipping it."""
    _plain_line(doc, label, value if value else NOT_LISTED)


def _license_line(doc, entry: dict, has_license_number: bool):
    """Licenses carry a license number; certifications (BLS, ACLS, etc.) structurally
    never do, so that field is only shown for licenses — never as a placeholder."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(entry.get("name", ""))
    run.bold = True
    run.font.size = Pt(10.5)
    if has_license_number:
        r2 = p.add_run(f" # {entry.get('id') or NOT_LISTED}")
        r2.font.size = Pt(10.5)
    r3 = p.add_run("| ")
    r3.font.size = Pt(10.5)
    r4 = p.add_run(f"Expires: {entry.get('expires') or NOT_LISTED}")
    r4.bold = True
    r4.font.size = Pt(10.5)


def generate_rightsourcing_docx(resume: dict, output_dir: str) -> str:
    """Render a structured resume into the HonorVet standard format (matching the
    reference "Resume 16" example): header, summary, education, licensure &
    certifications, professional experience. Transcribes only what's present in
    `resume` — missing per-job metadata is shown as a "[TO BE CONFIRMED]"
    placeholder rather than omitted."""
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

    # Candidate Header — name, then phone/email/address each on their own centered line
    name_line = resume.get("full_name", "")
    if resume.get("credentials_suffix"):
        name_line += f", {resume['credentials_suffix']}"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(name_line)
    run.bold = True
    run.font.size = Pt(15)

    for bit in [resume.get("phone"), resume.get("email"), resume.get("permanent_address")]:
        if not bit:
            continue
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_after = Pt(0)
        r = cp.add_run(bit)
        r.font.size = Pt(10.5)

    # Professional Summary
    if resume.get("professional_summary"):
        _section_header(doc, "Professional Summary:")
        for bullet in resume["professional_summary"]:
            _bullet(doc, bullet)

    # Education
    if resume.get("education"):
        _section_header(doc, "Education:")
        for edu in resume["education"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            dr = p.add_run(edu.get("degree", ""))
            dr.bold = True
            dr.font.size = Pt(10.5)

            tail = edu.get("school", "")
            if edu.get("location"):
                tail += f" – {edu['location']}" if tail else edu["location"]
            mr = p.add_run(f" {tail}" if tail else "")
            mr.font.size = Pt(10.5)

            r3 = p.add_run("| ")
            r3.font.size = Pt(10.5)
            r4 = p.add_run(edu.get("date", ""))
            r4.bold = True
            r4.font.size = Pt(10.5)

    # Licensure & Certifications
    if resume.get("licenses") or resume.get("certifications"):
        _section_header(doc, "Licensure & Certifications:")
        for lic in resume.get("licenses", []):
            _license_line(doc, lic, has_license_number=True)
        for cert in resume.get("certifications", []):
            _license_line(doc, cert, has_license_number=False)

    # Professional Experience
    if resume.get("experience"):
        _section_header(doc, "Professional Experience:")
        for job in resume["experience"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(0)
            loc = ", ".join(x for x in [job.get("city", ""), job.get("state", "")] if x)
            facility_line = job.get("facility_name", "")
            run = p.add_run(facility_line)
            run.bold = True
            run.font.size = Pt(10.5)
            if loc:
                lr = p.add_run(f", {loc}")
                lr.font.size = Pt(10.5)
            r3 = p.add_run("| ")
            r3.font.size = Pt(10.5)
            r4 = p.add_run(f"{job.get('start_date', '')} – {job.get('end_date', '')}")
            r4.bold = True
            r4.font.size = Pt(10.5)

            tp = doc.add_paragraph()
            tp.paragraph_format.space_after = Pt(2)
            tr = tp.add_run(job.get("job_title") or NOT_LISTED)
            tr.bold = True
            tr.font.size = Pt(10.5)

            _line_or_placeholder(doc, "Type of Facility", job.get("facility_type"))
            _line_or_placeholder(doc, "Trauma Level", job.get("trauma_level"))
            _line_or_placeholder(doc, "Bed Size", job.get("bed_size"))
            _line_or_placeholder(doc, "Patient Ratio", job.get("patient_ratio"))
            _line_or_placeholder(doc, "Charting System", job.get("emr"))

            for extra in job.get("additional_details", []):
                if extra.get("label") and extra.get("value"):
                    _plain_line(doc, extra["label"], extra["value"])

            for duty in job.get("duties", []):
                _bullet(doc, duty)

    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", resume.get("full_name", "candidate"))
    filename = f"{safe_name}_HonorVet_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
    filepath = os.path.join(output_dir, filename)
    doc.save(filepath)
    return filepath
