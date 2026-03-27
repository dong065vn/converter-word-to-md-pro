"""SmartChunker — context-aware text chunking adapted from Dich-Viet."""

import re
from typing import List
from dataclasses import dataclass, field


@dataclass
class TextChunk:
    """A text chunk with context and overlap metadata."""
    id: int
    text: str
    context_before: str = ""
    context_after: str = ""
    overlap_char_count: int = 0
    char_count: int = 0
    heading_summary: str = ""

    def __post_init__(self):
        self.char_count = len(self.text)


class SmartChunker:
    """Split text into chunks at safe boundaries with context preservation."""

    def __init__(self, max_chars: int = 5000, context_window: int = 200):
        self.max_chars = max_chars
        self.context_window = context_window

    def create_chunks(self, text: str) -> List[TextChunk]:
        """Split text into chunks at paragraph/heading boundaries."""
        if len(text) <= self.max_chars:
            return [TextChunk(id=1, text=text)]

        # Identify structural elements
        paragraphs = self._split_paragraphs(text)
        chunks = []
        current_parts = []
        current_length = 0
        chunk_id = 1
        pending_overlap = 0

        for i, para in enumerate(paragraphs):
            para_len = len(para)

            # If single paragraph exceeds max, split at sentences
            if para_len > self.max_chars:
                if current_parts:
                    last_part = current_parts[-1]
                    chunks.append(self._build_chunk(
                        chunk_id, current_parts, paragraphs, i - len(current_parts), i,
                        overlap_char_count=pending_overlap
                    ))
                    chunk_id += 1
                    pending_overlap = len(last_part)
                    current_parts = []
                    current_length = 0

                # Split long paragraph into sentences
                sentences = self._split_sentences(para)
                sent_buffer = []
                sent_len = 0
                for sent in sentences:
                    if sent_len + len(sent) > self.max_chars and sent_buffer:
                        chunks.append(TextChunk(
                            id=chunk_id,
                            text="\n".join(sent_buffer),
                            overlap_char_count=pending_overlap
                        ))
                        chunk_id += 1
                        pending_overlap = len(sent_buffer[-1]) if sent_buffer else 0
                        sent_buffer = [sent]
                        sent_len = len(sent)
                    else:
                        sent_buffer.append(sent)
                        sent_len += len(sent)
                if sent_buffer:
                    chunks.append(TextChunk(
                        id=chunk_id,
                        text="\n".join(sent_buffer),
                        overlap_char_count=pending_overlap
                    ))
                    chunk_id += 1
                    pending_overlap = 0
                continue

            # Normal paragraph — check if adding it exceeds max
            if current_length + para_len > self.max_chars and current_parts:
                last_part = current_parts[-1]
                chunks.append(self._build_chunk(
                    chunk_id, current_parts, paragraphs, i - len(current_parts), i,
                    overlap_char_count=pending_overlap
                ))
                chunk_id += 1
                pending_overlap = len(last_part)
                current_parts = [para]
                current_length = para_len
            else:
                current_parts.append(para)
                current_length += para_len

        # Final chunk
        if current_parts:
            chunks.append(self._build_chunk(
                chunk_id, current_parts, paragraphs,
                len(paragraphs) - len(current_parts), len(paragraphs),
                overlap_char_count=pending_overlap
            ))

        # Add context windows
        for i, chunk in enumerate(chunks):
            if i > 0:
                chunk.context_before = chunks[i - 1].text[-self.context_window:]
            if i < len(chunks) - 1:
                chunk.context_after = chunks[i + 1].text[:self.context_window]

        return chunks

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split on double newlines, preserving table/code blocks."""
        # Protect code blocks
        protected = {}
        counter = [0]

        def protect(match):
            key = f"__PROTECTED_{counter[0]}__"
            protected[key] = match.group(0)
            counter[0] += 1
            return key

        # Protect code blocks and tables
        safe_text = re.sub(r"```[\s\S]*?```", protect, text)
        safe_text = re.sub(r"(\|[^\n]+\|\n)+", protect, safe_text)

        # Split
        parts = re.split(r"\n\s*\n", safe_text)
        result = []
        for part in parts:
            # Restore protected content
            for key, val in protected.items():
                part = part.replace(key, val)
            part = part.strip()
            if part:
                result.append(part)

        return result

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        sentences = re.split(r'(?<=[.!?。！？])\s+(?=[A-Z\u4E00-\u9FFF])', text)
        merged = []
        buf = ""
        for s in sentences:
            if len(buf) + len(s) < 50:
                buf += " " + s if buf else s
            else:
                if buf:
                    merged.append(buf.strip())
                buf = s
        if buf:
            merged.append(buf.strip())
        return merged

    def _build_chunk(self, chunk_id, parts, all_parts, start_idx, end_idx,
                     overlap_char_count=0) -> TextChunk:
        """Build a TextChunk from parts."""
        text = "\n\n".join(parts)
        headings = [p for p in parts if p.startswith("#")]
        summary = headings[0][:60] if headings else parts[0][:60] if parts else ""

        return TextChunk(
            id=chunk_id,
            text=text,
            overlap_char_count=overlap_char_count,
            heading_summary=summary
        )
