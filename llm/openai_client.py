from .base import LLMClientBase, LLMError


class OpenAICompatibleClient(LLMClientBase):
    def __init__(self, base_url: str, model_name: str, api_key: str = "", timeout: int = 90, force_json_output: bool = False):
        super().__init__(base_url=base_url, model_name=model_name, api_key=api_key, timeout=timeout)
        self.force_json_output = force_json_output

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self.base_url or not self.model_name:
            raise LLMError("OpenAI-compatible provider requires base URL and model name.")

        url = "{}/chat/completions".format(self.base_url)
        headers = {
            "Content-Type": "application/json",
        }
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
        if self.force_json_output:
            payload["response_format"] = {"type": "json_object"}
        data = self._post_json(url, payload, headers)
        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
            if isinstance(content, list):
                return "".join(part.get("text", "") for part in content if isinstance(part, dict))
            return content
        except Exception as exc:
            raise LLMError("Unexpected OpenAI-compatible response: {}".format(exc))

    def list_models(self) -> list:
        if not self.base_url:
            raise LLMError("OpenAI-compatible provider requires base URL.")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer {}".format(self.api_key)
        data = self._get_json("{}/models".format(self.base_url), headers)
        models = []
        for item in data.get("data", []):
            model_id = item.get("id")
            if model_id:
                models.append(str(model_id))
        return models
