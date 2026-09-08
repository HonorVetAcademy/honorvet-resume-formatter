import json
import re


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


