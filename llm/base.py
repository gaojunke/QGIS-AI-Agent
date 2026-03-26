import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..i18n import choose


class LLMError(RuntimeError):
    pass


class LLMClientBase:
    def __init__(self, base_url: str, model_name: str, api_key: str = "", timeout: int = 90):
        self.base_url = (base_url or "").rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    def chat_with_metadata(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "content": self.chat(system_prompt, user_prompt),
            "reasoning_content": "",
            "tool_calls": [],
        }

    def call_plan_tool(self, system_prompt: str, user_prompt: str, tool_schema: dict) -> dict:
        raise LLMError(choose("当前模型客户端不支持 tool calling。", "The current model client does not support tool calling."))

    def list_models(self) -> list:
        raise NotImplementedError

    def test_connection(self) -> dict:
        models = self.list_models()
        return {
            "ok": True,
            "message": choose("连接成功，获取到 {} 个模型。", "Connection succeeded. Retrieved {} models.").format(len(models)),
            "models": models,
        }

    def _get_json(self, url: str, headers: dict) -> dict:
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise LLMError("HTTP {}: {}".format(exc.code, body or exc.reason))
        except URLError as exc:
            raise LLMError("Network error: {}".format(exc.reason))
        except Exception as exc:
            raise LLMError(str(exc))

    def _post_json(self, url: str, payload: dict, headers: dict) -> dict:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise LLMError("HTTP {}: {}".format(exc.code, body or exc.reason))
        except URLError as exc:
            raise LLMError("Network error: {}".format(exc.reason))
        except Exception as exc:
            raise LLMError(str(exc))
