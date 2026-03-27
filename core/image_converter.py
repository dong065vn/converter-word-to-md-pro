"""Image to Markdown converter — OCR pipeline adapted from SKILL image-ocr-workspace."""

import os
from pathlib import Path
from typing import Optional, Tuple

from .converter_base import ConverterBase


class ImageConverter(ConverterBase):
    """Convert images to Markdown via OCR preprocessing pipeline."""

    SUPPORTED = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

    def convert(self, filepath: str) -> str:
        # Step 1: Preprocess
        processed_path = self._preprocess(filepath)

        # Step 2: OCR with engine fallback chain
        text, confidence = self._run_ocr(processed_path)

        if not text.strip():
            return f"<!-- OCR: No text extracted from {Path(filepath).name} -->"

        # Step 3: Basic structure analysis
        structured_md = self._analyze_structure(text)

        # Step 4: Build output
        lines = [
            f"# OCR: {Path(filepath).name}",
            "",
            f"> Confidence: {confidence * 100:.1f}%",
            "",
            structured_md,
            "",
            "---",
            f"*Source: {Path(filepath).name}*",
        ]

        result = "\n".join(lines)
        return self.normalize_markdown(self.cleanup_text(result))

    def _preprocess(self, filepath: str) -> str:
        """Preprocess image for better OCR (grayscale, denoise, CLAHE, threshold)."""
        try:
            import cv2
            import numpy as np
            from PIL import Image

            img = cv2.imread(filepath)
            if img is None:
                pil_img = Image.open(filepath).convert("RGB")
                img = np.array(pil_img)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            # Grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Denoise
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            # CLAHE contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            # Adaptive threshold
            binary = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )

            # Upscale if small
            pil_img = Image.fromarray(binary)
            if pil_img.width < 1000:
                scale = 2
                pil_img = pil_img.resize(
                    (pil_img.width * scale, pil_img.height * scale),
                    Image.LANCZOS
                )

            # Save processed
            processed_dir = os.path.join(os.path.dirname(filepath), "processed")
            os.makedirs(processed_dir, exist_ok=True)
            processed_path = os.path.join(processed_dir,
                                          f"{Path(filepath).stem}_proc{Path(filepath).suffix}")
            pil_img.save(processed_path)
            return processed_path

        except ImportError:
            return filepath
        except Exception:
            return filepath

    def _run_ocr(self, filepath: str) -> Tuple[str, float]:
        """Run OCR with fallback chain: pytesseract → easyocr."""
        # Try pytesseract first
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(filepath)
            data = pytesseract.image_to_data(img, lang="vie+eng",
                                             output_type=pytesseract.Output.DICT)
            words = []
            confs = []
            for i, word in enumerate(data["text"]):
                if word.strip():
                    words.append(word)
                    conf = data["conf"][i]
                    if conf > 0:
                        confs.append(conf / 100.0)

            text = pytesseract.image_to_string(img, lang="vie+eng")
            avg_conf = sum(confs) / len(confs) if confs else 0.5
            if text.strip():
                return text.strip(), avg_conf
        except (ImportError, Exception):
            pass

        # Try easyocr
        try:
            import easyocr
            reader = easyocr.Reader(["vi", "en"], gpu=False, verbose=False)
            results = reader.readtext(filepath)
            lines = [r[1] for r in results]
            confs = [r[2] for r in results]
            text = "\n".join(lines)
            avg_conf = sum(confs) / len(confs) if confs else 0.5
            return text, avg_conf
        except (ImportError, Exception):
            pass

        # Try PaddleOCR
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang="vi", show_log=False)
            result = ocr.ocr(filepath, cls=True)
            lines = []
            confs = []
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        text_info = line[1]
                        if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                            lines.append(text_info[0])
                            confs.append(text_info[1])
            text = "\n".join(lines)
            avg_conf = sum(confs) / len(confs) if confs else 0.5
            return text, avg_conf
        except (ImportError, Exception):
            pass

        return "", 0.0

    def _analyze_structure(self, text: str) -> str:
        """Basic structure analysis: detect headings, lists, paragraphs."""
        import re
        lines = text.split("\n")
        result = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                result.append("")
                continue

            # Detect uppercase headings
            if stripped.isupper() and len(stripped) < 80 and len(stripped) > 3:
                result.append(f"## {stripped.title()}")
            # Detect bullet markers
            elif re.match(r"^[•●○▪▸►-]\s+", stripped):
                cleaned = re.sub(r"^[•●○▪▸►-]\s+", "", stripped)
                result.append(f"- {cleaned}")
            # Detect numbered lists
            elif re.match(r"^\d+[.)]\s+", stripped):
                result.append(stripped)
            else:
                result.append(stripped)

        return "\n".join(result)
