from __future__ import annotations

from pathlib import Path
import logging

from agentscope.tool import Toolkit

logger = logging.getLogger(__name__)


class SkillRegistry:
    def __init__(self, skill_root: Path | None = None) -> None:
        self.skill_root = skill_root or Path(__file__).resolve().parents[3] / "SKILLS"
        self.toolkit = Toolkit()
        self._skill_doc_cache: dict[str, str] = {}
        self._skill_doc_mtime: dict[str, float] = {}
        self._register_skills()

    def _register_skills(self) -> None:
        self.toolkit = Toolkit()
        if not self.skill_root.exists():
            logger.warning("Skill root does not exist: %s", self.skill_root)
            return
        for skill_dir in self.skill_root.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_doc = skill_dir / "SKILL.md"
            if not skill_doc.exists():
                continue
            try:
                self.toolkit.register_agent_skill(str(skill_dir))
            except Exception as exc:
                logger.warning("Failed to register skill %s: %s", skill_dir.name, exc)

    def list_skills(self) -> list[str]:
        return list(self.toolkit.skills.keys())

    def get_skill_prompt(self) -> str | None:
        return self.toolkit.get_agent_skill_prompt()

    def ensure_skill(self, name: str) -> None:
        if name not in self.toolkit.skills:
            raise ValueError(f"Unknown skill: {name}")

    def get_skill_doc(self, name: str) -> str:
        self.ensure_skill(name)
        skill_path = self.skill_root / name / "SKILL.md"
        mtime = skill_path.stat().st_mtime
        cached = self._skill_doc_cache.get(name)
        cached_mtime = self._skill_doc_mtime.get(name)
        if cached is None or cached_mtime != mtime:
            cached = skill_path.read_text(encoding="utf-8")
            self._skill_doc_cache[name] = cached
            self._skill_doc_mtime[name] = mtime
        return cached


_default_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = SkillRegistry()
    return _default_registry
