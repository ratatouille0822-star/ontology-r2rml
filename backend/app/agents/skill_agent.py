from pathlib import Path

from app.skills.r2rml_skill import run_matching


class SkillAgent:
    """通用智能体：按需加载 SKILL.md 并执行对应技能。"""

    def __init__(self, skill_name: str, skill_root: Path | None = None):
        self.skill_name = skill_name
        self.skill_root = skill_root or Path(__file__).resolve().parents[3] / "SKILLS"
        self._skill_doc: str | None = None

    def _load_skill_doc(self) -> str:
        if self._skill_doc is None:
            skill_path = self.skill_root / self.skill_name / "SKILL.md"
            self._skill_doc = skill_path.read_text(encoding="utf-8")
        return self._skill_doc

    def match(self, properties, tables, mode: str, threshold: float):
        skill_doc = self._load_skill_doc()
        if self.skill_name == "r2rml":
            return run_matching(properties, tables, mode, threshold, skill_doc)
        raise ValueError(f"未知技能: {self.skill_name}")
