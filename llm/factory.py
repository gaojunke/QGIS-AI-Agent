from .base import LLMError
from .deepseek_client import DeepSeekClient
from .gemini_client import GeminiClient
from .managed_backend_client import ManagedBackendClient
from .ollama_client import OllamaClient
from .openai_client import OpenAICompatibleClient


def default_base_url(provider: str) -> str:
    if provider == "deepseek":
        return "https://api.deepseek.com"
    if provider == "gemini":
        return "https://generativelanguage.googleapis.com/v1beta/openai/"
    if provider == "ollama":
        return "http://localhost:11434"
    if provider == "managed_backend":
        return "http://107.173.127.167:8000"
    return ""


def default_model(provider: str) -> str:
    if provider == "deepseek":
        return "deepseek-chat"
    if provider == "gemini":
        return "gemini-3-flash-preview"
    return ""


def normalize_base_url(provider: str, base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if not url:
        return default_base_url(provider)

    for suffix in ("/chat/completions", "/models", "/api/tags"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]

    if provider == "deepseek" and url.endswith("/v1"):
        url = url[:-3]

    return url.rstrip("/")


def create_client(
    provider: str,
    base_url: str,
    api_key: str,
    model_name: str,
    timeout: int,
    access_token: str = "",
    username: str = "",
    password: str = "",
    deepseek_enable_thinking: bool = True,
    deepseek_use_tool_calling: bool = True,
):
    provider = (provider or "").strip()
    base_url = normalize_base_url(provider, base_url)
    model_name = (model_name or "").strip() or default_model(provider)

    if provider == "deepseek":
        return DeepSeekClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
            force_json_output=True,
            enable_thinking=deepseek_enable_thinking,
            use_tool_calling=deepseek_use_tool_calling,
        )

    if provider == "ollama":
        return OllamaClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
        )

    if provider == "managed_backend":
        return ManagedBackendClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
            access_token=access_token,
            username=username,
            password=password,
        )

    if provider == "gemini":
        return GeminiClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
        )

    if provider in {"openai_compatible"}:
        return OpenAICompatibleClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
            force_json_output=(provider == "deepseek"),
        )

    raise LLMError("Unsupported provider: {}".format(provider))
