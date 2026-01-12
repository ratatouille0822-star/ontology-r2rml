from app.agents.agentscope_runner import AgentScopeSkillRunner
from app.agents.skill_agent import SkillAgent
from app.agents.skill_registry import SkillRegistry, get_skill_registry



class SkillDispatcher:
    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or get_skill_registry()
        self.match_agent = SkillAgent("r2rml", registry=self.registry)
        self.skill_runner = AgentScopeSkillRunner(self.registry)

    async def parse_tbox(self, content: bytes, filename: str):
        self.registry.ensure_skill("tbox-parse")
        file_id = self.skill_runner.store_file(filename or "", content)
        return await self.skill_runner.run_skill(
            "tbox-parse",
            "parse_tbox_tool",
            {"file_id": file_id, "filename": filename},
        )

    async def parse_data(self, files: list[tuple[str, bytes]]):
        self.registry.ensure_skill("data-parse")
        file_ids = []
        for filename, content in files:
            file_ids.append(self.skill_runner.store_file(filename or "", content))
        return await self.skill_runner.run_skill(
            "data-parse",
            "parse_data_tool",
            {"file_ids": file_ids},
        )

    async def match(self, properties, tables, mode: str, threshold: float):
        self.registry.ensure_skill("r2rml")
        return self.match_agent.match(properties, tables, mode, threshold)

    async def generate_abox(self, tables, mapping, base_iri: str):
        self.registry.ensure_skill("abox-generate")
        return await self.skill_runner.run_skill(
            "abox-generate",
            "generate_abox_tool",
            {"tables": tables, "mapping": mapping, "base_iri": base_iri},
        )

    async def generate_r2rml(self, mapping, table_name: str, base_iri: str):
        self.registry.ensure_skill("r2rml-generate")
        return await self.skill_runner.run_skill(
            "r2rml-generate",
            "generate_r2rml_tool",
            {"mapping": mapping, "table_name": table_name, "base_iri": base_iri},
        )
