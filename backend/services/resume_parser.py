import base64
import os
import anthropic
import PyPDF2
import docx
from pathlib import Path

_claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text.strip()


def extract_text_from_scanned_pdf(file_path: str) -> str:
    """Fallback for scanned/image-based PDFs with no embedded text layer — Claude reads the document directly."""
    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")

    message = _claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
                {"type": "text", "text": "Extract all text from this resume document, in reading order. Return only the extracted text, no commentary."},
            ],
        }],
    )
    return message.content[0].text.strip()


_IMAGE_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def extract_text_from_image(file_path: str) -> str:
    """Extract text from a photo/screenshot of a resume via Claude's vision."""
    ext = Path(file_path).suffix.lower()
    media_type = _IMAGE_MEDIA_TYPES[ext]
    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")

    message = _claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                {"type": "text", "text": "Extract all text from this resume image, in reading order. Return only the extracted text, no commentary."},
            ],
        }],
    )
    return message.content[0].text.strip()


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a Word document."""
    doc = docx.Document(file_path)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)


def extract_resume_text(file_path: str) -> str:
    """Extract text from a resume file (PDF or DOCX)."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
        if not text.strip():
            text = extract_text_from_scanned_pdf(file_path)
        return text
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext in _IMAGE_MEDIA_TYPES:
        return extract_text_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
