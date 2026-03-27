"""QualityValidator — content verification adapted from Dich-Viet."""

import re
from typing import List, Dict, Tuple
from dataclasses import dataclass, field
from difflib import SequenceMatcher


@dataclass
class VerificationResult:
    """Result of content verification."""
    passed: bool = True
    overall_score: float = 1.0
    length_score: float = 1.0
    structure_score: float = 1.0
    completeness_score: float = 1.0
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, any] = field(default_factory=dict)


class QualityValidator:
    """Validate conversion/translation quality."""

    @classmethod
    def verify_conversion(cls, source_path: str, output_md: str,
                          source_text: str = "") -> VerificationResult:
        """Verify markdown output against source."""
        result = VerificationResult()

        if not output_md.strip():
            result.passed = False
            result.overall_score = 0.0
            result.warnings.append("Output is empty")
            return result

        # Length check
        src_len = len(source_text) if source_text else 0
        out_len = len(output_md)

        if src_len > 0:
            ratio = out_len / src_len
            if 0.3 <= ratio <= 3.0:
                result.length_score = 1.0
            elif 0.15 <= ratio <= 5.0:
                result.length_score = 0.5
                result.warnings.append(f"Length ratio unusual: {ratio:.2f}")
            else:
                result.length_score = 0.2
                result.warnings.append(f"Length ratio suspicious: {ratio:.2f}")

        # Structure check
        heading_count = len(re.findall(r"^#{1,6}\s", output_md, re.MULTILINE))
        table_count = len(re.findall(r"^\|.+\|$", output_md, re.MULTILINE))
        list_count = len(re.findall(r"^[\s]*[-*+]\s|^\d+\.\s", output_md, re.MULTILINE))

        result.details = {
            "output_chars": out_len,
            "source_chars": src_len,
            "headings": heading_count,
            "tables": table_count,
            "lists": list_count,
        }

        if heading_count == 0 and out_len > 1000:
            result.warnings.append("No headings detected for long document")
            result.structure_score = 0.7

        # Completeness: check key phrases
        if source_text and len(source_text) > 100:
            completeness = cls._check_completeness(source_text, output_md)
            result.completeness_score = completeness
            if completeness < 0.8:
                result.warnings.append(f"Content completeness: {completeness:.0%}")

        # Overall score
        result.overall_score = (
            result.length_score * 0.3 +
            result.structure_score * 0.3 +
            result.completeness_score * 0.4
        )
        result.passed = result.overall_score >= 0.5

        return result

    @classmethod
    def verify_translation(cls, source: str, translated: str) -> VerificationResult:
        """Verify translation quality."""
        result = VerificationResult()

        if not translated.strip():
            result.passed = False
            result.overall_score = 0.0
            result.warnings.append("Translation is empty")
            return result

        # Length ratio
        ratio = len(translated) / max(len(source), 1)
        if 0.8 <= ratio <= 2.0:
            result.length_score = 1.0
        elif 0.5 <= ratio <= 3.0:
            result.length_score = 0.7
            result.warnings.append(f"Translation length ratio: {ratio:.2f}")
        else:
            result.length_score = 0.3
            result.warnings.append(f"Abnormal length ratio: {ratio:.2f}")

        # Completeness
        src_sentences = len(re.split(r"[.!?]", source))
        trans_sentences = len(re.split(r"[.!?]", translated))
        sent_ratio = trans_sentences / max(src_sentences, 1)
        if 0.7 <= sent_ratio <= 1.3:
            result.completeness_score = 1.0
        elif 0.5 <= sent_ratio <= 1.5:
            result.completeness_score = 0.7
        else:
            result.completeness_score = 0.3
            result.warnings.append("Sentence count mismatch")

        # Check for artifacts
        artifacts = [r"\[\[.*?\]\]", r"---START---", r"---END---", r"\[CHUNK \d+\]"]
        for pattern in artifacts:
            if re.search(pattern, translated):
                result.structure_score -= 0.2
                result.warnings.append("Translation contains artifacts")
                break

        # Check markdown structure preserved
        src_headings = len(re.findall(r"^#{1,6}\s", source, re.MULTILINE))
        trans_headings = len(re.findall(r"^#{1,6}\s", translated, re.MULTILINE))
        if src_headings > 0 and trans_headings == 0:
            result.structure_score -= 0.3
            result.warnings.append("Heading structure lost in translation")

        result.overall_score = (
            result.length_score * 0.3 +
            result.structure_score * 0.3 +
            result.completeness_score * 0.4
        )
        result.passed = result.overall_score >= 0.5
        return result

    @staticmethod
    def _check_completeness(source: str, output: str) -> float:
        """Check content completeness by key phrases."""
        # Strip markdown syntax
        clean_src = re.sub(r"[#*_|`\[\]()>-]", " ", source)
        clean_out = re.sub(r"[#*_|`\[\]()>-]", " ", output)

        # Extract key phrases (first 3 words of each paragraph)
        src_lines = [l.strip() for l in clean_src.split("\n") if l.strip() and len(l.strip()) > 10]
        key_phrases = []
        for line in src_lines[:50]:
            words = line.split()[:3]
            if len(words) >= 2:
                key_phrases.append(" ".join(words).lower())

        if not key_phrases:
            return 1.0

        # Check how many key phrases are present
        found = 0
        for phrase in key_phrases:
            if phrase in clean_out.lower():
                found += 1

        return found / len(key_phrases)
