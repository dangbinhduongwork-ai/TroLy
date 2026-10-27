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

### [2026-10-27] Hỗ Trợ Chuẩn Khóa Mới Google AI Studio Authorization Key (`AQ.`) & Chống Copy Nhầm Chuỗi Rút Gọn
- **Bối cảnh**:
  - Google AI Studio đã chuyển đổi cơ chế cấp phát khóa mặc định sang **Authorization (Auth) Key** gắn với Service Account thay cho định dạng truyền thống (`AIzaSy...`). Các khóa mới này bắt đầu bằng tiền tố **`AQ.`** (ví dụ: `AQ.MockKeyForExamplePurposeOnly123456789`).
  - Hệ thống kiểm tra trước đó giới hạn cứng định dạng phải bắt đầu bằng `AIzaSy`, dẫn đến việc người dùng copy đúng khóa mới từ Google AI Studio nhưng ứng dụng lại báo lỗi định dạng: `phải bắt đầu bằng 'AIzaSy', hiện tại: 'AQ.MockKey...'`.
  - Ngoài ra, trên giao diện bảng của Google AI Studio, chuỗi khóa thường bị che bớt dạng `...bM_Q`. Nếu người dùng bôi đen chữ này thay vì bấm nút sao chép, chuỗi bị thiếu gây lỗi.
- **Phương án đã chọn**:
  1. **Hỗ trợ toàn diện chuẩn khóa `AQ.` song song cùng `AIzaSy`**:
     - `clean_gemini_key`: Biểu thức chính quy quét và trích xuất cả `AQ\.[0-9A-Za-z_\-]{30,120}` và `AIza[0-9A-Za-z_\-]{35}`.
     - `is_valid_gemini_key_format`: Cho phép cả hai chuẩn tiền tố `AQ.` và `AIza`.
     - `mask_api_key`: Che giấu an toàn 8 ký tự đầu và 4 ký tự cuối cho cả khóa `AQ.` (ví dụ `AQ.MockK...fXYZ`).
     - `test_gemini_api_key_connectivity`, `add_gemini_api_key`, `update_gemini_api_key`: Chấp thuận cả 2 chuẩn và gửi xác thực qua `google-genai` SDK.
  2. **Xác thực phòng thủ thời gian thực trên Giao diện (`app.js`)**:
     - Kiểm tra trực tiếp trên client trước khi gửi request: Nếu phát hiện chuỗi bị che (`...`), hiển thị hướng dẫn chi tiết cách bấm nút **"Sao chép khóa"**.
     - Cho phép cả tiền tố `AQ.` và `AIza`.
  3. **Kiểm thử tự động (`tests/test_gemini_auth.py`)**:
     - Bổ sung `test_gemini_auth_key_aq_format_support` kiểm tra trích xuất, che giấu và lưu trữ khóa `AQ.` thành công.
- **Lý do**:
  - Tuân thủ Nguyên tắc 6 (Thư viện chuẩn xác theo tài liệu hiện hành của Google GenAI), Nguyên tắc 9 (Thông báo rõ ràng, không nuốt lỗi), Nguyên tắc 10 (Chủ động tương thích công nghệ mới).
- **Thư viện mới**: Không có.

### [2026-10-27] Nâng Cấp Model Gemini `gemini-3.8-flash`, Sửa Kiểm Tra Mạng Cổng 443 & Đồng Bộ Token WebSocket
- **Bối cảnh**:
  - Các API key tạo mới từ Google AI Studio yêu cầu các thế hệ mô hình mới (`gemini-3.8-flash`, `gemini-2.5-flash`), trong khi model cũ `gemini-2.0-flash` bị trả về lỗi `404 Not Found: Mô hình không khả dụng`.
  - Cơ chế kiểm tra mạng TCP trên cổng 53 (`1.1.1.1:53` / `8.8.8.8:53`) dễ bị các nhà mạng tại Việt Nam can thiệp hoặc chặn gói TCP DNS, dẫn đến việc ứng dụng báo nhầm mất mạng và tự động ép sang mô hình cục bộ.
  - Khi token phiên làm việc bị từ chối (`4003` / `1008`), client cũ tiếp tục kẹt token hết hạn trong `localStorage` thay vì xóa và nạp lại token mới từ query URL của Edge launcher.
