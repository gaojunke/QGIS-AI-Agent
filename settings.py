import json
from dataclasses import dataclass

from qgis.PyQt.QtCore import QSettings


SETTINGS_PREFIX = "nl_qgis_agent"
CHAT_HISTORY_LIMIT = 80
RECENT_OPERATIONS_LIMIT = 20


@dataclass
class PluginSettings:
    provider: str = "none"
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""
    request_timeout: int = 90
    auto_execute: bool = False
    require_confirmation: bool = True
    chat_mode: str = "auto"
    skill_text: str = ""
    mcp_servers_text: str = ""
    backend_username: str = ""
    backend_password: str = ""
    backend_access_token: str = ""
    allow_dynamic_processing: bool = False
    deepseek_enable_thinking: bool = True
    deepseek_use_tool_calling: bool = True


class SettingsManager:
    _session_secrets = {
        "api_key": "",
        "backend_password": "",
        "backend_access_token": "",
    }

    def __init__(self):
        self._settings = QSettings()

    def load(self) -> PluginSettings:
        return PluginSettings(
            provider=self._value("provider", "none"),
            base_url=self._value("base_url", ""),
            api_key=self._secret_value("api_key"),
            model_name=self._value("model_name", ""),
            request_timeout=int(self._value("request_timeout", 90)),
            auto_execute=self._bool_value("auto_execute", False),
            require_confirmation=self._bool_value("require_confirmation", True),
            chat_mode=self._value("chat_mode", "auto"),
            skill_text=self._value("skill_text", ""),
            mcp_servers_text=self._value("mcp_servers_text", ""),
            backend_username=self._value("backend_username", ""),
            backend_password=self._secret_value("backend_password"),
            backend_access_token=self._secret_value("backend_access_token"),
            allow_dynamic_processing=self._bool_value("allow_dynamic_processing", False),
            deepseek_enable_thinking=self._bool_value("deepseek_enable_thinking", True),
            deepseek_use_tool_calling=self._bool_value("deepseek_use_tool_calling", True),
        )

    def save(self, config: PluginSettings) -> None:
        self._settings.setValue(self._key("provider"), config.provider)
        self._settings.setValue(self._key("base_url"), config.base_url)
        self._settings.setValue(self._key("model_name"), config.model_name)
        self._settings.setValue(self._key("request_timeout"), int(config.request_timeout))
        self._settings.setValue(self._key("auto_execute"), bool(config.auto_execute))
        self._settings.setValue(self._key("require_confirmation"), bool(config.require_confirmation))
        self._settings.setValue(self._key("chat_mode"), config.chat_mode)
        self._settings.setValue(self._key("skill_text"), config.skill_text or "")
        self._settings.setValue(self._key("mcp_servers_text"), config.mcp_servers_text or "")
        self._settings.setValue(self._key("backend_username"), config.backend_username or "")
        self._settings.setValue(self._key("allow_dynamic_processing"), bool(config.allow_dynamic_processing))
        self._settings.setValue(self._key("deepseek_enable_thinking"), bool(config.deepseek_enable_thinking))
        self._settings.setValue(self._key("deepseek_use_tool_calling"), bool(config.deepseek_use_tool_calling))
        self._remember_secret("api_key", config.api_key)
        self._remember_secret("backend_password", config.backend_password)
        self._remember_secret("backend_access_token", config.backend_access_token)

    def load_chat_history(self) -> list:
        return self._load_json_list("chat_history")

    def save_chat_history(self, items: list) -> None:
        self._save_json_list("chat_history", items[-CHAT_HISTORY_LIMIT:])

    def load_recent_operations(self) -> list:
        return self._load_json_list("recent_operations")

    def save_recent_operations(self, items: list) -> None:
        self._save_json_list("recent_operations", items[-RECENT_OPERATIONS_LIMIT:])

    def _key(self, name: str) -> str:
        return "{}/{}".format(SETTINGS_PREFIX, name)

    def _value(self, name: str, default):
        return self._settings.value(self._key(name), default)

    def _secret_value(self, name: str) -> str:
        return str(self._session_secrets.get(name, "") or "")

    def _remember_secret(self, name: str, value: str) -> None:
        self._session_secrets[name] = (value or "").strip()

    def _bool_value(self, name: str, default: bool) -> bool:
        raw = self._settings.value(self._key(name), default)
        if isinstance(raw, bool):
            return raw
        if raw is None:
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def _load_json_list(self, name: str) -> list:
        raw = self._settings.value(self._key(name), "[]")
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_json_list(self, name: str, items: list) -> None:
        self._settings.setValue(self._key(name), json.dumps(items, ensure_ascii=False))
