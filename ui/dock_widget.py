from datetime import datetime

from qgis.PyQt.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QTextCursor
from qgis.PyQt.QtWidgets import QApplication, QComboBox, QDockWidget, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget
from qgis.core import QgsProject

from ..context import LocalQueryService, ProjectContextBuilder
from ..executor import AmbiguousLayerReferenceError, ExecutionCancelledError, MissingLayerReferenceError, PlanExecutor
from ..i18n import choose
from ..planner import CommandPlanner
from ..style_standards import StyleStandardRegistry
from ..tool_registry import ToolRegistry
from .chat_widgets import ChatInputEdit, ChatMessageList


class PlannerWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(object)
    cancelled = pyqtSignal()

    def __init__(self, planner, command_text: str, project_context: dict, config, request_mode: str, conversation_memory: dict):
        super().__init__()
        self.planner = planner
        self.command_text = command_text
        self.project_context = project_context
        self.config = config
        self.request_mode = request_mode
        self.conversation_memory = conversation_memory
        self.cancel_requested = False

    def run(self):
        try:
            if self.cancel_requested:
                self.cancelled.emit()
                return
            result = self.planner.plan(
                self.command_text,
                self.project_context,
                self.config,
                request_mode=self.request_mode,
                conversation_memory=self.conversation_memory,
            )
            if self.cancel_requested:
                self.cancelled.emit()
                return
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(exc)


