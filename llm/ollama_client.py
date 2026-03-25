from .base import LLMClientBase, LLMError


class OllamaClient(LLMClientBase):
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self.base_url or not self.model_name:
            raise LLMError("Ollama provider requires base URL and model name.")

        url = "{}/api/chat".format(self.base_url)
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": 0.1,
            },
        }
        data = self._post_json(url, payload, headers)
        try:
            return data["message"]["content"]
        except Exception as exc:
            raise LLMError("Unexpected Ollama response: {}".format(exc))

    def list_models(self) -> list:
        if not self.base_url:
            raise LLMError("Ollama provider requires base URL.")
        data = self._get_json("{}/api/tags".format(self.base_url), {"Content-Type": "application/json"})
        models = []
        for item in data.get("models", []):
            model_name = item.get("name")
            if model_name:
                models.append(str(model_name))
        return models
