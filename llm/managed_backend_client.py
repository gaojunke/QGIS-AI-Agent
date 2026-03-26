from ..i18n import choose
from .base import LLMClientBase, LLMError


class ManagedBackendClient(LLMClientBase):
    def __init__(
        self,
        base_url: str,
        model_name: str,
        api_key: str = "",
        timeout: int = 90,
        access_token: str = "",
        username: str = "",
        password: str = "",
    ):
        super().__init__(base_url=base_url, model_name=model_name, api_key=api_key, timeout=timeout)
        self.access_token = access_token or api_key
        self.username = username
        self.password = password

    def login(self) -> str:
        if not self.base_url:
            raise LLMError("Managed backend provider requires base URL.")
        if not self.username or not self.password:
            raise LLMError(choose("请先填写后端账号和密码。", "Please fill in the backend username and password first."))

        data = self._post_json(
            "{}/api/auth/login".format(self.base_url),
            {"username": self.username, "password": self.password},
            {"Content-Type": "application/json"},
        )
        token = str(data.get("access_token", "")).strip()
        if not token:
            raise LLMError(choose("登录成功，但后端没有返回 access_token。", "Login succeeded, but the backend did not return an access_token."))
        self.access_token = token
        return token

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self.base_url or not self.model_name:
            raise LLMError("Managed backend provider requires base URL and model name.")
        token = self._require_token()
        data = self._post_json(
            "{}/api/chat/completions".format(self.base_url),
            {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
            },
            self._auth_headers(token),
        )
        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
            if isinstance(content, list):
                return "".join(part.get("text", "") for part in content if isinstance(part, dict))
            return content
        except Exception as exc:
            raise LLMError("Unexpected managed backend response: {}".format(exc))

    def list_models(self) -> list:
        if not self.base_url:
            raise LLMError("Managed backend provider requires base URL.")
        token = self._require_token()
        data = self._get_json("{}/api/models".format(self.base_url), self._auth_headers(token))
        models = []
        for item in data.get("data", []):
            model_id = item.get("id")
            if model_id:
                models.append(str(model_id))
        return models

    def test_connection(self) -> dict:
        token = self._require_token()
        data = self._get_json("{}/healthz".format(self.base_url), self._auth_headers(token))
        models = self.list_models()
        return {
            "ok": bool(data.get("ok", True)),
            "message": data.get("message", choose("后端连接成功。", "Backend connection successful.")),
            "models": models,
        }

    def _require_token(self) -> str:
        token = (self.access_token or "").strip()
        if token:
            return token
        if self.username and self.password:
            return self.login()
        raise LLMError(choose("请先登录后端，或提供有效 access token。", "Please log in to the backend first, or provide a valid access token."))

    def _auth_headers(self, token: str) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(token),
        }