class NlQgisDockWidget(QDockWidget):
    def __init__(self, iface, settings_manager, parent=None, open_settings_callback=None):
        super().__init__(choose("QGIS AI 助手", "QGIS AI Agent"), parent or iface.mainWindow())
        self.iface = iface
        self.settings_manager = settings_manager
        self.open_settings_callback = open_settings_callback
        self.registry = ToolRegistry()
        self.style_standards = StyleStandardRegistry()
        self.context_builder = ProjectContextBuilder()
        self.query_service = LocalQueryService()
        self.planner = CommandPlanner(self.registry, style_standards=self.style_standards)
        self.executor = PlanExecutor(iface, self.context_builder, self.registry, style_standards=self.style_standards)
        self.last_context = None
        self.chat_history = self.settings_manager.load_chat_history()
        self.pending_resolution = None
        self.planner_thread = None
        self.planner_worker = None
        self.pending_command_text = ""
        self.execution_cancel_requested = False
        self.status_item = None
        self._last_status_text = ""
        self.conversation_memory = {
            "recent_user_commands": [],
            "recent_turns": [],
            "last_layer_name": "",
            "last_result_layer_name": "",
            "last_query_kind": "",
        }

        self.setObjectName("NlQgisAgentDockWidget")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setMinimumWidth(460)

        container = QWidget(self)
        self.setWidget(container)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(choose("自动", "Auto"), "auto")
        self.mode_combo.addItem(choose("问答", "Q&A"), "qa")
        self.mode_combo.addItem(choose("执行", "Execute"), "execute")
        self._set_mode_value(self.settings_manager.load().chat_mode)
        self.mode_combo.currentIndexChanged.connect(self._persist_mode)

        self.recent_button = QPushButton(choose("最近操作", "Recent"))
        self.recent_button.clicked.connect(self.show_recent_operations)
        self.settings_button = QPushButton(choose("API设置", "API Settings"))
        self.settings_button.clicked.connect(self.open_settings_dialog)
        self.clear_button = QPushButton(choose("清空聊天", "Clear Chat"))
        self.clear_button.clicked.connect(self.clear_chat_history)
        self.cancel_button = QPushButton(choose("取消", "Cancel"))
        self.cancel_button.clicked.connect(self.cancel_active_operation)
        self.cancel_button.setEnabled(False)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.addWidget(self.mode_combo)
        top_bar.addStretch(1)
        top_bar.addWidget(self.settings_button)
        top_bar.addWidget(self.recent_button)
        top_bar.addWidget(self.clear_button)
        top_bar.addWidget(self.cancel_button)

        self.chat_view = ChatMessageList()

        self.command_edit = ChatInputEdit()
        self.command_edit.setPlaceholderText(choose("输入你的 QGIS 命令，例如：把道路图层和行政区图层相交", "Enter a QGIS command, for example: intersect the roads layer with the administrative boundary layer"))
        self.command_edit.setFixedHeight(86)
        self.command_edit.setStyleSheet(
            "QPlainTextEdit { background: #ffffff; border: 1px solid #d1d5db; border-radius: 10px; padding: 8px; }"
        )
        self.command_edit.send_requested.connect(self.send_command)

        self.send_button = QPushButton(choose("发送", "Send"))
        self.send_button.clicked.connect(self.send_command)
        self.send_button.setFixedWidth(84)
        self.send_button.setStyleSheet(
            "QPushButton { background: #2563eb; color: white; border: none; border-radius: 10px; padding: 10px 14px; }"
            "QPushButton:hover { background: #1d4ed8; }"
        )

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.addWidget(self.command_edit)
        input_row.addWidget(self.send_button)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(top_bar)
        layout.addWidget(self.chat_view)
        layout.addLayout(input_row)

        if self.chat_history:
            for item in self.chat_history:
                self._append_message(item["role"], item["text"], kind=item.get("kind", "normal"), persist=False)
            self._rebuild_memory_from_chat_history()
        else:
            self._append_message(
                "assistant",
                choose("直接输入命令即可执行。你也可以把模式切到“问答”或“执行”。按 Enter 发送，Shift+Enter 换行。", "Enter a command to run it directly. You can also switch to Q&A or Execute mode. Press Enter to send and Shift+Enter for a new line."),
            )

        self._connect_project_signals()

    def refresh_settings_state(self):
        self._set_mode_value(self.settings_manager.load().chat_mode)

    def open_settings_dialog(self):
        if callable(self.open_settings_callback):
            self.open_settings_callback()

    def refresh_project_context(self):
        self.last_context = self.context_builder.build()

    def send_command(self):
        if self.pending_resolution is not None:
            self._append_message("assistant", choose("请先完成当前图层选择，再继续发送新命令。", "Please finish the current layer selection before sending a new command."), kind="info")
            return

        command_text = self.command_edit.toPlainText().strip()
        if not command_text:
            return

        self._append_message("user", command_text)
        self.command_edit.clear()
        self._remember_user_command(command_text)

        self.execution_cancel_requested = False
        self._set_busy(True)
        self._set_status_message("正在读取工程上下文...")
        self.pending_command_text = command_text
        QTimer.singleShot(0, lambda text=command_text: self._prepare_command(text))

    def _prepare_command(self, command_text: str):
        try:
            self.refresh_project_context()
            working_context = dict(self.last_context or {})
            working_context["_conversation_memory"] = dict(self.conversation_memory)
            config = self.settings_manager.load()
            request_mode = self.mode_combo.currentData()

            local_answer = self.query_service.answer(command_text, working_context, request_mode=request_mode)
            if local_answer:
                self._remember_layer(self.query_service.last_target_layer_info)
                self.conversation_memory["last_query_kind"] = self.query_service.last_query_kind or self.conversation_memory.get("last_query_kind", "")
                self._append_message("assistant", local_answer)
                self._set_busy(False)
                self._set_status_message(choose("本地问答已完成。", "Local answer completed."))
                return

            if config.provider in {"deepseek", "openai_compatible", "gemini"} and not config.api_key:
                raise ValueError(choose("当前模型需要 API Key，请先在 Agent Settings 中完成配置并测试连接。", "The current model requires an API key. Please configure it in Model/API Settings and test the connection first."))

            self._start_planning_worker(command_text, working_context, config, request_mode)
        except Exception as exc:
            self._append_message("assistant", self._format_error(exc), kind="error")
            if self.pending_resolution is None:
                self._set_busy(False)
            self._set_status_message("命令准备失败。")

    def _start_planning_worker(self, command_text: str, project_context: dict, config, request_mode: str):
        self._cleanup_planning_worker()
        self.planner_thread = QThread(self)
        self.planner_worker = PlannerWorker(
            self.planner,
            command_text,
            project_context,
            config,
            request_mode,
            dict(self.conversation_memory),
        )
        self.planner_worker.moveToThread(self.planner_thread)
        self.planner_thread.started.connect(self.planner_worker.run)
        self.planner_worker.finished.connect(lambda result, text=command_text: self._handle_planning_result(result, text))
        self.planner_worker.failed.connect(self._handle_planning_error)
        self.planner_worker.cancelled.connect(self._handle_planning_cancelled)
        self.planner_worker.finished.connect(self.planner_thread.quit)
        self.planner_worker.failed.connect(self.planner_thread.quit)
        self.planner_worker.cancelled.connect(self.planner_thread.quit)
        self.planner_thread.finished.connect(self._cleanup_planning_worker)
        self.planner_thread.start()

    def _handle_planning_result(self, result, command_text: str):
        try:
            if result.warnings:
                self._append_message("assistant", "\n".join(result.warnings), kind="info")
            if result.reasoning_text:
                self._append_message("assistant", self._reasoning_summary(result.reasoning_text), kind="info")

            if not result.plan.steps:
                self.conversation_memory["last_query_kind"] = "qa"
                self._append_message("assistant", self._answer_summary(result))
                self._set_busy(False)
                self._set_status_message(choose("问答已完成。", "Answer completed."))
                return

            self._append_message("assistant", self._plan_summary(result))

            if self._request_layer_resolution(result.plan, command_text):
                return

            self._continue_execution(result.plan, command_text)
        except Exception as exc:
            self._append_message("assistant", self._format_error(exc), kind="error")
            if self.pending_resolution is None:
                self._set_busy(False)
            self._set_status_message("规划结果处理失败。")

    def _handle_planning_error(self, exc):
        self._append_message("assistant", self._format_error(exc), kind="error")
        if self.pending_resolution is None:
            self._set_busy(False)
        self._set_status_message("规划失败。")

    def _handle_planning_cancelled(self):
        self._append_message("assistant", choose("已取消当前规划。", "The current planning task was cancelled."), kind="info")
        if self.pending_resolution is None:
            self._set_busy(False)
        self._set_status_message(choose("规划已取消。", "Planning cancelled."))

    def _cleanup_planning_worker(self):
        if self.planner_worker is not None:
            self.planner_worker.deleteLater()
            self.planner_worker = None
        if self.planner_thread is not None:
            self.planner_thread.deleteLater()
            self.planner_thread = None

    def show_recent_operations(self):
        operations = self.settings_manager.load_recent_operations()
        if not operations:
            self._append_message("assistant", choose("最近还没有执行记录。", "There are no recent operations yet."), kind="info")
            return
        recent_items = operations[-8:]
        lines = [choose("点击下面的命令可复用到输入框：", "Click a command below to reuse it in the input box:")]
        actions = []
        for index, item in enumerate(recent_items):
            label = "{} | {}".format(item.get("time", ""), item.get("summary", ""))
            lines.append("- {}".format(label))
            actions.append({"id": "reuse:{}".format(index), "label": label})
        self._append_message(
            "assistant",
            "\n".join(lines),
            kind="info",
            persist=False,
            actions=actions,
            action_handler=lambda action_id, items=recent_items: self._handle_recent_action(action_id, items),
        )

    def clear_chat_history(self):
        self.chat_view.clear()
        self.chat_history = []
        self.settings_manager.save_chat_history([])
        self.conversation_memory = {
            "recent_user_commands": [],
            "recent_turns": [],
            "last_layer_name": "",
            "last_result_layer_name": "",
            "last_query_kind": "",
        }
        self._append_message(
            "assistant",
            choose("聊天记录已清空。直接输入命令即可执行，或切换到问答模式。", "Chat history has been cleared. Enter a command to run it directly, or switch to Q&A mode."),
            kind="info",
        )

    def _request_layer_resolution(self, plan, command_text):
        issues = self.executor.find_layer_reference_issues(
            plan,
            allow_dynamic_processing=bool(self.settings_manager.load().allow_dynamic_processing),
        )
        if not issues:
            return False

        issue = issues[0]
        options = issue.candidates or [layer["name"] for layer in self.last_context.get("layers", [])]
        if not options:
            raise issue

        self.pending_resolution = {
            "plan": plan,
            "command_text": command_text,
            "reference": issue.reference,
        }
        prompt = "图层引用“{}”{}".format(
            issue.reference,
            "存在歧义，请在下面选择具体图层。" if isinstance(issue, AmbiguousLayerReferenceError) else "未找到，请在下面选择替代图层。",
        )
        actions = [{"id": "layer:{}".format(name), "label": name} for name in options]
        actions.append({"id": "layer_cancel", "label": choose("取消本次执行", "Cancel this run")})
        self._append_message(
            "assistant",
            prompt,
            kind="info",
            persist=False,
            actions=actions,
            action_handler=self._handle_layer_resolution_action,
        )
        self._set_busy(False)
        self._set_status_message("等待图层选择...")
        return True

    def _handle_layer_resolution_action(self, action_id: str):
        if self.pending_resolution is None:
            return
        if action_id == "layer_cancel":
            self._append_message("assistant", choose("已取消本次执行。", "This execution has been cancelled."))
            self.pending_resolution = None
            self._set_busy(False)
            self._set_status_message(choose("执行已取消。", "Execution cancelled."))
            return

        selected_layer = action_id.split(":", 1)[1]
        self._append_message("assistant", "已选择图层“{}”。".format(selected_layer), kind="info")
        self._set_busy(True)
        try:
            plan = self.executor.apply_layer_selection(
                self.pending_resolution["plan"],
                self.pending_resolution["reference"],
                selected_layer,
            )
            command_text = self.pending_resolution["command_text"]
            self.pending_resolution = None
            if self._request_layer_resolution(plan, command_text):
                return
            self._continue_execution(plan, command_text)
        except Exception as exc:
            self.pending_resolution = None
            self._append_message("assistant", self._format_error(exc), kind="error")
        finally:
            if self.pending_resolution is None:
                self._set_busy(False)

    def _continue_execution(self, plan, command_text):
        config = self.settings_manager.load()
        if plan.requires_confirmation:
            self._set_busy(False)
            answer = QMessageBox.question(
                self,
                choose("确认执行", "Confirm Execution"),
                choose("该命令包含需要确认的操作，是否继续？", "This command contains operations that require confirmation. Continue?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self._append_message("assistant", choose("已取消执行。", "Execution cancelled."))
                self._set_status_message(choose("执行已取消。", "Execution cancelled."))
                return
            self._set_busy(True)

        self.execution_cancel_requested = False
        self._set_status_message(choose("正在执行计划...", "Executing plan..."))
        try:
            report = self.executor.execute(
                plan,
                allow_dynamic_processing=bool(config.allow_dynamic_processing),
                event_pump=self._pump_events,
                progress_callback=self._report_execution_progress,
                is_cancelled=lambda: self.execution_cancel_requested,
            )
            self.refresh_project_context()
            self._remember_layer_name(self._preferred_memory_layer_name(plan, report))
            if report.added_layers:
                self.conversation_memory["last_result_layer_name"] = report.added_layers[-1]
            self.conversation_memory["last_query_kind"] = "operation"
            self._append_message("assistant", self._execution_summary(report))
            self._record_recent_operation(command_text, plan, report)
            self._set_status_message(choose("执行完成。", "Execution completed."))
        except ExecutionCancelledError:
            self._append_message("assistant", choose("已取消当前执行。", "The current execution was cancelled."), kind="info")
            self._set_status_message(choose("执行已取消。", "Execution cancelled."))
        except Exception as exc:
            self._append_message("assistant", self._format_error(exc), kind="error")
            self._set_status_message(choose("执行失败。", "Execution failed."))
        finally:
            self._set_busy(False)

    def _plan_summary(self, planning_result):
        lines = [choose("准备执行以下操作:", "The following operations are ready to run:")]
        for index, step in enumerate(planning_result.plan.steps, start=1):
            lines.append("{}. {}".format(index, self._describe_step(step)))
        return "\n".join(lines)

    def _answer_summary(self, planning_result):
        lines = []
        if planning_result.plan.response_text:
            lines.append(planning_result.plan.response_text)
        else:
            lines.append(choose("这是一个问答型请求。", "This is an informational request."))
        lines.append(choose("未对图层和工程做任何操作。", "No layer or project operation was performed."))
        return "\n".join(lines)

    def _reasoning_summary(self, reasoning_text: str):
        text = (reasoning_text or "").strip()
        if not text:
            return ""
        return choose("DeepSeek 规划说明:\n{}", "DeepSeek planning notes:\n{}").format(self._truncate_text(text, 900))

    def _execution_summary(self, report):
        lines = [choose("执行完成。", "Execution completed.")]
        if report.added_layers:
            lines.append(choose("结果图层: {}", "Result layers: {}").format(", ".join(report.added_layers)))
        if report.undo_hint:
            lines.append(choose("回退建议: {}", "Undo hint: {}").format(report.undo_hint))
        if report.logs:
            lines.append("")
            lines.append(choose("执行记录:", "Execution log:"))
            lines.extend(report.logs)
        return "\n".join(lines)

    def _describe_step(self, step):
        if step.kind == "processing":
            parts = [step.label or step.tool_id]
            if isinstance(step.params, dict):
                refs = []
                for key in ("INPUT", "OVERLAY", "LAYERS"):
                    if key in step.params:
                        refs.append("{}={}".format(key, self._describe_value(step.params[key])))
                if "EXPRESSION" in step.params:
                    refs.append("表达式={}".format(step.params["EXPRESSION"]))
                if "DISTANCE" in step.params:
                    refs.append("距离={}".format(step.params["DISTANCE"]))
                if "TARGET_CRS" in step.params:
                    refs.append("目标坐标系={}".format(step.params["TARGET_CRS"]))
                if refs:
                    parts.append(" | " + ", ".join(refs))
            return "".join(parts)
        parts = [step.label or step.operation]
        if isinstance(step.args, dict):
            details = []
            for key in ("layer", "name", "expression", "visible", "path", "color", "field", "color_ramp", "standard_id", "style_set_id", "match_field"):
                if key in step.args:
                    details.append("{}={}".format(key, self._describe_value(step.args[key])))
            if details:
                parts.append(" | " + ", ".join(details))
        return "".join(parts)

    def _describe_value(self, value):
        if isinstance(value, dict):
            if "layer" in value:
                return value["layer"]
            if "result" in value:
                return "上一步结果"
        if isinstance(value, list):
            return "[" + ", ".join(self._describe_value(item) for item in value) + "]"
        return str(value)

    def _append_message(self, role: str, text: str, kind: str = "normal", persist: bool = True, actions=None, action_handler=None):
        item = self.chat_view.add_message(role=role, text=text, kind=kind, actions=actions, action_handler=action_handler)
        if persist and kind != "status":
            self.chat_history.append({"role": role, "text": text, "kind": kind})
            self.settings_manager.save_chat_history(self.chat_history)
            self._remember_turn(role, text, kind)
        return item

    def _persist_mode(self):
        config = self.settings_manager.load()
        config.chat_mode = self.mode_combo.currentData()
        self.settings_manager.save(config)

    def _set_mode_value(self, value: str):
        for index in range(self.mode_combo.count()):
            if self.mode_combo.itemData(index) == value:
                self.mode_combo.setCurrentIndex(index)
                return

    def _record_recent_operation(self, command_text, plan, report):
        items = self.settings_manager.load_recent_operations()
        items.append(
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": self.mode_combo.currentData(),
                "command": command_text,
                "summary": plan.summary or " -> ".join(report.operation_summary),
            }
        )
        self.settings_manager.save_recent_operations(items)

    def _handle_recent_action(self, action_id: str, operations: list):
        if not action_id.startswith("reuse:"):
            return
        index = int(action_id.split(":", 1)[1])
        if index < 0 or index >= len(operations):
            return
        command = operations[index].get("command", "")
        self.command_edit.setPlainText(command)
        self.command_edit.setFocus()
        cursor = self.command_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.command_edit.setTextCursor(cursor)
        self._append_message("assistant", choose("已将历史命令填入输入框，可直接修改后发送。", "The historical command has been filled into the input box. You can edit it and send it again."), kind="info")

    def _format_error(self, exc: Exception):
        if isinstance(exc, AmbiguousLayerReferenceError):
            return self._error_message(
                title="图层匹配存在歧义",
                reason="命令里的图层引用“{}”同时匹配到了多个图层。".format(exc.reference),
                suggestions=[
                    "直接在聊天里的候选按钮中选择一个图层。",
                    "把命令改得更具体，例如写完整图层名。",
                    "如果图层名很像，先把图层重命名后再执行。",
                ],
                detail="可选图层: {}".format(", ".join(exc.candidates)) if exc.candidates else "",
            )
        if isinstance(exc, MissingLayerReferenceError):
            return self._error_message(
                title="未找到图层",
                reason="当前工程中没有找到“{}”这个图层引用。".format(exc.reference),
                suggestions=[
                    "检查图层是否已经加载到当前工程。",
                    "把命令里的图层名改成工程中显示的精确名称。",
                    "如果只是简称，尽量写完整图层名。",
                ],
                detail="建议图层: {}".format(", ".join(exc.candidates)) if exc.candidates else "",
            )
        message = str(exc)
        if "HTTP" in message or "Network error" in message:
            return self._error_message(
                title="模型连接失败",
                reason="插件无法连接到当前配置的模型服务。",
                suggestions=[
                    "在 Agent Settings 里重新测试连接。",
                    "检查 Base URL、API Key 和所选模型是否正确。",
                    "如果是本地模型，确认服务已经启动。",
                ],
                detail=message,
            )
        if "JSON" in message or "LLM 规划失败" in message:
            return self._error_message(
                title="模型返回格式异常",
                reason="模型返回了插件无法解析的内容，没能形成可执行计划。",
                suggestions=[
                    "把命令写得更直接，例如“把A图层和B图层相交”。",
                    "避免一条命令里混入过多目标，先拆成两句试一次。",
                    "在设置里重新测试当前模型是否正常可用。",
                ],
                detail=message,
            )
        if "无法解析该命令" in message or "规则解析" in message:
            return self._error_message(
                title="命令解析失败",
                reason="插件没能把这句话稳定映射成问答或 QGIS 操作步骤。",
                suggestions=[
                    "把命令改成“动词 + 图层名”的形式。",
                    "例如：把道路图层和行政区图层相交。",
                    "如果涉及多个步骤，用“然后”分开写。",
                ],
                detail=message,
            )
        if "rename_layer 缺少有效图层或名称" in message:
            return self._error_message(
                title="重命名步骤参数不完整",
                reason="计划里包含了重命名图层，但没有拿到有效的目标图层或新名称。",
                suggestions=[
                    "把命令改成：把结果重命名为 相交1。",
                    "如果要给上一步结果命名，先确认前一步确实会生成结果图层。",
                    "也可以拆开说：先相交，然后把结果重命名为 相交1。",
                ],
                detail=message,
            )
        if "fieldcalculator" in message.lower() or "字段计算" in message:
            return self._error_message(
                title="字段计算失败",
                reason="面积或字段计算步骤执行失败，通常是图层类型、字段配置或表达式不满足要求。",
                suggestions=[
                    "确认目标图层是矢量图层。",
                    "如果是算面积，尽量写成：给地块图层计算面积并保存到字段 area。",
                    "如果需要平方米结果，先确认图层坐标系是否适合面积计算。",
                ],
                detail=message,
            )
        if "set_layer_color" in message or "set_categorized_renderer" in message or "符号化" in message or "分类渲染" in message:
            return self._error_message(
                title="图层符号化失败",
                reason="当前命令没有成功转换成可用的图层样式，或图层本身不支持该符号化方式。",
                suggestions=[
                    "单色渲染可写成：把地块图层符号化成红色。",
                    "分类渲染可写成：把地块图层按字段 dlbm 分类渲染。",
                    "先确认字段名在该图层中真实存在。",
                ],
                detail=message,
            )
        if "当前 QGIS 中未找到 Processing 算法" in message:
            return self._error_message(
                title="算法不可用",
                reason="模型规划了一个当前 QGIS 环境里不存在的 Processing 算法。",
                suggestions=[
                    "检查对应插件或处理组件是否已安装。",
                    "换一种更常见的表达方式重新发送。",
                    "如果是特定第三方算法，先确认它能在 QGIS 处理工具箱里手动找到。",
                ],
                detail=message,
            )
        if "缺少有效图层" in message:
            return self._error_message(
                title="执行步骤缺少图层",
                reason="某一步需要图层输入，但插件没有解析到有效图层。",
                suggestions=[
                    "把命令里的图层名写完整。",
                    "如果引用的是上一步结果，尽量把命令拆成“先...然后...”形式。",
                    "确认当前工程里已经加载了目标图层。",
                ],
                detail=message,
            )
        return self._error_message(
            title="执行失败",
            reason="插件在执行过程中遇到了未归类的错误。",
            suggestions=[
                "先检查计划说明里的每一步是否符合你的原意。",
                "把命令拆成更短、更明确的几句分别执行。",
                "如果问题持续出现，把当前命令和报错一起发给我继续修。",
            ],
            detail=message,
        )

    def _error_message(self, title: str, reason: str, suggestions: list, detail: str = ""):
        lines = [title, "", "原因：{}".format(reason)]
        if detail:
            lines.append("详情：{}".format(detail))
        if suggestions:
            lines.append("建议修改：")
            for index, suggestion in enumerate(suggestions, start=1):
                lines.append("{}. {}".format(index, suggestion))
        return "\n".join(lines)

    def _set_busy(self, busy: bool):
        self.send_button.setEnabled(not busy)
        self.command_edit.setReadOnly(busy)
        self.send_button.setText(choose("处理中...", "Working...") if busy else choose("发送", "Send"))
        self.cancel_button.setEnabled(busy)
        if busy:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def cancel_active_operation(self):
        self.execution_cancel_requested = True
        if self.planner_worker is not None and hasattr(self.planner_worker, "cancel_requested"):
            self.planner_worker.cancel_requested = True
        self._set_status_message(choose("已收到取消请求，正在停止...", "Cancellation requested. Stopping..."))

    def _remember_user_command(self, command_text: str):
        commands = list(self.conversation_memory.get("recent_user_commands") or [])
        commands.append(command_text)
        self.conversation_memory["recent_user_commands"] = commands[-5:]

    def _remember_turn(self, role: str, text: str, kind: str = "normal"):
        turns = list(self.conversation_memory.get("recent_turns") or [])
        turns.append({"role": role, "text": text, "kind": kind})
        self.conversation_memory["recent_turns"] = turns[-6:]

    def _remember_layer(self, layer_info):
        if layer_info and layer_info.get("name"):
            self.conversation_memory["last_layer_name"] = layer_info["name"]

    def _remember_layer_name(self, layer_name: str):
        if layer_name:
            self.conversation_memory["last_layer_name"] = layer_name

    def _preferred_memory_layer_name(self, plan, report):
        if report.added_layers:
            return report.added_layers[-1]
        for step in reversed(plan.steps):
            layer_name = self._extract_layer_name_from_value(step.params if step.kind == "processing" else step.args)
            if layer_name:
                return layer_name
        return ""

    def _extract_layer_name_from_value(self, value):
        if isinstance(value, dict):
            if "layer" in value and isinstance(value["layer"], str):
                return value["layer"]
            for item in value.values():
                resolved = self._extract_layer_name_from_value(item)
                if resolved:
                    return resolved
        if isinstance(value, list):
            for item in value:
                resolved = self._extract_layer_name_from_value(item)
                if resolved:
                    return resolved
        return ""

    def _rebuild_memory_from_chat_history(self):
        recent_turns = []
        recent_user_commands = []
        for item in self.chat_history[-12:]:
            role = item.get("role", "")
            text = item.get("text", "")
            kind = item.get("kind", "normal")
            recent_turns.append({"role": role, "text": text, "kind": kind})
            if role == "user":
                recent_user_commands.append(text)
        self.conversation_memory["recent_turns"] = recent_turns[-6:]
        self.conversation_memory["recent_user_commands"] = recent_user_commands[-5:]

    def _connect_project_signals(self):
        project = QgsProject.instance()
        for signal in (project.layersAdded, project.layersRemoved, project.cleared, project.readProject):
            signal.connect(self._invalidate_project_context_cache)

    def _invalidate_project_context_cache(self, *args):
        self.context_builder.invalidate()
        self.last_context = None

    def _pump_events(self):
        QApplication.processEvents()

    def _report_execution_progress(self, text: str):
        cleaned = (text or "").strip()
        if not cleaned or cleaned == self._last_status_text:
            self._pump_events()
            return
        self._last_status_text = cleaned
        self._set_status_message(cleaned)

    def _set_status_message(self, text: str):
        message = (text or "").strip() or choose("处理中...", "Working...")
        if self.status_item is None:
            self.status_item = self.chat_view.add_message("assistant", message, kind="status")
            return
        self.chat_view.update_message(self.status_item, message, kind="status")

    def _truncate_text(self, text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."
