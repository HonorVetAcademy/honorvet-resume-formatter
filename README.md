# HonorVet Resume Formatter

A local tool with two formatting modes:

- **HonorVet Standard** — reformats a raw resume into HonorVet's standard layout, with facility type, trauma level, bed size, and EMR/charting system automatically researched for each employer.
- **RightSourcing** — formats a resume for RightSourcing/Magnit client submission (intro table, Skills section, Position Type/Agency Name placeholders) and runs it against RightSourcing's pre-submission checklist before you download it, flagging missing fields, expired licenses, future/typo'd dates, and unexplained employment gaps.

**Live app:** https://honorvetacademy.github.io/honorvet-resume-formatter/ (frontend on GitHub Pages, backend on Render — the Anthropic API key lives only as a server-side environment variable on Render, never in the repo or the browser)

Open to anyone with the link — no login. Since usage is billed to HonorVet's Anthropic account, don't share the link outside the org.

## How it works

1. Upload a resume (PDF, DOCX, or TXT) on either tab
2. Claude parses it into structured fields, preserving your original wording
3. For each employer, Claude researches the facility on the web (type of facility, trauma level, bed size/EMR) — returning `null` rather than guessing when it can't verify a fact, with a confidence rating and source links so you can spot-check before sending
4. **RightSourcing tab only:** the parsed resume is run against the client's submission checklist (name format, contact info present, required fields per job, dates in the past, license not expired, employment gaps explained, etc.) and results are shown before download
5. A `.docx` is generated in the appropriate format and downloads

Facility research confidence + sources are always shown in the UI — AI-researched facts about bed counts/EMR vendors can be wrong or stale, so always spot-check before sending to a client.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python) |
| AI | Claude (`claude-sonnet-4-6`) via Anthropic SDK, with the hosted `web_search` tool for facility research |
| Document generation | python-docx |

## Deployment

- **Backend** deploys to [Render](https://render.com) from `render.yaml` — a FastAPI web service. `ANTHROPIC_API_KEY` is set as a Render environment variable (never committed).
- **Frontend** builds as a static Next.js export (`output: 'export'`) and deploys to GitHub Pages via `.github/workflows/deploy.yml` on every push to `master`. `NEXT_PUBLIC_API_URL` is baked in at build time from the `NEXT_PUBLIC_API_URL` repository variable, pointing at the Render backend's URL.

## Local development

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

Open: http://localhost:3000 (talks to the local backend, not the deployed one)

## Architecture

```
honorvet-resume-formatter/
├── backend/
│   ├── main.py                            # FastAPI app: /api/format, /api/rightsourcing/format, /api/download
│   └── services/
│       ├── resume_parser.py               # PDF/DOCX/TXT text extraction
│       ├── resume_formatter_service.py    # HonorVet Standard: resume parsing + facility web research
│       ├── resume_docx_generator.py       # Renders HonorVet Standard .docx (also provides shared docx helpers)
│       ├── rightsourcing_service.py       # RightSourcing: resume parsing + submission checklist
│       └── rightsourcing_docx_generator.py # Renders RightSourcing submission .docx
└── frontend/
    ├── app/page.tsx                       # Tab shell (HonorVet Standard / RightSourcing)
    ├── components/
    │   ├── HonorVetTab.tsx                # HonorVet Standard upload UI + facility research preview
    │   └── RightSourcingTab.tsx           # RightSourcing upload UI + checklist + facility research preview
    └── lib/api.ts                         # Typed API client
```

## Notes on the RightSourcing checklist

The checklist covers everything derivable from the resume itself: name format, contact info, per-job required fields (facility, dates, title, EMR, Trauma Level, Facility Type), dates that appear to be in the future (likely typos), expired licenses, and unexplained employment gaps — plus a few softer checks (summary quality, consistency of hospital settings, whether gaps are explained in the resume text) reviewed by Claude.

**Position Type** and **Agency Name** aren't present in a candidate's own resume — the generated document leaves placeholders for the recruiter to fill in per submission.

Checklist items that need separate documents — available interview times, shift preference, or matching dates against a reference-check sheet — aren't covered by this tool and should still be checked manually.
