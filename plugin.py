import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .i18n import choose
from .settings import SettingsManager
from .ui.dock_widget import NlQgisDockWidget
from .ui.settings_dialog import SettingsDialog


class NaturalLanguageQgisAgentPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.settings_manager = SettingsManager()
        self.menu_title = "&QGIS AI Agent"
        self.vector_menu_title = "&QGIS AI Agent"
        self.toolbar_action = None
        self.settings_action = None
        self.dock_widget = None

    def initGui(self):
        icon = QIcon(self._icon_path())
        self.toolbar_action = QAction(icon, choose("QGIS AI 助手", "QGIS AI Agent"), self.iface.mainWindow())
        self.toolbar_action.triggered.connect(self.show_dock)

        self.settings_action = QAction(choose("模型/API设置", "Model/API Settings"), self.iface.mainWindow())
        self.settings_action.triggered.connect(self.show_settings)

        self.iface.addToolBarIcon(self.toolbar_action)
        self.iface.addPluginToMenu(self.menu_title, self.toolbar_action)
        self.iface.addPluginToMenu(self.menu_title, self.settings_action)
        self.iface.addPluginToVectorMenu(self.vector_menu_title, self.toolbar_action)
        self.iface.addPluginToVectorMenu(self.vector_menu_title, self.settings_action)

    def unload(self):
        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

        if self.toolbar_action is not None:
            self.iface.removeToolBarIcon(self.toolbar_action)
            self.iface.removePluginMenu(self.menu_title, self.toolbar_action)
            self.iface.removePluginVectorMenu(self.vector_menu_title, self.toolbar_action)
            self.toolbar_action.deleteLater()
            self.toolbar_action = None

        if self.settings_action is not None:
            self.iface.removePluginMenu(self.menu_title, self.settings_action)
            self.iface.removePluginVectorMenu(self.vector_menu_title, self.settings_action)
            self.settings_action.deleteLater()
            self.settings_action = None

    def show_dock(self):
        if self.dock_widget is None:
            self.dock_widget = NlQgisDockWidget(self.iface, self.settings_manager, open_settings_callback=self.show_settings)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)

        self.dock_widget.refresh_project_context()
        self.dock_widget.show()
        self.dock_widget.raise_()
        self.dock_widget.activateWindow()

    def show_settings(self):
        dialog = SettingsDialog(self.iface.mainWindow(), self.settings_manager)
        if dialog.exec_() and self.dock_widget is not None:
            self.dock_widget.refresh_settings_state()

    def _icon_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), "resources", "icon.png")
