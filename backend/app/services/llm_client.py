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
        "你是一个 R2RML 映射智能体。",
        "先理解数据表结构与字段之间可能的关联，再与本体数据属性进行匹配。",
        "以本体数据属性为锚点，为每个属性匹配一个最合适的表字段。",
        "只允许使用给定的候选表名与字段名。",
        "输出 JSON 格式：{\"matches\": [{\"property_iri\":..., \"table_name\":..., \"field\":...}]}。",
        "如果没有合适字段，table_name 与 field 返回 null。",
    ]
    if skill_doc:
        system_parts.append("以下是技能说明，请遵循：\\n" + skill_doc)

    prompt = {
        "role": "system",
        "content": "\\n".join(system_parts),
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
