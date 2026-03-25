import json

from .base import LLMError
from .openai_client import OpenAICompatibleClient


class DeepSeekClient(OpenAICompatibleClient):
    def __init__(
        self,
        base_url: str,
        model_name: str,
        api_key: str = "",
        timeout: int = 90,
        force_json_output: bool = True,
        enable_thinking: bool = True,
        use_tool_calling: bool = True,
    ):
        super().__init__(base_url=base_url, model_name=model_name, api_key=api_key, timeout=timeout, force_json_output=force_json_output)
        self.enable_thinking = enable_thinking
        self.use_tool_calling = use_tool_calling

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        return self.chat_with_metadata(system_prompt, user_prompt).get("content", "")

    def chat_with_metadata(self, system_prompt: str, user_prompt: str) -> dict:
        data = self._chat_completion_payload(
            system_prompt,
            user_prompt,
            enable_thinking=self.enable_thinking,
        )
        message = self._extract_message(data)
        return {
            "content": self._message_text(message),
            "reasoning_content": self._message_reasoning(message),
            "tool_calls": message.get("tool_calls") or [],
        }

    def call_plan_tool(self, system_prompt: str, user_prompt: str, tool_schema: dict) -> dict:
        if not self.use_tool_calling:
            raise LLMError("当前 DeepSeek 配置未启用 tool calling。")
        data = self._chat_completion_payload(
            system_prompt,
            user_prompt,
            tools=[tool_schema],
            tool_choice={"type": "function", "function": {"name": tool_schema["function"]["name"]}},
            enable_thinking=self.enable_thinking,
        )
        message = self._extract_message(data)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            raise LLMError("DeepSeek 没有返回 tool call。")
        arguments = tool_calls[0].get("function", {}).get("arguments", "")
        if not arguments:
            raise LLMError("DeepSeek tool call 缺少 arguments。")
        try:
            parsed = json.loads(arguments)
        except Exception as exc:
            raise LLMError("DeepSeek tool call arguments 不是合法 JSON: {}".format(exc))
        return {
            "arguments": parsed,
            "reasoning_content": self._message_reasoning(message),
            "content": self._message_text(message),
        }

    def _chat_completion_payload(self, system_prompt: str, user_prompt: str, tools=None, tool_choice=None, enable_thinking: bool = True):
        if not self.base_url or not self.model_name:
            raise LLMError("DeepSeek provider requires base URL and model name.")
        url = "{}/chat/completions".format(self.base_url)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer {}".format(self.api_key)

        payload = {
            "model": self.model_name,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.force_json_output and tools is None:
            payload["response_format"] = {"type": "json_object"}
        if enable_thinking:
            payload["thinking"] = {"type": "enabled"}
        if tools:
            payload["tools"] = [{"type": "function", "function": tool["function"]} for tool in tools]
        if tool_choice:
            payload["tool_choice"] = tool_choice
        return self._post_json(url, payload, headers)

    def _extract_message(self, data: dict):
        try:
            return data["choices"][0]["message"]
        except Exception as exc:
            raise LLMError("Unexpected DeepSeek response: {}".format(exc))

    def _message_text(self, message: dict) -> str:
        content = message.get("content")
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return content or ""

    def _message_reasoning(self, message: dict) -> str:
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, list):
            return "".join(part.get("text", "") for part in reasoning if isinstance(part, dict))
        return reasoning or ""
