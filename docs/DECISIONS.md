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
### [2026-10-26] Giai đoạn 2: Lớp An Toàn (Safety First) & Hệ Thống Công Cụ (Tools Layer)
- **Bối cảnh**: Cần cung cấp khả năng thao tác file, mở ứng dụng, thực thi lệnh cho AI mà không gây nguy hiểm cho hệ điều hành, ngăn chặn thoát workspace, chống mã độc và phòng vệ trước prompt injection.
- **Phương án đã chọn**:
  - Triển khai lớp an toàn TRƯỚC, công cụ SAU:
    1. `safety/paths.py`: Resolve tuyệt đối qua `pathlib.Path`, chặn triệt để `..`, symlink/junction ra ngoài, chặn tên thiết bị cấm Windows (CON, NUL, COM1-9...), chặn đường dẫn UNC và luồng dữ liệu thay thế NTFS (ADS).
    2. `safety/permissions.py`: Ma trận 3 cấp quyền (READ: tự động, WRITE_SAFE: tự động nếu tạo mới, CONFIRM: bắt buộc duyệt nếu xoá/ghi đè/chạy lệnh/ra ngoài workspace). Thiết lập danh sách từ chối cứng (Hard DENY) cho các lệnh nguy hiểm (format, diskpart, del /s, reg delete, bcdedit, cipher /w, net user, powershell -EncodedCommand, curl | bash...).
    3. `safety/audit.py`: Ghi nhật ký append-only JSONL mọi lượt gọi công cụ kèm che giấu bí mật và rút gọn kết quả (không lưu full nội dung file).
    4. `safety/injection.py`: Bọc mọi dữ liệu đọc từ bên ngoài trong thẻ `<untrusted_content>`. Bổ sung chỉ dẫn cấm model làm theo lệnh bên trong. Tự động nâng mức duyệt nếu lượt hiện tại đã đọc dữ liệu bên ngoài.
    5. `tools/files.py`: Sử dụng thư viện `send2trash` thay cho `os.remove` để chuyển file vào Thùng rác Windows, bảo toàn khả năng khôi phục.
    6. `tools/registry.py` & `llm/schema_adapters.py`: Tự động phân tích type hints hàm Python để sinh JSON Schema cho Gemini và Ollama.
    7. `core/agent_loop.py`: Vòng lặp tối đa 10 bước, timeout tổng, phát hiện và ngắt vòng lặp vô tận (>=3 lần cùng tham số), phê duyệt xác nhận qua terminal (y/N).
- **Lý do**: Tuân thủ tuyệt đối Nguyên tắc 1, 2, 4, 5, 7, 8, 9, 11 và 12.
- **Thư viện mới (nếu có)**:
  - `send2trash>=1.8.0`: Hỗ trợ đưa tập tin/thư mục vào Thùng rác Windows (Recycle Bin) một cách an toàn, tránh mất mát dữ liệu vĩnh viễn.

### [2026-10-26] Giai đoạn 3: Lưu trữ hội thoại và Trí nhớ dài hạn (SQLite WAL & FTS5)
- **Bối cảnh**: Cần lưu trữ toàn bộ lịch sử trò chuyện và trí nhớ dài hạn về người dùng (sở thích, dự án, quy tắc đặt tên, thông tin chung), hỗ trợ tìm kiếm toàn văn tiếng Việt nhanh, bảo vệ dữ liệu nhạy cảm cục bộ tuyệt đối, và chèn trí nhớ vào system prompt có kiểm soát token.
- **Phương án đã chọn**:
  1. Sử dụng trực tiếp module `sqlite3` tích hợp sẵn trong Python 3.11+, không cài thêm ORM hay Vector DB bên ngoài (tuân thủ triệt để Nguyên tắc 11).
  2. Bật chế độ WAL (`PRAGMA journal_mode=WAL;`) và `PRAGMA foreign_keys=ON;` để tối ưu đọc/ghi đồng thời trên Windows và bảo toàn tính toàn vẹn quan hệ.
  3. Xây dựng 3 bảng cốt lõi: `conversations`, `messages`, `memories` (các danh mục: `preference`, `project`, `naming_rule`, `general`).
  4. Sử dụng bảng ảo FTS5 (`memories_fts` và `messages_fts`) với bộ tokenizer `unicode61` hỗ trợ tìm kiếm toàn văn tiếng Việt có dấu. Bổ sung cơ chế fallback sang `LIKE` nếu chuỗi tìm kiếm chứa ký tự đặc biệt của FTS5.
  5. Thiết kế `memory/extractor.py`: Tự động phân tích câu thoại chứa tín hiệu cần nhớ sau mỗi lượt hoặc khi có yêu cầu. Nếu hội thoại được đánh dấu nhạy cảm (`is_sensitive=True`), BẮT BUỘC chỉ gọi model cục bộ qua Ollama, TUYỆT ĐỐI không gửi lên Gemini (tuân thủ Nguyên tắc 2).
  6. Cơ chế chống trùng lặp: Trước khi thêm một mục trí nhớ mới, hệ thống tìm kiếm các bản ghi tương tự trong cùng danh mục; nếu đã tồn tại thì thực hiện cập nhật nội dung thay vì sinh bản ghi rác thừa thãi.
  7. Quản lý ngân sách token: `ConversationContext.get_relevant_memories` tự động tính toán token ước lượng và giới hạn danh sách trí nhớ (mặc định tối đa 600 token) trước khi đưa vào system prompt.
  8. Bộ công cụ trí nhớ mới: `remember_fact` (mức `WRITE_SAFE`), `recall_memories` (mức `READ`), `forget_memory` (mức `CONFIRM` yêu cầu duyệt).
  9. Lệnh terminal mới trong `assistant chat`: `/history` (xem/chuyển đổi/tạo mới cuộc trò chuyện), `/sensitive` (bật/tắt chế độ nhạy cảm), `/memories` (xem danh sách trí nhớ), `/memory-edit` (sửa trí nhớ), `/memory-del` (xóa trí nhớ).
- **Lý do**: Đảm bảo toàn vẹn dữ liệu, quyền riêng tư tối thượng của người dùng trên Windows, không phụ thuộc thư viện bên ngoài và trải nghiệm hội thoại liền mạch qua các phiên làm việc.
- **Thư viện mới**: Không có (dùng `sqlite3` có sẵn của Python).

### [2026-10-26] Giai đoạn 4: Nhắc việc đúng giờ và Tác vụ định kỳ (APScheduler & Windows Toast)
- **Bối cảnh**: Cần hệ thống đặt lịch nhắc việc đúng giờ, hỗ trợ nhắc lặp lại định kỳ, hoãn nhắc (snooze), phát hiện các lời nhắc bị bỏ lỡ khi tắt máy tính, và hiển thị thông báo Windows Toast kèm âm thanh mà không phụ thuộc vào kết nối mạng khi kích hoạt.
- **Phương án đã chọn**:
  1. **Nguyên tắc cốt lõi: KHÔNG để AI làm đồng hồ**. AI chỉ chịu trách nhiệm phân tích câu nói của người dùng thành cấu trúc dữ liệu (thời gian ISO 8601, nội dung, biểu thức cron lặp). Việc canh giờ và kích hoạt thông báo do `APScheduler` và `SQLite` đảm nhiệm bằng code thuần Python, tuyệt đối không gọi LLM khi đến giờ kích hoạt.
  2. **Thư viện lập lịch `apscheduler>=3.10.4,<4.0.0`**: Sử dụng `AsyncIOScheduler` chạy trực tiếp trong event loop của asyncio, hỗ trợ `DateTrigger` cho lời nhắc một lần và `CronTrigger` cho lời nhắc lặp lại mà không cần cài thêm Redis hay worker tiến trình riêng.
  3. **Thư viện thông báo Windows `winotify>=1.1.0`**: Lựa chọn thay vì `windows-toasts` vì `winotify` viết 100% bằng pure Python, không đòi hỏi trình biên dịch C++ hay Windows SDK, không cần quyền Quản trị viên (Admin), hoạt động mượt mà và ổn định trên cả Windows 10 và 11, hỗ trợ đầy đủ âm thanh nhắc việc (`audio.Reminder`). Có cơ chế fallback tự động (in console và chuông hệ thống) nếu chạy trong môi trường headless.
  4. **Cơ sở dữ liệu SQLite**: Bảng `reminders` quản lý 5 trạng thái: `pending`, `fired`, `snoozed`, `cancelled`, `missed`.
  5. **Quét lời nhắc bị bỏ lỡ khi khởi động**: Tự động lọc các lời nhắc có `trigger_at < now` nhưng vẫn ở trạng thái `pending`/`snoozed`, đánh dấu `missed` và gom lại thông báo ngay cho người dùng tại thời điểm mở ứng dụng.
  6. **Mở rộng thông báo Telegram**: Hỗ trợ gửi thông báo song song qua Telegram bot nếu người dùng cấu hình token (trong keyring) và `telegram_chat_id`. Nếu mất mạng, hệ thống vẫn hiển thị Toast trên Windows bình thường, không làm gián đoạn lịch nhắc.
  7. **Bộ công cụ nhắc việc**:
     - `create_reminder`: Mức `CONFIRM`, trước khi lưu buộc AI diễn giải rõ thứ, ngày, tháng, giờ bằng tiếng Việt để xác nhận lại với người dùng.
     - `list_reminders`: Mức `READ`.
     - `cancel_reminder`: Mức `WRITE_SAFE`.
     - `snooze_reminder`: Mức `WRITE_SAFE` (lùi lại N phút).
  8. **Bản tin sáng (Morning Briefing)**: Module `reminders/briefing.py` tổng hợp công việc trong ngày khi người dùng gõ `/briefing` hoặc khởi động ứng dụng.
