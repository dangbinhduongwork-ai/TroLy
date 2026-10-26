"""Kiểm thử tự động giao diện Desktop bằng Playwright (scripts/ui_check.py).

Kiểm tra:
1. 3 cỡ độ phân giải: 900x600, 1280x800, 1920x1080.
2. 2 chủ đề: Tối (Dark) và Sáng (Light).
3. Chụp ảnh màn hình lưu vào docs/ui-shots/.
4. Giám sát an toàn mạng: Chỉ được phép gửi request tới 127.0.0.1 / localhost (100% offline).
5. Giám sát Console: Thu thập toàn bộ lỗi JavaScript nếu có.
6. Kiểm tra tràn ngang (horizontal overflow) ngoài ý muốn.
"""

import asyncio
import json
import os
from pathlib import Path
import sys
import threading
import time

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from assistant.config import load_config
from assistant.server.app import create_app, get_current_session_token


VIEWPORTS = [
    {"name": "900x600", "width": 900, "height": 600},
    {"name": "1280x800", "width": 1280, "height": 800},
    {"name": "1920x1080", "width": 1920, "height": 1080},
]

THEMES = ["dark", "light"]


async def run_ui_audit(port: int = 8765) -> dict:
    shots_dir = Path(__file__).resolve().parent.parent / "docs" / "ui-shots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    if not HAS_PLAYWRIGHT:
        print("❌ [CHƯA CÀI PLAYWRIGHT] Vui lòng chạy: pip install playwright && playwright install chromium")
        return {"ok": False, "error": "Playwright is not installed"}

    config = load_config(create_dirs=True)
    token = get_current_session_token()
    app = create_app(config=config, session_token=token)

    import uvicorn
    server_config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(server_config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    base_url = f"http://127.0.0.1:{port}/?token={token}"
    report = {
        "ok": True,
        "scenarios": [],
        "external_network_requests": [],
        "console_errors": [],
        "layout_overflows": [],
        "screenshots": [],
    }

    async with async_playwright() as p:
        # Ưu tiên chromium tiêu chuẩn hoặc msedge
        browser = None
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception:
            try:
                browser = await p.chromium.launch(channel="msedge", headless=True)
            except Exception as err:
                print(f"❌ Không thể khởi chạy trình duyệt: {err}")
                server.should_exit = True
                return {"ok": False, "error": str(err)}

        for vp in VIEWPORTS:
            for theme in THEMES:
                scenario_name = f"{vp['name']}_{theme}"
                print(f"[*] Đang kiểm thử kịch bản: {scenario_name}...")

                context = await browser.new_context(
                    viewport={"width": vp["width"], "height": vp["height"]}
                )
                page = await context.new_page()

                # Bắt sự kiện request mạng
                page.on("request", lambda req: _audit_request(req.url, report))
                page.on("console", lambda msg: _audit_console(msg, scenario_name, report))

                await page.goto(base_url, wait_until="networkidle")

                # Áp dụng chủ đề nếu là light theme
                if theme == "light":
                    await page.evaluate("""() => {
                        document.body.className = 'light-theme';
                        const icon = document.getElementById('theme-icon');
                        if (icon) icon.innerText = '☀️';
                    }""")
                    await page.wait_for_timeout(200)

                # Kiểm tra tràn ngang
                overflow_elements = await page.evaluate("""() => {
                    const badElements = [];
                    const cw = document.documentElement.clientWidth;
                    document.querySelectorAll('*').forEach(el => {
                        if (el.scrollWidth > el.clientWidth && el.clientWidth > 0) {
                            const tag = el.tagName.toLowerCase();
                            const cls = el.className || '';
                            // Bỏ qua các phần tử được thiết kế cuộn ngang có chủ đích
                            if (!cls.includes('table-container') && !cls.includes('code-container') && tag !== 'pre' && !cls.includes('chat-messages')) {
                                badElements.push(tag + '.' + cls);
                            }
                        }
                    });
                    return badElements;
                }""")

                if overflow_elements:
                    report["layout_overflows"].append({
                        "scenario": scenario_name,
                        "elements": overflow_elements,
                    })

                # Chụp ảnh màn hình
                shot_path = shots_dir / f"shot_{scenario_name}.png"
                await page.screenshot(path=str(shot_path), full_page=False)
                report["screenshots"].append(str(shot_path.name))

                await context.close()

        await browser.close()

    server.should_exit = True

    # Lưu báo cáo JSON
    report_file = shots_dir / "audit_report.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("=" * 60)
    print(f"✅ Hoàn tất kiểm thử UI Playwright! Báo cáo: {report_file}")
    print(f"   Ảnh chụp màn hình: {len(report['screenshots'])} file tại docs/ui-shots/")
    print(f"   Yêu cầu mạng ra internet: {len(report['external_network_requests'])}")
    print(f"   Lỗi console: {len(report['console_errors'])}")
    print(f"   Phần tử tràn ngang: {len(report['layout_overflows'])}")
    print("=" * 60)
    return report


def _audit_request(url: str, report: dict) -> None:
    if not (url.startswith("http://127.0.0.1") or url.startswith("http://localhost")):
        report["external_network_requests"].append(url)
        report["ok"] = False


def _audit_console(msg, scenario: str, report: dict) -> None:
    if msg.type == "error":
        report["console_errors"].append({
            "scenario": scenario,
            "text": msg.text,
            "location": msg.location,
        })


if __name__ == "__main__":
    asyncio.run(run_ui_audit())
