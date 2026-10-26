"""Thiết lập hệ thống ghi log tập trung cho ứng dụng Trợ Lý AI.

Log xoay vòng ra file trong data_dir/logs và đồng thời hiển thị trên console.
Tuân thủ Nguyên tắc 3: Tuyệt đối không bao giờ ghi lộ khóa bí mật vào log.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re


class SecretFilter(logging.Filter):
    """Bộ lọc tự động che giấu khóa bí mật (API key, tokens) trước khi log."""

    # Nhận diện mẫu Google API Key (AIzaSy...) và các chuỗi token nhạy cảm
    API_KEY_PATTERN = re.compile(r"AIzaSy[0-9A-Za-z_-]{33}")
    _registered_secrets: set[str] = set()

    @classmethod
    def register_secret(cls, secret: str) -> None:
        """Đăng ký một chuỗi bí mật (như session token) cần tự động che giấu."""
        if secret and len(secret) >= 6:
            cls._registered_secrets.add(secret)

    @classmethod
    def clear_secrets(cls) -> None:
        """Xoá danh sách bí mật đã đăng ký (phục vụ kiểm thử)."""
        cls._registered_secrets.clear()

    def filter(self, record: logging.LogRecord) -> bool:
        if not isinstance(record.msg, str):
            return True

        msg = record.msg

        # 1. Che giấu API key nếu khớp pattern Google AI Studio
        msg = self.API_KEY_PATTERN.sub("[BÍ_MẬT_GEMINI_KEY]", msg)

        # 2. Che giấu giá trị GEMINI_API_KEY từ môi trường nếu có
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and len(gemini_key) > 5 and gemini_key in msg:
            msg = msg.replace(gemini_key, "[BÍ_MẬT_KEY]")

        # 3. Che giấu các token bí mật đã đăng ký (như session_token)
        for sec in self._registered_secrets:
            if sec in msg:
                msg = msg.replace(sec, "[BÍ_MẬT_TOKEN]")

        record.msg = msg
        return True



def setup_logging(
    data_dir: Path,
    log_level: str = "INFO",
    logger_name: str = "assistant",
) -> logging.Logger:
    """Khởi tạo và cấu hình hệ thống ghi log cho ứng dụng.

    Args:
        data_dir: Thư mục dữ liệu chứa thư mục con 'logs'.
        log_level: Mức độ log (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        logger_name: Tên logger cần khởi tạo.

    Returns:
        Đối tượng Logger đã được cấu hình hoàn chỉnh.
    """
    logger = logging.getLogger(logger_name)

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Tránh gắn lặp handlers nếu đã được thiết lập trước đó
    if logger.handlers:
        return logger

    # Định dạng log thống nhất
    log_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    secret_filter = SecretFilter()

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(log_format)
    console_handler.addFilter(secret_filter)
    logger.addHandler(console_handler)

    # 2. File Handler xoay vòng (Rotating File Handler)
    logs_dir = data_dir / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "assistant.log"

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB mỗi file
            backupCount=5,  # Giữ tối đa 5 file cũ
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(log_format)
        file_handler.addFilter(secret_filter)
        logger.addHandler(file_handler)
    except Exception as err:
        logger.warning(f"Không thể khởi tạo file log tại {logs_dir}: {err}")

    return logger
