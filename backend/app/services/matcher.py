from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable
import logging
import re

from app.models.schemas import MatchItem, PropertyItem
from app.services.llm_client import llm_match_properties
from app.utils.config import get_setting
from app.utils.match_logger import append_match_logs
from app.utils.text import normalize_text

logger = logging.getLogger(__name__)

LLM_BATCH_SIZE = 10


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
    logger.info("开始匹配：mode=%s，属性数=%d，表数=%d，阈值=%.2f", mode, len(properties), len(tables), threshold)
    candidates = _build_candidates(tables)
    table_summary = _build_table_summary(tables)
    relations = _infer_relations(table_summary)
    logger.info(
        "已解析候选字段：候选数=%d，关系数=%d",
        len(candidates),
        len(relations),
    )
    threshold = max(0.0, min(1.0, threshold))

    if mode == "llm":
        logger.info("进入 LLM 匹配流程")
        try:
            return llm_match(properties, candidates, table_summary, relations, threshold, skill_doc)
        except Exception as exc:
            logger.error("LLM 匹配失败，准备记录失败日志")
            log_entries = []
            reason = str(exc)
            for prop in properties:
                log_entries.append(
                    {
                        "level": "ERROR",
                        "property_label": prop.label or prop.local_name or prop.iri,
                        "group_name": _group_name_for_property(prop),
                        "field": "-",
                        "result": "匹配失败",
                        "reason": reason,
                    }
                )
            append_match_logs(log_entries)
            raise

    logger.info("进入启发式匹配流程")
    return heuristic_match(properties, candidates, table_summary, threshold)


def heuristic_match(
    properties: list[PropertyItem],
    candidates: list[FieldCandidate],
    tables: list[dict],
    threshold: float,
) -> list[MatchItem]:
    results: list[MatchItem] = []
    log_entries: list[dict] = []
    for prop in properties:
        scoped = _select_candidates_for_property(prop, candidates, tables)
        best = _best_candidate(prop, scoped)
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
            reason = "启发式匹配"
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
            if best:
                reason = "启发式匹配但置信度低于阈值"
            else:
                reason = "启发式未找到匹配"
            candidate = best[0] if best else None

        log_entries.append(
            {
                "level": "INFO",
                "property_label": prop.label or prop.local_name or prop.iri,
                "group_name": _group_name_for_property(prop),
                "field": candidate.field if candidate else "-",
                "result": "匹配成功" if best and score >= threshold else "匹配失败",
                "reason": reason,
            }
        )
    append_match_logs(log_entries)
    return results