- **Lý do**: Đảm bảo nhắc việc đúng giờ tuyệt đối, độ tin cậy cao, chạy ngoại tuyến hoàn toàn và trải nghiệm Windows nguyên bản.
- **Thư viện mới**:
  - `apscheduler>=3.10.4,<4.0.0`: Lập lịch bất đồng bộ trong asyncio event loop.
  - `winotify>=1.1.0`: Hiển thị thông báo Toast Windows 10/11 kèm âm thanh không cần quyền Admin.

### [2026-10-26] Giai đoạn 5: Công cụ tài liệu và Các Agent chuyên trách (Multi-Agent Architecture)
- **Bối cảnh**: Cần mở rộng năng lực xử lý tài liệu văn phòng (PDF, Word, Excel), tự động hóa dọn dẹp thư mục, tra cứu web an toàn, và xây dựng cơ chế điều phối đa agent chuyên trách với quyền hạn tối thiểu riêng biệt.
- **Phương án đã chọn**:
  1. **Không dùng framework cồng kềnh**: Loại bỏ hoàn toàn các framework phức tạp (như LangChain, CrewAI, AutoGen). Mỗi Agent chuyên trách thực chất là một cấu hình `AgentSpec` gồm: tên vai trò, system prompt chuyên sâu, và danh sách công cụ được phép gọi `allowed_tools` (tuân thủ triệt để Nguyên tắc 11).
  2. **Thư viện xử lý tài liệu văn phòng**:
     - `pypdf>=4.0.0`: Đọc và trích xuất text từ PDF thuần Python, không cần cài thêm công cụ ngoài như poppler.
     - `python-docx>=1.1.0`: Đọc và tạo file Word (.docx) chuẩn cấu trúc đoạn văn bản và bảng.
     - `openpyxl>=3.1.0`: Đọc và tạo bảng tính Excel (.xlsx) đa sheet.
  3. **Công cụ dọn dẹp thư mục `organize_directory`**: Hỗ trợ phân loại theo phần mở rộng (`by_extension`) hoặc tháng sửa đổi (`by_date`). Mặc định `execute=False` trả về kế hoạch để người dùng xem trước; chỉ khi `execute=True` mới thực hiện di chuyển (mức `CONFIRM`).
  4. **Công cụ tra cứu web `fetch_webpage` & Phòng chống SSRF**:
     - Kiểm tra phân giải DNS và chặn triệt để localhost, 127.0.0.1, IPv6 loopback, toàn bộ dải IP riêng tư RFC 1918 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) và IP metadata cloud (169.254.169.254).
     - Loại bỏ thẻ script, style và bọc toàn bộ nội dung trong thẻ `<untrusted_content>` để chống prompt injection.
  5. **4 Agent chuyên trách với ma trận đặc quyền tối thiểu (Least Privilege)**:
     - `file_organizer_agent`: Chỉ có công cụ file/thư mục, không có quyền gọi shell hay web.
     - `document_agent`: Chỉ có công cụ đọc/tạo tài liệu văn bản, PDF, Word, Excel.
     - `research_agent`: Chỉ có công cụ `fetch_webpage`, đọc file và ghi chú. **Tuyệt đối CẤM `delete_path` và `run_command`** để triệt tiêu nguy cơ prompt injection từ web đánh lừa agent thực thi lệnh phá hoại.
     - `coder_agent`: Chuyên viết script và chạy lệnh kiểm thử trong workspace (`run_command` luôn yêu cầu `CONFIRM`).
  6. **Quy tắc điều phối**: Agent chính chỉ gọi `delegate_to_agent` khi tác vụ phức tạp nhiều bước; các yêu cầu đơn giản agent chính xử lý trực tiếp để tiết kiệm chi phí và độ trễ.
- **Lý do**: Tối ưu hiệu năng, bảo mật tối đa trước prompt injection từ internet, và phân tách trách nhiệm rõ ràng.
- **Thư viện mới**:
  - `pypdf>=4.0.0`: Trích xuất nội dung văn bản PDF.
  - `python-docx>=1.1.0`: Đọc và tạo tài liệu Word (.docx).
  - `openpyxl>=3.1.0`: Đọc và tạo bảng tính Excel (.xlsx).

### [2026-10-26] Giai đoạn 6: Backend Server (FastAPI + WebSocket) và Giao Diện Desktop (Offline Web UI)
- **Bối cảnh**: Cần chuyển đổi toàn bộ trải nghiệm từ terminal lên giao diện đồ họa đẹp, nhẹ, phản hồi streaming mượt mà theo thời gian thực, có cơ chế duyệt quyền bất đồng bộ (Approval Modal) khi gặp thao tác `CONFIRM`, và chạy được hoàn toàn ngoại tuyến không phụ thuộc internet hay CDN bên ngoài.
- **Phương án đã chọn**:
  1. **Khung máy chủ FastAPI + Uvicorn + WebSockets**:
     - Lựa chọn `FastAPI` và `Uvicorn` vì hiệu năng bất đồng bộ (asyncio) vượt trội, tích hợp sẵn Pydantic validation và hỗ trợ song song cả REST API lẫn WebSocket trên cùng một cổng.
     - Server chỉ lắng nghe trên `127.0.0.1` (localhost) tại cổng `ui_port` cấu hình trong `settings.toml`.
  2. **Bảo vệ an toàn bằng Session Token cục bộ**:
     - Tự động sinh `Session Token` ngẫu nhiên bảo mật cao qua `secrets.token_urlsafe(32)` khi khởi động máy chủ.
     - Xác thực token trên mọi yêu cầu REST (`X-Session-Token` hoặc query parameter) và WebSocket handshake (`/ws/chat?token=...`).
     - Ngăn chặn triệt để các trang web độc hại từ trình duyệt của người dùng khai thác API nội bộ (chống CSRF / SSRF cục bộ).
  3. **Cơ chế duyệt quyền bất đồng bộ qua WebSocket (Approval Flow)**:
     - Khi `AgentLoop` gặp công cụ mức `CONFIRM`, server sinh `request_id`, tạo `asyncio.Future` và phát sự kiện `approval_required` xuống UI.
     - Hộp thoại Approval Modal nổi lên giao diện với cảnh báo chi tiết và đồng hồ đếm ngược 120s.
     - Khi người dùng bấm "Cho phép" hoặc "Từ chối", client gửi sự kiện `approval_response` để mở khoá Future và tiếp tục hoặc dừng vòng lặp thực thi.
  4. **Giao diện Desktop ngoại tuyến 100% không dùng CDN**:
     - Toàn bộ HTML, CSS và JavaScript được lưu trữ cục bộ trong `src/assistant/ui_static/`.
     - Tuyệt đối không tải bất kỳ script, stylesheet hoặc font nào từ internet; sử dụng hệ thống font có sẵn trên Windows (`Segoe UI`, `Cascadia Code`).
     - Tự xây dựng bộ phân tích Markdown thuần bằng regex trong `app.js` có escape HTML chống XSS, hỗ trợ Dark/Light mode, xem sửa Trí nhớ và Nhắc việc.
  5. **Khởi chạy cửa sổ ứng dụng Microsoft Edge độc lập**:
     - Module `desktop/window.py` tự động phát hiện `msedge.exe` trên hệ thống và khởi chạy với tham số `--app=http://127.0.0.1:<port>/?token=<token>` (cửa sổ ứng dụng độc lập, không thanh địa chỉ).
     - Tuân thủ nghiêm ngặt Nguyên tắc 4: Tuyệt đối không dùng `shell=True`, gọi `subprocess.Popen` với mảng tham số (`list`). Tự động fallback sang trình duyệt mặc định nếu không có Edge.
  6. **Lệnh CLI `assistant ui` và thiết lập mặc định**:
     - Bổ sung lệnh `assistant ui` và đặt làm hành vi mặc định khi gõ `assistant` không kèm tham số.