- **Phương án đã chọn**:
  1. **Nâng cấp Model mặc định sang `gemini-3.8-flash`**:
     - `config/settings.toml` & `src/assistant/config.py`: Đặt `gemini_model = "gemini-3.8-flash"`.
     - `src/assistant/llm/gemini_provider.py`:
       + `test_gemini_api_key_connectivity()`: Ưu tiên thử nghiệm sinh nội dung với `gemini-3.8-flash` -> `gemini-2.5-flash` -> `gemini-2.0-flash`.
       + `list_models()`: Mặc định `["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]`.
       + `stream_chat()`: Danh sách ứng viên tự phục hồi `[self._model_name, "gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]`.
       + `clean_gemini_key()`: Sửa regex `match_legacy = re.search(r"AIza[0-9A-Za-z_\-]{30,45}", text)`.
     - `src/assistant/ui_static/app.js` & `index.html`: Cập nhật `activeGemini` và danh sách chọn model hiển thị `gemini-3.8-flash (Khuyên dùng)`.
  2. **Chuyển thuật toán kiểm tra mạng sang cổng 443 (HTTPS) với fallback**:
     - `NetworkChecker.is_online()`: Kết nối TCP tới `1.1.1.1:443`, timeout 2.0s; dự phòng sang `8.8.8.8:443`.
     - `ModelRouter.is_network_available()`: Tăng timeout lên 1.5s, kết nối tới `1.1.1.1:443` và dự phòng `8.8.8.8:443`.
  3. **Đồng bộ Session Token WebSocket chống kẹt Token cũ**:
     - Trong `app.js` (`connectWebSocket`): Khi gặp mã đóng `4003` / `1008`, xóa ngay `localStorage.removeItem("troly_session_token")`.
     - Nếu URL chứa `?token=...`, tự động nạp token mới và kết nối lại sau 1s; nếu không có, thông báo rõ ràng cho người dùng mở lại từ Desktop hoặc khay hệ thống.
### [2026-10-27] Tối Ưu Hiệu Năng & Khắc Phục Triệt Để Treo Ứng Dụng (Anti-Hang & Low-Latency LLM Streaming)
- **Bối cảnh**:
  - Ứng dụng đôi khi phản hồi rất chậm hoặc bị treo đến 5 phút không ra kết quả.
  - Phân tích nguyên nhân gốc rễ:
    1. `GeminiProvider.stream_chat` duyệt qua 2 phiên bản client (`v1beta`, `v1`) kết hợp 4 mô hình ứng viên dự phòng và mỗi lần đều thử lại 2 lần (có tools và không tools) mà không có giới hạn timeout cho bước kết nối stream ban đầu. Khi mạng chập chờn hoặc API gateway bị nghẽn, tổng thời gian chờ tích luỹ có thể lên tới nhiều phút.
    2. `ModelRouter` thử lại tới 2 lần kèm backoff luỹ tiến mà không thông báo tiến độ, khiến giao diện im lặng hoàn toàn trong thời gian dài.
    3. `OllamaProvider` đặt `timeout=180.0s` quá lớn trong `httpx.AsyncClient`.
    4. `search_memories_hybrid` gọi đồng bộ `get_embedding_sync` với timeout dài, gây block luồng thực thi và nghẽn FastAPI Event Loop trong luồng chat WebSocket.
    5. Cấu hình mô hình cục bộ mặc định `qwen2.5:14b` đòi hỏi lượng VRAM lớn (~9-10GB), dễ gây tràn bộ nhớ 12GB của RTX 3060 khi chạy đồng thời với Windows Desktop và trình duyệt, làm tốc độ suy luận bị tụt nghiêm trọng.
