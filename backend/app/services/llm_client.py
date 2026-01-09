import json
import logging
import re
from typing import List

import httpx

from app.models.schemas import PropertyItem

logger = logging.getLogger(__name__)


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
        "你是一个通用智能体，具备理解和逻辑推理的强大能力。",
        "你是一个能力很强但绝对服从命令的员工，必须严格遵循技能文档执行。",
        "除技能文档明确要求外，不要擅自添加规则或更改输出格式。",
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

    payload_preview = json.dumps(user_payload, ensure_ascii=False)
    preview_limit = 2000
    if len(payload_preview) > preview_limit:
        payload_preview = payload_preview[:preview_limit] + "...(已截断)"
    logger.info(
        "调用 LLM：model=%s，属性数=%d，表数=%d，候选字段数=%d，关系数=%d",
        model,
        len(properties),
        len(tables),
        len(candidates),
        len(relations),
    )
    logger.info("LLM 请求内容预览：%s", payload_preview)

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
        try:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            detail = ""
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                detail = exc.response.text
            message = f"LLM 请求失败: {detail or str(exc)}"
            logger.error(message)
            raise RuntimeError(message) from exc

    content = data["choices"][0]["message"]["content"]
    try:
        parsed = _extract_json(content)
    except Exception as exc:
        snippet = content[:500]
        logger.error("LLM 返回解析失败，原文片段: %s", snippet)
        raise RuntimeError("LLM 返回格式无效，未解析到 JSON。") from exc
    matches = parsed.get("matches", []) if isinstance(parsed, dict) else parsed

    if not isinstance(matches, list):
        raise ValueError("Invalid LLM response format")

    return matches
