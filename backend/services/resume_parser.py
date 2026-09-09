import PyPDF2
import docx
from pathlib import Path

_IMAGE_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text.strip()


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a Word document."""
    doc = docx.Document(file_path)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)


def extract_resume_text(file_path: str) -> str:
    """Extract text from a resume file (PDF or DOCX). Requires a real text layer —
    there's no OCR/vision fallback, so scanned PDFs and image files aren't supported."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
        if not text.strip():
            raise ValueError("This PDF has no extractable text layer (it looks scanned/image-based). Upload a text-based PDF or DOCX instead.")
        return text
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext in _IMAGE_MEDIA_TYPES:
        raise ValueError("Image files aren't supported. Upload a text-based PDF or DOCX instead.")
    else:
        raise ValueError(f"Unsupported file type: {ext}")
