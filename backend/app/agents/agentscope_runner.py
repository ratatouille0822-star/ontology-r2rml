from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg, TextBlock
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit, ToolResponse

from app.agents.skill_registry import SkillRegistry, get_skill_registry
from app.services.abox_generator import generate_abox
from app.services.data_source import parse_tabular_files
from app.services.r2rml_generator import generate_r2rml
from app.services.tbox_parser import parse_tbox
from app.utils.config import get_setting



@dataclass
class StoredFile:
    filename: str
    content: bytes


class FileStore:
    def __init__(self) -> None:
        self._files: dict[str, StoredFile] = {}

    def put(self, filename: str, content: bytes) -> str:
        file_id = uuid.uuid4().hex
        self._files[file_id] = StoredFile(filename=filename, content=content)
        return file_id

    def pop(self, file_id: str) -> StoredFile:
        try:
            return self._files.pop(file_id)
        except KeyError as exc:
            raise ValueError(f"Unknown file id: {file_id}") from exc

    def pop_many(self, file_ids: list[str]) -> list[StoredFile]:
        return [self.pop(file_id) for file_id in file_ids]


class AgentScopeSkillRunner:
    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or get_skill_registry()
        self.file_store = FileStore()

    def store_file(self, filename: str, content: bytes) -> str:
        return self.file_store.put(filename, content)

    async def run_skill(
        self,
        skill_name: str,
        tool_name: str,
        payload: dict,
    ) -> dict:
        agent = self._build_agent(skill_name)
        message = Msg(
            name="user",
            role="user",
            content=json.dumps(
                {
                    "instruction": f"必须调用工具 {tool_name} 并只返回工具结果 JSON。",
                    "tool": tool_name,
                    "input": payload,
                },
                ensure_ascii=False,
            ),
        )
        reply = await agent.reply(message)
        result = self._extract_tool_result(reply, tool_name)
        if result is None:
            raise RuntimeError(f"Skill execution failed: {skill_name}")
        return result

    def _build_agent(self, skill_name: str) -> ReActAgent:
        api_key = get_setting("QWEN_API_KEY")
        base_url = get_setting("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        model_name = get_setting("QWEN_MODEL", "qwen-plus")

        if not api_key:
            raise RuntimeError("QWEN_API_KEY not configured for AgentScope.")

        skill_doc = self.registry.get_skill_doc(skill_name)
        sys_prompt = (
            "你是技能执行代理，必须严格按照技能文档执行并调用工具完成任务。\n"
            "只允许调用工具，不要输出解释性文字。\n"
            f"技能文档:\n{skill_doc}"
        )

        model = OpenAIChatModel(
            model_name=model_name,
            api_key=api_key,
            client_kwargs={"base_url": base_url},
            stream=False,
        )
        formatter = OpenAIChatFormatter()
        toolkit = Toolkit()
        toolkit.register_tool_function(self.parse_tbox_tool)
        toolkit.register_tool_function(self.parse_data_tool)
        toolkit.register_tool_function(self.generate_abox_tool)
        toolkit.register_tool_function(self.generate_r2rml_tool)

        return ReActAgent(
            name="skill-agent",
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            parallel_tool_calls=False,
            max_iters=3,
        )

    def _extract_tool_result(self, reply: Msg, tool_name: str) -> dict | None:
        blocks = reply.get_content_blocks("tool_result")
        for block in blocks:
            if block.get("name") != tool_name:
                continue
            output = block.get("output")
            if isinstance(output, str):
                return json.loads(output)
            if isinstance(output, list):
                text = "".join(
                    item.get("text", "")
                    for item in output
                    if isinstance(item, dict) and item.get("type") == "text"
                )
                if text:
                    return json.loads(text)
        return None

    def _json_response(self, payload: dict) -> ToolResponse:
        return ToolResponse(
            content=[TextBlock(type="text", text=json.dumps(payload, ensure_ascii=False))],
            metadata=payload,
        )

    def parse_tbox_tool(self, file_id: str, filename: str) -> ToolResponse:
        """Parse a TBox ontology file by stored file id."""
        stored = self.file_store.pop(file_id)
        result = parse_tbox(stored.content, filename or stored.filename)
        payload = {
            "properties": [item.model_dump() for item in result["properties"]],
            "classes": [item.model_dump() for item in result["classes"]],
            "object_properties": [item.model_dump() for item in result["object_properties"]],
            "ttl": result["ttl"],
        }
        return self._json_response(payload)

    def parse_data_tool(self, file_ids: list[str]) -> ToolResponse:
        """Parse tabular data files by stored file ids."""
        stored_items = self.file_store.pop_many(file_ids)
        files = [(item.filename, item.content) for item in stored_items]
        tables = parse_tabular_files(files)
        payload = {
            "tables": tables,
            "file_count": len(files),
            "table_count": len(tables),
        }
        return self._json_response(payload)

    def generate_abox_tool(self, tables: list, mapping: list, base_iri: str) -> ToolResponse:
        """Generate ABox Turtle content."""
        data_dir = get_setting("DATA_DIR", "./data")
        output_dir = str(Path(data_dir) / "abox")
        content, file_path = generate_abox(tables, mapping, base_iri, output_dir)
        return self._json_response({"format": "turtle", "content": content, "file_path": file_path})

    def generate_r2rml_tool(self, mapping: list, table_name: str, base_iri: str) -> ToolResponse:
        """Generate R2RML Turtle content."""
        content = generate_r2rml(mapping, table_name, base_iri)
        return self._json_response({"format": "turtle", "content": content})
