"""TranslatorWorker — translation QThread adapted from Dich-Viet."""

import os
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from workers.smart_chunker import SmartChunker
from workers.smart_merger import SmartMerger
from workers.quality_validator import QualityValidator
from workers.error_handler import ErrorHandler
from api.api_base import APIConfig


class TranslatorWorker(QThread):
    """Worker thread for translating markdown documents."""

    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    chunk_translated = pyqtSignal(int, int, str)  # (chunk_id, total, preview)
    completed = pyqtSignal(str)                    # translated_text
    error = pyqtSignal(str)                        # error_message

    def __init__(self, text: str, source_lang: str = "en", target_lang: str = "vi",
                 provider: str = "claude", api_config: dict = None,
                 chunk_size: int = 3000, parent=None):
        super().__init__(parent)
        self.text = text
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.provider = provider
        self.api_config = api_config or {}
        self.chunk_size = chunk_size
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _get_api_client(self):
        """Create API client."""
        config = APIConfig(
            api_key=self.api_config.get("api_key", ""),
            model=self.api_config.get("model", ""),
            max_tokens=self.api_config.get("max_tokens", 4096),
            temperature=0.3,
            base_url=self.api_config.get("base_url"),
        )

        if self.provider == "openai":
            from api.openai_client import OpenAIClient
            return OpenAIClient(config)
        elif self.provider == "claude":
            from api.claude_client import ClaudeClient
            return ClaudeClient(config)
        elif self.provider == "opencode":
            from api.opencode_client import OpenCodeClient
            return OpenCodeClient(config)
        elif self.provider == "custom":
            from api.custom_client import CustomClient
            return CustomClient(config)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def run(self):
        try:
            client = self._get_api_client()
            if not client.is_configured():
                self.error.emit("API key chưa được cấu hình. Mở Settings.")
                return
        except Exception as e:
            self.error.emit(f"Lỗi khởi tạo API: {e}")
            return

        try:
            # Step 1: Chunk text
            self.log.emit(f"📋 Chunking ({len(self.text)} chars)...")
            chunker = SmartChunker(max_chars=self.chunk_size, context_window=200)
            chunks = chunker.create_chunks(self.text)
            self.log.emit(f"📋 {len(chunks)} chunks")

            # Step 2: Build system prompt
            system_prompt = client.build_translation_prompt(self.source_lang, self.target_lang)

            # Step 3: Translate each chunk
            translated_chunks = []
            for chunk in chunks:
                if self._cancelled:
                    self.log.emit("⏹ Đã hủy dịch.")
                    return

                self.progress.emit(
                    int((chunk.id / len(chunks)) * 90),
                    f"Đang dịch phần {chunk.id}/{len(chunks)}..."
                )
                self.log.emit(f"  🌐 Translating chunk {chunk.id}/{len(chunks)}...")

                # Build content with context
                user_content = ""
                context_section = client.build_context_section(
                    chunk.context_before, chunk.context_after
                )
                if context_section:
                    user_content += context_section + "\n"
                user_content += (
                    f"TEXT TO TRANSLATE ({self.source_lang}):\n"
                    f"---START---\n{chunk.text}\n---END---\n\n"
                    f"IMPORTANT: Translate ONLY the text between ---START--- and ---END---.\n"
                    f"Output the {self.target_lang} translation only. No explanations, no context."
                )

                try:
                    result = client.process_with_retry(system_prompt, user_content)
                    # Clean result
                    result = result.replace("---START---", "").replace("---END---", "").strip()
                    chunk.text = result
                    translated_chunks.append(chunk)

                    preview = result[:100] + "..." if len(result) > 100 else result
                    self.chunk_translated.emit(chunk.id, len(chunks), preview)
                    self.log.emit(f"    ✅ Chunk {chunk.id}: {len(result)} chars")

                except Exception as e:
                    record = ErrorHandler.handle(e, context=f"translate:chunk_{chunk.id}")
                    user_msg = ErrorHandler.get_user_message(record)
                    self.log.emit(f"    ⚠️ Chunk {chunk.id}: {user_msg}")
                    # Keep original on failure
                    chunk.text = f"[TRANSLATION FAILED]\n{chunk.text}"
                    translated_chunks.append(chunk)

            # Step 4: Merge translated chunks
            self.progress.emit(95, "Gộp kết quả...")
            self.log.emit("🔗 Merging translated chunks...")
            merged = SmartMerger.merge_chunks(translated_chunks)

            # Step 5: Verify quality
            verification = QualityValidator.verify_translation(self.text, merged)
            if verification.warnings:
                for w in verification.warnings:
                    self.log.emit(f"  ⚠️ {w}")
            self.log.emit(f"📊 Translation quality: {verification.overall_score:.0%}")

            self.progress.emit(100, "Hoàn thành dịch!")
            self.completed.emit(merged)

        except Exception as e:
            record = ErrorHandler.handle(e, context="translator_worker")
            self.error.emit(ErrorHandler.get_user_message(record))
