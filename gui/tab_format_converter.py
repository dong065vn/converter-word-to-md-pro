"""Tab 3: Format Converter — Direct conversion using Pandoc."""

import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QTextEdit,
    QComboBox, QProgressBar, QFileDialog, QMessageBox, QStyle, QLineEdit,
    QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent


class PandocWorker(QThread):
    """Background thread for executing Pandoc conversions."""
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    completed = pyqtSignal(int, int) # success, total

    def __init__(self, file_paths, output_dir, target_ext, template_path=None, use_toc=False):
        super().__init__()
        self.file_paths = file_paths
        self.output_dir = output_dir
        self.target_ext = target_ext
        self.template_path = template_path
        self.use_toc = use_toc
        self.is_cancelled = False

    def run(self):
        total = len(self.file_paths)
        success = 0
        self.progress.emit(0, "Bắt đầu chuyển đổi...")

        for i, filepath in enumerate(self.file_paths):
            if self.is_cancelled:
                self.log.emit("⚠️ Đã hủy tiến trình.")
                break

            filename = Path(filepath).name
            stem = Path(filepath).stem
            self.log.emit(f"🔄 Đang xử lý: {filename}")
            
            # Format target extension to ensure it starts with dot
            ext = self.target_ext if self.target_ext.startswith('.') else f".{self.target_ext}"
            out_name = f"{stem}{ext}"
            out_path = os.path.join(self.output_dir, out_name)

            cmd = ["pandoc", filepath, "-o", out_path]
            
            if self.template_path and os.path.exists(self.template_path):
                cmd.extend(["--reference-doc", self.template_path])
                
            if self.use_toc:
                cmd.append("--toc")

            try:
                creationflags = 0
                if os.name == 'nt':
                    creationflags = subprocess.CREATE_NO_WINDOW
                    
                result = subprocess.run(cmd, check=True, creationflags=creationflags, capture_output=True, text=True)
                success += 1
                self.log.emit(f"  ✅ Thành công: {out_name}")
            except FileNotFoundError:
                self.log.emit("  ❌ Lỗi: Không tìm thấy Pandoc. Vui lòng cài đặt và thêm vào PATH.")
                break
            except subprocess.CalledProcessError as e:
                self.log.emit(f"  ❌ Lỗi Pandoc ({filename}): {e.stderr}")
            except Exception as e:
                self.log.emit(f"  ❌ Lỗi bất ngờ ({filename}): {str(e)}")

            pct = int(((i + 1) / total) * 100)
            self.progress.emit(pct, f"Đã xử lý {i + 1}/{total} file")

        self.completed.emit(success, total)

    def cancel(self):
        self.is_cancelled = True


