@echo off
chcp 65001 >nul
title Trợ Lý AI - Commit Từng Nhóm Lỗi Đã Sửa (fix/audit-1)

cd /d "%~dp0\.."

echo ========================================================
echo  COMMIT CÁC NHÓM SỬA THEO CHUẨN CONVENTIONAL COMMITS
echo ========================================================
echo.

:: Chuyển sang nhánh fix/audit-1
git checkout -b fix/audit-1 2>nul || git checkout fix/audit-1

:: 1. Nhóm Router (ERR-01)
git add src/assistant/core/router.py tests/test_router.py
git commit -m "fix(router): add is_network_available to ModelRouter with fast socket check and cache" 2>nul

:: 2. Nhóm Reminders (ERR-02)
git add src/assistant/reminders/scheduler.py tests/test_reminders.py
git commit -m "fix(reminders): support reminder_store parameter in ReminderScheduler" 2>nul

:: 3. Nhóm WebSocket & Trí nhớ (ERR-03)
git add src/assistant/server/ws.py tests/test_server.py
git commit -m "fix(ws): query and inject relevant long-term memories into websocket system prompt" 2>nul

:: 4. Nhóm Memory Store (ERR-04)
git add src/assistant/memory/store.py tests/test_memory_store.py
git commit -m "fix(memory): fallback to SQL LIKE on FTS5 syntax errors with special characters" 2>nul

:: 5. Nhóm Open App (ERR-05)
git add src/assistant/tools/apps.py tests/test_tools.py
git commit -m "fix(apps): use word boundary matching in open_app to avoid false positive substring matches" 2>nul

:: 6. Nhóm Audit Log API & UI (ERR-06)
git add src/assistant/server/app.py src/assistant/ui_static/index.html
git commit -m "fix(server): implement GET /api/audit endpoint and audit screen in web UI" 2>nul

:: 7. Nhóm Console UTF-8 (ERR-07)
git add src/assistant/main.py
git commit -m "fix(console): reconfigure Windows stdout and stderr encoding to UTF-8" 2>nul

:: 8. Nhóm Approval Modal Focus Trap (ERR-08)
git add src/assistant/ui_static/app.js
git commit -m "fix(ui): add focus trap, ESC rejection, and enter guard to approval modal" 2>nul

:: 9. Nhóm Markdown & DOMPurify (ERR-09, ERR-10)
git add src/assistant/ui_static/vendor/purify.min.js
git commit -m "fix(ui): embed offline DOMPurify vendor script and support markdown tables" 2>nul

:: 10. Nhóm CSS Tokens & WCAG AA (ERR-11)
git add src/assistant/ui_static/css/ src/assistant/ui_static/style.css
git commit -m "fix(ui): modularize CSS into design tokens, base, layout, components with WCAG AA compliance" 2>nul

:: 11. Nhóm i18n Từ Điển Tiếng Việt (ERR-12)
git add src/assistant/ui_static/i18n/vi.json
git commit -m "fix(ui): extract all frontend text to i18n/vi.json dictionary" 2>nul

:: 12. Nhóm QA Tool & Tests (ERR-13, ERR-14)
git add scripts/ui_check.py src/assistant/memory/extractor.py pyproject.toml
git commit -m "test(ui): add automated Playwright multi-viewport visual test runner scripts/ui_check.py" 2>nul

:: 13. Nhóm Tài Liệu Kiểm Toán & Báo Cáo QA
git add docs/AUDIT.md docs/QA.md docs/DECISIONS.md README.md scripts/
git commit -m "docs(audit): complete Master Audit Report, QA verification report, and ADRs" 2>nul

echo.
echo ========================================================
echo  ĐÃ COMMIT TOÀN BỘ CÁC NHÓM SỬA LÊN NHÁNH fix/audit-1!
echo ========================================================
git log -n 14 --oneline
echo.
pause
