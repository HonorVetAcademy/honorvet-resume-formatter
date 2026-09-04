import anthropic
import json
import os
import re

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


def _parse_json_response(text: str):
    """Extract a JSON object from a model response, tolerating commentary or code fences
    anywhere around it (models don't always follow "JSON only" instructions exactly)."""
    text = text.strip()

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    return json.loads(text)


def _extract_text_blocks(content) -> str:
    return "".join(block.text for block in content if block.type == "text")


def extract_structured_resume(resume_text: str) -> dict:
    """Parse raw resume text into structured fields for HonorVet standard formatting."""
    prompt = f"""You are a healthcare staffing resume formatter. Parse the resume below into structured JSON.

Preserve the candidate's own wording for the summary and duty bullets — clean up only grammar/spacing, do not invent or embellish content. Do not fabricate any facts not present in the source resume.

RESUME TEXT:
{resume_text}

Return a JSON object with this exact schema:
{{
  "full_name": "<name, no credentials>",
  "credentials_suffix": "<credentials after name if stated, e.g. 'BSN, RN, CNOR', else empty string>",
  "phone": "<phone number>",
  "email": "<email>",
  "location": "<City, State ZIP if available>",
  "professional_summary": ["<bullet 1>", "<bullet 2>", ...],
  "education": [{{"degree": "<degree>", "school": "<school name>", "location": "<city, state>", "date": "<date or date range>"}}],
  "certifications": [{{"name": "<certification name/abbreviation>", "issuer": "<issuing body>", "id": "<license/id number if stated, else empty>", "expires": "<expiration date if stated, else empty>"}}],
  "experience": [
    {{
      "facility_name": "<employer/facility name as written>",
      "city": "<city>",
      "state": "<state>",
      "start_date": "<start date, e.g. 'Jan 2025'>",
      "end_date": "<end date or 'Present'>",
      "job_title": "<job title>",
      "patient_ratio": "<patient ratio ONLY if explicitly stated in the resume, else empty string>",
      "duties": ["<duty bullet 1>", "<duty bullet 2>", ...]
    }}
  ]
}}

List experience most-recent-first. Return only valid JSON, no commentary."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    return _parse_json_response(message.content[0].text)


def research_facility(facility_name: str, city: str = "", state: str = "") -> dict:
    """Use Claude with web search to research a healthcare facility's profile."""
    location = f" in {city}, {state}" if city or state else ""
    prompt = f"""Research the healthcare facility "{facility_name}"{location}. Search the web for current, accurate, verifiable information about this specific facility.

Return a JSON object with exactly these fields:
{{
  "type_of_facility": "<e.g. 'Short-term acute care, Teaching/Academic Medical Center', 'Community Hospital', 'Critical Access Hospital', 'Long-term acute care', 'Rehabilitation Hospital', 'Skilled Nursing Facility' — or null if you cannot verify>",
  "trauma_level": "<e.g. 'Level I', 'Level II', 'Level III', 'Level IV', 'Not a designated trauma center' — or null if unknown/not applicable>",
  "bed_size": "<licensed bed count as a number, or null if unknown>",
  "emr_system": "<primary EMR/charting system used, e.g. 'Epic', 'Cerner', 'Meditech' — or null if you cannot verify>",
  "confidence": "<high|medium|low>",
  "sources": ["<source url>", ...]
}}

Rules:
- Do 1-2 searches at most, then answer with what you found. Do not keep searching to verify every field — a couple of searches is enough.
- Prefer null over a guess. Do not fabricate data.
- Only report facts you can attribute to a source found via search.
- If multiple facilities share this name, use the one matching the given location.
- You must always end by returning the JSON object, even if most fields are null.
- Do not write any explanation, reasoning, or notes before or after the JSON — not even a short one. Your entire response must be nothing but the JSON object itself, starting with {{ and ending with }}."""

    import logging

    last_error = None
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=6000,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}],
                messages=[{"role": "user", "content": prompt}]
            )
            text = _extract_text_blocks(response.content)
            if not text.strip():
                raise ValueError(f"empty text in response (stop_reason={response.stop_reason})")
            try:
                result = _parse_json_response(text)
            except Exception as parse_err:
                raise ValueError(f"{parse_err} -- raw text was: {text[:500]!r}") from parse_err
            result["facility_name"] = facility_name
            return result
        except Exception as e:
            last_error = e
            block_types = None
            try:
                block_types = [b.type for b in response.content]
            except Exception:
                pass
            logging.error(
                f"research_facility attempt {attempt + 1} failed for {facility_name}: {e} "
                f"(response blocks: {block_types})"
            )

    return {
        "facility_name": facility_name,
        "type_of_facility": None,
        "trauma_level": None,
        "bed_size": None,
        "emr_system": None,
        "confidence": "low",
        "sources": [],
        "error": str(last_error),
    }


def research_all_facilities(experience: list) -> dict:
    """Research every unique facility in the experience list, one at a time.

    Researching facilities concurrently was unreliable on constrained hosting (Render's
    free tier) — the web_search-enabled call would silently return empty/failed results
    for some facilities under concurrent load, even though each one works fine alone.
    Sequential is slower but consistently reliable, which matters more for this tool.
    """
    seen = {}
    for entry in experience:
        key = entry.get("facility_name", "").strip()
        if key and key not in seen:
            seen[key] = (entry.get("city", ""), entry.get("state", ""))

    results = {}
    for name, (city, state) in seen.items():
        try:
            results[name] = research_facility(name, city, state)
        except Exception as e:
            results[name] = {
                "facility_name": name, "type_of_facility": None, "trauma_level": None,
                "bed_size": None, "emr_system": None, "confidence": "low",
                "sources": [], "error": str(e),
            }
    return results


def build_formatted_resume(structured: dict, facility_research: dict) -> dict:
    """Merge parsed resume with facility research into the final HonorVet standard structure."""
    experience = []
    for entry in structured.get("experience", []):
        research = facility_research.get(entry.get("facility_name", "").strip(), {})
        experience.append({
            **entry,
            "type_of_facility": research.get("type_of_facility"),
            "trauma_level": research.get("trauma_level"),
            "bed_size": research.get("bed_size"),
            "emr_system": research.get("emr_system"),
            "research_confidence": research.get("confidence", "low"),
            "research_sources": research.get("sources", []),
        })

    return {**structured, "experience": experience}
