from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable
import re

from app.models.schemas import MatchItem, PropertyItem
from app.services.llm_client import llm_match_properties
from app.utils.config import get_setting
from app.utils.text import normalize_text


@dataclass
class FieldCandidate:
    table_name: str
    field: str
    samples: list


def match_properties(
    properties: list[PropertyItem],
    tables: list[dict],
    mode: str,
    threshold: float,
    skill_doc: str | None = None,
) -> list[MatchItem]:
    candidates = _build_candidates(tables)
    threshold = max(0.0, min(1.0, threshold))

    if mode == "llm":
        try:
            return llm_match(properties, candidates, threshold, skill_doc)
        except Exception:
            return heuristic_match(properties, candidates, threshold)

    return heuristic_match(properties, candidates, threshold)


def heuristic_match(
    properties: list[PropertyItem],
    candidates: list[FieldCandidate],
    threshold: float,
) -> list[MatchItem]:
    results: list[MatchItem] = []
    for prop in properties:
        best = _best_candidate(prop, candidates)
        score = best[1] if best else 0.0
        if best and score >= threshold:
            candidate = best[0]
            results.append(
                MatchItem(
                    property_iri=prop.iri,
                    property_label=prop.label or prop.local_name,
                    table_name=candidate.table_name,
                    field=candidate.field,
                    score=round(score, 4),
                )
            )
        else:
            results.append(
                MatchItem(
                    property_iri=prop.iri,
                    property_label=prop.label or prop.local_name,
                    table_name=None,
                    field=None,
                    score=round(score, 4) if score else None,
                )
            )
    return results


