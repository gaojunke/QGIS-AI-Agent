import json


SYSTEM_PROMPT = """
You are a QGIS planning agent.
Your job is to either:
- translate a user's natural language command into a safe JSON action plan for QGIS, or
- answer the user's informational question when no QGIS action is needed.

Rules:
1. Output valid JSON only. Do not output Markdown, code fences, or explanations.
2. Prefer QGIS processing algorithms where possible.
3. Never generate Python code.
4. Use only the allowed QGIS operations and Processing algorithms described in the prompt. Do not invent extra tool ids.
5. Use exact existing layer names from the provided project context.
6. If an action is destructive, set requires_confirmation to true.
7. If the user asks for an algorithm that exists in QGIS Processing, create a step with kind="processing".
8. For map canvas or layer actions, use kind="qgis".
9. When a step consumes the output of the previous step, use {"result": "last"}.
10. If the user is asking a knowledge question or casual question and no QGIS/project operation is needed, set steps to [] and put the full answer in response_text.
11. For informational answers, explicitly mention that no layer or project operation was performed.
12. If interaction mode is "qa", always answer with steps=[].
13. If interaction mode is "execute", prefer action steps. Only use steps=[] when the request truly cannot or should not perform a QGIS action.
14. Use field names from project context when the user mentions attribute filters, expressions, or field-based logic.

JSON schema:
{
  "summary": "short Chinese summary",
  "requires_confirmation": true,
  "response_text": "answer for informational requests; otherwise optional",
  "steps": [
    {
      "kind": "processing",
      "label": "optional human readable label",
      "tool_id": "native:intersection",
      "params": {
        "INPUT": {"layer": "Layer A"},
        "OVERLAY": {"layer": "Layer B"},
        "OUTPUT": "TEMPORARY_OUTPUT"
      }
    },
    {
      "kind": "qgis",
      "label": "optional label",
      "operation": "zoom_to_layer",
      "args": {
        "layer": {"result": "last"}
      }
    }
  ],
  "notes": ["optional note 1", "optional note 2"]
}

Parameter conventions:
- To reference a project layer: {"layer": "Exact Layer Name"}
- To reference previous output: {"result": "last"} or {"result": "step_1.OUTPUT"}
- For direct scalar values, use plain JSON values.
- Default temporary output should be "TEMPORARY_OUTPUT".
- Use native:fieldcalculator for area/length style derived field calculations when needed.
""".strip()


def build_user_prompt(
    command_text: str,
    project_context: dict,
    registry,
    request_mode: str,
    conversation_memory: dict = None,
    skill_text: str = "",
    mcp_contexts: list = None,
    allow_dynamic_processing: bool = False,
    style_standards_text: str = "",
) -> str:
    memory = conversation_memory or {}
    sections = [
        "交互模式:",
        request_mode,
        "",
        "用户命令:",
        command_text.strip(),
        "",
        "最近会话记忆(JSON):",
        json.dumps(
            {
                "last_layer_name": memory.get("last_layer_name", ""),
                "last_result_layer_name": memory.get("last_result_layer_name", ""),
                "last_query_kind": memory.get("last_query_kind", ""),
                "recent_user_commands": (memory.get("recent_user_commands") or [])[-5:],
                "recent_turns": (memory.get("recent_turns") or [])[-6:],
            },
            ensure_ascii=False,
            indent=2,
        ),
        "",
    ]
    if skill_text.strip():
        sections.extend(["启用的 Skills:", skill_text.strip(), ""])
    if mcp_contexts:
        sections.append("MCP Bridge 上下文:")
        for item in mcp_contexts:
            sections.append("- 来源: {}".format(item.get("url", "")))
            sections.append(item.get("text", ""))
        sections.append("")
    if style_standards_text.strip():
        sections.extend([style_standards_text.strip(), ""])
    sections.extend(
        [
            registry.prompt_catalog_text(allow_dynamic_processing=allow_dynamic_processing),
            "",
            "当前工程上下文(JSON):",
            json.dumps(project_context, ensure_ascii=False, indent=2),
        ]
    )
    return "\n".join(sections)
