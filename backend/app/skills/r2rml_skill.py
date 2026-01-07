from app.services.matcher import match_properties


def run_matching(properties, tables, mode: str, threshold: float, skill_doc: str | None):
    return match_properties(properties, tables, mode, threshold, skill_doc)
