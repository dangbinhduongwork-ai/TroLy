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



