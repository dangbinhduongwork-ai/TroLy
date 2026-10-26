# NHẬT KÝ QUYẾT ĐỊNH THIẾT KẾ (ARCHITECTURE DECISION RECORDS)

Tài liệu này ghi lại các quyết định kỹ thuật khi có điểm mơ hồ và lý do thêm các thư viện mới theo đúng Nguyên tắc 10 và 11.

---

## Mẫu ghi nhận quyết định (ADR template)

### [2026-10-26] Thiết lập Skills và Agents chuyên trách cho dự án
- **Bối cảnh**: Cần đảm bảo trợ lý AI luôn tuân thủ nghiêm ngặt 12 nguyên tắc an toàn, quy trình 5 bước mỗi giai đoạn và tương tác an toàn với Windows 10/11 mà không vi phạm bảo mật hệ thống.
- **Phương án đã chọn**:
  - Tạo 3 Skills trong `.agents/skills/`: `troly-phase-workflow` (quy trình 5 bước), `troly-security-checker` (bảng kiểm 12 nguyên tắc an toàn), `troly-windows-tools` (mẫu code tương tác an toàn trên Windows).
  - Tạo 2 Subagents trong `.agents/agents/`: `troly-safety-guard` (rà soát an toàn, bảo mật đường dẫn, bí mật), `troly-qa-tester` (kiểm thử, pytest, ruff).
- **Lý do**: Tận dụng cơ chế progressive disclosure và chuyên môn hóa vai trò của Antigravity IDE, ngăn ngừa sai sót chủ quan hoặc bỏ quên bước trong quá trình phát triển.
### [2026-10-26] Giai đoạn 0: Khởi tạo bộ khung dự án (Scaffold) & Thiết kế tối giản phụ thuộc
- **Bối cảnh**: Cần thiết lập cấu trúc mã nguồn theo chuẩn `src layout`, hỗ trợ cấu hình toml, biến môi trường, bảo vệ secret, và cung cấp lệnh chẩn đoán `assistant doctor`.
- **Phương án đã chọn**:
  - Dùng `tomllib` có sẵn trong Python 3.11+ để đọc `config/settings.toml`, không dùng thư viện bên ngoài.
  - Tự viết hàm nạp `.env` ngắn gọn trong `config.py` để không phải cài thêm `python-dotenv`.
  - Dùng `argparse` từ thư viện chuẩn thay vì các framework nặng như `click` hay `typer`.
  - Sử dụng `urllib.request` từ thư viện chuẩn để kiểm tra kết nối tới Ollama.
  - Sử dụng `RotatingFileHandler` tích hợp `SecretFilter` để xoay vòng log tối đa 5MB x 5 file và chặn lọt key.
  - Thêm thư viện `keyring` để đọc và lưu mật khẩu/token an toàn trong Windows Credential Locker theo Nguyên tắc 3.
  - Thêm `pytest` và `ruff` trong nhóm phụ thuộc phát triển (`dev`).
- **Lý do**: Tuân thủ triệt để Nguyên tắc 11 (Hạn chế phụ thuộc thư viện bên ngoài), tối ưu tốc độ khởi động và đảm bảo an toàn tối đa cho hệ thống.
### [2026-10-26] Giai đoạn 1: Thiết kế Lớp Model (LLM Layer) & Bộ Định Tuyến Thông Minh
- **Bối cảnh**: Cần tích hợp hai nguồn model (Gemini API đám mây & Ollama cục bộ), hỗ trợ streaming theo thời gian thực, tự động chuyển đổi nguồn model khi gặp sự cố mạng/quota/lỗi máy chủ hoặc yêu cầu nhạy cảm.
- **Phương án đã chọn**:
  - Tích hợp SDK chính thức mới `google-genai` (loại bỏ hoàn toàn thư viện cũ `google-generativeai`).
  - Sử dụng trực tiếp `httpx` để kết nối tới endpoint tương thích OpenAI `/v1/chat/completions` của Ollama qua SSE streaming (Server-Sent Events), thay vì cài thêm thư viện `openai` hay `ollama-python`.
  - Chuẩn hoá toàn bộ dữ liệu nội bộ qua `Pydantic` (`Message`, `ToolCall`, `ToolResult`, `Usage`, `StreamEvent`).
  - Thiết kế `ModelRouter` với 3 chế độ `auto`, `gemini`, `local`. Trong chế độ `auto`, kiểm tra kết nối mạng siêu tốc qua socket TCP (cache 10s), tự động điều hướng yêu cầu nhạy cảm sang cục bộ, tự động thử lại tối đa 2 lần với exponential backoff khi gặp lỗi mạng/429/5xx trước khi chuyển sang Ollama.
  - Xây dựng `ConversationContext` quản lý ngân sách token và tự động tóm tắt ngữ cảnh cũ bằng model cục bộ.
  - Bổ sung lệnh CLI `assistant set-key` ẩn ký tự bằng `getpass` lưu vào `keyring`, `assistant models` và `assistant chat`.
- **Lý do**: Đảm bảo tuân thủ Nguyên tắc 2 (An toàn bảo mật), Nguyên tắc 3 (Bảo vệ bí mật), Nguyên tắc 11 (Tối giản phụ thuộc thư viện bên ngoài) và Nguyên tắc 12 (Dữ liệu không tin cậy).
- **Thư viện mới (nếu có)**:
  - `google-genai>=0.1.1`: SDK chính thức mới nhất của Google Gemini.
  - `httpx>=0.27.0`: Client HTTP bất đồng bộ hỗ trợ streaming luồng SSE và kiểm tra kết nối mạng.
  - `pydantic>=2.0.0`: Thư viện xác thực schema và định dạng dữ liệu nội bộ nghiêm ngặt.
  - `pytest-asyncio>=0.23.0` (dev): Hỗ trợ kiểm thử tự động các hàm async trong pytest.