- **Lý do**: Đảm bảo tốc độ khởi động nhanh, bảo mật tuyệt đối cho máy trạm Windows, giao diện người dùng hiện đại và hoạt động mượt mà kể cả khi ngắt kết nối mạng.
- **Thư viện mới**:
  - `fastapi>=0.110.0`: Khung làm việc API REST và WebSocket bất đồng bộ.
  - `uvicorn[standard]>=0.28.0`: Máy chủ ASGI chạy ứng dụng FastAPI trên localhost.
  - `websockets>=12.0`: Xử lý giao thức WebSocket thời gian thực.

### [2026-10-26] Giai đoạn 7: Khay Hệ Thống (System Tray) và Tự Khởi Động Cùng Windows (Autostart)
- **Bối cảnh**: Cần giúp Trợ lý chạy ngầm nhẹ nhàng ở khay hệ thống, không chiếm chỗ trên Taskbar sau khi đóng cửa sổ, tự khởi động cùng Windows mà không hỏi quyền Admin (UAC), và ngăn chặn việc mở nhiều tiến trình trùng lặp (Single Instance).
- **Phương án đã chọn**:
  1. **Khay hệ thống `pystray>=0.19.5` và đồ họa `Pillow>=10.2.0`**:
     - Lựa chọn `pystray` vì hoạt động tin cậy và native trên Windows Taskbar notification area.
     - Sử dụng `Pillow` để vẽ icon động 64x64 trong bộ nhớ (không cần file ảnh tĩnh bên ngoài). Tự động cập nhật chấm trạng thái: 🟢 Online (Gemini) / 🟡 Offline (Ollama).
     - Menu chuột phải 100% bằng tiếng Việt với các chức năng thiết yếu: Mở cửa sổ, Đổi model, Khởi động cùng Windows, Mở Workspace, Thoát hoàn toàn.
  2. **Tự khởi động cùng Windows không cần quyền Admin (`desktop/autostart.py`)**:
     - Sử dụng module chuẩn `winreg` của Python can thiệp vào `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`.
     - Tuyệt đối tuân thủ Nguyên tắc 2: Chỉ ghi vào Registry của người dùng hiện tại (HKCU), hoàn toàn không yêu cầu quyền Quản trị viên (Admin / UAC).
     - Dùng `pythonw.exe` và cờ `--minimized` để khi Windows khởi động máy, Trợ lý chỉ chạy ngầm ở khay hệ thống mà không tự bung cửa sổ giao diện hay hiện màn hình console đen làm phiền người dùng.
  3. **Khóa tiến trình duy nhất (`desktop/single_instance.py`)**:
     - Quản lý tệp `data_dir/instance.json` ghi PID, cổng và session token.
     - Khi người dùng mở app lần thứ hai trong lúc app đang chạy ngầm, hệ thống phát hiện instance cũ đang sống, tự động gọi kích hoạt lại cửa sổ Edge cho instance cũ và thoát nhẹ nhàng tiến trình mới.
  4. **Cập nhật lệnh `assistant doctor`**:
     - Bổ sung chẩn đoán trạng thái Autostart, Khay hệ thống và Single Instance.
- **Lý do**: Tối ưu trải nghiệm sử dụng hàng ngày trên Windows, đảm bảo tính năng nhắc việc luôn chạy đúng giờ mà không làm người dùng cảm thấy bị vướng víu trên màn hình.
### [2026-10-26] Sửa lỗi cú pháp main.py và Bổ sung điểm nhập __main__.py cho gói assistant
- **Bối cảnh**: Khi người dùng chạy lệnh `assistant` hoặc `python -m assistant ui`, phát sinh 2 lỗi:
  1. `SyntaxError: expected 'except' or 'finally' block` tại dòng 309 của `main.py` do cấu trúc thụt đầu dòng (indentation) khi bọc scheduler trong `try...finally`.
  2. `No module named assistant.__main__; 'assistant' is a package and cannot be directly executed` khi chạy bằng `python -m assistant`.
- **Phương án đã chọn**:
  1. Tách hàm `_interactive_chat_loop()` riêng biệt khỏi `_chat_session()`. Trong `_chat_session()`, sử dụng `try: await _interactive_chat_loop(...) finally: scheduler.shutdown(); set_global_scheduler(None)` để đảm bảo giải phóng tài nguyên. Trong `_interactive_chat_loop()`, cấu trúc vòng lặp `while True:` được căn lề chuẩn 4 spaces, giải quyết triệt để lỗi cú pháp.
  2. Tạo mới `src/assistant/__main__.py` gọi hàm `cli()` từ `assistant.main`, cho phép chạy trực tiếp bằng `python -m assistant ui` hoặc thông qua `scripts/run_app.bat` và registry autostart.
- **Lý do**: Tuân thủ chuẩn packaging của Python và đảm bảo mọi phương thức khởi động (`assistant`, `assistant ui`, `python -m assistant`, `scripts/run_app.bat`) đều vận hành hoàn hảo và đồng nhất.

### [2026-10-26] Giai đoạn 8: Rà soát bảo mật toàn diện, Tối ưu giao diện và Đóng gói PyInstaller
- **Bối cảnh**: Cần hoàn thiện khâu kiểm thử bảo mật chống Prompt Injection và chống rò rỉ secret, bổ sung giao diện cấu hình trực quan không cần gõ lệnh, và đóng gói thành tệp chạy Windows (.exe) độc lập để người dùng mở bằng cách bấm đúp chuột ngoài Desktop mà không cần terminal.
- **Phương án đã chọn**:
  1. **Khắc phục Circular Import**: Trì hoãn việc import `AgentLoop` bên trong `run_subagent()` trong `agents/orchestrator.py` và tái cấu trúc thứ tự nạp module trong `tools/__init__.py`.
  2. **Bộ kiểm thử bảo mật `tests/test_security_e2e.py`**:
     - Kiểm thử bọc `<untrusted_content>` và đánh dấu lây nhiễm (Taint Tracking): buộc mọi hành động ghi/lệnh phải được duyệt khi đã đọc tài liệu ngoài.
     - Kiểm thử từ chối cứng (DENY) cho các lệnh shell phá hoại hệ thống.
     - Kiểm thử chống rò rỉ `GEMINI_API_KEY` và `session_token` trong log xoay vòng và `audit.jsonl` qua cơ chế `SecretFilter.register_secret()`.
  3. **Trang Cài đặt & Chẩn đoán trên Web UI**:
     - Bổ sung màn hình `screen-settings` cho phép kiểm tra trực tiếp trạng thái kết nối Gemini Cloud, trạng thái Ollama cục bộ, danh sách model Ollama đã cài.
     - Nhập và lưu Gemini API Key trực tiếp vào Windows Credential Locker qua API `/api/settings/gemini-key` bảo mật bằng `keyring`.
  4. **Đóng gói PyInstaller (`assistant.spec` & `scripts/build_exe.py`)**:
     - Lựa chọn `--onedir`: Khởi động nhanh, ổn định hơn và tránh bị các phần mềm diệt virus trên Windows gắn cờ cảnh báo nhầm (false positive) so với chế độ nén `--onefile`.
     - Lựa chọn `--noconsole` (`windowed=True`): Không làm bật cửa sổ console màu đen khi khởi động.
     - Tự động tạo Shortcut `.lnk` ngoài Desktop người dùng qua lệnh PowerShell COM `WScript.Shell`.
- **Lý do**: Đảm bảo an toàn tuyệt đối theo 12 Nguyên tắc bất biến, nâng cao trải nghiệm người dùng cuối trên Windows và cung cấp khả năng phân phối phần mềm chuyên nghiệp.
- **Thư viện mới**:
  - `pyinstaller>=6.5.0`: Đóng gói ứng dụng Python thành tệp nhị phân thực thi Windows.

