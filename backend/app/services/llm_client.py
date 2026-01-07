import json
import re
from typing import List

import httpx

from app.models.schemas import PropertyItem


def _extract_json(text: str):
    match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in response")
    return json.loads(match.group(0))


def llm_match_fields(
    fields: List[str],
    properties: List[PropertyItem],
    api_key: str,
    base_url: str,
    model: str,
) -> List[dict]:
    prompt = {
        "role": "system",
        "content": (
            "You are an R2RML mapping assistant. "
            "Map each field to the most relevant datatype property IRI. "
            "Return JSON as {\"matches\": [{\"field\":..., \"property_iri\":...}]} "
            "Only use provided property IRIs."
        ),
    }

    user_payload = {
        "fields": fields,
        "properties": [{
            "iri": prop.iri,
            "label": prop.label,
            "local_name": prop.local_name,
        } for prop in properties],
    }

    payload = {
        "model": model,
        "messages": [
            prompt,
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.2,
    }

    headers = {"Authorization": f"Bearer {api_key}"}
    url = base_url.rstrip("/") + "/chat/completions"

    with httpx.Client(timeout=60) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    parsed = _extract_json(content)
    matches = parsed.get("matches", []) if isinstance(parsed, dict) else parsed

    if not isinstance(matches, list):
        raise ValueError("Invalid LLM response format")

    return matches
