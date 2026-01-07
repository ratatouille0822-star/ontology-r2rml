from app.models.schemas import MatchItem, PropertyItem
from app.services.matcher import match_fields


class R2RMLAgent:
    """轻量级智能体封装，用于字段到属性的匹配。"""

    def match(self, fields: list[str], properties: list[PropertyItem], mode: str) -> list[MatchItem]:
        return match_fields(fields, properties, mode)