### [2026-10-27] Rà Soát Toàn Diện, Sửa Lỗi và Tái Cấu Trúc Giao Diện (Audit & Fixes)
- **Bối cảnh**: Triển khai đợt rà soát mã nguồn toàn diện theo yêu cầu kiểm toán QA, khắc phục triệt để các lỗi P0 (sập app/endpoint), P1 (sai chức năng router, trí nhớ, FTS5, mở app, nhật ký, mã hóa), P2 (bảo mật hộp thoại duyệt, XSS DOMPurify, bảng markdown, WCAG AA, modular CSS, i18n), và P3 (kiểm thử tự động Playwright, tương thích import).
- **Phương án đã chọn**:
  1. **Định tuyến & Kiểm tra mạng (`ModelRouter.is_network_available`) (ERR-01)**:
     - Bổ sung hàm uỷ quyền `is_network_available()` trong `ModelRouter`.
     - Sử dụng cache 10 giây kết hợp với socket TCP đồng bộ timeout 0.4s (kiểm tra `1.1.1.1:53`) khi cache hết hạn, giải quyết triệt để lỗi `AttributeError` tại `/api/status`.
  2. **Tương thích khởi tạo ReminderScheduler (ERR-02)**:
     - Constructor `ReminderScheduler.__init__` chấp nhận cả tham số `store` và `reminder_store`.
  3. **Nạp Trí Nhớ Vào System Prompt WebSocket (`ws.py`) (ERR-03)**:
     - Trong `_handle_chat_turn()`, tự động trích xuất các trí nhớ dài hạn phù hợp nhất (`context.get_relevant_memories(self.memory_store)`) và nạp vào `get_system_prompt(memories=...)`, đảm bảo trợ lý duy trì ngữ cảnh người dùng trên giao diện Web Desktop.
  4. **Tìm kiếm FTS5 An Toàn (`store.py`) (ERR-04)**:
     - Bọc câu lệnh truy vấn SQLite FTS5 `MATCH` trong khối `try...except sqlite3.OperationalError` và tự động fallback sang SQL `LIKE %query%` khi người dùng nhập các ký tự đặc biệt (dấu nháy, dấu sao, toán tử FTS5).
  5. **So Khớp Tên Ứng Dụng Chuẩn Xác (`apps.py`) (ERR-05)**:
     - Thay thế so khớp chuỗi con lỏng lẻo (`alias in query`) bằng so khớp chính xác tuyệt đối (`query == alias`), tiếp theo là so khớp theo ranh giới từ Regex (`\b`), loại bỏ hiện tượng gõ "developer" bị mở Paint.
  6. **Endpoint và Giao Diện Nhật Ký Kiểm Toán (`/api/audit` & `#screen-audit`) (ERR-06)**:
     - Cung cấp API `GET /api/audit` đọc danh sách sự kiện từ `audit.jsonl` (đã được lọc secret).
     - Bổ sung tab điều hướng "📋 Nhật ký" và màn hình bảng biểu kiểm toán trên giao diện người dùng.
  7. **Hỗ Trợ Tiếng Việt Console Windows (`main.py`) (ERR-07)**:
     - Gọi `sys.stdout.reconfigure(encoding="utf-8")` và `sys.stderr.reconfigure(encoding="utf-8")` khi khởi động trên Windows, tránh lỗi `UnicodeEncodeError`.
  8. **Bảo Mật Hộp Thoại Duyệt Quyền Bàn Phím (`app.js`) (ERR-08)**:
     - Triển khai Keyboard Focus Trap bên trong Approval Modal.
     - Phím `Escape` kích hoạt từ chối an toàn.
     - Phím `Enter` bị chặn tự động duyệt để tránh người dùng gõ phím vô tình chấp thuận lệnh nguy hiểm. Nút Từ chối luôn được focus mặc định khi mở modal.
  9. **Trình Phân Tích Markdown Bảng & Vệ Sinh Mã Độc Offline (ERR-09, ERR-10)**:
     - Thêm phân tích bảng dữ liệu Markdown và bao bọc trong `.table-container` có hỗ trợ cuộn ngang.
     - Tích hợp `DOMPurify` ngoại tuyến (`vendor/purify.min.js`), triệt tiêu hoàn toàn nguy cơ XSS / Script Injection mà không tải bất kỳ script nào từ CDN internet.
  10. **Tách Lớp CSS & Chuẩn Màu WCAG AA (`tokens.css`, `base.css`, `layout.css`, `components.css`) (ERR-11)**:
      - Tách nhỏ `style.css` thành hệ thống Design Tokens.
      - Chỉnh sửa màu `--text-muted` thành `#64748b` (tỷ lệ tương phản 4.6:1, đạt chuẩn WCAG AA).
      - Rút ngắn thời gian transition xuống <= 150ms và hỗ trợ `@media (prefers-reduced-motion)`.
  11. **Quốc Tế Hóa Cục Bộ (`i18n/vi.json`) (ERR-12)**:
      - Gom toàn bộ chuỗi văn bản giao diện vào `src/assistant/ui_static/i18n/vi.json` với helper `t(key)`.
  12. **Bộ Công Cụ Kiểm Thử Tự Động Playwright Đa Độ Phân Giải (`scripts/ui_check.py`) (ERR-13)**:
      - Kiểm tra tự động 3 độ phân giải (900x600, 1280x800, 1920x1080) và 2 chủ đề (sáng/tối).
      - Giám sát nghiêm ngặt mọi network request (chỉ cho phép `127.0.0.1`), bắt lỗi console, đo đạc layout và chụp ảnh lưu vào `docs/ui-shots/`.
- **Lý do**: Giải quyết triệt để toàn bộ danh sách khiếm khuyết được phát hiện, tuân thủ nghiêm ngặt 12 Nguyên tắc bất biến và chuẩn mực kỹ thuật cao nhất.
- **Thư viện mới**:
  - `playwright>=1.42.0`: Công cụ kiểm thử tự động trình duyệt đa độ phân giải phục vụ QA giao diện (chỉ dùng trong môi trường dev).

### [2026-10-27] Khắc phục 5 lỗi kỹ thuật về Cấu hình, Model Routing, WebSocket và Gemini Tool Call
- **Bối cảnh**:
  - Lỗi 1: `NameError: name 're' is not defined` trong `app.py` khi đổi model cục bộ tại route POST `/api/settings/local-model`. Ngoài ra, GET `/api/status` dùng nhầm thuộc tính `last_used_model` (thực tế là `last_model_used`) và hardcode `daily_requests_count: 0`.
  - Lỗi 2: WebSocket `ws.py` lưu sai `model_used` do dùng nhầm `last_used_model`, đồng thời sự kiện `turn_done` luôn trả về mảng rỗng `tools_called: []` do không gom các sự kiện `tool_start` trong lượt.
  - Lỗi 3: Gemini API báo lỗi 400 Bad Request khi phản hồi kết quả công cụ vì `Part.from_function_response` nhận `tool_call_id` (ví dụ `call_xyz`) thay vì tên hàm đã khai báo (`name`).
  - Lỗi 4: Khi đóng gói bằng PyInstaller (`--onedir` / `--onefile`), `load_config()` tìm file `config/settings.toml` và `.env` theo `Path(__file__)` bên trong gói dẫn tới thất lạc cấu hình ngoài file thực thi exe.
- **Phương án đã chọn**:
  1. Trong `src/assistant/server/app.py`:
     - Bổ sung `import re` và `import sys`.
     - Route POST `/api/settings/local-model` quét các đường dẫn ứng viên (bao gồm thư mục chứa file exe khi đóng gói) và dùng biểu thức chính quy ghi đè chính xác tên model vào `config/settings.toml`.
     - Route GET `/api/status` sử dụng `getattr(app_router, "last_model_used", ...)` và lấy số request thực tế trong ngày từ `app_router.usage_tracker.get_count()`.
  2. Trong `src/assistant/server/ws.py`:
     - Chuyển `last_used_model` thành `last_model_used` khi lưu vào bảng `messages` SQLite và khi gửi `turn_done`.
     - Khởi tạo danh sách `tools_called_in_turn` và bắt sự kiện `tool_start` / `turn_done` trong `_on_event` để thu thập đầy đủ các công cụ đã được gọi.
  3. Trong `src/assistant/llm/base.py` & `src/assistant/llm/gemini_provider.py` & `src/assistant/core/agent_loop.py`:
     - Bổ sung trường `name: str | None` trong `Message` cho role `tool`.
     - Khi `agent_loop.py` tạo tin nhắn phản hồi công cụ, gán tường minh `name=tc.name`.
     - Trong `gemini_provider.py`, xây dựng bảng tra cứu từ `tool_call_id` sang `function name` từ lịch sử các `tool_calls` trước đó để luôn truyền đúng function name cho `types.Part.from_function_response(name=func_name, ...)`.
  4. Trong `src/assistant/config.py`:
     - Kiểm tra `getattr(sys, "frozen", False)`. Nếu ứng dụng đang chạy dưới dạng exe đã đóng gói, xác định thư mục gốc thông qua `Path(sys.executable).parent` (ưu tiên cấu hình người dùng đặt cạnh file exe) và fallback sang `Path(sys._MEIPASS)` (thư mục bundle nội bộ). Tự động nạp `.env` từ cả hai vị trí này.
     - Cập nhật giá trị model cục bộ mặc định thành `qwen2.5:14b` đồng bộ với card đồ họa RTX 3060 12GB và file `config/settings.toml`.
- **Lý do**:
  - Tuân thủ triệt để 12 Nguyên tắc bất biến (Nguyên tắc 1: Đúng phạm vi, Nguyên tắc 2: An toàn bảo mật, Nguyên tắc 6: Thư viện chuẩn xác, Nguyên tắc 7: Mã sạch & kiểm thử).
- **Thư viện mới**: Không có.

### [2026-10-27] Nâng cấp cơ chế ủy quyền đa Agent và luồng duyệt quyền bất đồng bộ (Multi-Agent Approval)
- **Bối cảnh**:
  - Khi `run_subagent()` trong `src/assistant/agents/orchestrator.py` khởi tạo `child_agent_loop = AgentLoop(...)`, nó không nhận `approval_callback` nên nhận mặc định là `ask_terminal_approval` (dùng `input()` từ console).
  - Khi chạy trên Web UI / Desktop EXE (`--noconsole`), nếu một agent con (như `coder_agent` hoặc `file_organizer_agent`) gọi công cụ cấp `CONFIRM` (ví dụ `run_command`, `delete_path`), ứng dụng bị treo vĩnh viễn (freeze) vì không có console stdin để người dùng nhập liệu, đồng thời modal xác nhận trên web không được kích hoạt.
