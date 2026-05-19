"""APIConverterWorker — Stream 2: API-based extraction QThread."""

import os
import json
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from core.format_utils import get_converter_for_file, get_file_type
from workers.smart_chunker import SmartChunker
from workers.smart_merger import SmartMerger
from workers.quality_validator import QualityValidator
from workers.error_handler import ErrorHandler
from api.api_base import APIConfig


class APIConverterWorker(QThread):
    """Worker thread for API-based document extraction."""

    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    phase_created = pyqtSignal(int, str, str)
    file_completed = pyqtSignal(str, str)
    error = pyqtSignal(str, str)
    warning = pyqtSignal(str, str)
    all_completed = pyqtSignal(list)

    def __init__(self, file_paths: list, output_dir: str = "output",
                 provider: str = "openai", api_config: dict = None,
                 use_phases: bool = True, auto_merge: bool = True,
                 verify: bool = True, chunk_size: int = 5000,
                 parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.output_dir = output_dir
        self.provider = provider
        self.api_config = api_config or {}
        self.use_phases = use_phases
        self.auto_merge = auto_merge
        self.verify = verify
        self.chunk_size = chunk_size
        self._cancelled = False
        os.makedirs(output_dir, exist_ok=True)

    def cancel(self):
        self._cancelled = True

    def _get_api_client(self):
        """Create API client from provider name and config."""
        config = APIConfig(
            api_key=self.api_config.get("api_key", ""),
            model=self.api_config.get("model", ""),
            max_tokens=self.api_config.get("max_tokens", 4096),
            temperature=0.3,
            base_url=self.api_config.get("base_url"),
        )

        if self.provider == "openai":
            from api.openai_client import OpenAIClient
            return OpenAIClient(config)
        elif self.provider == "claude":
            from api.claude_client import ClaudeClient
            return ClaudeClient(config)
        elif self.provider == "opencode":
            from api.opencode_client import OpenCodeClient
            return OpenCodeClient(config)
        elif self.provider == "custom":
            from api.custom_client import CustomClient
            return CustomClient(config)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def run(self):
        results = []
        total = len(self.file_paths)

        # Validate API
        try:
            client = self._get_api_client()
            if not client.is_configured():
                self.error.emit("", "API key chưa được cấu hình. Mở Settings.")
                return
        except Exception as e:
            self.error.emit("", f"Lỗi khởi tạo API: {e}")
            return

        for idx, filepath in enumerate(self.file_paths):
            if self._cancelled:
                self.log.emit("⏹ Đã hủy.")
                break

            filename = Path(filepath).name
            pct = int((idx / total) * 100)
            self.progress.emit(pct, f"[API] Đang xử lý: {filename} ({idx + 1}/{total})")
            self.log.emit(f"🤖 Bắt đầu (API): {filename}")

            try:
                result = self._process_file(filepath, client)
                if result:
                    results.append(result)
            except Exception as e:
                record = ErrorHandler.handle(e, context=f"api_convert:{filename}", filepath=filepath)
                user_msg = ErrorHandler.get_user_message(record)
                self.error.emit(filepath, user_msg)
                self.log.emit(f"❌ {filename}: {user_msg}")

        self.progress.emit(100, "Hoàn thành!")
        self.all_completed.emit(results)

    def _process_file(self, filepath: str, client):
        """Process file via API extraction."""
        filename = Path(filepath).name
        stem = Path(filepath).stem

        # Step 1: Extract raw text using local converter
        self.log.emit(f"  📝 Extracting raw text...")
        try:
            converter = get_converter_for_file(filepath, self.output_dir)
            raw_text = converter.convert(filepath)
        except Exception:
            # If local converter fails, try reading raw
            with open(filepath, "rb") as f:
                raw_text = f.read().decode("utf-8", errors="ignore")

        if not raw_text.strip():
            self.warning.emit(filepath, "Không trích xuất được text từ file")
            return None

        # Step 2: Extract text into semantic blocks
        from core.ast_tools.extractor import BlockExtractor
        from core.ast_tools.models import MarkdownBlock
        self.log.emit(f"  📋 Extracting semantic blocks...")
        source_blocks = BlockExtractor.extract_source_blocks(raw_text, filepath)
        self.log.emit(f"  📋 {len(source_blocks)} raw blocks found")

        # Group blocks into chunks of ~chunk_size
        batches = []
        current_batch = []
        current_len = 0
        for sb in source_blocks:
            sb_len = len(sb.text)
            if current_len + sb_len > self.chunk_size and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_len = 0
            current_batch.append(sb)
            current_len += sb_len
        if current_batch:
            batches.append(current_batch)

        # Step 3: Process each batch via API
        system_prompt = client.build_conversion_prompt()
        system_prompt += "\n\nCRITICAL INSTRUCTION: You MUST return ONLY a JSON object matching this schema exactly: {\"blocks\": [{\"block_id\": \"b1\", \"markdown\": \"...\"}]}. The block_id in your response must match the block_id provided in the input JSON exactly."
        
        processed_markdown_blocks = []
        phase_mds = []

        for idx, batch in enumerate(batches):
            if self._cancelled:
                break

            self.log.emit(f"  🤖 API batch {idx+1}/{len(batches)}...")
            
            # Prepare user content as JSON
            batch_data = [{"block_id": b.block_id, "text": b.text} for b in batch]
            user_content = "CONVERT THESE BLOCKS TO MARKDOWN. RETURN JSON ONLY:\n" + json.dumps(batch_data, ensure_ascii=False)

            batch_md_output = ""
            try:
                result = client.process_with_retry(system_prompt, user_content)
                # Clean markdown code blocks if the AI surrounded the JSON with ```json ... ```
                if result.strip().startswith("```"):
                    lines = result.strip().split("\n")
                    result = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                    
                parsed_json = json.loads(result)
                
                if "blocks" in parsed_json:
                    for mb in parsed_json["blocks"]:
                        processed_markdown_blocks.append(MarkdownBlock(**mb))
                        batch_md_output += mb.get("markdown", "") + "\n\n"
            except Exception as e:
                self.warning.emit(filepath, f"Batch {idx+1} failed or invalid JSON: {e}")
                # Fallback: keep original text
                for b in batch:
                    processed_markdown_blocks.append(MarkdownBlock(block_id=b.block_id, markdown=b.text))
                    batch_md_output += b.text + "\n\n"
                    
            phase_mds.append(batch_md_output)

        # Step 4: Emit phases if requested
        if self.use_phases:
            phase_dir = os.path.join(self.output_dir, f"{stem}_phases")
            os.makedirs(phase_dir, exist_ok=True)
            for idx, batch_md in enumerate(phase_mds):
                phase_path = os.path.join(phase_dir, f"{stem}_phase_{idx:03d}.md")
                with open(phase_path, "w", encoding="utf-8") as f:
                    f.write(batch_md)
                preview = batch_md[:200] + "..." if len(batch_md) > 200 else batch_md
                self.phase_created.emit(idx, phase_path, preview)

        # Step 5: Merge
        merged_md = "\n\n".join(mb.markdown for mb in processed_markdown_blocks)
        output_path = os.path.join(self.output_dir, f"{stem}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(merged_md)

        # Step 6: Verify
        if self.verify:
            # Legacy verify
            result = QualityValidator.verify_conversion(filepath, merged_md, raw_text)
            
            # New AST-based verify
            from core.ast_tools.validate_markdown_structure import MarkdownValidator
            from core.ast_tools.compare_source_vs_markdown import ContentComparator
            
            ast_validator = MarkdownValidator()
            issues = ast_validator.validate_blocks(processed_markdown_blocks)
            for iss in issues:
                self.warning.emit(filepath, f"AST: {iss.message}")
                
            comparator = ContentComparator()
            alignments = comparator.compare(source_blocks, processed_markdown_blocks)
            high_risk_count = 0
            for align in alignments:
                if align.suspected_rewrite and align.risk == "high":
                    high_risk_count += 1
                    
            if high_risk_count > 0:
                self.warning.emit(filepath, f"Phát hiện {high_risk_count} blocks có rủi ro điêu tiếng/sai số liệu!")

            if result.warnings:
                for w in result.warnings:
                    self.warning.emit(filepath, w)
            self.log.emit(f"  📊 Quality: {result.overall_score:.0%} | Lỗi AST: {len(issues)}")

        self.file_completed.emit(filepath, output_path)
        self.log.emit(f"  ✅ Done (API): {filename} → {Path(output_path).name}")
        return (filepath, output_path)
