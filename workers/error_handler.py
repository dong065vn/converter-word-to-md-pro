"""ErrorHandler — error classification and logging adapted from Dich-Viet."""

import traceback
import logging
from zipfile import BadZipFile
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass

from docx.opc.exceptions import PackageNotFoundError

logger = logging.getLogger("DocToMarkdownPro")


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    API_ERROR = "api_error"
    CONVERSION_ERROR = "conversion_error"
    OCR_ERROR = "ocr_error"
    FILE_IO_ERROR = "file_io_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    CONFIG_ERROR = "config_error"
    PHASE_ERROR = "phase_error"
    UNKNOWN = "unknown"


@dataclass
class ErrorRecord:
    """Error record for tracking."""
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    detail: str = ""
    filepath: str = ""
    recoverable: bool = True


class ErrorHandler:
    """Classify, log, and provide recovery guidance for errors."""

    @staticmethod
    def classify(exception: Exception) -> tuple:
        """Classify exception into severity + category."""
        exc_type = type(exception).__name__
        msg = str(exception).lower()

        # API errors
        if "httpstatuserror" in exc_type.lower() or "apierror" in exc_type.lower():
            status = ""
            if hasattr(exception, "response"):
                status = str(getattr(exception.response, "status_code", ""))
            if "429" in status or "rate" in msg:
                return ErrorSeverity.MEDIUM, ErrorCategory.API_ERROR
            elif "401" in status or "403" in status or "unauthorized" in msg:
                return ErrorSeverity.HIGH, ErrorCategory.CONFIG_ERROR
            elif status.startswith("5"):
                return ErrorSeverity.MEDIUM, ErrorCategory.API_ERROR
            return ErrorSeverity.MEDIUM, ErrorCategory.API_ERROR

        # Timeout
        if "timeout" in exc_type.lower() or "timeout" in msg:
            return ErrorSeverity.MEDIUM, ErrorCategory.TIMEOUT_ERROR

        # Network
        if "connection" in exc_type.lower() or "network" in msg or "dns" in msg:
            return ErrorSeverity.HIGH, ErrorCategory.NETWORK_ERROR

        # File IO
        if exc_type in ("FileNotFoundError", "IsADirectoryError"):
            return ErrorSeverity.MEDIUM, ErrorCategory.FILE_IO_ERROR
        if exc_type == "PermissionError":
            return ErrorSeverity.HIGH, ErrorCategory.FILE_IO_ERROR
        if isinstance(exception, (BadZipFile, PackageNotFoundError)):
            return ErrorSeverity.MEDIUM, ErrorCategory.CONVERSION_ERROR

        # OCR
        if "tesseract" in msg or "ocr" in msg or "paddleocr" in msg:
            return ErrorSeverity.MEDIUM, ErrorCategory.OCR_ERROR

        # Memory
        if exc_type == "MemoryError":
            return ErrorSeverity.CRITICAL, ErrorCategory.CONVERSION_ERROR

        # Generic conversion
        if exc_type in ("ValueError", "TypeError", "AttributeError", "KeyError"):
            return ErrorSeverity.MEDIUM, ErrorCategory.CONVERSION_ERROR

        return ErrorSeverity.MEDIUM, ErrorCategory.UNKNOWN

    @classmethod
    def handle(cls, exception: Exception, context: str = "",
               filepath: str = "") -> ErrorRecord:
        """Handle exception: classify, log, return record."""
        severity, category = cls.classify(exception)
        detail = traceback.format_exc()

        record = ErrorRecord(
            severity=severity,
            category=category,
            message=f"[{category.value}] {type(exception).__name__}: {str(exception)}",
            detail=detail,
            filepath=filepath,
            recoverable=severity != ErrorSeverity.CRITICAL
        )

        # Log
        log_msg = f"{context} | {record.message}"
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == ErrorSeverity.HIGH:
            logger.error(log_msg)
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return record

    @staticmethod
    def get_user_message(record: ErrorRecord) -> str:
        """Get user-friendly error message."""
        cat = record.category

        if cat == ErrorCategory.CONFIG_ERROR:
            return "❌ API key không hợp lệ. Vui lòng kiểm tra Settings."
        elif cat == ErrorCategory.NETWORK_ERROR:
            return "❌ Không thể kết nối mạng. Kiểm tra Internet."
        elif cat == ErrorCategory.TIMEOUT_ERROR:
            return "⏱️ Timeout — thử giảm chunk size hoặc thử lại."
        elif cat == ErrorCategory.API_ERROR:
            if "429" in record.message:
                return "⏳ Rate limit — chờ vài giây rồi thử lại."
            return "❌ Lỗi API — thử lại hoặc đổi provider."
        elif cat == ErrorCategory.FILE_IO_ERROR:
            if "permission" in record.message.lower():
                return "❌ Không có quyền truy cập file. Đóng apps khác."
            return "❌ File không tìm thấy hoặc bị lỗi."
        elif cat == ErrorCategory.OCR_ERROR:
            return "⚠️ OCR engine lỗi. Kiểm tra cài đặt Tesseract/EasyOCR."
        elif cat == ErrorCategory.CONVERSION_ERROR:
            if "invalid or unreadable" in record.message.lower() or "badzipfile" in record.message.lower():
                return "⚠️ File Word bị lỗi hoặc không đúng định dạng .docx."
            detail = record.message.split(": ", 1)[-1].strip()
            if detail:
                return f"⚠️ Lỗi chuyển đổi: {detail[:140]}"
            return "⚠️ Lỗi chuyển đổi tài liệu."
        else:
            return f"⚠️ Lỗi: {record.message[:100]}"