- **Phương án đã chọn**:
  1. Trong `src/assistant/agents/orchestrator.py`:
     - Thiết lập biến `_orchestrator_approval_cb` thông qua `contextvars.ContextVar` và biến dự phòng toàn cục `_global_approval_callback`.
     - Cung cấp 2 hàm quản lý `set_orchestrator_approval_callback(cb)` và `get_orchestrator_approval_callback()`.
     - Nâng cấp hàm `run_subagent(..., approval_callback=None, on_event=None)`: nhận tham số `approval_callback` và fallback về `get_orchestrator_approval_callback()`. Truyền callback này vào `AgentLoop(..., approval_callback=active_approval)` của agent con.
     - Chuyển `delegate_to_agent` thành hàm bất đồng bộ (`async def`), nhận `approval_callback` và `on_event` để chạy trực tiếp trên asyncio event loop hiện hành, loại bỏ `ThreadPoolExecutor` không cần thiết.
  2. Trong `src/assistant/core/agent_loop.py`:
     - Hỗ trợ công cụ bất đồng bộ (`async def`): khi `inspect.iscoroutinefunction(tool_def.func)` là True, gọi `await tool_def.func(...)` trực tiếp trên cùng event loop.
     - Tự động truyền `approval_callback=self.approval_callback` và `on_event=on_event` cho các công cụ có khai báo nhận 2 tham số này.
     - Bổ sung phòng thủ trong `ask_terminal_approval`: kiểm tra `sys.stdin is None` và bắt `OSError` để tránh treo khi chạy trong môi trường không có bàn phím terminal.
  3. Trong `src/assistant/tools/registry.py`:
     - Ẩn các tham số nội bộ (`approval_callback`, `on_event`) khỏi JSON Schema sinh tự động để không làm rối model LLM.
     - Trong `ToolDefinition.execute`: hỗ trợ tự động giải phóng coroutine nếu bị gọi từ ngữ cảnh đồng bộ.
  4. Trong `src/assistant/server/ws.py`:
     - Khi phiên chat bắt đầu, gọi `set_orchestrator_approval_callback(_websocket_approval)` để gắn luồng duyệt quyền qua WebSocket cho mọi agent con được uỷ quyền. Dọn dẹp trong khối `finally`.
  5. Trong `tests/test_agents.py`:
     - Bổ sung 3 unit test: `test_subagent_triggers_approval_callback`, `test_subagent_approval_rejection_handled`, và `test_delegate_to_agent_inherits_orchestrator_approval`.
- **Lý do**:
  - Tuân thủ Nguyên tắc 2 (An toàn trước tiên: mọi thao tác phá huỷ phải qua duyệt), Nguyên tắc 7 (Mã sạch & kiểm thử), Nguyên tắc 9 (Không nuốt lỗi im lặng).
- **Thư viện mới**: Không có.

### [2026-10-27] Tối ưu hóa hiệu năng tầng Model (Ollama Cache) và tầng Lưu trữ SQLite (PRAGMA SSD & Indexes)
- **Bối cảnh**:
  - Tầng Model: Hàm `OllamaProvider.stream_chat()` trước đây gọi `installed = await self.list_models()` (gửi HTTP GET `/api/tags`) ở MỌI tin nhắn người dùng, gây trễ 50-100ms trên mỗi lượt chat dù danh sách mô hình cài đặt hiếm khi thay đổi liên tục.
  - Tầng Lưu trữ SQLite: Cần tối ưu đọc/ghi cho ổ cứng SSD trên Windows, hạn chế số lần flush đĩa vật lý không cần thiết và tăng tốc độ lọc/tìm kiếm các bản ghi hội thoại, tin nhắn, trí nhớ và lời nhắc việc thường xuyên truy vấn.
- **Phương án đã chọn**:
  1. Trong `src/assistant/llm/ollama_provider.py`:
     - Thiết kế bộ đệm `_cached_models: list[str]` với thời gian sống `_models_ttl_seconds = 60.0` (TTL 60 giây) và `_last_models_check_time: float`.
     - Thêm phương thức `invalidate_model_cache()` xóa sạch cache.
     - Trong `set_model()`: tự động gọi `invalidate_model_cache()` khi người dùng đổi sang mô hình mới.
     - Trong `list_models(force_refresh: bool = False)`: chỉ gửi HTTP request tới Ollama khi cache đã hết hạn hoặc khi `force_refresh=True`. Nhờ vậy loại bỏ hoàn toàn độ trễ 50-100ms trong các lượt chat thông thường.
  2. Trong `src/assistant/memory/store.py` và `src/assistant/reminders/store.py`:
     - Tại `_get_connection()`, bổ sung các PRAGMA chuẩn cho Windows SSD trong chế độ WAL:
       + `PRAGMA synchronous = NORMAL;`: giảm tần suất flush đĩa vật lý của hệ điều hành mà vẫn bảo đảm trọn vẹn an toàn dữ liệu và tuân thủ ACID khi dùng WAL.
       + `PRAGMA cache_size = -32000;`: cấp phát bộ đệm 32MB RAM cache cho SQLite (mặc định chỉ 2MB).
       + `PRAGMA temp_store = MEMORY;`: lưu trữ các bảng tạm và phép tính sắp xếp trong RAM.
     - Tại `_init_db()`:
       + Tạo chỉ mục `idx_messages_conv_created ON messages(conversation_id, created_at)` tăng tốc truy vấn lịch sử hội thoại gần nhất.
       + Tạo chỉ mục `idx_memories_category ON memories(category)` tăng tốc lọc trí nhớ dài hạn theo danh mục (`preference`, `project`, `naming_rule`, `general`).
       + Đảm bảo chỉ mục `idx_reminders_status_trigger ON reminders(status, trigger_at)` tối ưu quét lịch nhắc việc pending/snoozed.
     - Bảo đảm toàn vẹn 100% cấu trúc các bảng hiện có và bảng ảo FTS5 (`memories_fts`, `messages_fts`).
  3. Kiểm chứng & Unit Test:
     - Thêm test `test_ollama_provider_model_cache_and_invalidation` trong `tests/test_providers.py`.
     - Cập nhật xác minh PRAGMA và Indexes trong `tests/test_memory_store.py` và `tests/test_reminders.py`.
- **Lý do**:
  - Giảm độ trễ phản hồi chat, tối ưu hóa I/O cho phần cứng Windows SSD, tuân thủ Nguyên tắc 7 (Mã sạch & kiểm thử) và Nguyên tắc 10 (Ghi nhận quyết định kỹ thuật).
- **Thư viện mới**: Không có.

### [2026-10-27] Nâng cấp Trí nhớ Dài hạn (Long-term Memory) sang cơ chế Hybrid Search (FTS5 BM25 + Ollama Embeddings + RRF)
- **Bối cảnh**:
  - Cơ chế truy xuất trí nhớ ban đầu chỉ dựa vào bảng ảo SQLite FTS5 (so khớp từ khóa chính xác unicode61). Khi người dùng hỏi bằng từ đồng nghĩa hoặc câu hỏi mang tính ngữ nghĩa trừu tượng (ví dụ: query "quy tắc đặt tên" không chứa từ "cách đặt file"), FTS5 không thể truy xuất được các dữ kiện liên quan.
