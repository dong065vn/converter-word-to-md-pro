"""Abstract base class for all document converters."""

import os
import re
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class ConverterBase(ABC):
    """Base converter with common utilities."""

    def __init__(self, output_dir: str = "output", image_output_dir: Optional[str] = None):
        self.output_dir = output_dir
        self.image_output_dir = image_output_dir or os.path.join(output_dir, "images")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.image_output_dir, exist_ok=True)

    @abstractmethod
    def convert(self, filepath: str) -> str:
        """Convert file to markdown string."""
        pass

    def convert_and_save(self, filepath: str, output_path: Optional[str] = None) -> str:
        """Convert and save to .md file. Returns output path."""
        md_content = self.convert(filepath)
        if not output_path:
            stem = Path(filepath).stem
            output_path = os.path.join(self.output_dir, f"{stem}.md")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        return output_path

    @staticmethod
    def cleanup_text(text: str) -> str:
        """Normalize unicode, fix whitespace, clean text."""
        if not text:
            return ""
        # Normalize unicode
        text = unicodedata.normalize("NFC", text)
        # Fix multiple spaces (but not newlines)
        text = re.sub(r"[^\S\n]+", " ", text)
        # Fix multiple blank lines (max 2)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip trailing whitespace per line
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)
        return text.strip()

    @staticmethod
    def normalize_markdown(text: str) -> str:
        """Post-process markdown for consistency."""
        if not text:
            return ""
        # Ensure headings have blank line before
        text = re.sub(r"([^\n])\n(#{1,6}\s)", r"\1\n\n\2", text)
        # Ensure blank line after headings
        text = re.sub(r"(#{1,6}\s[^\n]+)\n([^\n#])", r"\1\n\n\2", text)
        # Fix table alignment
        text = re.sub(r"\n{2,}(\|)", r"\n\1", text)
        # Remove trailing spaces
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)
        # Max 2 consecutive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def escape_md(text: str) -> str:
        """Escape special markdown characters in inline text."""
        if not text:
            return ""
        for ch in ["\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "!", "|"]:
            text = text.replace(ch, f"\\{ch}")
        return text
