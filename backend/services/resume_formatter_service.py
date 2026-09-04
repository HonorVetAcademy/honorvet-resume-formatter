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
