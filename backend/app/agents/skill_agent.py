from app.agents.skill_registry import SkillRegistry, get_skill_registry
from app.skills.r2rml_skill import run_matching


class SkillAgent:
    """通用智能体：按需加载 SKILL.md 并执行对应技能。"""

    def __init__(self, skill_name: str, registry: SkillRegistry | None = None):
        self.skill_name = skill_name
        self.registry = registry or get_skill_registry()

    def _load_skill_doc(self) -> str:
        return self.registry.get_skill_doc(self.skill_name)

    def match(self, properties, tables, mode: str, threshold: float):
        skill_doc = self._load_skill_doc()
        if self.skill_name == "r2rml":
            return run_matching(properties, tables, mode, threshold, skill_doc)
        raise ValueError(f"未知技能: {self.skill_name}")
