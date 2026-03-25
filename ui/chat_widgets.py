from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QKeyEvent
from qgis.PyQt.QtWidgets import (
    QPushButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ChatInputEdit(QPlainTextEdit):
    send_requested = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ChatMessageWidget(QFrame):
    action_triggered = pyqtSignal(str)

    def __init__(self, role: str, text: str, kind: str = "normal", actions=None, parent=None):
        super().__init__(parent)
        self.role = role
        self.kind = kind
        self.actions = list(actions or [])

        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.outer_layout = QHBoxLayout(self)
        self.outer_layout.setContentsMargins(18, 8, 18, 8)

        self.bubble = QFrame()
        self.bubble.setMaximumWidth(720)
        self.bubble_layout = QVBoxLayout(self.bubble)
        self.bubble_layout.setContentsMargins(12, 10, 12, 10)
        self.bubble_layout.setSpacing(4)

        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("color: #6b7280; font-size: 11px;")

        self.body_label = QLabel()
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body_label.setTextFormat(Qt.PlainText)
        self.body_label.setStyleSheet("color: #111827; font-size: 13px; line-height: 1.6;")

        self.bubble_layout.addWidget(self.title_label)
        self.bubble_layout.addWidget(self.body_label)
        self.actions_layout = QVBoxLayout()
        self.actions_layout.setContentsMargins(0, 6, 0, 0)
        self.actions_layout.setSpacing(6)
        self.bubble_layout.addLayout(self.actions_layout)

        if role == "user":
            self.outer_layout.addStretch(1)
            self.outer_layout.addWidget(self.bubble)
        else:
            self.outer_layout.addWidget(self.bubble)
            self.outer_layout.addStretch(1)

        self.set_text(text)
        self.set_actions(self.actions)
        self._apply_style()

    def set_text(self, text: str):
        self.body_label.setText(text or "")

    def set_actions(self, actions):
        self.actions = list(actions or [])
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for action in self.actions:
            button = QPushButton(action.get("label", "选择"))
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { text-align: left; background: #ffffff; border: 1px solid #cbd5e1; "
                "border-radius: 8px; padding: 8px 10px; }"
                "QPushButton:hover { background: #eff6ff; border-color: #93c5fd; }"
            )
            button.clicked.connect(lambda checked=False, action_id=action.get("id", ""): self.action_triggered.emit(action_id))
            self.actions_layout.addWidget(button)

    def _apply_style(self):
        title = "你" if self.role == "user" else "AI"
        background = "#dbeafe" if self.role == "user" else "#ffffff"
        border = "#bfdbfe" if self.role == "user" else "#e5e7eb"

        if self.kind == "status":
            background = "#eff6ff"
            border = "#bfdbfe"
            title = "状态"
        elif self.kind == "error":
            background = "#fef2f2"
            border = "#fecaca"
            title = "错误"
        elif self.kind == "info":
            background = "#f0fdf4"
            border = "#bbf7d0"
            title = "提示"

        self.title_label.setText(title)
        self.bubble.setStyleSheet(
            "QFrame { background: %s; border: 1px solid %s; border-radius: 14px; }" % (background, border)
        )


class ChatMessageList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWordWrap(True)
        self.setSpacing(2)
        self.setStyleSheet("QListWidget { background: #f8fafc; border: none; }")

    def add_message(self, role: str, text: str, kind: str = "normal", actions=None, action_handler=None):
        item = QListWidgetItem()
        widget = ChatMessageWidget(role=role, text=text, kind=kind, actions=actions)
        if action_handler is not None:
            widget.action_triggered.connect(action_handler)
        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)
        self.scrollToBottom()
        return item

    def update_message(self, item: QListWidgetItem, text: str, kind: str = None, actions=None, action_handler=None):
        widget = self.itemWidget(item)
        if widget is None:
            return
        next_kind = kind or widget.kind
        should_replace = (kind and widget.kind != kind) or actions is not None
        if should_replace:
            replacement = ChatMessageWidget(role=widget.role, text=text, kind=next_kind, actions=actions or widget.actions)
            if action_handler is not None:
                replacement.action_triggered.connect(action_handler)
            item.setSizeHint(replacement.sizeHint())
            self.setItemWidget(item, replacement)
        else:
            widget.set_text(text)
            item.setSizeHint(widget.sizeHint())
        self.scrollToBottom()
