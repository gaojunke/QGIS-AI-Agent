import glob
import importlib
import os
import sys

from ..i18n import choose
from .base import LLMClientBase, LLMError


class GeminiClient(LLMClientBase):
    def _import_openai(self):
        try:
            return importlib.import_module("openai")
        except Exception:
            pass

        for candidate in self._candidate_site_packages():
            if candidate not in sys.path and os.path.isdir(candidate):
                sys.path.append(candidate)
                try:
                    return importlib.import_module("openai")
                except Exception:
                    continue
        raise LLMError(choose("Gemini 依赖 openai SDK，但当前 QGIS Python 环境未能导入 openai。", "Gemini depends on the openai SDK, but the current QGIS Python environment could not import openai."))

    def _build_client(self):
        if not self.base_url or not self.model_name:
            raise LLMError("Gemini provider requires base URL and model name.")
        if not self.api_key:
            raise LLMError("Gemini provider requires API Key.")
        openai_module = self._import_openai()
        OpenAI = getattr(openai_module, "OpenAI", None)
        if OpenAI is None:
            raise LLMError(choose("当前 openai SDK 不包含 OpenAI 客户端，请升级 openai 包。", "The current openai SDK does not include the OpenAI client. Please upgrade the openai package."))
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url.rstrip("/") + "/",
            timeout=self.timeout,
        )

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        client = self._build_client()
        try:
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            message = response.choices[0].message
            content = getattr(message, "content", None)
            if isinstance(content, list):
                return "".join(getattr(part, "text", "") or part.get("text", "") for part in content)
            return content or ""
        except Exception as exc:
            raise LLMError(choose("Gemini chat 请求失败: {}", "Gemini chat request failed: {}").format(exc))

    def list_models(self) -> list:
        client = self._build_client()
        try:
            response = client.models.list()
            models = []
            for item in response.data:
                model_id = getattr(item, "id", "")
                if model_id:
                    models.append(str(model_id))
            return models
        except Exception as exc:
            raise LLMError(choose("Gemini 获取模型失败: {}", "Failed to fetch Gemini models: {}").format(exc))

    def _candidate_site_packages(self):
        candidates = []
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        app_data = os.environ.get("APPDATA", "")
        user_profile = os.environ.get("USERPROFILE", "")

        patterns = []
        if local_app_data:
            patterns.append(os.path.join(local_app_data, "Programs", "Python", "Python*", "Lib", "site-packages"))
        if app_data:
            patterns.append(os.path.join(app_data, "Python", "Python*", "site-packages"))
        if user_profile:
            patterns.append(os.path.join(user_profile, "AppData", "Local", "Programs", "Python", "Python*", "Lib", "site-packages"))

        for pattern in patterns:
            for path in glob.glob(pattern):
                if path not in candidates:
                    candidates.append(path)
        return candidates
