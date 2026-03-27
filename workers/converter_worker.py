"""ConverterWorker — Stream 1: Python Scripts (offline) QThread."""

import os
import json
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from core.format_utils import get_converter_for_file, get_file_type
from workers.smart_chunker import SmartChunker
from workers.smart_merger import SmartMerger
from workers.quality_validator import QualityValidator
from workers.error_handler import ErrorHandler


class ConverterWorker(QThread):
    """Worker thread for local Python script-based conversion."""

    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    phase_created = pyqtSignal(int, str, str)  # (index, path, preview_text)
    file_completed = pyqtSignal(str, str)       # (input_path, output_path)
    error = pyqtSignal(str, str)                # (filepath, error_msg)
    warning = pyqtSignal(str, str)              # (filepath, warning_msg)
    all_completed = pyqtSignal(list)             # [(input, output), ...]

    def __init__(self, file_paths: list, output_dir: str = "output",
                 use_phases: bool = True, auto_merge: bool = True,
                 verify: bool = True, chunk_size: int = 5000,
                 parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.output_dir = output_dir
        self.use_phases = use_phases
        self.auto_merge = auto_merge
        self.verify = verify
        self.chunk_size = chunk_size
        self._cancelled = False
        os.makedirs(output_dir, exist_ok=True)

    def cancel(self):
        self._cancelled = True

    def run(self):
        results = []
        total = len(self.file_paths)

        for idx, filepath in enumerate(self.file_paths):
            if self._cancelled:
                self.log.emit("⏹ Đã hủy.")
                break

            filename = Path(filepath).name
            pct = int((idx / total) * 100)
            self.progress.emit(pct, f"Đang xử lý: {filename} ({idx + 1}/{total})")
            self.log.emit(f"📄 Bắt đầu: {filename}")

            try:
                result = self._process_file(filepath)
                if result:
                    results.append(result)
            except Exception as e:
                record = ErrorHandler.handle(e, context=f"convert:{filename}", filepath=filepath)
                user_msg = ErrorHandler.get_user_message(record)
                self.error.emit(filepath, user_msg)
                self.log.emit(f"❌ {filename}: {user_msg}")

        self.progress.emit(100, "Hoàn thành!")
        self.all_completed.emit(results)

    def _process_file(self, filepath: str):
        """Process a single file through the full pipeline."""
        filename = Path(filepath).name
        stem = Path(filepath).stem

        # Step 1: Validate
        if not os.path.exists(filepath):
            self.error.emit(filepath, "File không tồn tại")
            return None

        file_type = get_file_type(filepath)
        if not file_type:
            self.error.emit(filepath, f"Format không hỗ trợ: {Path(filepath).suffix}")
            return None

        # Step 2: Convert
        self.log.emit(f"  🔄 Converting ({file_type})...")
        converter = get_converter_for_file(filepath, self.output_dir)
        raw_md = converter.convert(filepath)

        # Step 3: Check raw output
        if not raw_md or not raw_md.strip():
            self.warning.emit(filepath, "Trích xuất rỗng — có thể cần dùng API stream")
            return None

        if len(raw_md) < 50:
            self.warning.emit(filepath, f"Nội dung rất ngắn ({len(raw_md)} chars)")

        self.log.emit(f"  ✅ Extracted: {len(raw_md)} chars")

        # Step 4: Phase splitting (if enabled and file is large)
        if self.use_phases and len(raw_md) > self.chunk_size:
            self.log.emit(f"  📋 Splitting into phases (max {self.chunk_size} chars/phase)...")
            chunker = SmartChunker(max_chars=self.chunk_size)
            chunks = chunker.create_chunks(raw_md)

            # Save phases
            phase_dir = os.path.join(self.output_dir, f"{stem}_phases")
            os.makedirs(phase_dir, exist_ok=True)

            metadata_phases = []
            for chunk in chunks:
                phase_path = os.path.join(phase_dir, f"{stem}_phase_{chunk.id:03d}.md")
                content = f"<!-- Phase {chunk.id}/{len(chunks)} -->\n\n{chunk.text}"
                with open(phase_path, "w", encoding="utf-8") as f:
                    f.write(content)

                preview = chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text
                self.phase_created.emit(chunk.id, phase_path, preview)
                self.log.emit(f"    Phase {chunk.id}: {chunk.char_count} chars")

                metadata_phases.append({
                    "index": chunk.id,
                    "filename": f"{stem}_phase_{chunk.id:03d}.md",
                    "chars": chunk.char_count,
                    "heading": chunk.heading_summary,
                })

            # Save metadata
            meta_path = os.path.join(phase_dir, "metadata.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"phases": metadata_phases, "total": len(chunks)}, f,
                          indent=2, ensure_ascii=False)

            # Step 5: Auto merge
            if self.auto_merge:
                self.log.emit(f"  🔗 Merging {len(chunks)} phases...")
                merged_md = SmartMerger.merge_chunks(chunks)
                output_path = os.path.join(self.output_dir, f"{stem}.md")
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(merged_md)

                # Verify merge
                ratio = len(merged_md) / max(sum(c.char_count for c in chunks), 1)
                if abs(ratio - 1.0) > 0.05:
                    self.warning.emit(filepath,
                                      f"Merge ratio: {ratio:.2f} (expected ~1.0)")
                self.log.emit(f"  ✅ Merged: {len(merged_md)} chars → {output_path}")
            else:
                output_path = phase_dir
        else:
            # No phases — save directly
            output_path = os.path.join(self.output_dir, f"{stem}.md")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(raw_md)

        # Step 6: Verify
        if self.verify:
            self.log.emit(f"  🔍 Verifying...")
            result = QualityValidator.verify_conversion(filepath, raw_md)
            if result.warnings:
                for w in result.warnings:
                    self.warning.emit(filepath, w)
            self.log.emit(f"  📊 Quality: {result.overall_score:.0%}")

        self.file_completed.emit(filepath, output_path)
        self.log.emit(f"  ✅ Done: {filename} → {Path(output_path).name}")
        return (filepath, output_path)
