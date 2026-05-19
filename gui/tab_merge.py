"""Tab 4: Merge — combine multiple files of the same type."""

import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QTextEdit,
    QCheckBox, QProgressBar, QFileDialog, QMessageBox, QStyle,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from workers.merge_worker import detect_merge_type, MERGE_EXTENSIONS


# Display config per merge type
TYPE_CONFIG = {
    "markdown": {"icon": "📄", "label": "Markdown", "filter": "Markdown (*.md *.txt)"},
    "word": {"icon": "📝", "label": "Word", "filter": "Word (*.docx)"},
    "pdf": {"icon": "📕", "label": "PDF", "filter": "PDF (*.pdf)"},
}


class TabMerge(QWidget):
    """Tab 4: Merge multiple files of the same type into one."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.worker = None
        self._current_type = ""  # locked merge type
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # === LEFT SIDEBAR ===
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)

        # File management
        file_grp = QGroupBox("📂 Danh sách file gộp")
        file_layout = QVBoxLayout(file_grp)

        # Type indicator
        self.label_type = QLabel("Chưa chọn file — hỗ trợ: MD, Word, PDF")
        self.label_type.setObjectName("label_subtitle")
        self.label_type.setWordWrap(True)
        file_layout.addWidget(self.label_type)

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("📎 Thêm file")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_remove = QPushButton()
        self.btn_remove.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.btn_remove.setToolTip("Bỏ file đã chọn")
        self.btn_remove.setMaximumWidth(52)
        self.btn_remove.setMinimumWidth(52)
        self.btn_remove.setMinimumHeight(44)
        self.btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        file_layout.addLayout(btn_row)

        # File list with drag-drop reorder
        self.file_list = QListWidget()
        self.file_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.file_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setAlternatingRowColors(True)
        file_layout.addWidget(self.file_list)

        # Reorder buttons
        reorder_row = QHBoxLayout()
        self.btn_move_up = QPushButton("🔼 Lên")
        self.btn_move_up.clicked.connect(self._move_up)
        self.btn_move_down = QPushButton("🔽 Xuống")
        self.btn_move_down.clicked.connect(self._move_down)
        self.btn_clear = QPushButton("🗑️ Xóa hết")
        self.btn_clear.clicked.connect(self._clear_all)
        reorder_row.addWidget(self.btn_move_up)
        reorder_row.addWidget(self.btn_move_down)
        reorder_row.addWidget(self.btn_clear)
        file_layout.addLayout(reorder_row)

        sidebar_layout.addWidget(file_grp)

        # Options
        opt_grp = QGroupBox("⚙️ Tùy chọn")
        opt_layout = QVBoxLayout(opt_grp)

        self.chk_page_break = QCheckBox("☑ Ngắt trang giữa các file (Word/PDF)")
        self.chk_page_break.setChecked(True)
        opt_layout.addWidget(self.chk_page_break)

        self.chk_separator = QCheckBox("☑ Chèn dấu phân cách --- (Markdown)")
        self.chk_separator.setChecked(True)
        opt_layout.addWidget(self.chk_separator)

        self.chk_source_marker = QCheckBox("☐ Đánh dấu nguồn file gốc (Markdown)")
        self.chk_source_marker.setChecked(False)
        opt_layout.addWidget(self.chk_source_marker)

        sidebar_layout.addWidget(opt_grp)

        # Action buttons
        sidebar_layout.addStretch()

        self.btn_merge = QPushButton("🚀 Gộp File")
        self.btn_merge.setObjectName("btn_success")
        self.btn_merge.clicked.connect(self._start_merge)
        sidebar_layout.addWidget(self.btn_merge)

        self.btn_cancel = QPushButton("⏹ Hủy")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        sidebar_layout.addWidget(self.btn_cancel)

        sidebar.setMinimumWidth(280)
        sidebar.setMaximumWidth(360)
        splitter.addWidget(sidebar)

        # === MAIN PANEL ===
        main_panel = QWidget()
        main_layout_right = QVBoxLayout(main_panel)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Sẵn sàng — kéo thả file vào danh sách bên trái")
        self.progress_label.setObjectName("label_subtitle")
        main_layout_right.addWidget(self.progress_bar)
        main_layout_right.addWidget(self.progress_label)

        # Log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText(
            "📎 Hướng dẫn sử dụng:\n\n"
            "1. Thêm file cùng loại (MD, Word, hoặc PDF)\n"
            "2. Kéo thả để sắp xếp thứ tự gộp\n"
            "3. Nhấn 🚀 Gộp File\n\n"
            "Lưu ý: Chỉ gộp được các file cùng định dạng.\n"
            "File đầu tiên quyết định loại merge."
        )
        main_layout_right.addWidget(self.log_text)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        self.btn_open_folder = QPushButton("📁 Mở thư mục Output")
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_open_folder)
        main_layout_right.addLayout(bottom_row)

        splitter.addWidget(main_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)

    # ── File Management ──────────────────────────────────────────

    def _add_files(self):
        """Add files via file dialog, filtered by current merge type."""
        if self._current_type:
            config = TYPE_CONFIG[self._current_type]
            filter_str = f"{config['filter']};;Tất cả (*.*)"
        else:
            all_exts = " ".join(f"*{e}" for e in MERGE_EXTENSIONS)
            filter_str = (
                f"Tất cả hỗ trợ ({all_exts});;"
                "Markdown (*.md *.txt);;"
                "Word (*.docx);;"
                "PDF (*.pdf)"
            )

        files, _ = QFileDialog.getOpenFileNames(self, "Chọn file để gộp", "", filter_str)
        for f in files:
            self._add_file_to_list(f)

    def _add_file_to_list(self, filepath: str) -> bool:
        """Add a single file, enforcing same-type constraint. Returns success."""
        file_type = detect_merge_type(filepath)
        if not file_type:
            self.log_text.append(
                f"⚠️ Bỏ qua: {Path(filepath).name} — định dạng không hỗ trợ"
            )
            return False

        # Lock type from first file
        if not self._current_type:
            self._current_type = file_type
            self._update_type_label()
        elif file_type != self._current_type:
            config = TYPE_CONFIG[self._current_type]
            self.log_text.append(
                f"⚠️ Bỏ qua: {Path(filepath).name} — "
                f"đang gộp file {config['label']}, không thể thêm file {file_type}"
            )
            return False

        # Prevent duplicates
        for i in range(self.file_list.count()):
            if self.file_list.item(i).data(Qt.ItemDataRole.UserRole) == filepath:
                return False

        config = TYPE_CONFIG[file_type]
        item = QListWidgetItem(f"{config['icon']} {Path(filepath).name}")
        item.setData(Qt.ItemDataRole.UserRole, filepath)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        self.file_list.addItem(item)
        return True

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        if self.file_list.count() == 0:
            self._current_type = ""
            self._update_type_label()

    def _clear_all(self):
        self.file_list.clear()
        self._current_type = ""
        self._update_type_label()
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText("Sẵn sàng — kéo thả file vào danh sách bên trái")

    def _move_up(self):
        row = self.file_list.currentRow()
        if row > 0:
            item = self.file_list.takeItem(row)
            self.file_list.insertItem(row - 1, item)
            self.file_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.file_list.currentRow()
        if row < self.file_list.count() - 1:
            item = self.file_list.takeItem(row)
            self.file_list.insertItem(row + 1, item)
            self.file_list.setCurrentRow(row + 1)

    def _update_type_label(self):
        if self._current_type:
            config = TYPE_CONFIG[self._current_type]
            self.label_type.setText(
                f"{config['icon']} Đang gộp file: {config['label']} "
                f"({self.file_list.count()} file)"
            )
        else:
            self.label_type.setText("Chưa chọn file — hỗ trợ: MD, Word, PDF")

    def _get_file_paths(self) -> list:
        paths = []
        for i in range(self.file_list.count()):
            paths.append(self.file_list.item(i).data(Qt.ItemDataRole.UserRole))
        return paths

    # ── Merge Execution ──────────────────────────────────────────

    def _start_merge(self):
        file_paths = self._get_file_paths()
        if len(file_paths) < 2:
            QMessageBox.warning(self, "Cảnh báo", "Cần ít nhất 2 file để gộp!")
            return

        if not self._current_type:
            QMessageBox.warning(self, "Cảnh báo", "Không xác định được loại file!")
            return

        # Determine output path
        config = TYPE_CONFIG[self._current_type]
        first_stem = Path(file_paths[0]).stem
        ext = Path(file_paths[0]).suffix

        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        default_name = f"{first_stem}_merged{ext}"
        default_path = os.path.join(output_dir, default_name)

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu file gộp",
            default_path,
            f"{config['filter']};;Tất cả (*.*)",
        )
        if not output_path:
            return

        # Prepare options
        options = {
            "add_page_break": self.chk_page_break.isChecked(),
            "add_separator": self.chk_separator.isChecked(),
            "add_source_marker": self.chk_source_marker.isChecked(),
        }

        # UI state
        self.btn_merge.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setValue(0)

        # Start worker
        from workers.merge_worker import MergeWorker

        self.worker = MergeWorker(
            file_paths=file_paths,
            output_path=output_path,
            merge_type=self._current_type,
            options=options,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._on_log)
        self.worker.completed.connect(self._on_completed)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self.log_text.append("⏹ Đã hủy.")

    def _on_progress(self, pct, msg):
        self.progress_bar.setValue(pct)
        self.progress_label.setText(msg)

    def _on_log(self, msg):
        self.log_text.append(msg)

    def _on_completed(self, output_path):
        self.progress_label.setText(f"✅ Gộp thành công: {Path(output_path).name}")
        reply = QMessageBox.question(
            self,
            "Thành công",
            f"Đã gộp {self.file_list.count()} file thành:\n{Path(output_path).name}\n\n"
            "Mở thư mục chứa file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            os.startfile(os.path.dirname(output_path))

    def _on_error(self, msg):
        self.log_text.append(f"❌ Lỗi: {msg}")
        self.progress_label.setText(f"❌ Lỗi: {msg[:80]}")
        QMessageBox.critical(self, "Lỗi Gộp File", msg)

    def _on_finished(self):
        self.btn_merge.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def _open_output_folder(self):
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        os.startfile(output_dir)

    # ── Drag & Drop from Explorer ────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        added = 0
        rejected = 0
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if self._add_file_to_list(path):
                added += 1
            else:
                rejected += 1

        self._update_type_label()

        if added:
            self.log_text.append(f"📎 Đã thêm {added} file từ kéo thả")
        if rejected:
            self.log_text.append(f"⚠️ Bỏ qua {rejected} file (khác định dạng)")
