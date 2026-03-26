import json
import re
from dataclasses import dataclass, field

from ..i18n import choose
from ..llm import create_client
from ..llm.base import LLMError
from .mcp_bridge import McpBridgeService
from .prompt_builder import SYSTEM_PROMPT, build_user_prompt
from .rule_based_parser import RuleBasedPlanner
from .schema import ActionPlan


@dataclass
class PlanningResult:
    plan: ActionPlan
    source: str
    warnings: list = field(default_factory=list)
    raw_response: str = ""
    reasoning_text: str = ""


class CommandPlanner:
    def __init__(self, registry, style_standards=None):
        self.registry = registry
        self.style_standards = style_standards
        self._rule_based = RuleBasedPlanner(registry, style_standards=style_standards)
        self._mcp_bridge = McpBridgeService()

    def plan(self, command_text: str, project_context: dict, config, request_mode: str = "auto", conversation_memory: dict = None) -> PlanningResult:
        warnings = []
        raw_response = ""
        reasoning_text = ""
        allow_dynamic_processing = bool(getattr(config, "allow_dynamic_processing", False))
        skill_text = (getattr(config, "skill_text", "") or "").strip()
        mcp_contexts = []
        mcp_servers_text = getattr(config, "mcp_servers_text", "") or ""
        if mcp_servers_text:
            bridge_contexts, bridge_warnings = self._mcp_bridge.fetch_contexts(
                mcp_servers_text,
                command_text,
                project_context,
                conversation_memory=conversation_memory,
                timeout=min(int(getattr(config, "request_timeout", 90)), 60),
            )
            mcp_contexts.extend(bridge_contexts)
            warnings.extend(bridge_warnings)

        if config.provider != "none":
            try:
                client = self._make_client(config)
                user_prompt = build_user_prompt(
                    command_text,
                    project_context,
                    self.registry,
                    request_mode,
                    conversation_memory,
                    skill_text=skill_text,
                    mcp_contexts=mcp_contexts,
                    allow_dynamic_processing=allow_dynamic_processing,
                    style_standards_text=self.style_standards.catalog_text() if self.style_standards is not None else "",
                )
                plan, raw_response, reasoning_text = self._plan_with_model(
                    client,
                    config,
                    user_prompt,
                    allow_dynamic_processing=allow_dynamic_processing,
                )
                if not plan.source:
                    plan.source = "llm"
                return PlanningResult(
                    plan=plan,
                    source=plan.source or "llm",
                    warnings=warnings,
                    raw_response=raw_response,
                    reasoning_text=reasoning_text,
                )
            except (LLMError, ValueError) as exc:
                detail = choose("LLM 规划失败，已回退到规则解析: {}", "LLM planning failed and fell back to rule-based parsing: {}").format(exc)
                if raw_response:
                    detail = "{} | {}".format(detail, choose("返回摘要: {}", "Response excerpt: {}").format(self._truncate(raw_response, 220)))
                warnings.append(detail)

        plan = self._rule_based.parse(command_text, project_context, request_mode=request_mode)
        if plan is None:
            if warnings:
                raise ValueError(
                    choose(
                        "模型规划失败，且规则解析也未匹配当前命令。最后一次模型错误: {}",
                        "Model planning failed, and rule-based parsing also could not match the command. Last model error: {}",
                    ).format(warnings[-1])
                )
            raise ValueError(
                choose(
                    "无法解析该命令。请补充更明确的图层名，或先在设置中测试模型连通性。",
                    "Unable to parse this command. Please provide a more specific layer name or test model connectivity in settings first.",
                )
            )
        return PlanningResult(
            plan=self.registry.enforce_on_plan(plan, allow_dynamic_processing=allow_dynamic_processing),
            source=plan.source or "rule-based",
            warnings=warnings,
            raw_response=raw_response,
            reasoning_text=reasoning_text,
        )

    def _make_client(self, config):
        return create_client(
            provider=config.provider,
            base_url=config.base_url,
            api_key=config.api_key,
            model_name=config.model_name,
            timeout=config.request_timeout,
            access_token=getattr(config, "backend_access_token", ""),
            username=getattr(config, "backend_username", ""),
            password=getattr(config, "backend_password", ""),
            deepseek_enable_thinking=bool(getattr(config, "deepseek_enable_thinking", True)),
            deepseek_use_tool_calling=bool(getattr(config, "deepseek_use_tool_calling", True)),
        )

    def _plan_with_model(self, client, config, user_prompt: str, allow_dynamic_processing: bool):
        provider = (getattr(config, "provider", "") or "").strip().lower()
        if provider == "deepseek" and bool(getattr(config, "deepseek_use_tool_calling", True)):
            try:
                tool_result = client.call_plan_tool(
                    SYSTEM_PROMPT,
                    user_prompt,
                    self._plan_tool_schema(),
                )
                raw_response = json.dumps(tool_result.get("arguments") or {}, ensure_ascii=False)
                plan = self.registry.enforce_on_plan(
                    ActionPlan.from_dict(tool_result.get("arguments") or {}),
                    allow_dynamic_processing=allow_dynamic_processing,
                )
                return plan, raw_response, (tool_result.get("reasoning_content") or "").strip()
            except (LLMError, ValueError) as exc:
                fallback_warning = choose(
                    "DeepSeek tool calling 失败，回退到 JSON 规划: {}",
                    "DeepSeek tool calling failed and fell back to JSON planning: {}",
                ).format(exc)
                response = client.chat_with_metadata(SYSTEM_PROMPT, user_prompt)
                raw_response = response.get("content", "") or ""
                plan = self.registry.enforce_on_plan(
                    ActionPlan.from_dict(self._extract_json(raw_response)),
                    allow_dynamic_processing=allow_dynamic_processing,
                )
                reasoning_text = (response.get("reasoning_content") or "").strip()
                if fallback_warning:
                    reasoning_text = "{}\n{}".format(fallback_warning, reasoning_text).strip()
                return plan, raw_response, reasoning_text

        response = client.chat_with_metadata(SYSTEM_PROMPT, user_prompt)
        raw_response = response.get("content", "") or ""
        plan = self.registry.enforce_on_plan(
            ActionPlan.from_dict(self._extract_json(raw_response)),
            allow_dynamic_processing=allow_dynamic_processing,
        )
        return plan, raw_response, (response.get("reasoning_content") or "").strip()

    def _plan_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "submit_plan",
                "description": "Return the final structured QGIS action plan for the user request.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "requires_confirmation": {"type": "boolean"},
                        "response_text": {"type": "string"},
                        "notes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "source": {"type": "string"},
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "kind": {"type": "string", "enum": ["processing", "qgis"]},
                                    "label": {"type": "string"},
                                    "tool_id": {"type": "string"},
                                    "params": {"type": "object"},
                                    "operation": {"type": "string"},
                                    "args": {"type": "object"},
                                },
                                "required": ["kind"],
                            },
                        },
                    },
                    "required": ["summary", "requires_confirmation", "steps", "response_text", "notes", "source"],
                },
            },
        }

    def _extract_json(self, raw_text: str) -> dict:
        text = (raw_text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise ValueError(choose("模型没有返回合法 JSON。", "The model did not return valid JSON."))
        return json.loads(text[start : end + 1])

    def _truncate(self, text: str, max_length: int) -> str:
        text = re.sub(r"\s+", " ", (text or "").strip())
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."
