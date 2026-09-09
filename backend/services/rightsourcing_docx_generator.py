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
    run.font.size = Pt(10.5)
    tail = f" | License Number: {entry.get('id') or NOT_LISTED} | Expiry: {entry.get('expires') or NOT_LISTED}" \
        if has_license_number else f" | Expiry: {entry.get('expires') or NOT_LISTED}"
    r2 = p.add_run(tail)
    r2.bold = True
    r2.font.size = Pt(10.5)


def generate_rightsourcing_docx(resume: dict, output_dir: str) -> str:
    """Render a structured resume into the HonorVet standard format: header, summary,
    education, licensure & certifications, professional experience. Transcribes only
    what's present in `resume` — missing per-job metadata is shown as a
    "[TO BE CONFIRMED]" placeholder rather than omitted."""
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

    # Candidate Header
    name_line = resume.get("full_name", "")
    if resume.get("credentials_suffix"):
        name_line += f", {resume['credentials_suffix']}"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(name_line)
    run.bold = True
    run.font.size = Pt(15)

    contact_line = " | ".join(x for x in [resume.get("permanent_address"), resume.get("phone"), resume.get("email")] if x)
    if contact_line:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_after = Pt(0)
        r = cp.add_run(contact_line)
        r.font.size = Pt(10.5)

    # Professional Summary
    if resume.get("professional_summary"):
        _section_header(doc, "Professional Summary")
        for bullet in resume["professional_summary"]:
            _bullet(doc, bullet)

    # Education
    if resume.get("education"):
        _section_header(doc, "Education")
        for edu in resume["education"]:
            dp = doc.add_paragraph()
            dp.paragraph_format.space_after = Pt(0)
            dr = dp.add_run(edu.get("degree", ""))
            dr.bold = True
            dr.font.size = Pt(10.5)

            tail = ", ".join(x for x in [edu.get("school", ""), edu.get("location", "")] if x)
            sp = doc.add_paragraph()
            sp.paragraph_format.space_after = Pt(4)
            sr = sp.add_run(" | ".join(x for x in [tail, edu.get("date", "")] if x))
            sr.font.size = Pt(10.5)

    # Licensure & Certifications
    if resume.get("licenses") or resume.get("certifications"):
        _section_header(doc, "Licensure & Certifications")
        for lic in resume.get("licenses", []):
            _license_line(doc, lic, has_license_number=True)
        for cert in resume.get("certifications", []):
            _license_line(doc, cert, has_license_number=False)

    # Professional Experience
    if resume.get("experience"):
        _section_header(doc, "Professional Experience")
        for job in resume["experience"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(0)
            loc = ", ".join(x for x in [job.get("city", ""), job.get("state", "")] if x)
            facility_line = job.get("facility_name", "")
            if loc:
                facility_line += f" - {loc}"
            run = p.add_run(facility_line)
            run.bold = True
            run.font.size = Pt(10.5)
            dates = f"{job.get('start_date', '')} – {job.get('end_date', '')}"
            r2 = p.add_run(f" | {dates}")
            r2.bold = True
            r2.font.size = Pt(10.5)

            tp = doc.add_paragraph()
            tp.paragraph_format.space_after = Pt(2)
            tr = tp.add_run(job.get("job_title") or NOT_LISTED)
            tr.italic = True
            tr.font.size = Pt(10.5)

            _line_or_placeholder(doc, "EMR", job.get("emr"))
            _line_or_placeholder(doc, "Facility Type", job.get("facility_type"))
            _line_or_placeholder(doc, "Trauma Level", job.get("trauma_level"))
            _line_or_placeholder(doc, "Bed Size", job.get("bed_size"))
            _line_or_placeholder(doc, "Patient Ratio", job.get("patient_ratio"))

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
