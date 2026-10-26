"""Công cụ tra cứu và đọc nội dung trang web (Web Tools).

Tuân thủ nghiêm ngặt:
- Chống SSRF (Server-Side Request Forgery): Chặn tuyệt đối localhost, 127.0.0.1, IP nội bộ (RFC 1918), link-local.
- Chỉ chấp nhận giao thức http:// và https://.
- Bắt buộc bọc toàn bộ nội dung trong thẻ <untrusted_content> để phòng vệ chống prompt injection.
- Giới hạn độ dài văn bản tải về để tránh tràn ngữ cảnh.
"""

from html import unescape
import ipaddress
import re
import socket
from typing import Any
import urllib.parse

import httpx

from assistant.safety.injection import wrap_untrusted_content
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import register_tool


def is_ssrf_safe_url(url_str: str) -> tuple[bool, str]:
    """Kiểm tra URL có an toàn trước các cuộc tấn công SSRF hay không."""
    try:
        parsed = urllib.parse.urlparse(url_str)
    except Exception:
        return False, "Không thể phân tích cú pháp URL."

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return False, f"Giao thức không được hỗ trợ: {scheme}. Chỉ cho phép http:// hoặc https://."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL không chứa tên miền hoặc địa chỉ máy chủ hợp lệ."

    host_lower = hostname.lower()

    # 1. Chặn danh sách tên miền nội bộ phổ biến
    forbidden_hosts = {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "local",
        "internal",
        "router.login",
    }
    if host_lower in forbidden_hosts or host_lower.endswith((".local", ".internal", ".localhost")):
        return False, f"Bị chặn an toàn: Tên miền nội bộ hoặc localhost ({hostname}) (Chống SSRF)."

    # 2. Phân giải DNS và kiểm tra IP
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for item in addr_info:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)

            if (
                ip_obj.is_loopback
                or ip_obj.is_private
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
                or ip_obj.is_unspecified
            ):
                return False, f"Bị chặn an toàn: Địa chỉ IP ({ip_str}) thuộc dải mạng nội bộ hoặc riêng tư (Chống SSRF)."
    except socket.gaierror:
        return False, f"Không thể phân giải tên miền: {hostname}."
    except Exception as err:
        return False, f"Lỗi kiểm tra địa chỉ mạng: {err}"

    return True, "Hợp lệ"


def extract_text_from_html(html_content: str) -> str:
    """Loại bỏ thẻ HTML và trích xuất nội dung văn bản thuần tuý."""
    # Xoá script, style, head, noscript
    clean_html = re.sub(r"<(script|style|head|noscript)[^>]*>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Xoá tất cả các thẻ HTML còn lại
    text = re.sub(r"<[^>]+>", " ", clean_html)
    # Giải mã HTML entities (&nbsp;, &amp;...)
    text = unescape(text)
    # Chuẩn hoá khoảng trắng
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text


@register_tool(
    name="fetch_webpage",
    description="Tải và trích xuất nội dung văn bản từ một trang web (URL công khai http/https). Chặn SSRF và IP nội bộ.",
    permission_level=PermissionLevel.READ,
    is_external_content=True,
)
def fetch_webpage(url: str, max_chars: int = 5000) -> dict[str, Any]:
    """Tải nội dung trang web an toàn."""
    clean_url = url.strip()

    # Kiểm tra phòng chống SSRF
    is_safe, reason = is_ssrf_safe_url(clean_url)
    if not is_safe:
        return {
            "ok": False,
            "data": None,
            "error": reason,
            "truncated": False,
        }

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(clean_url)

        if resp.status_code != 200:
            return {
                "ok": False,
                "data": None,
                "error": f"Máy chủ web trả về mã lỗi HTTP {resp.status_code}",
                "truncated": False,
            }

        # Trích xuất văn bản từ HTML
        text = extract_text_from_html(resp.text)
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + f"\n... [Đã cắt bớt nội dung, tổng độ dài: {len(text)} ký tự]"

        return {
            "ok": True,
            "data": wrap_untrusted_content(text, source_label=clean_url),
            "error": None,
            "truncated": truncated,
        }
    except httpx.TimeoutException:
        return {
            "ok": False,
            "data": None,
            "error": "Quá thời gian kết nối tới trang web (Timeout 10s).",
            "truncated": False,
        }
    except Exception as err:
        return {
            "ok": False,
            "data": None,
            "error": f"Lỗi tải trang web: {err}",
            "truncated": False,
        }
