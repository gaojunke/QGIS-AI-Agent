from qgis.PyQt.QtCore import QObject, QThread, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..llm import create_client, default_base_url, default_model, normalize_base_url
from ..llm.base import LLMError
from ..i18n import choose
from ..settings import PluginSettings


class SettingsNetworkWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.finished.emit(self._fn())
        except Exception as exc:
            self.failed.emit(exc)


class SettingsDialog(QDialog):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle(choose("QGIS AI 助手设置", "QGIS AI Agent Settings"))
        self.resize(640, 520)
        self.worker_thread = None
        self.worker = None

        config = self.settings_manager.load()

        self.provider_combo = QComboBox()
        self.provider_combo.addItem(choose("禁用", "Disabled"), "none")
        self.provider_combo.addItem(choose("托管后端", "Managed Backend"), "managed_backend")
        self.provider_combo.addItem("DeepSeek", "deepseek")
        self.provider_combo.addItem("Gemini", "gemini")
        self.provider_combo.addItem("OpenAI Compatible", "openai_compatible")
        self.provider_combo.addItem("Ollama", "ollama")
        self._set_combo_value(config.provider)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        self.base_url_edit = QLineEdit(normalize_base_url(config.provider, config.base_url))
        self.api_key_edit = QLineEdit(config.api_key)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.backend_username_edit = QLineEdit(config.backend_username or "")
        self.backend_password_edit = QLineEdit(config.backend_password or "")
        self.backend_password_edit.setEchoMode(QLineEdit.Password)
        self.backend_token_edit = QLineEdit(config.backend_access_token or "")
        self.backend_token_edit.setEchoMode(QLineEdit.Password)
        self.backend_token_edit.setReadOnly(True)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        self.model_combo.setMinimumWidth(260)
        if config.model_name:
            self.model_combo.addItem(config.model_name, config.model_name)

        self.fetch_models_button = QPushButton(choose("获取模型", "Fetch Models"))
        self.fetch_models_button.clicked.connect(self.fetch_models)
        self.login_button = QPushButton(choose("登录后端", "Backend Login"))
        self.login_button.clicked.connect(self.login_backend)
        self.test_button = QPushButton(choose("测试连接", "Test Connection"))
        self.test_button.clicked.connect(self.test_connection)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 600)
        self.timeout_spin.setValue(config.request_timeout)
        self.allow_dynamic_processing_check = QCheckBox(choose("允许调用当前 QGIS 中其他已安装算法（高级模式）", "Allow additional installed QGIS algorithms (advanced mode)"))
        self.allow_dynamic_processing_check.setChecked(bool(config.allow_dynamic_processing))
        self.deepseek_thinking_check = QCheckBox(choose("启用 DeepSeek thinking", "Enable DeepSeek thinking"))
        self.deepseek_thinking_check.setChecked(bool(config.deepseek_enable_thinking))
        self.deepseek_tool_calling_check = QCheckBox(choose("启用 DeepSeek tool calling", "Enable DeepSeek tool calling"))
        self.deepseek_tool_calling_check.setChecked(bool(config.deepseek_use_tool_calling))

        self.chat_mode_combo = QComboBox()
        self.chat_mode_combo.addItem(choose("自动", "Auto"), "auto")
        self.chat_mode_combo.addItem(choose("问答", "Q&A"), "qa")
        self.chat_mode_combo.addItem(choose("执行", "Execute"), "execute")
        self._set_chat_mode(config.chat_mode)

        self.skill_edit = QTextEdit(config.skill_text or "")
        self.skill_edit.setPlaceholderText(choose("可选：填写你希望模型长期遵守的 skill，例如土地整治、国土调查、林业专题、企业内部规范等。", "Optional: add long-term skills or domain rules for the model, such as land consolidation, cadastral survey, forestry topics, or internal standards."))
        self.skill_edit.setMinimumHeight(110)

        self.mcp_edit = QTextEdit(config.mcp_servers_text or "")
        self.mcp_edit.setPlaceholderText(
            choose(
                "可选：每行一个 MCP bridge URL。\n插件会在规划前向这些 URL 发送 POST JSON，取回上下文再交给模型。",
                "Optional: one MCP bridge URL per line.\nThe plugin will POST JSON to these URLs before planning and merge the returned context into the model prompt.",
            )
        )
        self.mcp_edit.setMinimumHeight(90)

        self.status_label = QLabel(choose("填写地址和 API Key 后，可先测试连接，再选择模型。", "After filling in the URL and API key, test the connection first and then choose a model."))
        self.status_label.setWordWrap(True)
        self.secret_hint_label = QLabel(choose("API Key、后端密码和访问令牌仅保留在本次 QGIS 会话中，不再写入本地配置。", "API keys, backend passwords, and access tokens are kept only for the current QGIS session and are not written to local settings."))
        self.secret_hint_label.setWordWrap(True)

        model_row = QWidget()
        model_layout = QHBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.addWidget(self.model_combo, 1)
        model_layout.addWidget(self.fetch_models_button)
        model_layout.addWidget(self.login_button)
        model_layout.addWidget(self.test_button)

        form_layout = QFormLayout()
        form_layout.addRow(choose("服务提供方", "Provider"), self.provider_combo)
        form_layout.addRow("Base URL", self.base_url_edit)
        form_layout.addRow("API Key", self.api_key_edit)
        form_layout.addRow(choose("后端用户名", "Backend Username"), self.backend_username_edit)
        form_layout.addRow(choose("后端密码", "Backend Password"), self.backend_password_edit)
        form_layout.addRow(choose("后端令牌", "Backend Token"), self.backend_token_edit)
        form_layout.addRow(choose("模型", "Model"), model_row)
        form_layout.addRow(choose("超时（秒）", "Timeout (s)"), self.timeout_spin)
        form_layout.addRow(choose("高级选项", "Advanced"), self.allow_dynamic_processing_check)
        form_layout.addRow("DeepSeek", self.deepseek_thinking_check)
        form_layout.addRow("", self.deepseek_tool_calling_check)
        form_layout.addRow(choose("默认模式", "Default Mode"), self.chat_mode_combo)
        form_layout.addRow("Skills", self.skill_edit)
        form_layout.addRow("MCP Bridge URLs", self.mcp_edit)
        form_layout.addRow(choose("状态", "Status"), self.status_label)
        form_layout.addRow(choose("安全说明", "Security"), self.secret_hint_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

        self._on_provider_changed()
        if config.model_name:
            self._set_model(config.model_name)

    def accept(self):
        provider = self.provider_combo.currentData()
        base_url = normalize_base_url(provider, self.base_url_edit.text().strip())
        model_name = self.current_model_name()
        base_url = base_url or default_base_url(provider)
        model_name = model_name or default_model(provider)

        config = PluginSettings(
            provider=provider,
            base_url=base_url,
            api_key=self.api_key_edit.text().strip(),
            model_name=model_name,
            request_timeout=int(self.timeout_spin.value()),
            auto_execute=True,
            require_confirmation=True,
            chat_mode=self.chat_mode_combo.currentData(),
            skill_text=self.skill_edit.toPlainText().strip(),
            mcp_servers_text=self.mcp_edit.toPlainText().strip(),
            backend_username=self.backend_username_edit.text().strip(),
            backend_password=self.backend_password_edit.text().strip(),
            backend_access_token=self.backend_token_edit.text().strip(),
            allow_dynamic_processing=bool(self.allow_dynamic_processing_check.isChecked()),
            deepseek_enable_thinking=bool(self.deepseek_thinking_check.isChecked()),
            deepseek_use_tool_calling=bool(self.deepseek_tool_calling_check.isChecked()),
        )
        if provider == "managed_backend" and not config.backend_access_token:
            QMessageBox.warning(self, choose("缺少登录信息", "Missing Login"), choose("托管后端模式需要先点击“登录后端”，成功后再保存。", "Managed backend mode requires clicking 'Backend Login' first. Save settings after a successful login."))
            return
        if provider in {"deepseek", "gemini", "openai_compatible"} and not config.api_key:
            QMessageBox.warning(self, choose("缺少 API Key", "Missing API Key"), choose("当前 Provider 需要填写 API Key。", "The current provider requires an API key."))
            return
        if provider != "none" and not config.base_url:
            QMessageBox.warning(self, choose("缺少地址", "Missing URL"), choose("请填写 Base URL。", "Please fill in the Base URL."))
            return
        if provider != "none" and not config.model_name:
            QMessageBox.warning(self, choose("缺少模型", "Missing Model"), choose("请先获取模型并选择一个模型。", "Please fetch models and select one first."))
            return
        self.settings_manager.save(config)
        super().accept()

    def fetch_models(self):
        provider = self.provider_combo.currentData()
        if provider == "none":
            self._set_status(choose("当前为 Disabled，无需获取模型。", "Provider is Disabled. No need to fetch models."))
            return
        self._run_network_task(
            lambda: self._build_client(require_model=False).list_models(),
            on_success=lambda models, current_provider=provider: self._on_models_loaded(current_provider, models),
            on_error=lambda exc: self._show_network_error(choose("获取模型失败", "Failed to Fetch Models"), exc),
            busy_text=choose("正在获取模型...", "Fetching models..."),
        )

    def test_connection(self):
        provider = self.provider_combo.currentData()
        if provider == "none":
            self._set_status(choose("Disabled 模式下不需要测试连接。", "No connection test is needed in Disabled mode."))
            return
        self._run_network_task(
            lambda: self._build_client(require_model=False).test_connection(),
            on_success=lambda result, current_provider=provider: self._on_connection_tested(current_provider, result),
            on_error=lambda exc: self._show_network_error(choose("连接失败", "Connection Failed"), exc),
            busy_text=choose("正在测试连接...", "Testing connection..."),
        )

    def login_backend(self):
        provider = self.provider_combo.currentData()
        if provider != "managed_backend":
            self._set_status(choose("只有托管后端模式需要登录。", "Only managed backend mode requires login."))
            return
        self._run_network_task(
            lambda: self._build_client(require_model=False).login(),
            on_success=self._on_backend_logged_in,
            on_error=lambda exc: self._show_network_error(choose("登录失败", "Login Failed"), exc),
            busy_text=choose("正在登录后端...", "Logging in to backend..."),
        )

    def current_model_name(self) -> str:
        return (self.model_combo.currentData() or self.model_combo.currentText() or "").strip()

    def _build_client(self, require_model: bool):
        provider = self.provider_combo.currentData()
        base_url = normalize_base_url(provider, self.base_url_edit.text().strip())
        api_key = self.api_key_edit.text().strip()
        model_name = self.current_model_name()
        if provider in {"deepseek", "gemini", "openai_compatible"} and not api_key:
            raise LLMError(choose("请先填写 API Key。", "Please fill in the API key first."))
        if not base_url:
            raise LLMError(choose("请先填写 Base URL。", "Please fill in the Base URL first."))
        if require_model and not model_name:
            raise LLMError(choose("请先选择模型。", "Please select a model first."))
        return create_client(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=int(self.timeout_spin.value()),
            access_token=self.backend_token_edit.text().strip(),
            username=self.backend_username_edit.text().strip(),
            password=self.backend_password_edit.text().strip(),
            deepseek_enable_thinking=bool(self.deepseek_thinking_check.isChecked()),
            deepseek_use_tool_calling=bool(self.deepseek_tool_calling_check.isChecked()),
        )

    def _on_provider_changed(self):
        provider = self.provider_combo.currentData()
        default_url = default_base_url(provider)
        if default_url:
            self.base_url_edit.setPlaceholderText(default_url)
            if not self.base_url_edit.text().strip():
                self.base_url_edit.setText(default_url)
        else:
            self.base_url_edit.setPlaceholderText("")

        is_managed_backend = provider == "managed_backend"
        self.api_key_edit.setEnabled(provider in {"deepseek", "gemini", "openai_compatible"})
        self.backend_username_edit.setEnabled(is_managed_backend)
        self.backend_password_edit.setEnabled(is_managed_backend)
        self.backend_token_edit.setEnabled(is_managed_backend)
        self.model_combo.setEnabled(provider != "none")
        self.fetch_models_button.setEnabled(provider != "none")
        self.test_button.setEnabled(provider != "none")
        self.login_button.setEnabled(is_managed_backend)
        is_deepseek = provider == "deepseek"
        self.deepseek_thinking_check.setEnabled(is_deepseek)
        self.deepseek_tool_calling_check.setEnabled(is_deepseek)

    def _set_status(self, text: str):
        self.status_label.setText(text)

    def _set_network_busy(self, busy: bool, text: str = ""):
        if busy and text:
            self._set_status(text)
        self.provider_combo.setEnabled(not busy)
        self.model_combo.setEnabled((not busy) and self.provider_combo.currentData() != "none")
        self.fetch_models_button.setEnabled((not busy) and self.provider_combo.currentData() != "none")
        self.test_button.setEnabled((not busy) and self.provider_combo.currentData() != "none")
        self.login_button.setEnabled((not busy) and self.provider_combo.currentData() == "managed_backend")
        is_deepseek = self.provider_combo.currentData() == "deepseek"
        self.deepseek_thinking_check.setEnabled((not busy) and is_deepseek)
        self.deepseek_tool_calling_check.setEnabled((not busy) and is_deepseek)

    def _run_network_task(self, fn, on_success, on_error, busy_text: str):
        if self.worker_thread is not None:
            return
        self._set_network_busy(True, busy_text)
        self.worker_thread = QThread(self)
        self.worker = SettingsNetworkWorker(fn)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(on_success)
        self.worker.failed.connect(on_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_network_worker)
        self.worker_thread.start()

    def _cleanup_network_worker(self):
        self._set_network_busy(False)
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
            self.worker_thread = None

    def _on_models_loaded(self, provider: str, models: list):
        if provider != self.provider_combo.currentData():
            return
        if not models:
            self._set_status(choose("连接成功，但没有返回可用模型。", "Connection succeeded, but no available models were returned."))
            return
        self.model_combo.clear()
        for model in models:
            self.model_combo.addItem(model, model)
        preferred = default_model(provider)
        if preferred and preferred in models:
            self._set_model(preferred)
        self._set_status(choose("获取模型成功，共 {} 个。", "Fetched models successfully. Total: {}.").format(len(models)))

    def _on_connection_tested(self, provider: str, result: dict):
        if provider != self.provider_combo.currentData():
            return
        models = result.get("models") or []
        if models and self.model_combo.count() == 0:
            for model in models:
                self.model_combo.addItem(model, model)
            preferred = default_model(provider)
            if preferred and preferred in models:
                self._set_model(preferred)
        selected = self.current_model_name() or (models[0] if models else "")
        message = result.get("message", choose("连接成功。", "Connection successful."))
        if selected:
            message = choose("{} 当前模型: {}", "{} Current model: {}").format(message, selected)
        self._set_status(message)
        QMessageBox.information(self, choose("连接成功", "Connection Successful"), message)

    def _on_backend_logged_in(self, token: str):
        self.backend_token_edit.setText(token)
        self._set_status(choose("后端登录成功，可继续获取模型或测试连接。", "Backend login successful. You can now fetch models or test the connection."))
        QMessageBox.information(self, choose("登录成功", "Login Successful"), choose("后端登录成功。", "Backend login successful."))

    def _show_network_error(self, title: str, exc: Exception):
        self._set_status("{}: {}".format(title, exc))
        QMessageBox.warning(self, title, str(exc))

    def _set_combo_value(self, value: str):
        for index in range(self.provider_combo.count()):
            if self.provider_combo.itemData(index) == value:
                self.provider_combo.setCurrentIndex(index)
                return

    def _set_model(self, model_name: str):
        for index in range(self.model_combo.count()):
            if self.model_combo.itemData(index) == model_name:
                self.model_combo.setCurrentIndex(index)
                return
        self.model_combo.addItem(model_name, model_name)
        self.model_combo.setCurrentIndex(self.model_combo.count() - 1)

    def _set_chat_mode(self, mode: str):
        for index in range(self.chat_mode_combo.count()):
            if self.chat_mode_combo.itemData(index) == mode:
                self.chat_mode_combo.setCurrentIndex(index)
                return