def llm_match(
    properties: list[PropertyItem],
    candidates: list[FieldCandidate],
    threshold: float,
    skill_doc: str | None,
) -> list[MatchItem]:
    api_key = get_setting("QWEN_API_KEY")
    base_url = get_setting("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = get_setting("QWEN_MODEL", "qwen-plus")

    if not api_key:
        return heuristic_match(properties, candidates, threshold)

    response = llm_match_properties(properties, candidates, api_key, base_url, model, skill_doc)
    response_map = {item.get("property_iri"): item for item in response if item.get("property_iri")}

    results: list[MatchItem] = []
    for prop in properties:
        item = response_map.get(prop.iri)
        candidate = None
        if item:
            candidate = _candidate_from_response(item, candidates)
        if candidate:
            score = _score_candidate(prop, candidate)
        else:
            best = _best_candidate(prop, candidates)
            candidate = best[0] if best else None
            score = best[1] if best else 0.0

        if candidate and score >= threshold:
            results.append(
                MatchItem(
                    property_iri=prop.iri,
                    property_label=prop.label or prop.local_name,
                    table_name=candidate.table_name,
                    field=candidate.field,
                    score=round(score, 4),
                )
            )
        else:
            results.append(
                MatchItem(
                    property_iri=prop.iri,
                    property_label=prop.label or prop.local_name,
                    table_name=None,
                    field=None,
                    score=round(score, 4) if score else None,
                )
            )

    return results


def _candidate_from_response(item: dict, candidates: list[FieldCandidate]) -> FieldCandidate | None:
    table_name = item.get("table_name")
    field = item.get("field")
    if not table_name or not field:
        return None
    for candidate in candidates:
        if candidate.table_name == table_name and candidate.field == field:
            return candidate
    return None


def _best_candidate(
    prop: PropertyItem,
    candidates: list[FieldCandidate],
) -> tuple[FieldCandidate, float] | None:
    best_candidate = None
    best_score = 0.0

    for candidate in candidates:
        score = _score_candidate(prop, candidate)
        if score > best_score:
            best_score = score
            best_candidate = candidate

    if not best_candidate:
        return None
    return best_candidate, best_score


def _score_candidate(prop: PropertyItem, candidate: FieldCandidate) -> float:
    name_score = _name_similarity(candidate.field, [prop.label, prop.local_name])
    domain_score = _domain_similarity(candidate.table_name, prop.domains)
    sample_score = _sample_similarity(candidate.samples, prop)

    return 0.6 * name_score + 0.2 * domain_score + 0.2 * sample_score


def _name_similarity(text: str, candidates: Iterable[str | None]) -> float:
    best = 0.0
    normalized_text = normalize_text(text)
    for value in candidates:
        if not value:
            continue
        normalized_value = normalize_text(value)
        if not normalized_value:
            continue
        score = SequenceMatcher(None, normalized_text, normalized_value).ratio()
        if score > best:
            best = score
    return best


def _domain_similarity(table_name: str, domains: list) -> float:
    if not domains:
        return 0.5
    candidates = []
    for domain in domains:
        candidates.append(domain.label)
        candidates.append(domain.local_name)
    return _name_similarity(table_name, candidates)


def _sample_similarity(samples: list, prop: PropertyItem) -> float:
    hints = _property_type_hints(prop)
    sample_type = _infer_sample_type(samples)

    if not hints:
        return 0.5
    if sample_type in hints:
        return 1.0
    if sample_type == "unknown":
        return 0.5
    return 0.0


def _property_type_hints(prop: PropertyItem) -> set[str]:
    hints: set[str] = set()
    labels = [prop.label, prop.local_name]
    for value in labels:
        if not value:
            continue
        text = value.lower()
        if "email" in text or "邮箱" in text:
            hints.add("email")
        if "date" in text or "time" in text or "日期" in text or "时间" in text:
            hints.add("date")
        if "url" in text or "link" in text or "链接" in text:
            hints.add("url")
        if "phone" in text or "mobile" in text or "电话" in text or "手机号" in text:
            hints.add("phone")
        if "age" in text or "年龄" in text:
            hints.add("number")
        if "amount" in text or "price" in text or "金额" in text or "价格" in text:
            hints.add("number")

    for item in prop.ranges:
        text = (item.local_name or item.label or item.iri).lower()
        if "boolean" in text:
            hints.add("boolean")
        if "date" in text or "time" in text:
            hints.add("date")
        if any(token in text for token in ["int", "decimal", "float", "double", "number"]):
            hints.add("number")
        if "string" in text:
            hints.add("text")

    return hints


def _infer_sample_type(samples: list) -> str:
    values = [value for value in samples if value not in (None, "")]
    if not values:
        return "unknown"

    email_count = 0
    url_count = 0
    number_count = 0
    date_count = 0
    phone_count = 0
    bool_count = 0

    for value in values:
        text = str(value).strip()
        if _looks_like_email(text):
            email_count += 1
        if _looks_like_url(text):
            url_count += 1
        if _looks_like_number(text):
            number_count += 1
        if _looks_like_date(text):
            date_count += 1
        if _looks_like_phone(text):
            phone_count += 1
        if _looks_like_bool(text):
            bool_count += 1

    total = len(values)
    if email_count / total >= 0.6:
        return "email"
    if url_count / total >= 0.6:
        return "url"
    if phone_count / total >= 0.6:
        return "phone"
    if bool_count / total >= 0.6:
        return "boolean"
    if date_count / total >= 0.6:
        return "date"
    if number_count / total >= 0.6:
        return "number"
    return "text"


def _looks_like_email(text: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", text))


def _looks_like_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://") or text.startswith("www.")


def _looks_like_number(text: str) -> bool:
    return bool(re.match(r"^-?\d+(\.\d+)?$", text))


def _looks_like_date(text: str) -> bool:
    return bool(re.match(r"^\d{4}[-/年]\d{1,2}[-/月]\d{1,2}", text))


def _looks_like_phone(text: str) -> bool:
    return bool(re.match(r"^\+?\d{7,}$", text))


def _looks_like_bool(text: str) -> bool:
    return text.lower() in {"true", "false", "yes", "no", "0", "1"}


def _build_candidates(tables: list) -> list[FieldCandidate]:
    candidates: list[FieldCandidate] = []
    for table in tables:
        table_name = _table_value(table, "name", "")
        fields = _table_value(table, "fields", [])
        sample_rows = _table_value(table, "sample_rows", [])
        for field in fields:
            samples = [row.get(field) for row in sample_rows if isinstance(row, dict)]
            candidates.append(FieldCandidate(table_name=table_name, field=field, samples=samples))
    return candidates


def _table_value(table, key: str, default):
    if isinstance(table, dict):
        return table.get(key, default)
    return getattr(table, key, default)
