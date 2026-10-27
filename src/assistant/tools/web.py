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
import xml.etree.ElementTree as ET

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


def _parse_duckduckgo_html(html_text: str, max_results: int) -> list[dict[str, str]]:
    """Phân tích kết quả tìm kiếm từ trang HTML của DuckDuckGo."""
    results: list[dict[str, str]] = []
    title_matches = list(re.finditer(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html_text,
        re.DOTALL | re.IGNORECASE,
    ))
    snippet_matches = list(re.finditer(
        r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
        html_text,
        re.DOTALL | re.IGNORECASE,
    ))

    snippets = [re.sub(r"<[^>]+>", "", unescape(m.group(1))).strip() for m in snippet_matches]

    for idx, match in enumerate(title_matches):
        if len(results) >= max_results:
            break
        raw_url = match.group(1)
        raw_title = match.group(2)
        clean_title = re.sub(r"<[^>]+>", "", unescape(raw_title)).strip()

        # Giải mã redirect url nếu có
        actual_url = raw_url
        if "uddg=" in raw_url:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
            if "uddg" in parsed and parsed["uddg"]:
                actual_url = parsed["uddg"][0]
        elif raw_url.startswith("//"):
            actual_url = "https:" + raw_url

        snippet = snippets[idx] if idx < len(snippets) else ""
        if clean_title and actual_url and actual_url.startswith(("http://", "https://")):
            results.append({
                "title": clean_title,
                "url": actual_url,
                "snippet": snippet,
            })
    return results


def _search_google_news_rss(query: str, max_results: int) -> list[dict[str, str]]:
    """Tìm kiếm kết quả qua Google News RSS bằng ElementTree."""
    results: list[dict[str, str]] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    encoded_q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=vi&gl=VN&ceid=VN:vi"
    with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
    if resp.status_code == 200:
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item"):
            if len(results) >= max_results:
                break
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_elem = item.find("pubDate")

            title = title_elem.text if title_elem is not None and title_elem.text else ""
            link = link_elem.text if link_elem is not None and link_elem.text else ""
            desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
            pub = pub_elem.text if pub_elem is not None and pub_elem.text else ""

            clean_desc = re.sub(r"<[^>]+>", " ", unescape(desc)).strip()
            if title and link:
                results.append({
                    "title": title,
                    "url": link,
                    "snippet": f"[{pub}] {clean_desc}" if pub else clean_desc,
                })
    return results


@register_tool(
    name="search_web",
    description="Tìm kiếm thông tin tổng hợp trên Internet thời gian thực. Trả về tiêu đề, đường dẫn và tóm tắt kết quả.",
    permission_level=PermissionLevel.READ,
    is_external_content=True,
)
def search_web(query: str, max_results: int = 5) -> dict[str, Any]:
    """Tìm kiếm web thời gian thực an toàn với cơ chế bảo vệ SSRF và bọc untrusted content."""
    clean_query = query.strip()
    if not clean_query:
        return {"ok": False, "data": None, "error": "Từ khóa tìm kiếm không được để trống.", "results": []}

    limit = max(1, min(max_results, 10))
    results: list[dict[str, str]] = []

    # 1. Thử tìm kiếm qua DuckDuckGo HTML
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
            resp = client.post("https://html.duckduckgo.com/html/", data={"q": clean_query})
            if resp.status_code == 200:
                results = _parse_duckduckgo_html(resp.text, limit)
    except Exception:
        pass

    # 2. Nếu DuckDuckGo không có kết quả, fallback qua Google News RSS
    if not results:
        try:
            results = _search_google_news_rss(clean_query, limit)
        except Exception:
            pass

    # Lọc kết quả qua SSRF check
    safe_results = []
    for r in results:
        is_safe, _ = is_ssrf_safe_url(r.get("url", ""))
        if is_safe:
            safe_results.append(r)

    if not safe_results:
        return {
            "ok": True,
            "data": wrap_untrusted_content(f"Không tìm thấy kết quả phù hợp cho từ khóa '{clean_query}'.", source_label=f"search:{clean_query}"),
            "error": None,
            "results": [],
            "count": 0,
        }

    lines = [f"KẾT QUẢ TÌM KIẾM CHO: '{clean_query}' ({len(safe_results)} kết quả)\n"]
    for idx, r in enumerate(safe_results, 1):
        lines.append(f"{idx}. {r['title']}")
        lines.append(f"   Đường dẫn: {r['url']}")
        if r.get("snippet"):
            lines.append(f"   Tóm tắt: {r['snippet']}")
        lines.append("")

    formatted_text = "\n".join(lines)
    return {
        "ok": True,
        "data": wrap_untrusted_content(formatted_text, source_label=f"search:{clean_query}"),
        "error": None,
        "results": safe_results,
        "count": len(safe_results),
    }


@register_tool(
    name="fetch_news",
    description="Tra cứu tin tức thời sự, kinh tế, công nghệ mới nhất từ các nguồn báo chí uy tín theo chủ đề (general, business, technology, science, sports).",
    permission_level=PermissionLevel.READ,
    is_external_content=True,
)
def fetch_news(topic: str = "general", max_results: int = 5) -> dict[str, Any]:
    """Tra cứu tin tức mới nhất từ RSS uy tín."""
    limit = max(1, min(max_results, 10))
    topic_map = {
        "business": "BUSINESS",
        "technology": "TECHNOLOGY",
        "science": "SCIENCE",
        "sports": "SPORTS",
        "entertainment": "ENTERTAINMENT",
        "health": "HEALTH",
    }
    section = topic_map.get(topic.strip().lower())
    if section:
        url = f"https://news.google.com/rss/headlines/section/topic/{section}?hl=vi&gl=VN&ceid=VN:vi"
    else:
        url = "https://news.google.com/rss?hl=vi&gl=VN&ceid=VN:vi"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return {"ok": False, "data": None, "error": f"Lỗi tải tin tức: HTTP {resp.status_code}", "results": []}

        root = ET.fromstring(resp.content)
        items: list[dict[str, str]] = []
        for item in root.findall(".//item"):
            if len(items) >= limit:
                break
            title_elem = item.find("title")
            link_elem = item.find("link")
            pub_elem = item.find("pubDate")
            desc_elem = item.find("description")

            title = title_elem.text if title_elem is not None and title_elem.text else ""
            link = link_elem.text if link_elem is not None and link_elem.text else ""
            pub = pub_elem.text if pub_elem is not None and pub_elem.text else ""
            desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
            clean_desc = re.sub(r"<[^>]+>", " ", unescape(desc)).strip()

            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "published": pub,
                    "snippet": clean_desc,
                })

        safe_items = [i for i in items if is_ssrf_safe_url(i["url"])[0]]
        lines = [f"TIN TỨC MỚI NHẤT ({topic.upper()} - {len(safe_items)} tin)\n"]
        for idx, item in enumerate(safe_items, 1):
            lines.append(f"{idx}. {item['title']}")
            if item.get("published"):
                lines.append(f"   Thời gian: {item['published']}")
            lines.append(f"   Đường dẫn: {item['url']}")
            lines.append("")

        formatted = "\n".join(lines)
        return {
            "ok": True,
            "data": wrap_untrusted_content(formatted, source_label=f"news:{topic}"),
            "error": None,
            "results": safe_items,
            "count": len(safe_items),
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": f"Không thể lấy tin tức: {exc}",
            "results": [],
        }

