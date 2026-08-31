from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import os
import shutil
import uuid

load_dotenv()

from services.resume_parser import extract_resume_text
from services.resume_formatter_service import (
    extract_structured_resume,
    research_all_facilities,
    build_formatted_resume,
)
from services.resume_docx_generator import generate_formatted_resume_docx

app = FastAPI(
    title="HonorVet Resume Formatter API",
    description="Reformat any resume into HonorVet standard formatting, with AI-researched facility type, bed size, and EMR system.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
INBOX_DIR = os.path.join(UPLOAD_DIR, "inbox")
OUTPUT_DIR = os.path.join(UPLOAD_DIR, "formatted_resumes")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/format")
async def format_resume(resume: UploadFile = File(...)):
    """Parse a raw resume, research each employer's facility profile, and produce a HonorVet-standard formatted resume."""
    os.makedirs(INBOX_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{resume.filename.replace(' ', '_')}"
    file_path = os.path.join(INBOX_DIR, safe_name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(resume.file, f)

    try:
        resume_text = extract_resume_text(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read resume file: {e}")

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="No readable text found in the uploaded resume.")

    try:
        structured = extract_structured_resume(resume_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to parse resume content: {e}")

    facility_research = research_all_facilities(structured.get("experience", []))
    formatted = build_formatted_resume(structured, facility_research)

    try:
        docx_path = generate_formatted_resume_docx(formatted, OUTPUT_DIR)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate formatted document: {e}")

    return {
        "resume": formatted,
        "download_filename": os.path.basename(docx_path),
    }


@app.get("/api/download/{filename}")
def download_formatted_resume(filename: str):
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath) or not os.path.abspath(filepath).startswith(os.path.abspath(OUTPUT_DIR)):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
