"""Base API client — unified interface adapted from Dich-Viet BaseAIProvider."""

import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger("DocToMarkdownPro")


@dataclass
class APIConfig:
    """API provider configuration."""
    api_key: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.3
    base_url: Optional[str] = None


class APIBase(ABC):
    """Abstract base for all API clients."""

    def __init__(self, config: APIConfig):
        self.config = config
        self.max_retries = 5
        self.retry_delay = 3

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def _call_api(self, system_prompt: str, user_content: str) -> str:
        """Make API call and return response text."""
        pass

    def is_configured(self) -> bool:
        """Check if API key is set."""
        return bool(self.config.api_key and self.config.api_key.strip())

    def process_with_retry(self, system_prompt: str, user_content: str,
                           max_retries: Optional[int] = None) -> str:
        """Call API with retry and exponential backoff."""
        retries = max_retries or self.max_retries

        for attempt in range(1, retries + 1):
            try:
                result = self._call_api(system_prompt, user_content)
                if result and result.strip():
                    return result.strip()
                raise ValueError("Empty API response")

            except Exception as e:
                err_msg = str(e).lower()
                logger.warning(f"[{self.provider_name}] Attempt {attempt}/{retries}: {e}")

                if attempt >= retries:
                    raise

                # Determine wait time
                if "429" in str(e) or "rate" in err_msg:
                    wait = self.retry_delay * attempt * 2
                elif "timeout" in err_msg:
                    wait = self.retry_delay * attempt
                else:
                    wait = self.retry_delay * attempt

                logger.info(f"Waiting {wait}s before retry...")
                time.sleep(wait)

        raise RuntimeError(f"Failed after {retries} attempts")

    def build_conversion_prompt(self) -> str:
        """System prompt for document-to-markdown conversion."""
        return (
            "Bạn là chuyên gia chuyển đổi văn bản sang Markdown chuẩn.\n\n"
            "QUY TẮC NGHIÊM NGẶT:\n"
            "1. KHÔNG thêm nội dung không có trong văn bản gốc\n"
            "2. KHÔNG bỏ sót bất kỳ nội dung nào\n"
            "3. KHÔNG diễn giải, tóm tắt, hay sửa đổi nội dung\n"
            "4. Headings: # cho tiêu đề chính, ## cho mục, ### cho tiểu mục\n"
            "5. Tables → markdown table với | và ---\n"
            "6. Lists → dùng - hoặc 1. 2. 3.\n"
            "7. Giữ **bold**, *italic*, [links](url), `code`\n"
            "8. Giữ đúng thứ tự nội dung trong văn bản gốc\n"
            "9. Trả về CHỈ nội dung Markdown, không giải thích"
        )

    def build_translation_prompt(self, source_lang: str, target_lang: str) -> str:
        """System prompt for translation."""
        return (
            f"You are an expert translator with 20 years of experience.\n"
            f"Translate from {source_lang} to {target_lang}.\n\n"
            "IMPORTANT REQUIREMENTS:\n"
            "1. Translate ALL content, do not omit anything\n"
            "2. Preserve meaning and tone\n"
            "3. Natural, fluent style - not machine translation\n"
            "4. Preserve ALL formatting (headings, tables, code blocks, lists)\n"
            "5. Proper nouns: transcribe or keep original as appropriate\n"
            "6. Preserve code blocks, URLs, and technical terms\n"
            "7. DO NOT add or remove any content\n\n"
            "Output ONLY the translated text. No explanations."
        )

    def build_context_section(self, context_before: str = "", context_after: str = "") -> str:
        """Build context section for prompts (DO NOT translate/include)."""
        if not context_before and not context_after:
            return ""

        parts = [
            "\n" + "=" * 50,
            "CONTEXT (DO NOT include in your output - reference only):",
            "Use this context to maintain consistency in terminology and tone.",
            "-" * 50,
        ]
        if context_before:
            parts.append(f"[Previous]: ...{context_before}")
        if context_after:
            parts.append(f"[Next]: {context_after}...")
        parts.append("=" * 50 + "\n")
        return "\n".join(parts)
