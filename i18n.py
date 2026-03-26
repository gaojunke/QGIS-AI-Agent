from qgis.PyQt.QtCore import QLocale, QSettings


def current_locale_name() -> str:
    settings = QSettings()
    locale_name = (settings.value("locale/userLocale", "") or "").strip()
    if locale_name:
        return locale_name
    return QLocale.system().name() or "en"


def is_chinese_locale() -> bool:
    return current_locale_name().lower().startswith("zh")


def ui_language_code() -> str:
    return "zh" if is_chinese_locale() else "en"


def preferred_language_name() -> str:
    return "Chinese" if is_chinese_locale() else "English"


def choose(zh_text: str, en_text: str) -> str:
    return zh_text if is_chinese_locale() else en_text
