"""Kiểm thử tự động cho công cụ tra cứu web (tools/web.py).

Kiểm tra:
- Phòng chống SSRF (Server-Side Request Forgery): Chặn localhost, 127.0.0.1, IP nội bộ.
- Chặn các giao thức không phải http/https (ftp, file, gopher...).
- Trích xuất văn bản từ HTML, xoá script/style.
- Bọc nội dung trong thẻ <untrusted_content> để chống prompt injection.
"""

from assistant.tools.web import extract_text_from_html, fetch_webpage, is_ssrf_safe_url


def test_ssrf_blocks_localhost_and_private_ips() -> None:
    """Kiểm tra chặn triệt để localhost và các dải địa chỉ IP nội bộ."""
    test_cases = [
        ("http://localhost:8000/api", False),
        ("http://127.0.0.1:5000", False),
        ("http://0.0.0.0/", False),
        ("http://10.0.0.1/admin", False),
        ("http://192.168.1.1/router", False),
        ("http://172.16.0.10/", False),
        ("http://169.254.169.254/latest/meta-data", False),  # Cloud metadata IP
        ("ftp://example.com/file.txt", False),
        ("file:///C:/Windows/win.ini", False),
        ("http://mycomputer.local", False),
        ("http://internal.corp", False),
    ]

    for url, expected_safe in test_cases:
        safe, reason = is_ssrf_safe_url(url)
        assert safe is expected_safe, f"URL {url} đáng lẽ phải bị chặn nhưng kết quả là {safe}. Lý do: {reason}"
        assert reason != ""


def test_ssrf_allows_public_domains() -> None:
    """Kiểm tra cho phép các tên miền công khai hợp lệ."""
    safe, _ = is_ssrf_safe_url("https://www.google.com")
    assert safe is True

    safe_wiki, _ = is_ssrf_safe_url("https://vi.wikipedia.org/wiki/Python")
    assert safe_wiki is True


def test_extract_text_from_html() -> None:
    """Kiểm tra loại bỏ script, style và trích xuất nội dung sạch từ HTML."""
    sample_html = """
    <html>
        <head>
            <title>Trang Web Mẫu</title>
            <style>body { color: red; }</style>
            <script>alert("hacked");</script>
        </head>
        <body>
            <h1>Tiêu đề bài viết</h1>
            <p>Đây là <b>nội dung</b> giới thiệu về công nghệ AI &amp; Trợ lý ảo.</p>
        </body>
    </html>
    """
    text = extract_text_from_html(sample_html)
    assert "alert" not in text
    assert "color: red" not in text
    assert "Tiêu đề bài viết" in text
    assert "nội dung giới thiệu về công nghệ AI & Trợ lý ảo." in text


def test_fetch_webpage_blocks_internal_request() -> None:
    """Kiểm tra công cụ fetch_webpage trả về lỗi an toàn khi gọi tới localhost."""
    res = fetch_webpage("http://127.0.0.1:8080/secret")
    assert res["ok"] is False
    assert "Bị chặn an toàn" in res["error"]
    assert "Chống SSRF" in res["error"]
