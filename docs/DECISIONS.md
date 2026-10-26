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
- **Thư viện mới**:
  - `pystray>=0.19.5`: Điều khiển biểu tượng khay hệ thống trên Windows.
  - `Pillow>=10.2.0`: Tự sinh ảnh biểu tượng icon động trong bộ nhớ.