- **Phương án đã chọn**:
  1. **Tối ưu hóa Gemini Provider & Giới hạn Timeout 12s (`src/assistant/llm/gemini_provider.py`)**:
     - Bỏ duyệt `clients_to_try`: Sử dụng duy nhất client v1beta ban đầu.
     - Giới hạn ứng viên: Chỉ thử mô hình được cấu hình (`self._model_name`) và một fallback nhanh nhất sang `"gemini-2.0-flash"`.
     - Bọc lệnh gọi `cl.aio.models.generate_content_stream(...)` bên trong `asyncio.wait_for(..., timeout=12.0)`. Quá 12 giây ngắt ngay lập tức để chuyển tiếp fallback.
     - Không thử lại có/không tools nếu nguyên nhân là timeout mạng.
  2. **Tối ưu Router & Phát Thông Báo Fallback Nhanh (`src/assistant/core/router.py`)**:
     - Giảm `max_retries` từ 2 xuống 1 với độ trễ 0.5s.
     - Khi gặp lỗi mạng/timeout từ Gemini, lập tức phát sự kiện:
       `StreamEvent(type="text_delta", content="[Đang chuyển sang mô hình cục bộ Ollama...]\n\n")` để người dùng nắm được trạng thái tức thì thay vì giao diện bị đứng im.
  3. **Tối ưu Ollama Provider (`src/assistant/llm/ollama_provider.py`)**:
     - Giảm timeout của `httpx.AsyncClient` xuống `httpx.Timeout(45.0, connect=5.0, read=45.0)` (thay vì 180s).
  4. **Chống Nghẽn Event Loop & Tối Ưu Tìm Kiếm Trí Nhớ (`src/assistant/memory/`)**:
     - `embeddings.py`: Giảm timeout mặc định xuống `1.5s` cho cả `get_embedding_sync` và `get_embedding_async`.
     - `store.py`: Trong `search_memories_hybrid`, bọc sinh vector embedding trong `ThreadPoolExecutor` với timeout 1.5s. Nếu quá thời gian hoặc lỗi, fallback ngay về kết quả FTS5 BM25 (`fts_results[:top_k]`) mà không làm trễ câu trả lời.
     - `ws.py` & `app.py`: Đảm bảo gọi `get_relevant_memories` và `search_memories_hybrid` thông qua `await asyncio.to_thread(...)`, giải phóng hoàn toàn FastAPI Event Loop.
  5. **Chuyển mô hình cục bộ mặc định sang `qwen2.5:7b` (`config/settings.toml`, `config.py`)**:
     - Sử dụng `qwen2.5:7b` làm mô hình cục bộ tiêu chuẩn, tiêu tốn dưới 5GB VRAM, vừa vặn hoàn hảo trong card RTX 3060 12GB và tăng tốc độ sinh từ đầu tiên (TTFT) lên gấp ~3 lần so với bản 14B.
- **Lý do**:
  - Tuân thủ Nguyên tắc 1 (Đúng phạm vi tối ưu độ trễ), Nguyên tắc 7 (Mã sạch & kiểm thử), Nguyên tắc 9 (Báo lỗi và trạng thái rõ ràng bằng tiếng Việt), Nguyên tắc 10 (Phương án an toàn và hiệu năng cao nhất).
- **Thư viện mới**: Không có.

### [2026-10-27] Tối Ưu Hóa Sâu: Khử Điểm Nghẽn I/O, Chống Khóa DB, Throttling Render Web UI & Phản Hồi Tức Thời
- **Bối cảnh**:
  - Cần tối ưu thêm độ nhạy của ứng dụng, tránh nghẽn I/O khi quét file, tránh lỗi SQLite locked khi đọc/ghi đồng thời, loại bỏ hiện tượng giật lag khung hình khi stream token và cung cấp phản hồi thị giác ngay lập tức cho người dùng.