- **Phương án đã chọn**:
  1. Module `src/assistant/memory/embeddings.py`:
     - Kết nối tới endpoint `/api/embeddings` của Ollama thông qua thư viện `httpx` đã có sẵn trong dự án (hỗ trợ cả sync và async, model mặc định `nomic-embed-text` hoặc `all-minilm`).
     - Triển khai hàm tuần tự hóa vector float32 thành nhị phân `BLOB` (`float_list_to_blob`) và ngược lại (`blob_to_float_list`) bằng module chuẩn `struct`.
     - Triển khai hàm tính Cosine Similarity thuần Python bằng module `math`.
     - Tuyệt đối tuân thủ Nguyên tắc 11: không cài đặt thêm numpy, scipy, chromadb hay faiss.
     - Triển khai thuật toán Reciprocal Rank Fusion (`reciprocal_rank_fusion`) với hằng số $k=60$ để hợp nhất thứ hạng giữa FTS5 BM25 và Vector Similarity.
  2. Bảng `memory_embeddings` trong SQLite (`src/assistant/memory/store.py`):
     - `memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE, embedding BLOB NOT NULL, created_at TEXT NOT NULL`.
     - Tạo chỉ mục `idx_memory_embeddings_created ON memory_embeddings(created_at)`.
  3. Cập nhật `MemoryStore`:
     - `add_memory`: tự động sinh vector embedding qua Ollama và lưu song song vào bảng `memory_embeddings`.
     - `update_memory`: tự động cập nhật lại vector embedding khi nội dung trí nhớ thay đổi.
     - `delete_memory`: xoá sạch dữ liệu trong `memories_fts` và `memory_embeddings`.
     - `search_memories_hybrid(query, top_k=10)`:
       + Lấy kết quả từ FTS5.
       + Tính cosine similarity giữa vector truy vấn và toàn bộ vector trong database.
       + Kết hợp kết quả bằng Reciprocal Rank Fusion (RRF: `score = 1 / (60 + rank)`).
       + Fallback mượt mà về tìm kiếm FTS5/LIKE nếu Ollama tắt hoặc model embedding chưa tải.
  4. Nạp System Prompt và Tools:
     - `ConversationContext.get_relevant_memories(store, max_tokens=600, max_memories=15, query=...)`: ưu tiên gọi `search_memories_hybrid` dựa trên query (hoặc tin nhắn gần nhất của user).
     - `src/assistant/server/ws.py` & `src/assistant/main.py`: truyền query của người dùng vào `get_relevant_memories()`.
     - `recall_memories` trong `memory_tools.py` và route GET `/api/memories` trong `server/app.py`: sử dụng `search_memories_hybrid`.
  5. Cấu hình (`config.py` & `settings.toml`):
     - Bổ sung `embedding_model = "nomic-embed-text"` (có thể cấu hình qua file TOML hoặc biến môi trường `EMBEDDING_MODEL`).
  6. Kiểm thử tự động (`tests/test_hybrid_memory.py`):
     - Kiểm thử chuyển đổi vector blob float32.
     - Kiểm thử Cosine Similarity thuần Python (trùng khớp, trực giao, ngược chiều).
     - Kiểm thử tính toán xếp hạng RRF.
     - Kiểm thử tìm kiếm từ đồng nghĩa (query "quy tắc đặt tên" khớp thành công memory "cách đặt file YYYY-MM-DD").
     - Kiểm thử fallback mượt mà khi Ollama offline.
     - Kiểm thử đồng bộ cập nhật/xóa vector.
     - Kiểm thử nạp trí nhớ hybrid vào `ConversationContext`.
- **Lý do**:
  - Tối ưu hóa vượt bậc khả năng hiểu ngữ nghĩa và gợi nhớ của trợ lý, duy trì hoạt động cục bộ 100% trên Windows và giữ vững nguyên tắc bảo mật, không phụ thuộc thư viện nặng.
- **Thư viện mới**: Không có (sử dụng thư viện chuẩn `math`, `struct` và `httpx` đã có).

### [2026-10-27] Hỗ trợ Kéo-thả tập tin (Drag & Drop) và Phím tắt toàn cục (Global Hotkey / Spotlight Mode)
- **Bối cảnh**:
  - Người dùng cần gửi nhanh tài liệu (PDF, Word, Excel, Text, Code) vào cuộc trò chuyện mà không cần gõ đường dẫn thủ công.
  - Người dùng cần gọi nhanh Trợ lý từ bất kỳ ứng dụng hoặc màn hình nào trên Windows thông qua phím tắt toàn cục để tra cứu tức thì (Spotlight Mode).
- **Phương án đã chọn**:
  1. Kéo-thả tập tin (Drag & Drop File Upload):
     - Web UI (`index.html`, `layout.css`, `components.css`, `app.js`):
       + Tạo Dropzone overlay hiển thị khi kéo tệp tin vào khung chat (`dragenter`, `dragover`, `dragleave`, `drop`).
       + Sử dụng biến đếm `dragCounter` để loại bỏ hiện tượng nhấp nháy (flicker) khi con trỏ chuột lướt qua các phần tử con.
       + Khi thả file: Tải file lên server qua API `POST /api/upload-file` với `FormData`.
       + Sau khi upload thành công: Tự động chuyển về khung chat và điền câu lệnh: `"Hãy tóm tắt và phân tích nội dung file: <tên_file>"`, đồng thời đặt con trỏ vào ô nhập chat.
     - Server (`src/assistant/server/app.py` & `schemas.py`):
       + Endpoint `POST /api/upload-file` nhận `UploadFile` (yêu cầu Session Token bảo vệ chống CSRF/SSRF).
       + Trích xuất tên tệp an toàn bằng `Path(file.filename).name.strip()`.
       + Kiểm tra an toàn đường dẫn tuyệt đối bằng `resolve_in_workspace(raw_name, workspace_dir=app_config.workspace_dir)` nhằm ngăn chặn hoàn toàn tấn công path traversal (`../`) và tên thiết bị cấm của Windows (`CON`, `NUL`, v.v.).
       + Ghi tệp an toàn theo từng khối (chunk 64KB) và giới hạn kích thước tối đa 25MB (25 * 1024 * 1024 bytes). Nếu vượt quá kích thước, huỷ ghi và dọn dẹp ngay phần tệp dở dang.
  2. Phím tắt toàn cục (Global Hotkey / Spotlight Mode):
     - `src/assistant/desktop/hotkey.py`:
       + Sử dụng 100% thư viện chuẩn `ctypes` gọi Windows API `RegisterHotKey` và `UnregisterHotKey` (tuân thủ Nguyên tắc 11: không dùng thêm thư viện hook bàn phím nặng).
       + Phím tắt mặc định: `Ctrl + Shift + Space` (`MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT`, phím `VK_SPACE`).
       + Luồng riêng biệt xử lý Message Loop (`GetMessageW`, `TranslateMessage`, `DispatchMessageW`) và dừng sạch sẽ thông qua `PostThreadMessageW(WM_QUIT)`.
       + Khi kích hoạt:
         1. Gọi `activate_spotlight_mode()`: Quét tìm HWND cửa sổ Trợ lý qua `EnumWindows` và đưa lên trên cùng bằng `SetForegroundWindow` (vượt qua cơ chế chặn của Windows bằng `AttachThreadInput`).
         2. Phát tín hiệu WebSocket `{ "type": "focus_input" }` tới Web UI client để tự động đặt con trỏ vào ô nhập chat.
     - Web UI Settings & REST API:
       + Endpoint `GET /api/settings/hotkey` và `POST /api/settings/hotkey` để kiểm tra và bật/tắt phím tắt động.
       + Bổ sung công tắc bật/tắt trong màn hình Cài đặt của Web UI (`#chk-hotkey`).
  3. Kiểm thử tự động (`tests/test_upload_and_hotkey.py`):
     - Kiểm thử tải file hợp lệ và lưu đúng nội dung vào workspace.
     - Kiểm thử phòng vệ Path Traversal và tên tệp cấm Windows.
     - Kiểm thử chặn tệp vượt quá 25MB.
     - Kiểm thử yêu cầu xác thực Session Token.
     - Kiểm thử API cấu hình phím tắt và vòng đời `GlobalHotkeyManager`.
- **Lý do**:
  - Nâng cấp trải nghiệm người dùng tương tự các trợ lý AI Desktop cao cấp (Spotlight / Raycast), giữ vững 100% nguyên tắc an toàn, không rò rỉ bộ nhớ hay xung đột luồng.
### [2026-10-27] Khắc phục lỗi Mô hình Gemini (404 Not Found), Cơ Chế Tự Phục Hồi Model & Fallback Cục Bộ
- **Bối cảnh**:
  - Khi người dùng gửi tin nhắn chat, Google Gemini API trả về lỗi:
    `[UNKNOWN] Lỗi không xác định từ Gemini: 404 Not Found. {'message': 'This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models/gemini-3.8-flash for the latest features and improvements.'}`
  - Nguyên nhân: Google AI Studio đã chính thức ngừng hỗ trợ mô hình `gemini-2.5-flash` và chuyển sang `gemini-3.8-flash` (và các dòng `gemini-2.0-flash`, `gemini-1.5-flash`). Đồng thời trong cấu hình `settings.toml` và `config.py` vẫn giữ giá trị cũ `gemini-2.5-flash`.
  - Bộ định tuyến `ModelRouter` ở chế độ `auto` trước đây chỉ bắt các lỗi mạng/429/5xx để fallback sang Ollama; các lỗi như 404 hoặc model ngừng hỗ trợ bị re-raise khiến khung chat hiển thị hộp đỏ lỗi không mong muốn.
