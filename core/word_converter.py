"""Word (.docx) to Markdown converter — XML tree traversal."""

from typing import Optional
from zipfile import BadZipFile

from docx import Document
from docx.oxml.ns import qn
from docx.opc.exceptions import PackageNotFoundError

from .converter_base import ConverterBase


class WordConverter(ConverterBase):
    """Convert .docx to Markdown using XML body tree traversal."""

    def convert(self, filepath: str) -> str:
        try:
            doc = Document(filepath)
        except (BadZipFile, PackageNotFoundError) as exc:
            raise ValueError(f"Word package is invalid or unreadable: {filepath}") from exc

        lines = []
        footnotes = {}

        # Extract footnotes if available
        try:
            footnotes = self._extract_footnotes(doc)
        except Exception:
            pass

        # Iterate XML body children to preserve table/paragraph order
        body = doc.element.body
        for child in body:
            tag = self._local_name(child)

            if tag == "p":
                line = self._process_paragraph(child, doc, filepath)
                if line is not None:
                    lines.append(line)

            elif tag == "tbl":
                table_md = self._process_table_element(child, doc)
                if table_md:
                    lines.append("")
                    lines.append(table_md)
                    lines.append("")

            elif tag == "sectPr":
                continue  # Skip section properties

        # Append footnotes
        if footnotes:
            lines.append("")
            lines.append("---")
            lines.append("")
            for fn_id, fn_text in sorted(footnotes.items()):
                lines.append(f"[^{fn_id}]: {fn_text}")

        result = "\n".join(lines)
        return self.normalize_markdown(self.cleanup_text(result))

    def _process_paragraph(self, p_element, doc, filepath) -> Optional[str]:
        """Process a single paragraph element."""
        from docx.text.paragraph import Paragraph
        para = Paragraph(p_element, doc)
        run_map = {id(run._element): run for run in para.runs}

        # Get style info
        try:
            style_name = para.style.name if para.style else ""
        except Exception:
            style_name = ""
        text_parts = []

        # Process runs and hyperlinks in original XML order.
        for child in p_element:
            tag = self._local_name(child)
            if tag == "r":
                run = run_map.get(id(child))
                run_text = self._format_run(run) if run is not None else self._text_from_element(child)
                if run_text:
                    text_parts.append(run_text)
            elif tag == "hyperlink":
                link_text = self._extract_hyperlink_text(child)
                if not link_text:
                    continue
                url = self._extract_hyperlink_url(child, doc)
                text_parts.append(f"[{link_text}]({url})" if url else link_text)
            elif tag in {"bookmarkStart", "bookmarkEnd", "proofErr"}:
                continue

        text = "".join(text_parts)

        if not text.strip():
            return ""

        # Detect heading
        if style_name.startswith("Heading"):
            try:
                level = int(style_name.split()[-1])
                level = min(level, 6)
            except (ValueError, IndexError):
                level = 1
            return f"{'#' * level} {text.strip()}"

        # Detect list items
        pPr = p_element.find(qn("w:pPr"))
        numPr = pPr.find(qn("w:numPr")) if pPr is not None else None
        if numPr is not None:
            ilvl_elem = numPr.find(qn("w:ilvl"))
            indent_level = int(ilvl_elem.get(qn("w:val"), "0")) if ilvl_elem is not None else 0
            indent = "  " * indent_level

            numId_elem = numPr.find(qn("w:numId"))
            if numId_elem is not None:
                num_id = numId_elem.get(qn("w:val"), "0")
                # Simple heuristic: even numId = ordered, odd = unordered
                if int(num_id) % 2 == 0:
                    return f"{indent}1. {text.strip()}"
            return f"{indent}- {text.strip()}"

        # Detect indentation for blockquote
        if pPr is not None:
            ind = pPr.find(qn("w:ind"))
            if ind is not None:
                left = ind.get(qn("w:left"), "0")
                if int(left) > 700:  # ~1cm indent
                    return f"> {text.strip()}"

        return text.strip()

    def _process_table_element(self, tbl_element, doc) -> str:
        """Process table element to markdown table."""
        rows_data = []

        for tr in tbl_element:
            if self._local_name(tr) != "tr":
                continue
            row = []
            for tc in tr:
                if self._local_name(tc) != "tc":
                    continue
                cell_text = self._text_from_element(tc)
                cell_text = cell_text.replace("|", "\\|").replace("\n", " ").strip()
                row.append(cell_text)
            if row:
                rows_data.append(row)

        if not rows_data:
            return ""

        # Normalize column count
        max_cols = max(len(r) for r in rows_data)
        for row in rows_data:
            while len(row) < max_cols:
                row.append("")

        # Build markdown table
        lines = []
        header = "| " + " | ".join(rows_data[0]) + " |"
        separator = "| " + " | ".join(["---"] * max_cols) + " |"
        lines.append(header)
        lines.append(separator)
        for row in rows_data[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def _extract_footnotes(self, doc) -> dict:
        """Extract footnotes from document."""
        footnotes = {}
        try:
            fn_part = doc.part.footnotes_part
            if fn_part:
                for fn in fn_part.element:
                    if self._local_name(fn) != "footnote":
                        continue
                    fn_id = fn.get(qn("w:id"))
                    if fn_id and int(fn_id) > 0:
                        text_parts = []
                        for p in fn:
                            if self._local_name(p) != "p":
                                continue
                            paragraph_text = self._text_from_element(p).strip()
                            if paragraph_text:
                                text_parts.append(paragraph_text)
                        if text_parts:
                            footnotes[fn_id] = " ".join(text_parts)
        except Exception:
            pass
        return footnotes

    @staticmethod
    def _local_name(element) -> str:
        """Return XML tag local name regardless of namespace."""
        tag = getattr(element, "tag", "")
        return tag.split("}", 1)[-1] if "}" in tag else tag

    def _text_from_element(self, element) -> str:
        """Collect concatenated text recursively from an XML element."""
        parts = []
        for node in element.iter():
            if self._local_name(node) in {"t", "instrText"} and node.text:
                parts.append(node.text)
            elif self._local_name(node) == "tab":
                parts.append("\t")
            elif self._local_name(node) in {"br", "cr"}:
                parts.append("\n")
        return "".join(parts)

    def _format_run(self, run) -> str:
        """Apply basic markdown formatting to a run safely."""
        run_text = (run.text or "") if run is not None else ""
        if not run_text:
            return ""

        try:
            if run.bold and run.italic:
                run_text = f"***{run_text}***"
            elif run.bold:
                run_text = f"**{run_text}**"
            elif run.italic:
                run_text = f"*{run_text}*"
            if run.underline:
                run_text = f"<u>{run_text}</u>"
            if getattr(run.font, "strikethrough", False):
                run_text = f"~~{run_text}~~"
        except Exception:
            return run_text

        return run_text

    def _extract_hyperlink_text(self, hyperlink_element) -> str:
        """Extract visible hyperlink text."""
        return self._text_from_element(hyperlink_element).strip()

    @staticmethod
    def _extract_hyperlink_url(hyperlink_element, doc) -> str:
        """Resolve hyperlink target from document relationships."""
        r_id = hyperlink_element.get(qn("r:id"))
        if not r_id:
            return ""
        try:
            rel = doc.part.rels.get(r_id)
            return rel.target_ref if rel else ""
        except Exception:
            return ""
