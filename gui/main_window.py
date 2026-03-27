"""MainWindow — 2-tab application with settings."""

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QStatusBar, QLabel,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from gui.tab_converter import TabConverter
from gui.tab_translation import TabTranslation
from gui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Main application window with 2 tabs."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DocToMarkdown Pro — Document Converter & Translator")
        self.setMinimumSize(1000, 680)
        self.resize(1200, 750)

        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()

    def _setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tab_converter = TabConverter()
        self.tab_translation = TabTranslation()

        self.tabs.addTab(self.tab_converter, "📄 Chuyển đổi Markdown")
        self.tabs.addTab(self.tab_translation, "🌐 Dịch tài liệu")

        self.setCentralWidget(self.tabs)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        title = QLabel("  DocToMarkdown Pro  ")
        title.setObjectName("label_title")
        toolbar.addWidget(title)

        spacer = QLabel()
        spacer.setMinimumWidth(20)
        toolbar.addWidget(spacer)

        subtitle = QLabel("Word • Excel • Slide • PDF • Image → Markdown")
        subtitle.setObjectName("label_subtitle")
        toolbar.addWidget(subtitle)

        # Spacer
        spacer2 = QLabel()
        toolbar.addWidget(spacer2)
        spacer_action = toolbar.addWidget(spacer2)

        # Settings button
        settings_action = QAction("⚙️ Settings", self)
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

    def _setup_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("DocToMarkdown Pro v1.0 — Ready")

    def _open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