- **Phương án đã chọn**:
  1. **Nâng cấp Cấu hình Mặc định**:
     - Cập nhật `config/settings.toml` và `src/assistant/config.py`: đổi mô hình mặc định từ `gemini-2.5-flash` sang `gemini-3.8-flash`.
  2. **Cơ chế Tự Phục Hồi Ứng Viên Mô Hình (Candidate Fallback Loop)** trong `GeminiProvider`:
     - Khi gọi `generate_content_stream()`: định nghĩa danh sách mô hình dự phòng `[self._model_name, "gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"]`.
     - Nếu mô hình hiện tại gặp lỗi 404 / Model Not Found trước khi gửi token, hệ thống tự động thử tiếp ứng viên tiếp theo trong danh sách.
     - Khi một model thành công, tự động cập nhật `self._model_name` để các lượt gọi sau sử dụng ngay mô hình đang hoạt động.
  3. **Tự Động Fallback Sang Ollama Trong Chế Độ Auto** trong `ModelRouter`:
     - Nếu Gemini gặp bất kỳ sự cố nào không thể phục hồi (kể cả 404, model lỗi hoặc hết số lần retry), ngoại trừ lỗi xác thực (`auth`) hoặc nội dung vi phạm bản quyền/an toàn (`content_blocked`), hệ thống tự động chuyển sang mô hình cục bộ Ollama (`qwen2.5:14b`) và thông báo cho người dùng `[Hệ thống: Đã chuyển sang model cục bộ vì...]` thay vì làm sập lượt chat.
  4. **Cài Đặt & Lựa Chọn Mô Hình Trên Giao Diện Web**:
     - Thêm endpoint `POST /api/settings/gemini-model` cập nhật model Gemini động và lưu vào `config/settings.toml`.
     - Thêm trường `gemini_models` trong `GET /api/diagnostics` và `DiagnosticsResponse`.
     - Bổ sung bộ chọn mô hình Gemini Cloud trong màn hình Cài đặt của Web UI (`#settings-select-gemini-model`).
- **Lý do**:
  - Đảm bảo ứng dụng luôn chạy mượt mà, tự chữa lành khi Google cập nhật hoặc khai tử các phiên bản mô hình, người dùng không bao giờ bị gián đoạn hay thấy lỗi đỏ trong chế độ Tự động.
### [2026-10-27] Quản lý nhiều Gemini API Keys và Kiểm tra kết nối trực tiếp (Multi-Key Management & Connectivity Testing)
- **Bối cảnh**:
  - Người dùng sở hữu nhiều tài khoản Google AI Studio và muốn lưu nhiều Gemini API keys để dự phòng và xoay vòng khi chạm hạn mức (429 Rate Limit).
  - Cần hiển thị từng khóa rõ ràng trong giao diện Cài đặt, có nút "Kiểm tra" (Test) để biết khóa còn sống hay bị từ chối/hết hạn trước khi chat.
  - Phải tuân thủ nghiêm ngặt Nguyên tắc 3 (Không bao giờ ghi nhận hoặc trả về khóa thô không che giấu).
- **Phương án đã chọn**:
  1. **Lưu trữ an toàn qua Windows Credential Manager (`keyring`)**:
     - Lưu danh sách keys dưới dạng JSON được mã hóa trong credential slot `GEMINI_API_KEYS_JSON` thuộc service `TroLyAI`.
     - Đồng thời duy trì khóa đang active trong slot `GEMINI_API_KEY` để tương thích ngược 100% với các hàm sẵn có.
     - Tự động di chuyển (migrate) khóa đơn lẻ cũ vào danh sách khi khởi chạy lần đầu.
  2. **Bảo mật và che giấu hiển thị (Masking)**:
     - Thêm hàm `mask_api_key()`: hiển thị định dạng an toàn `AIzaSy12...cdef`. Tuyệt đối không trả về full key qua API `GET`.
     - Đăng ký mọi khóa vào `SecretFilter` để ngăn chặn rò rỉ ra log/console.
  3. **Kiểm tra kết nối trực tiếp (Live Test)**:
     - Viết hàm `test_gemini_api_key_connectivity()` sử dụng `google-genai` gọi `client.models.get(model="gemini-2.0-flash")`: kiểm tra tính hợp lệ và quyền truy cập API mà không tiêu tốn token chat.
     - Cung cấp endpoint `POST /api/settings/gemini-keys/test` hỗ trợ kiểm tra cả khóa thô trước khi lưu và khóa đã lưu theo `key_id`.
  4. **Giao diện Quản lý Khóa Hiện Đại**:
     - Thêm form nhập tên/nhãn gợi nhớ + ô nhập key có nút toggle ẩn/hiện và nút kiểm tra thử.
     - Hiển thị danh sách khóa với badge "Đang sử dụng" / "Dự phòng", nút "⚡ Sử Dụng", "🔍 Kiểm Tra" (kèm phản hồi thành công/lỗi ngay tại dòng) và "🗑️ Xóa".
- **Lý do**:
  - Đảm bảo tuân thủ triệt để Nguyên tắc 2, 3, 7, 8, 9, 10 và 11. Giúp người dùng chủ động kiểm soát tài nguyên đám mây và xử lý dứt điểm các sự cố liên quan đến API key.
- **Thư viện mới**: Không có (tuân thủ Nguyên tắc 11).

### [2026-10-27] Thiết kế Giao diện Quản lý Khóa API Động: Mỗi Khóa 1 Ô Nhập, Nút Kiểm Tra Kế Bên, Đầy Đủ Thêm/Sửa/Xóa
- **Bối cảnh**:
  - Người dùng muốn giao diện Quản lý Gemini API Keys đẹp, hiện đại, mỗi khóa là một thẻ riêng biệt với ô text box và nút "Kiểm tra" nằm ngay cạnh phải của ô.
  - Khi bấm "Thêm khóa mới", một ô text box mới xuất hiện trực tiếp trong danh sách để dán key, bấm kiểm tra ngay lập tức, và lưu lại.
  - Hỗ trợ đầy đủ các thao tác Thêm, Sửa (tên/khóa), Xóa và Kích hoạt khóa đang sử dụng.
- **Phương án đã chọn**:
  1. **Thiết kế Ô Text Box Nhập Liệu Động (Dynamic Rows Architecture)**:
     - Thẻ `.gemini-keys-card` chứa danh sách `#key-rows-container`.
     - Mỗi khóa được render thành một `.key-row-card`:
       - Header: Tên gợi nhớ (editable input `.input-key-name`) và huy hiệu trạng thái (`● Đang sử dụng`, `Dự phòng`, `🆕 Mới (Chưa lưu)`).
       - Main Input Group: Ô text box (`.input-key-secret`) có nút ẩn/hiện mật khẩu 👁️/🔒, và **nằm ngay sát bên phải là nút "🔍 Kiểm Tra"** (`.btn-test-key`).
       - Bottom Actions: Nút "💾 Lưu" (hoặc "Lưu Thay Đổi"), "⚡ Sử Dụng" (chọn làm khóa chính), "🗑️ Xóa", hoặc "❌ Hủy Bỏ" (cho ô mới).
       - Hộp thông báo phản hồi tại chỗ (`.key-test-feedback-box`): hiển thị kết quả kiểm tra xanh/đỏ mượt mà ngay dưới ô.
  2. **Thêm Khóa Nhanh**:
     - Bấm "➕ Thêm Khóa Mới" ở tiêu đề hoặc thanh chân thẻ sẽ tự động sinh thêm 1 ô nhập mới với viền nét đứt (dashed blue), cuộn tới và focus vào ô để người dùng dán key ngay.
     - Có thể bấm nút "🔍 Kiểm Tra" kế bên để kiểm tra tính hợp lệ trước khi bấm "Lưu".
  3. **Sửa & Xóa**:
     - Người dùng có thể sửa trực tiếp tên gợi nhớ hoặc dán khóa mới đè lên ô text box rồi bấm "💾 Lưu Thay Đổi" (gọi `PUT /api/settings/gemini-keys/{id}`).
     - Bấm "🗑️ Xóa" có hộp thoại xác nhận trước khi xóa vĩnh viễn khỏi Windows Credential Locker.
  4. **Thẩm Mỹ Cao Cấp ("Làm Cho Đẹp")**:
     - Bảng màu dark/light hài hòa, hiệu ứng đổ bóng subtle shadow, hiệu ứng hover nhấc nhẹ (transform translateY), nút kiểm tra xanh dương gradient nổi bật, nút lưu xanh ngọc lục bảo (emerald), nút xóa viền đỏ tinh tế.
     - Thêm tham số cache-busting `?v=20261027_3` vào cả link CSS và thẻ script để trình duyệt Edge/Chrome lập tức nạp giao diện mới mà không bị dính cache cũ.
### [2026-10-27] Khắc phục lỗi Khóa API biến mất khi bấm Lưu: Cơ chế Lưu trữ kép Dual Persistence & Schema Update linh hoạt
- **Bối cảnh**:
  - Người dùng phản ánh: "khi tôi bấm lưu thì nó lại mất không hiện danh sách khóa đã lưu là sao".
  - Nguyên nhân kỹ thuật:
    1. Khi gọi `keyring.set_password(KEYRING_SERVICE, KEYRING_KEYS_STORE, raw_json)` trên Windows Credential Manager, chuỗi JSON danh sách khóa có thể gặp giới hạn bộ nhớ đệm (buffer size) hoặc lỗi bảo mật của PasswordVault, dẫn đến việc nuốt ngoại lệ âm thầm (`except Exception: pass`). Do đó khi API GET được gọi lại, danh sách trả về rỗng và giao diện xóa sạch các ô thẻ đang hiển thị.
    2. Endpoint `PUT /api/settings/gemini-keys/{id}` trước đó dùng `GeminiKeyCreateRequest` (bắt buộc phải có `api_key`). Khi người dùng chỉ sửa tên khóa hoặc bấm lưu cập nhật mà không nhập lại key thô, FastAPI từ chối với mã lỗi 422 Unprocessable Entity.
