"""Tab 1: Converter — 2 streams (Python Scripts + API)."""

import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QTextEdit,
    QRadioButton, QButtonGroup, QComboBox, QCheckBox, QSlider,
    QProgressBar, QTabWidget, QFileDialog, QApplication, QMessageBox,
    QStyle,
)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from core.format_utils import get_filter_string, ALL_EXTENSIONS
from gui.settings_dialog import SettingsDialog


class TabConverter(QWidget):
    """Tab 1: Document to Markdown conversion with 2 streams."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # === LEFT SIDEBAR ===
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)

        # File management
        file_grp = QGroupBox("📂 Files")
        file_layout = QVBoxLayout(file_grp)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("📎 Thêm file")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_remove = QPushButton()
        self.btn_remove.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.btn_remove.setIconSize(self.btn_add.iconSize())
        self.btn_remove.setToolTip("Bỏ file đã chọn khỏi danh sách")
        self.btn_remove.setAccessibleName("Xóa file đã chọn")
        self.btn_remove.setMaximumWidth(52)
        self.btn_remove.setMinimumWidth(52)
        self.btn_remove.setMinimumHeight(44)
        self.btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        file_layout.addLayout(btn_row)

        self.file_list = QListWidget()
        self.file_list.setDragDropMode(QListWidget.DragDropMode.NoDragDrop)
        file_layout.addWidget(self.file_list)

        sidebar_layout.addWidget(file_grp)

        # Stream selection
        stream_grp = QGroupBox("⚡ Luồng xử lý")
        stream_layout = QVBoxLayout(stream_grp)

        self.radio_script = QRadioButton("⚡ Python Scripts (offline)")
        self.radio_api = QRadioButton("🤖 API Extraction")
        self.radio_script.setChecked(True)

        self.stream_group = QButtonGroup()
        self.stream_group.addButton(self.radio_script, 1)
        self.stream_group.addButton(self.radio_api, 2)
        self.stream_group.buttonClicked.connect(self._on_stream_changed)

        stream_layout.addWidget(self.radio_script)
        stream_layout.addWidget(self.radio_api)

        # API provider (shown for stream 2)
        self.api_combo_label = QLabel("API Provider:")
        self.api_combo = QComboBox()
        self.api_combo.addItems(["openai", "claude", "opencode", "custom"])
        self.api_combo_label.setVisible(False)
        self.api_combo.setVisible(False)
        stream_layout.addWidget(self.api_combo_label)
        stream_layout.addWidget(self.api_combo)

        sidebar_layout.addWidget(stream_grp)

        # Options
        opt_grp = QGroupBox("⚙️ Options")
        opt_layout = QVBoxLayout(opt_grp)

        self.chk_phases = QCheckBox("☑ Chia phases (file lớn)")
        self.chk_phases.setChecked(True)
        self.chk_merge = QCheckBox("☑ Tự động gộp phases")
        self.chk_merge.setChecked(True)
        self.chk_verify = QCheckBox("☑ Xác minh dữ liệu")
        self.chk_verify.setChecked(True)
        opt_layout.addWidget(self.chk_phases)
        opt_layout.addWidget(self.chk_merge)
        opt_layout.addWidget(self.chk_verify)

        chunk_row = QHBoxLayout()
        chunk_row.addWidget(QLabel("Chunk:"))
        self.chunk_slider = QSlider(Qt.Orientation.Horizontal)
        self.chunk_slider.setRange(1000, 20000)
        self.chunk_slider.setValue(5000)
        self.chunk_slider.setSingleStep(500)
        self.chunk_label = QLabel("5000")
        self.chunk_slider.valueChanged.connect(
            lambda v: self.chunk_label.setText(str(v))
        )
        chunk_row.addWidget(self.chunk_slider)
        chunk_row.addWidget(self.chunk_label)
        opt_layout.addLayout(chunk_row)

        sidebar_layout.addWidget(opt_grp)

        # Action buttons
        sidebar_layout.addStretch()
        self.btn_convert = QPushButton("🚀 Bắt đầu chuyển đổi")
        self.btn_convert.setObjectName("btn_success")
        self.btn_convert.clicked.connect(self._start_conversion)
        sidebar_layout.addWidget(self.btn_convert)

        self.btn_cancel = QPushButton("⏹ Hủy")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        sidebar_layout.addWidget(self.btn_cancel)

        sidebar.setMinimumWidth(260)
        sidebar.setMaximumWidth(340)
        splitter.addWidget(sidebar)

        # === MAIN PANEL ===
        main_panel = QWidget()
        main_layout_right = QVBoxLayout(main_panel)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Sẵn sàng")
        self.progress_label.setObjectName("label_subtitle")
        main_layout_right.addWidget(self.progress_bar)
        main_layout_right.addWidget(self.progress_label)

        # Tabs: Preview / Phases / Log
        self.result_tabs = QTabWidget()

        # Preview tab
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.result_tabs.addTab(self.preview_text, "📄 Preview")

        # Phases tab
        phases_widget = QWidget()
        phases_layout = QVBoxLayout(phases_widget)
        self.phases_list = QListWidget()
        self.phases_list.itemClicked.connect(self._on_phase_clicked)
        phases_layout.addWidget(self.phases_list)

        phase_btn_row = QHBoxLayout()
        self.btn_copy_phase = QPushButton("📋 Copy Phase")
        self.btn_copy_phase.clicked.connect(self._copy_current_phase)
        self.btn_merge = QPushButton("📎 Gộp tất cả")
        phase_btn_row.addWidget(self.btn_copy_phase)
        phase_btn_row.addWidget(self.btn_merge)
        phases_layout.addLayout(phase_btn_row)

        self.phase_preview = QTextEdit()
        self.phase_preview.setReadOnly(True)
        self.phase_preview.setMaximumHeight(200)
        phases_layout.addWidget(self.phase_preview)

        self.result_tabs.addTab(phases_widget, "📋 Phases")

        # Log tab
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.result_tabs.addTab(self.log_text, "📝 Log")

        main_layout_right.addWidget(self.result_tabs)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        self.btn_verify = QPushButton("✔️ Verify")
        self.btn_open_folder = QPushButton("📁 Open Folder")
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_verify)
        bottom_row.addWidget(self.btn_open_folder)
        main_layout_right.addLayout(bottom_row)

        splitter.addWidget(main_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)

    def _on_stream_changed(self, button):
        is_api = self.radio_api.isChecked()
        self.api_combo_label.setVisible(is_api)
        self.api_combo.setVisible(is_api)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn file", "",
            get_filter_string()
        )
        for f in files:
            if not any(self.file_list.item(i).data(Qt.ItemDataRole.UserRole) == f
                       for i in range(self.file_list.count())):
                item = QListWidgetItem(f"📄 {Path(f).name}")
                item.setData(Qt.ItemDataRole.UserRole, f)
                self.file_list.addItem(item)

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def _get_file_paths(self) -> list:
        paths = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            paths.append(item.data(Qt.ItemDataRole.UserRole))
        return paths

    def _get_settings(self) -> dict:
        try:
            settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                         "config", "settings.json")
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _start_conversion(self):
        file_paths = self._get_file_paths()
        if not file_paths:
            QMessageBox.warning(self, "Warning", "Chưa chọn file nào!")
            return

        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

        self.log_text.clear()
        self.phases_list.clear()
        self.phase_preview.clear()
        self.preview_text.clear()
        self.btn_convert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)

        if self.radio_script.isChecked():
            from workers.converter_worker import ConverterWorker
            self.worker = ConverterWorker(
                file_paths=file_paths,
                output_dir=output_dir,
                use_phases=self.chk_phases.isChecked(),
                auto_merge=self.chk_merge.isChecked(),
                verify=self.chk_verify.isChecked(),
                chunk_size=self.chunk_slider.value(),
            )
        else:
            from workers.api_converter_worker import APIConverterWorker
            settings = self._get_settings()
            provider = self.api_combo.currentText()
            api_config = settings.get("api", {}).get(provider, {})

            self.worker = APIConverterWorker(
                file_paths=file_paths,
                output_dir=output_dir,
                provider=provider,
                api_config=api_config,
                use_phases=self.chk_phases.isChecked(),
                auto_merge=self.chk_merge.isChecked(),
                verify=self.chk_verify.isChecked(),
                chunk_size=self.chunk_slider.value(),
            )

        # Connect signals
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._on_log)
        self.worker.phase_created.connect(self._on_phase_created)
        self.worker.file_completed.connect(self._on_file_completed)
        self.worker.error.connect(self._on_error)
        self.worker.warning.connect(self._on_warning)
        self.worker.all_completed.connect(self._on_all_completed)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _cancel(self):
        if self.worker:
            self.worker.cancel()

    def _on_progress(self, pct, msg):
        self.progress_bar.setValue(pct)
        self.progress_label.setText(msg)

    def _on_log(self, msg):
        self.log_text.append(msg)

    def _on_phase_created(self, index, path, preview):
        item = QListWidgetItem(f"Phase {index} ({len(preview)} chars)")
        item.setData(Qt.ItemDataRole.UserRole, {"path": path, "preview": preview})
        self.phases_list.addItem(item)

    def _on_phase_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            try:
                with open(data["path"], "r", encoding="utf-8") as f:
                    content = f.read()
                self.phase_preview.setPlainText(content)
            except Exception:
                self.phase_preview.setPlainText(data.get("preview", ""))

    def _copy_current_phase(self):
        text = self.phase_preview.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def _on_file_completed(self, input_path, output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.preview_text.setPlainText(content)
        except Exception:
            pass

    def _on_error(self, filepath, msg):
        self.log_text.append(f"❌ Error: {msg}")

    def _on_warning(self, filepath, msg):
        self.log_text.append(f"⚠️ {msg}")

    def _on_all_completed(self, results):
        n = len(results)
        self.log_text.append(f"\n✅ Hoàn thành: {n} file(s)")

    def _on_finished(self):
        self.btn_convert.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def _open_output_folder(self):
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        os.startfile(output_dir)

    # Drag & Drop
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            ext = Path(path).suffix.lower()
            if ext in ALL_EXTENSIONS:
                item = QListWidgetItem(f"📄 {Path(path).name}")
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.file_list.addItem(item)
