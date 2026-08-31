# HonorVet Resume Formatter

Upload any raw resume and get back a resume reformatted into HonorVet standard formatting — with facility type, trauma level, bed size, and EMR/charting system automatically researched for each employer.

## How it works

1. Upload a resume (PDF, DOCX, or TXT)
2. Claude parses it into structured fields, preserving the candidate's original wording
3. For each employer, Claude researches the facility on the web (type of facility, trauma level, bed size, EMR system) — returning `null` rather than guessing when it can't verify a fact, with a confidence rating and source links
4. A `.docx` is generated in HonorVet standard formatting: centered header, Professional Summary, Education, Licensure & Certifications, then Professional Experience with each job listing Type of Facility / Trauma Level / Bed Size / Patient Ratio / Charting System followed by duty bullets

Facility research is surfaced in the UI with confidence + sources before download, since AI-researched facts about bed counts/EMR vendors can be wrong or stale — always spot-check before sending to a client.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python) |
| AI | Claude (`claude-sonnet-4-6`) via Anthropic SDK, with the hosted `web_search` tool for facility research |
| Document generation | python-docx |

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- An [Anthropic API key](https://console.anthropic.com) with web search enabled

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
cp .env.example .env         # then fill in ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:3000

## Architecture

```
honorvet-resume-formatter/
├── backend/
│   ├── main.py                        # FastAPI app + /api/format, /api/download endpoints
│   └── services/
│       ├── resume_parser.py           # PDF/DOCX/TXT text extraction
│       ├── resume_formatter_service.py  # Claude resume parsing + facility web research
│       └── resume_docx_generator.py   # Renders the structured resume into HonorVet-formatted .docx
└── frontend/
    ├── app/page.tsx                   # Upload UI, progress states, facility research preview
    └── lib/api.ts                     # Typed API client
```
