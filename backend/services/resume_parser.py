import gc
import logging
import numpy as np
import PyPDF2
import docx
import pymupdf as fitz
from pathlib import Path
from rapidocr_onnxruntime import RapidOCR

_IMAGE_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

# Two rounds of CPU/memory optimization didn't move Render's free-tier request
# failure point at all (~200-210s both times), pointing to a fixed platform
# timeout rather than something code efficiency can fix. At ~50s/page observed
# there, 3 pages leaves a real margin under that ceiling; a longer scan loses
# whatever's past page 3 rather than crashing and losing the whole document.
MAX_OCR_PAGES = 3

_ocr_engine = None


def _get_ocr_engine() -> RapidOCR:
    """Lazily construct the OCR engine — it loads ONNX models from disk, so building
    it once and reusing it is much cheaper than one per request."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text.strip()


def extract_text_from_scanned_pdf(file_path: str) -> str:
    """OCR fallback for PDFs with no embedded text layer (scanned/photographed pages).
    Fully local and offline — PyMuPDF rasterizes each page, RapidOCR (CPU-only ONNX
    models) reads the text. No external API calls.

    Renders at a deliberately modest 100 DPI and frees each page's image before
    moving to the next — this runs on a memory-constrained (512MB) host, and a
    multi-page scan at a higher DPI was enough to crash the whole process. Passes
    the raw pixel array straight to RapidOCR rather than round-tripping through
    PNG encode/decode, which cost real time and an extra full-image buffer for
    no benefit — RapidOCR would only decode it right back to an array anyway."""
    ocr = _get_ocr_engine()
    pages_text = []
    with fitz.open(file_path) as doc:
        if doc.page_count > MAX_OCR_PAGES:
            logging.warning(
                f"OCR: {file_path} has {doc.page_count} pages, only scanning the "
                f"first {MAX_OCR_PAGES} to stay under the host's request timeout."
            )
        for page in doc[:MAX_OCR_PAGES]:
            pix = page.get_pixmap(dpi=100)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            result, _ = ocr(arr)
            pix = None
            arr = None
            if result:
                pages_text.append("\n".join(line[1] for line in result))
            gc.collect()
    return "\n".join(pages_text).strip()


def extract_text_from_image(file_path: str) -> str:
    """OCR a photo/screenshot of a resume, fully local and offline."""
    result, _ = _get_ocr_engine()(file_path)
    return "\n".join(line[1] for line in result).strip() if result else ""


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a Word document."""
    doc = docx.Document(file_path)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)


def extract_resume_text(file_path: str) -> str:
    """Extract text from a resume file (PDF, DOCX, TXT, or image). Scanned PDFs and
    photos fall back to local OCR — no external API calls anywhere in this path."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
        if not text.strip():
            text = extract_text_from_scanned_pdf(file_path)
        if not text.strip():
            raise ValueError("Couldn't read any text from this PDF, even with OCR. It may be blank or too low-quality to scan.")
        return text
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext in _IMAGE_MEDIA_TYPES:
        text = extract_text_from_image(file_path)
        if not text.strip():
            raise ValueError("Couldn't read any text from this image, even with OCR.")
        return text
    else:
        raise ValueError(f"Unsupported file type: {ext}")
