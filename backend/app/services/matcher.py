from difflib import SequenceMatcher
from typing import List

from app.models.schemas import MatchItem, PropertyItem
from app.services.llm_client import llm_match_fields
from app.utils.config import get_setting
from app.utils.text import normalize_text


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def heuristic_match(fields: List[str], properties: List[PropertyItem]) -> List[MatchItem]:
    matches: List[MatchItem] = []
    for field in fields:
        normalized_field = normalize_text(field)
        best_score = 0.0
        best_prop = None

        for prop in properties:
            candidates = [prop.local_name or "", prop.label or ""]
            for candidate in candidates:
                normalized_candidate = normalize_text(candidate)
                if not normalized_candidate:
                    continue
                score = _similarity(normalized_field, normalized_candidate)
                if score > best_score:
                    best_score = score
                    best_prop = prop

        if best_prop:
            matches.append(
                MatchItem(
                    field=field,
                    property_iri=best_prop.iri,
                    property_label=best_prop.label or best_prop.local_name,
                    score=round(best_score, 4),
                )
            )
        else:
            matches.append(MatchItem(field=field))

    return matches


def llm_match(fields: List[str], properties: List[PropertyItem]) -> List[MatchItem]:
    api_key = get_setting("QWEN_API_KEY")
    base_url = get_setting("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = get_setting("QWEN_MODEL", "qwen-plus")

    if not api_key:
        return heuristic_match(fields, properties)

    response = llm_match_fields(fields, properties, api_key, base_url, model)
    prop_lookup = {prop.iri: prop for prop in properties}
    matches: List[MatchItem] = []

    for item in response:
        field = item.get("field")
        property_iri = item.get("property_iri")
        if not field:
            continue
        prop = prop_lookup.get(property_iri) if property_iri else None
        matches.append(
            MatchItem(
                field=field,
                property_iri=property_iri,
                property_label=prop.label if prop else None,
                score=None,
            )
        )

    return matches


def match_fields(fields: List[str], properties: List[PropertyItem], mode: str) -> List[MatchItem]:
    if mode == "llm":
        try:
            return llm_match(fields, properties)
        except Exception:
            return heuristic_match(fields, properties)
    return heuristic_match(fields, properties)