def llm_match(
    properties: list[PropertyItem],
    candidates: list[FieldCandidate],
    tables: list[dict],
    relations: list[dict],
    threshold: float,
    skill_doc: str | None,
) -> list[MatchItem]:
    api_key = get_setting("QWEN_API_KEY")
    base_url = get_setting("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = get_setting("QWEN_MODEL", "qwen-plus")

    if not api_key:
        raise RuntimeError("QWEN_API_KEY 未配置，无法进行 LLM 匹配。")

    total_batches = (len(properties) + LLM_BATCH_SIZE - 1) // LLM_BATCH_SIZE
    logger.info(
        "准备分批调用 LLM：批大小=%d，总批次=%d，模型=%s",
        LLM_BATCH_SIZE,
        total_batches,
        model,
    )
    response_map: dict[str, dict] = {}
    for index in range(total_batches):
        batch = properties[index * LLM_BATCH_SIZE : (index + 1) * LLM_BATCH_SIZE]
        logger.info(
            "调用 LLM 批次 %d/%d：属性数=%d",
            index + 1,
            total_batches,
            len(batch),
        )
        response = llm_match_properties(
            batch,
            candidates,
            tables,
            relations,
            api_key,
            base_url,
            model,
            skill_doc,
        )
        logger.info("LLM 批次 %d/%d 返回条目数=%d", index + 1, total_batches, len(response))
        for item in response:
            property_iri = item.get("property_iri")
            if property_iri:
                response_map[property_iri] = item

    results: list[MatchItem] = []
    log_entries: list[dict] = []
    for prop in properties:
        item = response_map.get(prop.iri)
        llm_confidence = _extract_llm_confidence(item)
        explicit_null = (
            item is not None
            and item.get("table_name") is None
            and item.get("field") is None
        )
        candidate = None
        if item and not explicit_null:
            candidate = _candidate_from_response(item, candidates)
        if candidate:
            score = _score_candidate(prop, candidate)
            score_source = "local"
        elif explicit_null:
            score = llm_confidence or 0.0
            score_source = "llm"
        elif item is not None:
            score = llm_confidence or 0.0
            score_source = "llm"
        else:
            scoped = _select_candidates_for_property(prop, candidates, tables)
            best = _best_candidate(prop, scoped)
            candidate = best[0] if best else None
            score = best[1] if best else 0.0
            score_source = "local"

        if llm_confidence is not None:
            score = llm_confidence
            score_source = "llm"

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
            result = "匹配成功"
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
            result = "匹配失败"

        reason = None
        if item:
            reason = item.get("reason")
        if not reason:
            if item is None:
                reason = "LLM 未返回该属性匹配结果"
            elif explicit_null:
                reason = "LLM 判定无合适字段"
            else:
                reason = "LLM 未返回匹配原因"
        if item is not None and not explicit_null and candidate is None:
            reason = f"{reason}；LLM 返回字段不在候选列表"
        if candidate and score < threshold:
            reason = f"{reason}；置信度低于阈值"
        if score_source == "llm" and llm_confidence is not None:
            reason = f"{reason}；LLM置信度={llm_confidence:.2f}"
        elif score_source == "local":
            reason = f"{reason}；使用本地评分"

        log_entries.append(
            {
                "level": "INFO",
                "property_label": prop.label or prop.local_name or prop.iri,
                "group_name": _group_name_for_property(prop),
                "field": candidate.field if candidate else "-",
                "result": result,
                "reason": reason,
            }
        )

    append_match_logs(log_entries)
    return results


def _extract_llm_confidence(item: dict | None) -> float | None:
    if not item:
        return None
    value = item.get("confidence")
    if value is None:
        value = item.get("score")
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence > 1 and confidence <= 100:
        confidence = confidence / 100
    if confidence < 0:
        return None
    if confidence > 1:
        confidence = 1.0
    return round(confidence, 4)


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


def _select_candidates_for_property(
    prop: PropertyItem,
    candidates: list[FieldCandidate],
    tables: list[dict],
) -> list[FieldCandidate]:
    preferred_tables = _rank_tables_for_property(prop, tables)
    if not preferred_tables:
        return candidates
    return [item for item in candidates if item.table_name in preferred_tables]


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


def _group_name_for_property(prop: PropertyItem) -> str:
    if prop.domains:
        domain = prop.domains[0]
        return domain.label or domain.local_name or domain.iri
    return "未分群"


def _rank_tables_for_property(prop: PropertyItem, tables: list[dict]) -> list[str]:
    if not tables or not prop.domains:
        return []
    scored: list[tuple[str, float]] = []
    for table in tables:
        name = table.get("name") or ""
        if not name:
            continue
        scored.append((name, _domain_similarity(name, prop.domains)))
    if not scored:
        return []
    scored.sort(key=lambda item: item[1], reverse=True)
    selected = [name for name, score in scored if score >= 0.35]
    if not selected:
        selected = [scored[0][0]]
    return selected[:3]


def _build_table_summary(tables: list) -> list[dict]:
    summary: list[dict] = []
    for table in tables:
        name = _table_value(table, "name", "")
        fields = _table_value(table, "fields", [])
        sample_rows = _table_value(table, "sample_rows", [])
        summary.append(
            {
                "name": name,
                "fields": fields,
                "sample_rows": sample_rows[:3] if isinstance(sample_rows, list) else [],
            }
        )
    return summary


def _infer_relations(tables: list[dict]) -> list[dict]:
    relations: list[dict] = []
    for i, left in enumerate(tables):
        left_fields = set(left.get("fields") or [])
        for right in tables[i + 1 :]:
            right_fields = set(right.get("fields") or [])
            shared = sorted(left_fields & right_fields)
            if shared:
                relations.append(
                    {
                        "left_table": left.get("name"),
                        "right_table": right.get("name"),
                        "shared_fields": shared[:5],
                    }
                )
    return relations
