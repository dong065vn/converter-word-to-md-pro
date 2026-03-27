"""PDF to Markdown converter — font-size heading detection + table exclusion + OCR fallback."""

import re
from typing import List, Optional

import pdfplumber

from .converter_base import ConverterBase


class PdfConverter(ConverterBase):
    """Convert PDF to Markdown with smart heading detection and OCR fallback."""

    def convert(self, filepath: str) -> str:
        pages_md = []

        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = self._process_page(page, page_num)
                if page_text:
                    pages_md.append(page_text)

        # If no text extracted, try OCR fallback
        if not any(p.strip() for p in pages_md):
            ocr_result = self._ocr_fallback(filepath)
            if ocr_result:
                return self.normalize_markdown(self.cleanup_text(ocr_result))

        result = "\n\n".join(pages_md)
        return self.normalize_markdown(self.cleanup_text(result))

    def _process_page(self, page, page_num: int) -> str:
        """Process a single PDF page with table exclusion zones."""
        lines = []

        # Step 1: Extract tables and their bounding boxes
        tables = page.find_tables()
        table_bboxes = []
        table_markdowns = []

        for table in tables:
            try:
                bbox = table.bbox
                table_bboxes.append(bbox)
                table_data = table.extract()
                if table_data:
                    table_md = self._table_to_markdown(table_data)
                    table_markdowns.append((bbox[1], table_md))  # (y_position, markdown)
            except Exception:
                continue

        # Step 2: Extract text with font-size analysis, excluding table zones
        try:
            chars = page.chars
        except Exception:
            chars = []

        if chars:
            text_md = self._chars_to_markdown(chars, table_bboxes)
        else:
            # Fallback to simple text extraction
            text = page.extract_text() or ""
            if text.strip():
                # Exclude table content from text
                for bbox in table_bboxes:
                    crop = page.within_bbox(bbox)
                    table_text = crop.extract_text() or ""
                    text = text.replace(table_text, "", 1)
                text_md = text.strip()
            else:
                text_md = ""

        # Step 3: Interleave tables at approximate positions
        if table_markdowns and text_md:
            # Simple approach: append tables after text for now
            parts = [text_md]
            for _, tmd in sorted(table_markdowns, key=lambda x: x[0]):
                parts.append("")
                parts.append(tmd)
            lines.append("\n".join(parts))
        elif text_md:
            lines.append(text_md)
        elif table_markdowns:
            for _, tmd in sorted(table_markdowns, key=lambda x: x[0]):
                lines.append(tmd)

        return "\n".join(lines)

    def _chars_to_markdown(self, chars: List[dict], table_bboxes: List) -> str:
        """Convert chars with font-size analysis to markdown."""
        # Filter chars outside table zones
        filtered_chars = []
        for ch in chars:
            if ch.get("text", "").strip() == "":
                filtered_chars.append(ch)
                continue
            in_table = False
            for bbox in table_bboxes:
                x0, y0, x1, y1 = bbox
                cx, cy = ch.get("x0", 0), ch.get("top", 0)
                if x0 <= cx <= x1 and y0 <= cy <= y1:
                    in_table = True
                    break
            if not in_table:
                filtered_chars.append(ch)

        if not filtered_chars:
            return ""

        # Compute median font size
        font_sizes = [ch.get("size", 12) for ch in filtered_chars if ch.get("text", "").strip()]
        if not font_sizes:
            return ""
        font_sizes.sort()
        median_size = font_sizes[len(font_sizes) // 2]

        # Group chars into lines by y-coordinate
        lines_dict = {}
        for ch in filtered_chars:
            y = round(ch.get("top", 0), 1)
            # Group by similar y (within 2 points)
            found_y = None
            for existing_y in lines_dict:
                if abs(existing_y - y) < 2:
                    found_y = existing_y
                    break
            if found_y is not None:
                lines_dict[found_y].append(ch)
            else:
                lines_dict[y] = [ch]

        # Sort lines by y position, sort chars by x position
        result_lines = []
        for y in sorted(lines_dict.keys()):
            line_chars = sorted(lines_dict[y], key=lambda c: c.get("x0", 0))
            line_text = "".join(ch.get("text", "") for ch in line_chars).strip()
            if not line_text:
                result_lines.append("")
                continue

            # Determine if heading based on font size
            avg_size = sum(ch.get("size", median_size) for ch in line_chars if ch.get("text", "").strip()) / max(
                len([ch for ch in line_chars if ch.get("text", "").strip()]), 1
            )

            if avg_size > median_size * 1.5 and len(line_text) < 100:
                result_lines.append(f"# {line_text}")
            elif avg_size > median_size * 1.3 and len(line_text) < 100:
                result_lines.append(f"## {line_text}")
            elif avg_size > median_size * 1.15 and len(line_text) < 100:
                result_lines.append(f"### {line_text}")
            else:
                # Detect list items
                if re.match(r"^[•●○▪▸►]\s*", line_text):
                    line_text = re.sub(r"^[•●○▪▸►]\s*", "- ", line_text)
                elif re.match(r"^\d+[.)\]]\s+", line_text):
                    pass  # Already numbered
                result_lines.append(line_text)

        # Group into paragraphs
        final_lines = []
        prev_empty = False
        for line in result_lines:
            if not line:
                if not prev_empty:
                    final_lines.append("")
                prev_empty = True
            else:
                prev_empty = False
                final_lines.append(line)

        return "\n".join(final_lines)

    def _table_to_markdown(self, table_data: List[List]) -> str:
        """Convert table data to markdown table."""
        if not table_data:
            return ""

        # Clean cells
        cleaned = []
        for row in table_data:
            cleaned_row = []
            for cell in row:
                text = str(cell or "").replace("|", "\\|").replace("\n", " ").strip()
                cleaned_row.append(text)
            cleaned.append(cleaned_row)

        max_cols = max(len(r) for r in cleaned)
        for row in cleaned:
            while len(row) < max_cols:
                row.append("")

        lines = []
        lines.append("| " + " | ".join(cleaned[0]) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        for row in cleaned[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def _ocr_fallback(self, filepath: str) -> Optional[str]:
        """OCR fallback for scanned PDFs using PyMuPDF + pytesseract."""
        try:
            import fitz  # PyMuPDF
            from PIL import Image
            import io

            doc = fitz.open(filepath)
            pages_text = []

            for page_num in range(doc.page_count):
                page = doc[page_num]
                # Render at 300 DPI
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))

                # OCR
                try:
                    import pytesseract
                    text = pytesseract.image_to_string(img, lang="vie+eng")
                    if text.strip():
                        pages_text.append(text.strip())
                except ImportError:
                    try:
                        import easyocr
                        reader = easyocr.Reader(["vi", "en"], gpu=False, verbose=False)
                        results = reader.readtext(img_data)
                        text = "\n".join(r[1] for r in results)
                        if text.strip():
                            pages_text.append(text.strip())
                    except ImportError:
                        pass

            doc.close()
            return "\n\n".join(pages_text) if pages_text else None

        except ImportError:
            return None
        except Exception:
            return None
