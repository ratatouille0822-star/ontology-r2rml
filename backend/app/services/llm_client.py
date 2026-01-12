import json
import logging
import re
from typing import List

import httpx

from app.models.schemas import PropertyItem
from app.utils.config import get_setting

logger = logging.getLogger(__name__)


def _extract_json(text: str):
    match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in response")
    return json.loads(match.group(0))


def _chat_completion(
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    url = base_url.rstrip("/") + "/chat/completions"

    with httpx.Client(timeout=60) as client:
        try:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            detail = ""
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                detail = exc.response.text
            message = f"LLM request failed: {detail or str(exc)}"
            logger.error(message)
            raise RuntimeError(message) from exc

    return data["choices"][0]["message"]["content"]


def _parse_model_candidates(raw: str | None, default_model: str) -> list[str]:
    if not raw:
        return [default_model]
    candidates = [item.strip() for item in raw.split(",") if item.strip()]
    if default_model not in candidates:
        candidates.insert(0, default_model)
    seen = set()
    unique = []
    for item in candidates:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def select_llm_model(
    properties: List[PropertyItem],
    candidates: List,
    tables: List[dict],
    relations: List[dict],
    default_model: str,
    api_key: str,
    base_url: str,
    skill_doc: str | None = None,
) -> str:
    raw_candidates = get_setting("QWEN_MODEL_CANDIDATES")
    model_candidates = _parse_model_candidates(raw_candidates, default_model)
    if len(model_candidates) <= 1:
        return default_model
    router_model = get_setting("QWEN_ROUTER_MODEL", default_model)

    system_parts = [
        "You are a model router. Choose the best model from the candidate list.",
        'Return strict JSON: {"model": "...", "reason": "..."}.',
        "Only choose from the candidate list.",
    ]
    if skill_doc:
        system_parts.append("Skill instructions:\n" + skill_doc)

    user_payload = {
        "task": "r2rml_match",
        "default_model": default_model,
        "candidates": model_candidates,
        "stats": {
            "property_count": len(properties),
            "table_count": len(tables),
            "candidate_count": len(candidates),
            "relation_count": len(relations),
        },
    }

    messages = [
        {"role": "system", "content": "\n".join(system_parts)},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]
    try:
        content = _chat_completion(api_key, base_url, router_model, messages, temperature=0.0)
        parsed = _extract_json(content)
    except Exception as exc:
        logger.warning("Model selection failed, fallback to default: %s", exc)
        return default_model

    if isinstance(parsed, dict):
        selected = parsed.get("model")
    else:
        selected = None
    if selected in model_candidates:
        logger.info("Selected model by router: %s", selected)
        return selected
    logger.warning("Router returned invalid model: %s", selected)
    return default_model


def llm_match_properties(
    properties: List[PropertyItem],
    candidates: List,
    tables: List[dict],
    relations: List[dict],
    api_key: str,
    base_url: str,
    model: str,
    skill_doc: str | None,
) -> List[dict]:
    system_parts = [
        "You are a reliable assistant for ontology field matching.",
        "Follow the skill document instructions strictly.",
        "Do not change the output format unless required by the skill document.",
    ]
    if skill_doc:
        system_parts.append("Skill instructions:\n" + skill_doc)

    prompt = {
        "role": "system",
        "content": "\n".join(system_parts),
    }

    user_payload = {
        "properties": [
            {
                "iri": prop.iri,
                "label": prop.label,
                "local_name": prop.local_name,
                "domains": [
                    {
                        "iri": domain.iri,
                        "label": domain.label,
                        "local_name": domain.local_name,
                    }
                    for domain in prop.domains
                ],
                "ranges": [
                    {
                        "iri": item.iri,
                        "label": item.label,
                        "local_name": item.local_name,
                    }
                    for item in prop.ranges
                ],
            }
            for prop in properties
        ],
        "tables": tables,
        "relations": relations,
        "candidates": [
            {
                "table_name": candidate.table_name,
                "field": candidate.field,
                "sample_values": candidate.samples[:3],
            }
            for candidate in candidates
        ],
    }

    payload_preview = json.dumps(user_payload, ensure_ascii=False)
    preview_limit = 2000
    if len(payload_preview) > preview_limit:
        payload_preview = payload_preview[:preview_limit] + "...(truncated)"
    logger.info(
        "Calling LLM: model=%s, properties=%d, tables=%d, candidates=%d, relations=%d",
        model,
        len(properties),
        len(tables),
        len(candidates),
        len(relations),
    )
    logger.info("LLM request preview: %s", payload_preview)

    messages = [
        prompt,
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]

    content = _chat_completion(api_key, base_url, model, messages, temperature=0.2)
    try:
        parsed = _extract_json(content)
    except Exception as exc:
        snippet = content[:500]
        logger.error("LLM response parse failed, snippet: %s", snippet)
        raise RuntimeError("LLM response invalid: no JSON parsed") from exc
    matches = parsed.get("matches", []) if isinstance(parsed, dict) else parsed

    if not isinstance(matches, list):
        raise ValueError("Invalid LLM response format")

    return matches