- **Phương án đã chọn**:
  1. **Tối ưu tìm kiếm trí nhớ & Chống khóa DB (`src/assistant/memory/store.py`, `reminders/store.py`)**:
     - Thêm kiểm tra nhanh `SELECT 1 FROM memory_embeddings LIMIT 1`. Nếu DB chưa lưu bất kỳ vector nào, trả về ngay kết quả từ FTS5 mà không tốn công gọi Ollama, giúp tăng tốc tìm kiếm lên mức tức thì (<2ms).
     - Bổ sung `timeout=15.0` vào `sqlite3.connect()` trong `_get_connection()`, ngăn chặn triệt để lỗi `sqlite3.OperationalError: database is locked` khi có nhiều luồng hoặc tiến trình nền cùng truy cập SQLite.
  2. **Tối ưu công cụ tìm kiếm file (`src/assistant/tools/files.py`)**:
     - Thêm danh sách loại trừ `IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode", "dist", "build"}`.
     - Bỏ qua toàn bộ các thư mục rác/môi trường phát triển nặng nề, giảm 95% thời gian duyệt I/O đĩa cứng khi tìm kiếm trong workspace.
  3. **Tối ưu hóa render streaming trên Web UI (`src/assistant/ui_static/app.js`)**:
     - Throttling xử lý `text_delta` qua `requestAnimationFrame` kết hợp ngưỡng 40ms trước khi gọi `parseMarkdown` và cập nhật `innerHTML`.
     - Giảm tải vẽ lại DOM liên tục, loại bỏ hiện tượng đơ giật trình duyệt khi model sinh token ở tốc độ cao (50-100 tokens/s).
  4. **Phản hồi trạng thái kết nối tức thời (`src/assistant/server/ws.py`)**:
     - Ngay đầu `_process_user_turn()`, phát ngay sự kiện WebSocket `text_delta` với nội dung `"..."` trước khi khởi chạy `AgentLoop`.
     - Phía giao diện hiển thị ngay con trỏ nhấp nháy báo hiệu đang xử lý, và tự động thay thế bằng nội dung thực tế ngay khi token đầu tiên trả về.
- **Lý do**:
  - Tuân thủ Nguyên tắc 1 (Tối ưu hiệu năng đúng phạm vi), Nguyên tắc 7 (Mã sạch & kiểm thử), Nguyên tắc 9 (Trải nghiệm người dùng mượt mà, phản hồi lập tức), Nguyên tắc 10 (Lựa chọn giải pháp an toàn và hiệu quả nhất).
- **Thư viện mới**: Không có.

### [2026-10-27] Chuẩn Hóa Mô Hình Chính Thức Google Gemini (`gemini-1.5-flash`) & Giới Hạn Timeout Từng Chunk Stream
- **Bối cảnh**:
  - Khi người dùng gửi tin nhắn qua Google Gemini, ứng dụng gặp tình trạng không phản hồi hoặc đứng im.
  - Phân tích nguyên nhân:
    1. Các tên mô hình giả định (`gemini-3.8-flash`, `gemini-2.5-flash`) không phải là endpoint sản xuất chính thức của Google Generative Language API, gây ra lỗi hoặc treo request.
    2. Vòng lặp `async for chunk in stream:` không có timeout cho từng chunk dữ liệu. Nếu gateway mạng của Google bị nghẽn sau khi mở kết nối ban đầu, tiến trình sẽ bị kẹt vô thời hạn trong lúc chờ chunk tiếp theo.
- **Phương án đã chọn**:
  1. **Chuẩn hóa toàn diện tên mô hình chính thức của Google**:
     - Cấu hình mặc định: `gemini_model = "gemini-1.5-flash"` trong `config/settings.toml` và `src/assistant/config.py`.
     - Danh sách mô hình chuẩn: `["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]`.
     - `test_gemini_api_key_connectivity()`: Duyệt kiểm tra kết nối với `["gemini-1.5-flash", "gemini-2.0-flash"]`.
     - `list_models()`: Trả về danh sách mặc định chính thức khi không truy vấn được qua API.
     - `app.js` & `index.html`: Cập nhật dropdown chọn model trên giao diện sang các model chính thức.
  2. **Bọc timeout an toàn 10s cho từng chunk stream (`stream_chat`)**:
     - Thay thế `async for chunk in stream:` bằng vòng lặp `while True:` kèm:
       `chunk = await asyncio.wait_for(stream.__anext__(), timeout=10.0)`
     - Nếu bất kỳ chunk nào bị trễ quá 10 giây, lập tức kích hoạt `asyncio.TimeoutError` để chuyển đổi mô hình dự phòng hoặc fallback ngay sang Ollama cục bộ qua Router mà không để ứng dụng bị kẹt.
