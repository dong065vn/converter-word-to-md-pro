"""MergeWorker — QThread for background file merging."""

import os
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


MERGE_EXTENSIONS = {
    ".md": "markdown",
    ".txt": "markdown",
    ".docx": "word",
    ".pdf": "pdf",
}


def detect_merge_type(filepath: str) -> str:
    """Return merge type from file extension."""
    ext = Path(filepath).suffix.lower()
    return MERGE_EXTENSIONS.get(ext, "")


class MergeWorker(QThread):
    """Worker thread for merging files."""

    progress = pyqtSignal(int, str)   # (percentage, message)
    log = pyqtSignal(str)             # log message
    completed = pyqtSignal(str)       # output_path
    error = pyqtSignal(str)           # error message

    def __init__(
        self,
        file_paths: list,
        output_path: str,
        merge_type: str,
        options: dict = None,
        parent=None,
    ):
        super().__init__(parent)
        self.file_paths = file_paths
        self.output_path = output_path
        self.merge_type = merge_type
        self.options = options or {}
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._validate()
            self._execute_merge()
            self._verify()
        except Exception as e:
            self.error.emit(str(e))

    def _validate(self):
        """Validate all files exist and are same type."""
        self.log.emit(f"🔍 Validating {len(self.file_paths)} files...")
        self.progress.emit(0, "Đang kiểm tra file...")

        for filepath in self.file_paths:
            if self._cancelled:
                return

            if not os.path.exists(filepath):
                raise FileNotFoundError(f"File không tồn tại: {filepath}")

            detected = detect_merge_type(filepath)
            if detected != self.merge_type:
                raise ValueError(
                    f"File {Path(filepath).name} ({detected}) "
                    f"không cùng loại với merge type ({self.merge_type})"
                )

        self.log.emit(f"  ✅ Tất cả {len(self.file_paths)} file hợp lệ")

    def _execute_merge(self):
        """Run the appropriate merger."""
        if self._cancelled:
            return

        total = len(self.file_paths)
        self.log.emit(f"🔗 Bắt đầu gộp {total} file ({self.merge_type})...")

        def on_progress(i, t, name):
            if self._cancelled:
                return
            pct = int((i / max(t, 1)) * 80) + 10  # 10-90%
            self.progress.emit(pct, f"Đang gộp: {name} ({i + 1}/{t})")
            if i < t:
                self.log.emit(f"  📄 [{i + 1}/{t}] {name}")

        if self.merge_type == "markdown":
            from core.md_merger import MarkdownMerger
            merger = MarkdownMerger()
            merger.merge(
                self.file_paths,
                self.output_path,
                add_separator=self.options.get("add_separator", True),
                add_source_marker=self.options.get("add_source_marker", False),
                on_progress=on_progress,
            )

        elif self.merge_type == "word":
            from core.word_merger import WordMerger
            merger = WordMerger()
            merger.merge(
                self.file_paths,
                self.output_path,
                add_page_break=self.options.get("add_page_break", True),
                on_progress=on_progress,
            )

        elif self.merge_type == "pdf":
            from core.pdf_merger import PdfMerger
            merger = PdfMerger()
            merger.merge(
                self.file_paths,
                self.output_path,
                on_progress=on_progress,
            )

        else:
            raise ValueError(f"Unsupported merge type: {self.merge_type}")

        self.progress.emit(90, "Đã gộp xong, đang kiểm tra...")
        self.log.emit(f"  ✅ Gộp hoàn tất → {Path(self.output_path).name}")

    def _verify(self):
        """Verify the merged output."""
        if self._cancelled:
            return

        self.log.emit("🔍 Đang xác minh kết quả...")

        if not os.path.exists(self.output_path):
            raise FileNotFoundError(f"File output không tồn tại: {self.output_path}")

        output_size = os.path.getsize(self.output_path)
        if output_size == 0:
            raise ValueError("File output rỗng!")

        # Type-specific verification
        if self.merge_type == "markdown":
            from core.md_merger import MarkdownMerger
            result = MarkdownMerger.verify(self.file_paths, self.output_path)
            if not result["complete"]:
                missing = ", ".join(result["missing"])
                self.log.emit(f"  ⚠️ Thiếu nội dung từ: {missing}")
            else:
                self.log.emit(f"  ✅ Xác minh: {result['found']}/{result['total_sources']} file đầy đủ")

        elif self.merge_type == "word":
            from core.word_merger import WordMerger
            result = WordMerger.verify(self.file_paths, self.output_path)
            if not result["complete"]:
                missing = ", ".join(result["missing"])
                self.log.emit(f"  ⚠️ Thiếu nội dung từ: {missing}")
            else:
                self.log.emit(f"  ✅ Xác minh: {result['found']}/{result['total_sources']} file đầy đủ")

        elif self.merge_type == "pdf":
            from core.pdf_merger import PdfMerger
            result = PdfMerger.verify(self.file_paths, self.output_path)
            self.log.emit(
                f"  📊 Tổng trang: {result['actual_pages']}/{result['expected_pages']} "
                f"({result['output_size_mb']} MB)"
            )
            if not result["complete"]:
                self.log.emit(f"  ⚠️ Số trang không khớp!")

        self.progress.emit(100, "Hoàn thành!")
        size_display = (
            f"{output_size / (1024 * 1024):.1f} MB"
            if output_size > 1024 * 1024
            else f"{output_size / 1024:.1f} KB"
        )
        self.log.emit(f"\n✅ Gộp thành công: {Path(self.output_path).name} ({size_display})")
        self.completed.emit(self.output_path)
