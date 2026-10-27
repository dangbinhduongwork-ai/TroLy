"""Kiểm thử tự động cho công cụ tra cứu web realtime (Web Search Tools)."""

from unittest.mock import MagicMock, patch
import pytest

from assistant.tools.web import (
    _parse_duckduckgo_html,
    extract_text_from_html,
    fetch_news,
    is_ssrf_safe_url,
    search_web,
)


def test_is_ssrf_safe_url() -> None:
    """Kiểm tra chức năng chống SSRF: chặn localhost, dải private IP."""
    # 1. Chặn localhost và IP loopback
    safe, _ = is_ssrf_safe_url("http://localhost:8000/api")
    assert safe is False

    safe, _ = is_ssrf_safe_url("http://127.0.0.1:11434")
    assert safe is False

    # 2. Chặn private network IP (RFC 1918)
    safe, _ = is_ssrf_safe_url("http://192.168.1.1/admin")
    assert safe is False

    safe, _ = is_ssrf_safe_url("http://10.0.0.1")
    assert safe is False

    # 3. Chặn giao thức không hợp lệ (file://, ftp://)
    safe, _ = is_ssrf_safe_url("file:///etc/passwd")
    assert safe is False

    # 4. Cho phép tên miền công cộng hợp lệ
    safe, _ = is_ssrf_safe_url("https://www.google.com")
    assert safe is True


def test_parse_duckduckgo_html() -> None:
    """Kiểm tra phân tích kết quả HTML từ DuckDuckGo."""
    sample_html = """
    <div class="result__body">
        <h2 class="result__title">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org&rut=...">Welcome to Python.org</a>
        </h2>
        <a class="result__snippet" href="...">The official home of the Python Programming Language.</a>
    </div>
    <div class="result__body">
        <h2 class="result__title">
            <a class="result__a" href="https://docs.python.org/3/">Python 3 Documentation</a>
        </h2>
        <a class="result__snippet" href="...">Official Python language reference and tutorials.</a>
    </div>
    """
    results = _parse_duckduckgo_html(sample_html, max_results=5)
    assert len(results) == 2
    assert results[0]["title"] == "Welcome to Python.org"
    assert results[0]["url"] == "https://python.org"
    assert "official home" in results[0]["snippet"].lower()
    assert results[1]["title"] == "Python 3 Documentation"
    assert results[1]["url"] == "https://docs.python.org/3/"


def test_search_web_empty_query() -> None:
    """Kiểm tra search_web với từ khóa rỗng."""
    res = search_web("   ")
    assert res["ok"] is False
    assert "không được để trống" in res["error"]


def test_search_web_mocked_results() -> None:
    """Kiểm tra search_web trả về kết quả được bọc trong <untrusted_content>."""
    sample_duck_html = """
    <a class="result__a" href="https://vnexpress.net/thoi-su">Tin tức thời sự</a>
    <a class="result__snippet">Cập nhật tin thời sự mới nhất trong ngày tại Việt Nam.</a>
    """
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_duck_html
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        res = search_web("thời sự việt nam", max_results=3)
        assert res["ok"] is True
        assert res["count"] >= 1
        assert "<untrusted_content" in res["data"]
        assert "</untrusted_content>" in res["data"]


def test_fetch_news_mocked_rss() -> None:
    """Kiểm tra fetch_news phân tích RSS bằng ElementTree và bọc untrusted content."""
    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Google News</title>
            <item>
                <title>Hội nghị công nghệ AI Việt Nam 2026</title>
                <link>https://news.google.com/articles/fake-ai-2026</link>
                <pubDate>Tue, 27 Oct 2026 12:00:00 GMT</pubDate>
                <description>&lt;a href="..."&gt;Chi tiết diễn đàn AI&lt;/a&gt;</description>
            </item>
        </channel>
    </rss>
    """
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = sample_rss.encode("utf-8")
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        res = fetch_news("technology", max_results=3)
        assert res["ok"] is True
        assert res["count"] == 1
        assert "<untrusted_content" in res["data"]
        assert "Hội nghị công nghệ AI Việt Nam 2026" in res["data"]
