"""Tab 2: Translation — markdown to translated markdown."""

import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QProgressBar, QFileDialog,
    QApplication, QMessageBox, QGroupBox,
)
from PyQt6.QtCore import Qt


class TabTranslation(QWidget):
    """Tab 2: Translate markdown documents."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Source section
        src_grp = QGroupBox("📝 Nguồn")
        src_layout = QVBoxLayout(src_grp)

        src_top = QHBoxLayout()
        self.btn_browse = QPushButton("📂 Chọn file MD")
        self.btn_browse.clicked.connect(self._browse_file)
        self.label_file = QLabel("Chưa chọn file")
        self.label_file.setObjectName("label_subtitle")
        src_top.addWidget(self.btn_browse)
        src_top.addWidget(self.label_file)
        src_top.addStretch()
        src_layout.addLayout(src_top)

        self.source_text = QTextEdit()
        self.source_text.setPlaceholderText("Paste nội dung cần dịch vào đây, hoặc chọn file...")
        self.source_text.setMaximumHeight(180)
        src_layout.addWidget(self.source_text)
        layout.addWidget(src_grp)

        # Settings row
        settings_row = QHBoxLayout()

        settings_row.addWidget(QLabel("Từ:"))
        self.combo_source_lang = QComboBox()
        self.combo_source_lang.addItems(["en", "vi", "zh", "ja", "ko", "fr", "de", "es"])
        settings_row.addWidget(self.combo_source_lang)

        settings_row.addWidget(QLabel("→"))

        settings_row.addWidget(QLabel("Sang:"))
        self.combo_target_lang = QComboBox()
        self.combo_target_lang.addItems(["vi", "en", "zh", "ja", "ko", "fr", "de", "es"])
        settings_row.addWidget(self.combo_target_lang)

        settings_row.addSpacing(20)

        settings_row.addWidget(QLabel("API:"))
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(["claude", "openai", "opencode", "custom"])
        settings_row.addWidget(self.combo_provider)

        settings_row.addStretch()
        layout.addLayout(settings_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Sẵn sàng")
        self.progress_label.setObjectName("label_subtitle")
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)

        # Result section
        result_grp = QGroupBox("🌐 Kết quả dịch")
        result_layout = QVBoxLayout(result_grp)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Kết quả dịch sẽ hiển thị tại đây...")
        result_layout.addWidget(self.result_text)

        result_btn_row = QHBoxLayout()
        self.btn_copy_all = QPushButton("📋 Copy All")
        self.btn_copy_all.clicked.connect(self._copy_all)
        result_btn_row.addWidget(self.btn_copy_all)
        result_btn_row.addStretch()
        result_layout.addLayout(result_btn_row)

        layout.addWidget(result_grp)

        # Action buttons
        action_row = QHBoxLayout()
        self.btn_translate = QPushButton("🌐 Bắt đầu dịch")
        self.btn_translate.setObjectName("btn_success")
        self.btn_translate.clicked.connect(self._start_translation)
        action_row.addWidget(self.btn_translate)

        self.btn_cancel = QPushButton("⏹ Hủy")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        action_row.addWidget(self.btn_cancel)

        action_row.addStretch()

        self.btn_save = QPushButton("💾 Lưu file")
        self.btn_save.clicked.connect(self._save_result)
        action_row.addWidget(self.btn_save)

        layout.addLayout(action_row)

        # Log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setPlaceholderText("Log...")
        layout.addWidget(self.log_text)

    def _browse_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Markdown", "",
            "Markdown (*.md);;Text (*.txt);;All (*.*)"
        )
        if filepath:
            self.label_file.setText(Path(filepath).name)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                self.source_text.setPlainText(content)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Không đọc được file: {e}")

    def _get_settings(self) -> dict:
        try:
            settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                         "config", "settings.json")
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _start_translation(self):
        text = self.source_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Warning", "Chưa có nội dung cần dịch!")
            return

        provider = self.combo_provider.currentText()
        settings = self._get_settings()
        api_config = settings.get("api", {}).get(provider, {})

        if not api_config.get("api_key"):
            QMessageBox.warning(self, "Warning",
                                f"Chưa cấu hình API key cho {provider}. Mở Settings.")
            return

        self.btn_translate.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.result_text.clear()
        self.log_text.clear()
        self.progress_bar.setValue(0)

        from workers.translator_worker import TranslatorWorker

        trans_settings = settings.get("translation", {})
        self.worker = TranslatorWorker(
            text=text,
            source_lang=self.combo_source_lang.currentText(),
            target_lang=self.combo_target_lang.currentText(),
            provider=provider,
            api_config=api_config,
            chunk_size=trans_settings.get("chunk_size", 3000),
        )

        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._on_log)
        self.worker.chunk_translated.connect(self._on_chunk_translated)
        self.worker.completed.connect(self._on_completed)
        self.worker.error.connect(self._on_error)
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

    def _on_chunk_translated(self, chunk_id, total, preview):
        self.log_text.append(f"  ✅ Chunk {chunk_id}/{total}: {preview}")

    def _on_completed(self, translated_text):
        self.result_text.setPlainText(translated_text)
        self.progress_label.setText("✅ Hoàn thành dịch!")
        self.log_text.append(f"\n✅ Dịch hoàn thành: {len(translated_text)} chars")

    def _on_error(self, msg):
        self.log_text.append(f"❌ {msg}")
        self.progress_label.setText(f"❌ Lỗi: {msg[:50]}")

    def _on_finished(self):
        self.btn_translate.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def _copy_all(self):
        text = self.result_text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def _save_result(self):
        text = self.result_text.toPlainText()
        if not text:
            QMessageBox.warning(self, "Warning", "Chưa có kết quả để lưu!")
            return

        target = self.combo_target_lang.currentText()
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Lưu file", f"translated_{target}.md",
            "Markdown (*.md);;Text (*.txt)"
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
            self.log_text.append(f"💾 Đã lưu: {filepath}")