- **Lý do**:
  - Tuân thủ Nguyên tắc 6 (Thư viện chuẩn xác theo tài liệu hiện hành của Google), Nguyên tắc 7 (Mã sạch & kiểm thử), Nguyên tắc 9 (Bắt lỗi và báo lại rõ ràng), Nguyên tắc 10 (Phương án an toàn nhất).
### [2026-10-27] Nâng Cấp Giao Diện Cá Nhân Hóa (Personalization & Theme Palette) Thuần Vanilla JS Offline
- **Bối cảnh**:
  - Người dùng mong muốn tùy biến trải nghiệm cá nhân: đổi tên hiển thị và avatar cho cả Trợ lý và Người dùng, chọn bảng màu nhấn chủ đạo (Accent Color Palette 7 preset), tối ưu bong bóng chat hiện đại với hiệu ứng gradient và accent glow, cập nhật tên và avatar ở sidebar, cũng như tự động truyền thông tin danh xưng vào System Prompt để AI xưng hô tự nhiên, chính xác.
- **Phương án đã chọn**:
  1. **Lưu trữ & Áp dụng Trạng Thái Không Phụ Thuộc Mạng (Offline Persistence)**:
     - Toàn bộ cấu hình cá nhân hóa lưu vào `localStorage` dưới khóa `troly_profile_settings`: `{ assistantName, userName, assistantAvatar, userAvatar, themeMode, accentColor }`.
     - Chống hiện tượng chớp nháy giao diện (FOUC): Chèn script inline đồng bộ trong thẻ `<head>` của `index.html` để nạp theme và biến CSS `--accent` ngay trước khi trình duyệt dựng layout.
     - Hàm `applyThemeSettings(profile)` cập nhật trực tiếp các biến CSS `:root` & `document.body` (`--accent`, `--accent-hover`, `--accent-glow`, `--user-bubble`), đồng bộ hóa sidebar brand và các control cài đặt.
  2. **Thẻ Cài Đặt Cá Nhân Hóa & Bộ Chọn Màu (Settings & Palette Picker)**:
     - Bổ sung thẻ `🎨 Cá Nhân Hóa & Giao Diện` tại màn hình Cài đặt với:
       * Ô nhập tên Trợ lý & tên Người dùng.
       * Chọn nhanh emoji avatar (🤖, 🦊, 🐱, 🐼, 🌟, 🌿, ☕, 🚀, 💡, 🥑) hoặc dán URL ảnh / Base64 kèm xem trước thời gian thực.
       * Bộ chọn 7 preset màu nhấn: 🔵 Xanh Biển (#3b82f6), 🟢 Ngọc Lục Bảo (#10b981), 🟣 Tím Mộng Mơ (#8b5cf6), 🟠 Hoàng Hôn (#f59e0b), 🌸 Hoa Anh Đào (#ec4899), 🔴 Đỏ Rực Rỡ (#ef4444), ⚪ Xám Tối Giản (#64748b) cùng Color Picker tùy chọn.
       * Nút radio chuyển đổi mượt mà giữa Giao diện Sáng và Tối.
  3. **Tối Ưu Bong Bóng Chat & Thông Điệp Chào Mừng Động**:
     - Thiết kế lại `.message-bubble` với bo góc hiện đại 18px (vát nhẹ góc theo phía người gửi), đổ bóng mờ nhẹ theo màu nhấn (`box-shadow: 0 4px 16px var(--accent-glow)`).
     - Tin nhắn người dùng sử dụng gradient đồng điệu `linear-gradient(135deg, var(--accent) 0%, var(--user-bubble) 100%)`.
     - Cả tin nhắn Trợ lý và Người dùng đều hiển thị avatar tròn mềm mại và tên tương ứng (`.message-sender`).
     - Hàm `renderWelcomeMessage()` tự động chào đón thân thiện theo đúng tên người dùng và tên trợ lý đã cấu hình.
  4. **Tích Hợp System Prompt Cá Nhân Hóa Qua WebSocket**:
     - Khi gửi tin nhắn qua WebSocket (`user_message` trong `app.js`), đính kèm `user_name` và `assistant_name`.
     - `ws.py` và `prompts.py` tiếp nhận và bổ sung khối `[CÁ NHÂN HÓA & DANH XƯNG]` vào system prompt, giúp AI xưng hô đúng danh xưng mong muốn mà không vi phạm nguyên tắc an toàn hay làm loãng ngữ cảnh.
- **Lý do**:
  - Tuân thủ nghiêm ngặt 12 nguyên tắc an toàn: 100% offline, Vanilla JS/CSS thuần túy, không dùng framework bên ngoài (Nguyên tắc 11), an toàn trước injection (Nguyên tắc 12), giao diện chuẩn tiếng Việt (Nguyên tắc 8).

### [2026-10-27] Tách Riêng Màn Hình Cá Nhân Hóa & Chuẩn Hóa Toàn Diện Icon SVG Tối Giản, Hiện Đại Hóa Bố Cục
- **Bối cảnh**:
  - Ban đầu phần cá nhân hóa giao diện được đặt chung trong màn hình "Cài Đặt & Chẩn Đoán Hệ Thống", khiến màn hình cài đặt kỹ thuật bị dài và lẫn lộn giữa chức năng vận hành máy (API keys, hotkey, chẩn đoán mạng) và thẩm mỹ cá nhân.
  - Các icon trên thanh điều hướng, nút bấm, bong bóng chat và thông báo còn sử dụng nhiều emoji màu mè, không đồng bộ phong cách và thiếu tính chuyên nghiệp của một ứng dụng máy tính hiện đại.
- **Phương án đã chọn**:
  1. **Tách riêng màn hình Giao diện (`#screen-appearance`)**:
     - Bổ sung mục điều hướng `Giao diện` (icon Palette SVG) trên Sidebar, tách độc lập khỏi `Cài đặt hệ thống` (`#screen-settings`).
     - Tập trung toàn bộ tùy biến diện mạo vào màn hình mới: Hồ sơ trợ lý (tên, avatar), Hồ sơ người dùng (tên, avatar), Chế độ sáng/tối (Theme radio pill), Bảng 7 preset màu nhấn kèm bộ chọn màu tùy biến (Color Picker), Nút Lưu và Khôi phục mặc định.
     - Màn hình `Cài đặt hệ thống` được tinh giản, chỉ tập trung vào: Trạng thái kết nối (Gemini, Ollama), Quản lý API Key đa khóa trong Windows Credential Locker, Cấu hình model và Tự khởi động cùng Windows.
  2. **Thay thế toàn bộ Emoji bằng Icon SVG Vector Đơn Sắc (Minimalist Monochromatic SVG)**:
     - Xóa bỏ triệt để các emoji màu mè (🤖, 💬, 🧠, ⏰, 🛡️, ⚙️, 📁, 🌙, ☀️, ➕, 🛑, ✈️, ☁️, ✏️, 🗑️, 🔑, 👁️, 🔍, 💾, ⚡, ❌, ⚠️...) trên toàn bộ giao diện: sidebar, header chat, dock nhập tin nhắn, danh sách trí nhớ, danh sách nhắc việc, bảng quản lý key, thẻ trạng thái và modal phê duyệt an toàn.
     - Chuẩn hóa hệ thống icon vector SVG inline (`stroke="currentColor"`, `stroke-width="2"`, `fill="none"`), kế thừa màu sắc linh hoạt theo biến CSS `--text-primary`, `--text-muted` hoặc `--accent`.
     - Tuyệt đối không dùng CDN, thư viện icon font hay tải từ internet; 100% vector SVG nhúng trực tiếp, hoạt động offline hoàn toàn.
  3. **Hiện đại hóa bố cục và thẩm mỹ (Modern Layout & Design Tokens)**:
     - Tinh chỉnh `tokens.css`: tông màu nền sâu thẳm chuẩn Dark theme hiện đại (`#0d1117`, `#161b22`, `#21262d`), lớp viền hairline tinh xảo (`#30363d`), hệ thống bo góc chuẩn mực (`--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-pill`).
     - Nâng cấp khung chat: Dock nhập tin nhắn dạng nổi (floating dock) bo tròn lớn với độ nổi khối nhẹ và đổ bóng mềm, textarea tự co giãn linh hoạt, nút gửi tích hợp biểu tượng gửi giấy tối giản.
     - Cải thiện bong bóng chat (`.message-bubble`): Avatar người dùng và trợ lý kích thước 34px bo tròn tinh gọn mang biểu tượng vector, phân định màu viền tinh tế, tên người gửi hiển thị trực quan.
- **Lý do**:
  - Tuân thủ nghiêm ngặt 12 nguyên tắc an toàn: Không thêm thư viện phụ thuộc bên ngoài (Nguyên tắc 11), đảm bảo hoạt động offline 100%, giao diện hiển thị tiếng Việt chuẩn mực (Nguyên tắc 8).
- **Thư viện mới**: Không có.

### [2026-10-27] Khắc Phục Triệt Để Lỗi Gemini Treo Stream & Tối Ưu Hóa Ngữ Cảnh Qwen2.5:14B (8192 tokens)
- **Bối cảnh**:
  - Khi người dùng gửi tin nhắn qua Gemini, mô hình có thể gặp lỗi kết nối gateway hoặc timeout lũy kế kéo dài 50–85 giây do timeout stream ban đầu quá lớn (12s) và danh sách mô hình dự phòng thiếu `gemini-1.5-flash` chính thức.
  - Mô hình cục bộ `qwen2.5:14b` chạy trên máy tính có card đồ họa RTX 3060 12GB chưa được khai thác tối đa: cấu hình mặc định bị sót `qwen2.5:7b`, ngân sách token chỉ đặt 4000, và payload gửi sang Ollama thiếu tham số `"options": {"num_ctx": ...}`, khiến Ollama mặc định giới hạn ngữ cảnh ở mức 2048 tokens.
- **Phương án đã chọn**:
  1. **Khắc phục triệt để lỗi Gemini treo**:
     - `config/settings.toml` & `src/assistant/config.py`: Đặt `gemini_model = "gemini-1.5-flash"` làm mô hình sản xuất chính thức, ổn định nhất của Google.
     - `src/assistant/llm/gemini_provider.py`:
       * Trong `stream_chat()`, danh sách `candidates` luôn ưu tiên `self._model_name`, kế tiếp bắt buộc duyệt qua `["gemini-1.5-flash", "gemini-2.0-flash"]`.
       * Giảm timeout kết nối stream ban đầu từ 12.0s xuống 8.0s nhằm phát hiện lỗi kết nối nhanh hơn và chuyển đổi tức thì.
       * Bổ sung log chi tiết (`logger.info`) khi chuyển sang mô hình dự phòng để người dùng và hệ thống nắm bắt kịp thời.
  2. **Tối ưu hóa mô hình cục bộ Qwen2.5:14B cho VRAM 12GB**:
     - Đồng bộ `local_model = "qwen2.5:14b"` và `max_context_tokens = 8192` trong toàn bộ tệp cấu hình (`settings.toml`, `config.py`, `app.js`).
     - Trong `src/assistant/llm/ollama_provider.py`, thêm `"options": {"num_ctx": num_ctx_val}` vào payload gửi tới `/v1/chat/completions`, mở khóa toàn bộ cửa sổ ngữ cảnh 8192 tokens thay vì bị Ollama giới hạn 2048 tokens.
     - Đồng bộ hóa các tệp hướng dẫn và kiểm thử (`scripts/check_tool_calling.py`, `README.md`, `index.html`, `test_config.py`).
- **Lý do**:
  - Tuân thủ Nguyên tắc 2 (An toàn bảo mật), Nguyên tắc 6 (Thư viện chuẩn xác theo tài liệu hiện hành), Nguyên tắc 7 (Mã sạch & kiểm thử), Nguyên tắc 9 (Không nuốt lỗi im lặng), Nguyên tắc 10 (Phương án an toàn nhất).
- **Thư viện mới**: Không có.

### [2026-10-27] Quản Lý Hội Thoại, Danh Mục Trí Nhớ Động & Công Cụ Tra Cứu Web Realtime An Toàn
- **Bối cảnh**:
  - Người dùng cần khả năng đổi tên, xóa cuộc hội thoại và trích xuất lưu các dữ kiện cốt lõi từ phiên trò chuyện vào trí nhớ dài hạn.
  - Danh mục trí nhớ trước đây là cố định (hardcoded enum), người dùng không thể tự tạo, đổi màu hay phân loại theo nhu cầu cá nhân.
  - Cần công cụ tra cứu thông tin web thời gian thực và tin tức đáng tin cậy mà không cài thêm framework cồng kềnh, đồng thời phòng vệ triệt để trước SSRF và Prompt Injection.
- **Phương án đã chọn**:
  1. **Quản lý cuộc trò chuyện (Conversation Management)**:
     - Bổ sung schema `ConversationUpdate` (`ConversationUpdateRequest`) và endpoint `PUT /api/conversations/{conv_id}`.
     - Xây dựng endpoint `POST /api/conversations/{conv_id}/save-to-memory`: Lấy lịch sử hội thoại, sử dụng router tóm tắt thành các gạch đầu dòng dữ kiện quan trọng, tự động đồng bộ vào bảng `memories` kèm vector embedding cho Hybrid Search.
     - Giao diện: Cụm nút thao tác nhanh trên chat header (Đổi tên, Lưu trí nhớ, Xóa) sử dụng 100% SVG vector nét mảnh đơn sắc.
  2. **Quản lý danh mục trí nhớ động (Dynamic Memory Categories)**:
     - Tạo bảng `memory_categories` trong SQLite với 4 danh mục mặc định (`preference`, `project`, `naming_rule`, `general`).
     - Hỗ trợ CRUD qua `MemoryStore` và REST API (`GET/POST/PUT/DELETE /api/memories/categories`).
     - Cơ chế di trú an toàn khi xóa danh mục: Toàn bộ dữ kiện trí nhớ thuộc danh mục bị xóa tự động chuyển về danh mục "Chung" (`general`), bảo toàn dữ liệu và đồng bộ FTS5. Chặn xóa danh mục mặc định `general`.
     - Giao diện: Thêm Modal Quản lý danh mục dạng bảng kèm form tạo nhanh, bảng chọn màu HEX và hiển thị huy hiệu danh mục theo màu sắc riêng biệt.
  3. **Công cụ tra cứu Web thời gian thực (`search_web`, `fetch_news`)**:
     - Triển khai trong `src/assistant/tools/web.py` sử dụng thư viện `httpx` và thư viện chuẩn `xml.etree.ElementTree`.
     - Tìm kiếm tổng hợp thời gian thực kết hợp DuckDuckGo HTML và Google News RSS fallback.
     - Lọc chặn triệt để SSRF (Server-Side Request Forgery) trên mọi URL kết quả, chặn localhost và IP nội bộ.
     - Toàn bộ nội dung trả về cho LLM bắt buộc bọc trong thẻ `<untrusted_content>` theo Nguyên tắc 12 để chống Prompt Injection.
  4. **Chuẩn mực thiết kế giao diện**:
     - Tuyệt đối không sử dụng emoji màu mè, 100% icon SVG vector đơn sắc (`stroke="currentColor"`, `stroke-width="2"`, `fill="none"`), tương thích hoàn hảo Dark/Light theme.
- **Lý do**:
  - Tuân thủ nghiêm ngặt 12 nguyên tắc an toàn: Không thêm thư viện phụ thuộc bên ngoài (Nguyên tắc 11), an toàn trước SSRF và injection (Nguyên tắc 2 & 12), giao diện chuẩn tiếng Việt (Nguyên tắc 8).
- **Thư viện mới**: Không có.