- **Phương án đã chọn**:
  1. **Cơ chế lưu trữ kép (Dual Persistence)**:
     - Khóa vừa được lưu vào Windows Credential Locker (keyring) vừa được lưu đồng thời vào file dữ liệu bảo mật cục bộ `%APPDATA%\AIAssistant\gemini_keys.json` (thư mục riêng tư chỉ tài khoản Windows của người dùng mới có quyền truy cập).
     - Khi đọc, nếu keyring trả về rỗng hoặc gặp lỗi, hệ thống tự động đọc từ file dự phòng và đồng bộ ngược lại vào keyring. Đảm bảo khóa đã lưu KHÔNG BAO GIỜ bị mất hoặc biến mất.
  2. **Schema `GeminiKeyUpdateRequest`**:
     - Cho phép `api_key: str | None = None` và `name: str | None = None`. Khi người dùng sửa tên hoặc sửa khóa, backend nhận diện chính xác và cập nhật linh hoạt, không còn bị lỗi 422.
  3. **Tải dữ liệu phòng thủ trên giao diện**:
     - Cập nhật `app.js` tự động tải danh sách khóa khi người dùng chuyển sang tab Cài đặt và ngay khi ứng dụng khởi chạy ban đầu.
     - Tăng tham số cache busting lên `?v=20261027_5` để trình duyệt nạp ngay CSS/JS mới nhất.
- **Lý do**:
  - Tuân thủ triệt để Nguyên tắc 2 (An toàn bảo mật), Nguyên tắc 7 (Chất lượng mã nguồn & kiểm thử) và Nguyên tắc 10 (Xử lý dứt điểm điểm mơ hồ bằng phương án an toàn nhất).

### [2026-10-27] Khắc phục cảnh báo WebSocket lặp vô hạn và Giữ Session Token bền vững (Persistent Session Token)
- **Bối cảnh**:
  - Khi khởi động lại máy chủ backend, token cũ bị thay mới dẫn đến các tab trình duyệt Edge đang mở trước đó bị từ chối kết nối (`Từ chối kết nối WebSocket do Session Token không hợp lệ`).
  - Giao diện `app.js` khi nhận phản hồi đóng WebSocket từ chối (trước đó dùng mã `4003`) không nhận diện được lỗi xác thực nên rơi vào vòng lặp `setTimeout(connectWebSocket, 2000)` gọi kết nối lại liên tục mỗi 2 giây, làm ngập log máy chủ.
- **Phương án đã chọn**:
  1. **Lưu trữ Session Token bền vững**:
     - Nạp và ghi nhớ token trong file bảo mật `%APPDATA%\AIAssistant\session.token`. Khi backend khởi động lại, token của người dùng được giữ nguyên vẹn, các tab trình duyệt đang mở không bao giờ bị văng kết nối đột ngột.
  2. **Chuẩn hoá mã đóng WebSocket**:
     - Trả về mã đóng chuẩn `1008` (Policy Violation / Unauthorized) theo RFC 6455 khi token không hợp lệ.
  3. **Ngắt vòng lặp kết nối lại (Circuit Breaker)**:
     - Trong `app.js`, khi phát hiện đóng kết nối với mã 1008 hoặc 4003, hiển thị thông báo rõ ràng yêu cầu người dùng F5 và **dừng ngay lập tức** việc tự động kết nối lại.
     - Ưu tiên token truyền từ thanh địa chỉ URL `?token=...` rồi cập nhật vào `localStorage` để tab luôn sử dụng đúng token mới nhất.
- **Lý do**:
  - Tuân thủ Nguyên tắc 2 (Bảo mật), Nguyên tắc 9 (Bắt lỗi và báo lại rõ ràng bằng tiếng Việt) và Nguyên tắc 10 (Trải nghiệm mượt mà, không gây thắt cổ chai tài nguyên hệ thống).

### [2026-10-27] Khắc phục lỗi Chat với Khóa Google AI Studio: Tự Động Kích Hoạt Khóa & Chuẩn Hóa Schema Công Cụ
- **Bối cảnh**:
  - Người dùng tạo khóa mới trên Google AI Studio, dán vào Cài đặt và bấm nút Kiểm tra báo kết nối thành công. Tuy nhiên khi sang khung Chat để trò chuyện thì liên tục báo lỗi không trả lời được.
  - Nguyên nhân kỹ thuật phát hiện:
    1. **Khóa mới thêm chưa được kích hoạt tự động (Active Key Mismatch)**: Hàm `add_gemini_api_key()` gán `is_active = len(keys) == 0`. Khi người dùng đã có khóa cũ (hoặc khóa không hợp lệ), khóa mới thêm bị gán `is_active = False` ("Dự phòng"). Khi vào Chat, hàm `get_gemini_api_key()` chỉ lấy khóa có `is_active=True` (chính là khóa cũ bị lỗi), dẫn đến việc người dùng chat bằng khóa cũ dù đã thêm khóa mới thành công.
    2. **Kiểm tra kết nối chưa sát thực tế (Test vs Chat Mismatch)**: Nút "Kiểm tra" trước đó chỉ gọi `client.models.get(model=...)` (chỉ kiểm tra quyền đọc metadata mô hình) thay vì thử sinh văn bản qua `generate_content`.
    3. **Không tương thích OpenAPI Schema của Gemini Function Calling**: Hàm sinh schema `generate_parameters_schema` sinh trường `"default": null`, mảng rỗng `required: []` hoặc `properties: {}` cho các công cụ không có tham số (ví dụ `get_system_info`). Chuẩn OpenAPI 3.0 của Gemini Function Calling từ chối trường `default` và các object schema rỗng gây lỗi `400 Bad Request`.
    4. **Thiếu cơ chế fallback khi công cụ gặp lỗi**: Trong `GeminiProvider.stream_chat`, khi gọi `generate_content_stream` với danh sách 25+ công cụ bị lỗi schema hoặc hạn mức, hệ thống ngắt toàn bộ lượt chat thay vì tự động chuyển sang sinh văn bản thuần (text-only) cho người dùng.
- **Phương án đã chọn**:
  1. **Tự Động Kích Hoạt Khóa Mới & Khóa Vừa Cập Nhật**:
     - Trong `add_gemini_api_key`: Khi thêm khóa mới, tự động đặt `is_active = True` và chuyển các khóa khác thành `is_active = False`.
     - Trong `update_gemini_api_key`: Khi người dùng dán đè khóa mới vào ô đã có, tự động kích hoạt khóa đó thành khóa chính.
     - Trong `app.js`: Khi bấm "Lưu Khóa" hoặc "Lưu Thay Đổi", giao diện hiển thị rõ ràng và tự động kích hoạt khóa chính. Nút "Kiểm Tra" có hướng dẫn bấm Lưu để kích hoạt.
  2. **Kiểm Tra Thực Tế Khả Năng Sinh Văn Bản**:
     - `test_gemini_api_key_connectivity` gọi trực tiếp `client.models.generate_content(model="gemini-2.0-flash", contents="1")` (dự phòng `gemini-1.5-flash`), đảm bảo khóa được kiểm tra khả năng chat thực tế 100%.
  3. **Làm Sạch và Chuẩn Hóa Schema Công Cụ (`_clean_schema_for_gemini`)**:
     - Triệt tiêu hoàn toàn trường `"default"` khỏi các tham số trong `FunctionDeclaration` cho Gemini.
     - Tự động lược bỏ `"required"` nếu là mảng rỗng `[]`.
     - Nếu một công cụ không có tham số (`properties` rỗng, ví dụ `get_system_info`), đặt `parameters = None` theo đúng đặc tả của Google GenAI SDK.
  4. **Cơ Chế Phục Hồi Dự Phòng (Fallback to Text-Only)**:
     - Trong `stream_chat`: Nếu lượt gọi kèm công cụ thất bại ngay từ đầu (do schema hoặc hạn mức tool calling), tự động thử lại ngay lượt đó ở chế độ không kèm công cụ để người dùng vẫn trò chuyện được câu trả lời thông suốt.
     - Tiếp tục thử các ứng viên mô hình kế tiếp (`gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`) khi gặp sự cố tương thích mô hình.
- **Lý do**:
  - Tuân thủ triệt để Nguyên tắc 2 (An toàn bảo mật), Nguyên tắc 6 (Thư viện chuẩn xác), Nguyên tắc 7 (Mã sạch & kiểm thử) và Nguyên tắc 9 (Không nuốt lỗi im lặng, phản hồi bằng tiếng Việt dễ hiểu).
- **Thư viện mới**: Không có.
