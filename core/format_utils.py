"""Utility functions: converter factory, extension handling, normalization."""

import os
from pathlib import Path
from typing import Optional

# Supported extensions by category
WORD_EXTENSIONS = {".docx"}
EXCEL_EXTENSIONS = {".xlsx", ".xls"}
PPTX_EXTENSIONS = {".pptx"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

ALL_EXTENSIONS = WORD_EXTENSIONS | EXCEL_EXTENSIONS | PPTX_EXTENSIONS | PDF_EXTENSIONS | IMAGE_EXTENSIONS


def get_file_type(filepath: str) -> Optional[str]:
    """Return file type category: 'word', 'excel', 'pptx', 'pdf', 'image' or None."""
    ext = Path(filepath).suffix.lower()
    if ext in WORD_EXTENSIONS:
        return "word"
    elif ext in EXCEL_EXTENSIONS:
        return "excel"
    elif ext in PPTX_EXTENSIONS:
        return "pptx"
    elif ext in PDF_EXTENSIONS:
        return "pdf"
    elif ext in IMAGE_EXTENSIONS:
        return "image"
    return None


def get_converter_for_file(filepath: str, output_dir: str = "output"):
    """Factory: return appropriate converter instance for file."""
    file_type = get_file_type(filepath)
    if file_type == "word":
        from .word_converter import WordConverter
        return WordConverter(output_dir)
    elif file_type == "excel":
        from .excel_converter import ExcelConverter
        return ExcelConverter(output_dir)
    elif file_type == "pptx":
        from .pptx_converter import PptxConverter
        return PptxConverter(output_dir)
    elif file_type == "pdf":
        from .pdf_converter import PdfConverter
        return PdfConverter(output_dir)
    elif file_type == "image":
        from .image_converter import ImageConverter
        return ImageConverter(output_dir)
    else:
        raise ValueError(f"Unsupported file format: {Path(filepath).suffix}")


def supported_extensions_display() -> str:
    """Return human-readable supported extensions string."""
    exts = sorted(ALL_EXTENSIONS)
    return ", ".join(e.upper().lstrip(".") for e in exts)


def get_filter_string() -> str:
    """Return file dialog filter string."""
    all_exts = " ".join(f"*{e}" for e in sorted(ALL_EXTENSIONS))
    return (
        f"All Supported ({all_exts});;"
        f"Word (*.docx);;"
        f"Excel (*.xlsx *.xls);;"
        f"PowerPoint (*.pptx);;"
        f"PDF (*.pdf);;"
        f"Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp)"
    )
