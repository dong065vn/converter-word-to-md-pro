"""Settings dialog — API keys, OCR, preferences."""

import json
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QPushButton, QGroupBox, QFormLayout, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy


SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             "config", "settings.json")


class SettingsDialog(QDialog):
    """Settings dialog for API keys, OCR settings, and preferences."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Settings")
        self.setMinimumSize(700, 640)
        self.resize(760, 700)
        self.settings = self._load_settings()
        self._setup_ui()
        self._load_from_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # API Tab
        api_widget = QWidget()
        api_layout = QVBoxLayout(api_widget)
        api_layout.setContentsMargins(8, 8, 8, 8)
        api_layout.setSpacing(14)

        # OpenAI
        openai_grp = QGroupBox("OpenAI")
        openai_form = QFormLayout(openai_grp)
        self._configure_form_layout(openai_form)
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_model = QComboBox()
        self.openai_model.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
        self.openai_model.setEditable(True)
        self._configure_text_field(self.openai_key)
        self._configure_text_field(self.openai_model)
        openai_form.addRow("API Key:", self.openai_key)
        openai_form.addRow("Model:", self.openai_model)
        api_layout.addWidget(openai_grp)

        # Claude
        claude_grp = QGroupBox("Claude (Anthropic)")
        claude_form = QFormLayout(claude_grp)
        self._configure_form_layout(claude_form)
        self.claude_key = QLineEdit()
        self.claude_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.claude_model = QComboBox()
        self.claude_model.addItems(["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"])
        self.claude_model.setEditable(True)
        self._configure_text_field(self.claude_key)
        self._configure_text_field(self.claude_model)
        claude_form.addRow("API Key:", self.claude_key)
        claude_form.addRow("Model:", self.claude_model)
        api_layout.addWidget(claude_grp)

        # OpenCode
        opencode_grp = QGroupBox("OpenCode")
        opencode_form = QFormLayout(opencode_grp)
        self._configure_form_layout(opencode_form)
        self.opencode_key = QLineEdit()
        self.opencode_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.opencode_model = QComboBox()
        self.opencode_model.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"])
        self.opencode_model.setEditable(True)
        self.opencode_url = QLineEdit()
        self.opencode_url.setPlaceholderText("https://api.openai.com/v1")
        self._configure_text_field(self.opencode_key)
        self._configure_text_field(self.opencode_model)
        self._configure_text_field(self.opencode_url)
        opencode_form.addRow("API Key:", self.opencode_key)
        opencode_form.addRow("Model:", self.opencode_model)
        opencode_form.addRow("Base URL:", self.opencode_url)
        api_layout.addWidget(opencode_grp)

        # Custom
        custom_grp = QGroupBox("Custom Provider")
        custom_form = QFormLayout(custom_grp)
        self._configure_form_layout(custom_form)
        self.custom_key = QLineEdit()
        self.custom_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.custom_model = QLineEdit()
        self.custom_url = QLineEdit()
        self.custom_url.setPlaceholderText("https://your-api.com/v1")
        self._configure_text_field(self.custom_key)
        self._configure_text_field(self.custom_model)
        self._configure_text_field(self.custom_url)
        custom_form.addRow("API Key:", self.custom_key)
        custom_form.addRow("Model:", self.custom_model)
        custom_form.addRow("Base URL:", self.custom_url)
        api_layout.addWidget(custom_grp)

        api_layout.addStretch()
        tabs.addTab(api_widget, "🔑 API Keys")

        # Processing tab
        proc_widget = QWidget()
        proc_layout = QVBoxLayout(proc_widget)
        proc_layout.setContentsMargins(8, 8, 8, 8)
        proc_layout.setSpacing(14)

        conv_grp = QGroupBox("Conversion Settings")
        conv_form = QFormLayout(conv_grp)
        self._configure_form_layout(conv_form)
        self.chunk_size = QSpinBox()
        self.chunk_size.setRange(1000, 50000)
        self.chunk_size.setSingleStep(500)
        self.use_phases = QCheckBox("Tự động chia phases cho file lớn")
        self.auto_merge = QCheckBox("Tự động gộp phases")
        self.verify_output = QCheckBox("Xác minh dữ liệu sau chuyển đổi")
        conv_form.addRow("Chunk size:", self.chunk_size)
        conv_form.addRow("", self.use_phases)
        conv_form.addRow("", self.auto_merge)
        conv_form.addRow("", self.verify_output)
        proc_layout.addWidget(conv_grp)

        trans_grp = QGroupBox("Translation Settings")
        trans_form = QFormLayout(trans_grp)
        self._configure_form_layout(trans_form)
        self.trans_chunk = QSpinBox()
        self.trans_chunk.setRange(500, 20000)
        self.trans_chunk.setSingleStep(500)
        self.max_retries = QSpinBox()
        self.max_retries.setRange(1, 10)
        self.source_lang = QComboBox()
        self.source_lang.addItems(["en", "vi", "zh", "ja", "ko", "fr", "de", "es"])
        self.target_lang = QComboBox()
        self.target_lang.addItems(["vi", "en", "zh", "ja", "ko", "fr", "de", "es"])
        trans_form.addRow("Chunk size:", self.trans_chunk)
        trans_form.addRow("Max retries:", self.max_retries)
        trans_form.addRow("Source lang:", self.source_lang)
        trans_form.addRow("Target lang:", self.target_lang)
        proc_layout.addWidget(trans_grp)

        proc_layout.addStretch()
        tabs.addTab(proc_widget, "⚡ Processing")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Save")
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _configure_form_layout(self, form: QFormLayout):
        """Give settings forms a stable label/field layout."""
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setContentsMargins(14, 18, 14, 14)

    def _configure_text_field(self, widget):
        """Keep line edits and combos readable even on narrow layouts."""
        widget.setMinimumHeight(34)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _load_settings(self) -> dict:
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_from_settings(self):
        api = self.settings.get("api", {})
        self.openai_key.setText(api.get("openai", {}).get("api_key", ""))
        self.openai_model.setCurrentText(api.get("openai", {}).get("model", "gpt-4o"))
        self.claude_key.setText(api.get("claude", {}).get("api_key", ""))
        self.claude_model.setCurrentText(api.get("claude", {}).get("model", "claude-sonnet-4-20250514"))
        self.opencode_key.setText(api.get("opencode", {}).get("api_key", ""))
        self.opencode_model.setCurrentText(api.get("opencode", {}).get("model", "gpt-4o"))
        self.opencode_url.setText(api.get("opencode", {}).get("base_url", ""))
        self.custom_key.setText(api.get("custom", {}).get("api_key", ""))
        self.custom_model.setText(api.get("custom", {}).get("model", ""))
        self.custom_url.setText(api.get("custom", {}).get("base_url", ""))

        conv = self.settings.get("conversion", {})
        self.chunk_size.setValue(conv.get("chunk_size", 5000))
        self.use_phases.setChecked(conv.get("use_phases", True))
        self.auto_merge.setChecked(conv.get("auto_merge", True))
        self.verify_output.setChecked(conv.get("verify_output", True))

        trans = self.settings.get("translation", {})
        self.trans_chunk.setValue(trans.get("chunk_size", 3000))
        self.max_retries.setValue(trans.get("max_retries", 5))
        idx = self.source_lang.findText(trans.get("source_lang", "en"))
        if idx >= 0:
            self.source_lang.setCurrentIndex(idx)
        idx = self.target_lang.findText(trans.get("target_lang", "vi"))
        if idx >= 0:
            self.target_lang.setCurrentIndex(idx)

    def _save(self):
        self.settings = {
            "api": {
                "openai": {
                    "api_key": self.openai_key.text(),
                    "model": self.openai_model.currentText(),
                    "max_tokens": 4096,
                },
                "claude": {
                    "api_key": self.claude_key.text(),
                    "model": self.claude_model.currentText(),
                    "max_tokens": 4096,
                },
                "opencode": {
                    "api_key": self.opencode_key.text(),
                    "model": self.opencode_model.currentText(),
                    "base_url": self.opencode_url.text(),
                    "max_tokens": 4096,
                },
                "custom": {
                    "api_key": self.custom_key.text(),
                    "model": self.custom_model.text(),
                    "base_url": self.custom_url.text(),
                    "max_tokens": 4096,
                },
            },
            "conversion": {
                "chunk_size": self.chunk_size.value(),
                "use_phases": self.use_phases.isChecked(),
                "auto_merge": self.auto_merge.isChecked(),
                "verify_output": self.verify_output.isChecked(),
            },
            "translation": {
                "chunk_size": self.trans_chunk.value(),
                "max_retries": self.max_retries.value(),
                "source_lang": self.source_lang.currentText(),
                "target_lang": self.target_lang.currentText(),
            },
        }

        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)

        self.accept()

    def get_provider_config(self, provider: str) -> dict:
        """Get config dict for a specific provider."""
        api = self.settings.get("api", {})
        return api.get(provider, {})
