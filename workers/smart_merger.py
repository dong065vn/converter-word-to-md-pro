"""SmartMerger — 3-tier overlap detection adapted from Dich-Viet."""

import re
from typing import List
from difflib import SequenceMatcher

from .smart_chunker import TextChunk


class SmartMerger:
    """Merge chunks with intelligent overlap deduplication."""

    EXPANSION_FACTOR = 1.2  # Vietnamese text expansion factor

    @staticmethod
    def find_overlap_exact(text1: str, text2: str, min_overlap: int = 20) -> int:
        """Find exact overlap between end of text1 and start of text2."""
        max_check = min(len(text1), len(text2), 500)

        # Word-level matching first
        words1 = text1.split()
        words2 = text2.split()
        for i in range(min(len(words1), len(words2), 50), 2, -1):
            if words1[-i:] == words2[:i]:
                return len(" ".join(words2[:i]))

        # Character-level fallback
        for i in range(max_check, min_overlap, -1):
            if text1[-i:] == text2[:i]:
                return i

        return 0

    @staticmethod
    def find_overlap_fuzzy(text1: str, text2: str, min_match: int = 50) -> int:
        """Find overlap using fuzzy matching (SequenceMatcher)."""
        end1 = text1[-500:] if len(text1) > 500 else text1
        start2 = text2[:500] if len(text2) > 500 else text2

        matcher = SequenceMatcher(None, end1, start2)
        match = matcher.find_longest_match(0, len(end1), 0, len(start2))

        if match.size >= min_match:
            return match.b + match.size
        return 0

    @classmethod
    def merge_chunks(cls, chunks: List[TextChunk]) -> str:
        """Merge chunks with 3-tier overlap detection."""
        if not chunks:
            return ""

        sorted_chunks = sorted(chunks, key=lambda c: c.id)
        merged = sorted_chunks[0].text.strip()

        for i in range(1, len(sorted_chunks)):
            chunk = sorted_chunks[i]
            current = chunk.text.strip()
            if not current:
                continue

            overlap = 0

            # Priority 1: Use overlap_char_count metadata
            if chunk.overlap_char_count > 0:
                estimated = int(chunk.overlap_char_count * cls.EXPANSION_FACTOR)
                overlap = min(estimated, len(current) // 2)

            # Priority 2: Exact match
            if overlap == 0:
                overlap = cls.find_overlap_exact(merged, current)

            # Priority 3: Fuzzy match
            if overlap == 0:
                overlap = cls.find_overlap_fuzzy(merged, current, min_match=30)

            # Merge
            if overlap > 20:
                merged = merged + current[overlap:]
            else:
                # No overlap — join with appropriate separator
                if merged and current:
                    if merged[-1] in ".!?" and len(current) > 0 and current[0].isupper():
                        merged = merged + "\n\n" + current
                    else:
                        merged = merged + "\n\n" + current

        return cls.post_process(merged)

    @staticmethod
    def merge_phase_files(phase_dir: str) -> str:
        """Merge phase files from a directory."""
        import os
        import json
        from pathlib import Path

        phase_dir = Path(phase_dir)
        # Try metadata.json first
        meta_path = phase_dir / "metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            phase_files = [phase_dir / p["filename"] for p in sorted(meta.get("phases", []),
                                                                       key=lambda x: x.get("index", 0))]
        else:
            # Glob and sort
            phase_files = sorted(phase_dir.glob("*_phase_*.md"))

        parts = []
        for pf in phase_files:
            if pf.exists():
                content = pf.read_text(encoding="utf-8").strip()
                # Remove phase markers
                content = re.sub(r"<!-- Phase \d+/\d+ -->", "", content).strip()
                if content:
                    parts.append(content)

        if not parts:
            return ""

        # Simple merge with overlap detection
        merged = parts[0]
        for part in parts[1:]:
            overlap = SmartMerger.find_overlap_exact(merged, part)
            if overlap == 0:
                overlap = SmartMerger.find_overlap_fuzzy(merged, part)
            if overlap > 20:
                merged = merged + part[overlap:]
            else:
                merged = merged + "\n\n" + part

        return SmartMerger.post_process(merged)

    @staticmethod
    def post_process(text: str) -> str:
        """Clean merged text."""
        text = re.sub(r" +", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        text = re.sub(r"\[CHUNK \d+\]", "", text)
        text = re.sub(r"---START---|---END---", "", text)
        text = re.sub(r'"\s*"', '"', text)
        return text.strip()