class TabFormatConverter(QWidget):
    """Tab 3: Batch document conversion using Pandoc."""

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
        file_grp = QGroupBox("📂 File Cần Chuyển Đổi")
        file_layout = QVBoxLayout(file_grp)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("📎 Thêm file (Word, MD, TXT)")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_remove = QPushButton()
        self.btn_remove.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.btn_remove.setIconSize(self.btn_add.iconSize())
        self.btn_remove.setToolTip("Bỏ file đã chọn")
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
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        file_layout.addWidget(self.file_list)

        sidebar_layout.addWidget(file_grp)

        # Format Settings
        fmt_grp = QGroupBox("⚙️ Cấu Hình Chuyển Đổi")
        fmt_layout = QVBoxLayout(fmt_grp)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Định dạng đích:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems([
            "pdf", "docx", "html", "epub", "rst", "latex", "custom..."
        ])
        self.combo_format.currentTextChanged.connect(self._on_format_changed)
        fmt_row.addWidget(self.combo_format)
        fmt_layout.addLayout(fmt_row)
        
        self.line_custom_ext = QLineEdit()
        self.line_custom_ext.setPlaceholderText("VD: odt, rtf, txte...")
        self.line_custom_ext.setVisible(False)
        fmt_layout.addWidget(self.line_custom_ext)
        
        self.chk_toc = QCheckBox("☑ Tạo Mục lục (TOC)")
        fmt_layout.addWidget(self.chk_toc)

        # Template for Word
        self.template_layout = QVBoxLayout()
        self.template_layout.addWidget(QLabel("Template Word (Reference Doc):"))
        tpl_row = QHBoxLayout()
        self.line_template = QLineEdit()
        self.line_template.setPlaceholderText("Đường dẫn file .docx")
        self.btn_browse_tpl = QPushButton("📁")
        self.btn_browse_tpl.clicked.connect(self._browse_template)
        tpl_row.addWidget(self.line_template)
        tpl_row.addWidget(self.btn_browse_tpl)
        self.template_layout.addLayout(tpl_row)
        fmt_layout.addLayout(self.template_layout)

        sidebar_layout.addWidget(fmt_grp)

        # Action buttons
        sidebar_layout.addStretch()
        self.btn_convert = QPushButton("🚀 Chuyển Đổi Hàng Loạt")
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

        # Log Result
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Tiến trình và kết quả chuyển đổi sẽ hiển thị tại đây...")
        main_layout_right.addWidget(self.log_text)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        self.btn_open_folder = QPushButton("📁 Mở Thư mục Output")
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_open_folder)
        main_layout_right.addLayout(bottom_row)

        splitter.addWidget(main_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)
        
        self._on_format_changed(self.combo_format.currentText())

    def _on_format_changed(self, text):
        is_custom = text == "custom..."
        self.line_custom_ext.setVisible(is_custom)
        
        is_docx = text == "docx" or (is_custom and self.line_custom_ext.text().strip().lower() == "docx")
        for i in range(self.template_layout.count()):
            widget = self.template_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(is_docx)
            elif self.template_layout.itemAt(i).layout():
                layout = self.template_layout.itemAt(i).layout()
                for j in range(layout.count()):
                    w = layout.itemAt(j).widget()
                    if w: w.setVisible(is_docx)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn file", "",
            "Tài liệu hỗ trợ (*.docx *.md *.txt);;Word (*.docx);;Markdown (*.md);;Text (*.txt);;Tất cả (*.*)"
        )
        for f in files:
            self._add_file_to_list(f)

    def _add_file_to_list(self, filepath):
        if not any(self.file_list.item(i).data(Qt.ItemDataRole.UserRole) == filepath
                   for i in range(self.file_list.count())):
            item = QListWidgetItem(f"📄 {Path(filepath).name}")
            item.setData(Qt.ItemDataRole.UserRole, filepath)
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

    def _browse_template(self):
        file, _ = QFileDialog.getOpenFileName(self, "Chọn file Template", "", "Word Document (*.docx)")
        if file:
            self.line_template.setText(file)

    def _start_conversion(self):
        file_paths = self._get_file_paths()
        if not file_paths:
            QMessageBox.warning(self, "Cảnh báo", "Chưa có file nào trong danh sách!")
            return

        fmt = self.combo_format.currentText()
        if fmt == "custom...":
            fmt = self.line_custom_ext.text().strip()
            if not fmt:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập định dạng mở rộng tùy chỉnh!")
                return
                
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)

        self.btn_convert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        tpl_path = self.line_template.text().strip() if "docx" in fmt else None

        self.worker = PandocWorker(
            file_paths=file_paths,
            output_dir=output_dir,
            target_ext=fmt,
            template_path=tpl_path,
            use_toc=self.chk_toc.isChecked()
        )
        
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._on_log)
        self.worker.completed.connect(self._on_completed)
        self.worker.start()

    def _cancel(self):
        if self.worker:
            self.worker.cancel()

    def _on_progress(self, pct, msg):
        self.progress_bar.setValue(pct)
        self.progress_label.setText(msg)

    def _on_log(self, msg):
        self.log_text.append(msg)

    def _on_completed(self, success, total):
        self.btn_convert.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        if success == total:
            self.progress_label.setText(f"✅ Đã hoàn thành toàn bộ ({success}/{total} file)")
        else:
            self.progress_label.setText(f"⚠️ Hoàn thành với lỗi ({success}/{total} thành công)")

    def _open_output_folder(self):
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        os.startfile(output_dir)

    # Drag & Drop Support
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            ext = Path(path).suffix.lower()
            if ext in [".docx", ".md", ".txt"]:
                self._add_file_to_list(path)
            else:
                self.log_text.append(f"⚠️ Bỏ qua file không hỗ trợ: {Path(path).name}")
