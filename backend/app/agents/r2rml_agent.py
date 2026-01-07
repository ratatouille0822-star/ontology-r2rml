from app.agents.skill_agent import SkillAgent


class R2RMLAgent:
    """R2RML 技能入口，委托给通用智能体执行。"""

    def __init__(self) -> None:
        self.agent = SkillAgent("r2rml")

    def match(self, properties, tables, mode: str, threshold: float):
        return self.agent.match(properties, tables, mode, threshold)
