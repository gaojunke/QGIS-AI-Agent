import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class McpBridgeService:
    def fetch_contexts(self, endpoints_text: str, command_text: str, project_context: dict, conversation_memory: dict = None, timeout: int = 30):
        contexts = []
        warnings = []
        for url in self._parse_urls(endpoints_text):
            try:
                payload = {
                    "command": command_text,
                    "project_context": project_context,
                    "conversation_memory": conversation_memory or {},
                }
                request = Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=timeout) as response:
                    raw_body = response.read().decode("utf-8", errors="ignore")
                text = self._extract_context_text(raw_body)
                if text:
                    contexts.append({"url": url, "text": text})
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                warnings.append("MCP bridge 请求失败 [{}]: HTTP {} {}".format(url, exc.code, body or exc.reason))
            except URLError as exc:
                warnings.append("MCP bridge 连接失败 [{}]: {}".format(url, exc.reason))
            except Exception as exc:
                warnings.append("MCP bridge 处理失败 [{}]: {}".format(url, exc))
        return contexts, warnings

    def _parse_urls(self, endpoints_text: str):
        urls = []
        for line in (endpoints_text or "").splitlines():
            cleaned = line.strip()
            if cleaned and cleaned not in urls:
                urls.append(cleaned)
        return urls[:6]

    def _extract_context_text(self, raw_body: str) -> str:
        text = (raw_body or "").strip()
        if not text:
            return ""
        try:
            data = json.loads(text)
        except Exception:
            return text[:4000]

        if isinstance(data, dict):
            for key in ("context", "text", "summary", "content"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:4000]
            if "data" in data:
                return json.dumps(data["data"], ensure_ascii=False)[:4000]

        if isinstance(data, list):
            return json.dumps(data, ensure_ascii=False)[:4000]

        return text[:4000]
