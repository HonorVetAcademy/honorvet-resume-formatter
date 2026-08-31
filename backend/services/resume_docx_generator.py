import os
import re
from datetime import datetime

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")


def _add_run_with_bold_markers(paragraph, text: str, base_bold=False, size=10.5):
    """Add text to a paragraph, honoring **bold** markers left over from AI-authored summary bullets."""
    pos = 0
    for match in BOLD_PATTERN.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos:match.start()])
            run.bold = base_bold
            run.font.size = Pt(size)
        run = paragraph.add_run(match.group(1))
        run.bold = True
        run.font.size = Pt(size)
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        run.bold = base_bold
        run.font.size = Pt(size)


def _section_header(doc, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.underline = True
    run.font.size = Pt(11)
    return p


def _bullet(doc, text: str, indent=False):
    p = doc.add_paragraph(style="List Bullet")
    if indent:
        p.paragraph_format.left_indent = Pt(28)
    p.paragraph_format.space_after = Pt(3)
    _add_run_with_bold_markers(p, text)
    return p


def _plain_line(doc, label: str, value):
    if value in (None, "", "null"):
        return
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    run = p.add_run(f"{label}: ")
    run.font.size = Pt(10.5)
    run2 = p.add_run(str(value))
    run2.font.size = Pt(10.5)


def generate_formatted_resume_docx(resume: dict, output_dir: str) -> str:
    """Render a structured, facility-enriched resume into a .docx matching HonorVet standard formatting."""
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

    contact_bits = [b for b in [resume.get("phone"), resume.get("email"), resume.get("location")] if b]
    for bit in contact_bits:
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
            run = p.add_run(edu.get("degree", ""))
            run.bold = True
            run.font.size = Pt(10.5)
            tail = " ".join(x for x in [edu.get("school", ""), "–", edu.get("location", "")] if x)
            r2 = p.add_run(f" {tail}")
            r2.font.size = Pt(10.5)
            if edu.get("date"):
                r3 = p.add_run(f" | {edu['date']}")
                r3.bold = True
                r3.font.size = Pt(10.5)

    # Licensure & Certifications
    if resume.get("certifications"):
        _section_header(doc, "Licensure & Certifications:")
        for cert in resume["certifications"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            label = cert.get("name", "")
            if cert.get("issuer"):
                label += f" – {cert['issuer']}"
            run = p.add_run(label)
            run.font.size = Pt(10.5)
            extras = []
            if cert.get("id"):
                extras.append(f"# {cert['id']}")
            if cert.get("expires"):
                extras.append(f"Expires: {cert['expires']}")
            if extras:
                r2 = p.add_run(" | " + " | ".join(extras))
                r2.bold = True
                r2.font.size = Pt(10.5)

    # Professional Experience
    if resume.get("experience"):
        _section_header(doc, "Professional Experience:")
        for job in resume["experience"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(0)
            facility_line = job.get("facility_name", "")
            loc = ", ".join(x for x in [job.get("city", ""), job.get("state", "")] if x)
            if loc:
                facility_line += f", {loc}"
            run = p.add_run(facility_line)
            run.bold = True
            run.font.size = Pt(10.5)
            dates = f"{job.get('start_date', '')} – {job.get('end_date', '')}"
            r2 = p.add_run(f" | {dates}")
            r2.bold = True
            r2.font.size = Pt(10.5)

            if job.get("job_title"):
                tp = doc.add_paragraph()
                tp.paragraph_format.space_after = Pt(2)
                tr = tp.add_run(job["job_title"])
                tr.bold = True
                tr.font.size = Pt(10.5)

            _plain_line(doc, "Type of Facility", job.get("type_of_facility"))
            _plain_line(doc, "Trauma Level", job.get("trauma_level"))
            _plain_line(doc, "Bed Size", job.get("bed_size"))
            _plain_line(doc, "Patient Ratio", job.get("patient_ratio"))
            _plain_line(doc, "Charting System", job.get("emr_system"))

            for duty in job.get("duties", []):
                _bullet(doc, duty, indent=True)

    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", resume.get("full_name", "candidate"))
    filename = f"{safe_name}_HonorVet_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
    filepath = os.path.join(output_dir, filename)
    doc.save(filepath)
    return filepath
