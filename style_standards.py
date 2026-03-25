import json
import os


class StyleStandardRegistry:
    def __init__(self, standards_dir: str = ""):
        self._standards_dir = standards_dir or os.path.join(os.path.dirname(__file__), "standards")
        self._cache = None

    def load_all(self):
        if self._cache is not None:
            return self._cache
        standards = []
        if os.path.isdir(self._standards_dir):
            for name in sorted(os.listdir(self._standards_dir)):
                if not name.lower().endswith(".json"):
                    continue
                path = os.path.join(self._standards_dir, name)
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                standards.append(data)
        self._cache = standards
        return self._cache

    def invalidate(self):
        self._cache = None

    def find_standard(self, text: str):
        lowered = (text or "").strip().lower()
        for standard in self.load_all():
            tokens = [standard.get("standard_id", ""), standard.get("name", "")]
            tokens.extend(standard.get("aliases", []))
            if any(token and token.lower() in lowered for token in tokens):
                return standard
        return None

    def find_style_set(self, standard_id: str, text: str):
        lowered = (text or "").strip().lower()
        standard = self.get_standard(standard_id)
        if standard is None:
            return None
        for style_set in standard.get("style_sets", []):
            tokens = [style_set.get("id", ""), style_set.get("name", "")]
            tokens.extend(style_set.get("aliases", []))
            if any(token and token.lower() in lowered for token in tokens):
                return style_set
        return None

    def find_style_set_global(self, text: str):
        lowered = (text or "").strip().lower()
        for standard in self.load_all():
            for style_set in standard.get("style_sets", []):
                tokens = [style_set.get("id", ""), style_set.get("name", "")]
                tokens.extend(style_set.get("aliases", []))
                if any(token and token.lower() in lowered for token in tokens):
                    return standard, style_set
        return None, None

    def get_standard(self, standard_id: str):
        key = (standard_id or "").strip()
        for standard in self.load_all():
            if standard.get("standard_id", "") == key:
                return standard
        return None

    def get_style_set(self, standard_id: str, style_set_id: str):
        standard = self.get_standard(standard_id)
        if standard is None:
            return None
        key = (style_set_id or "").strip()
        for style_set in standard.get("style_sets", []):
            if style_set.get("id", "") == key:
                return style_set
        return None

    def catalog_text(self) -> str:
        lines = ["可用标准样式包:"]
        for standard in self.load_all():
            lines.append("- {} ({})".format(standard.get("name", ""), standard.get("standard_id", "")))
            for style_set in standard.get("style_sets", []):
                lines.append("  - {} ({})".format(style_set.get("name", ""), style_set.get("id", "")))
        return "\n".join(lines)
