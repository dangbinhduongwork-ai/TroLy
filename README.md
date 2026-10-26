# Trợ Lý (AI Assistant trên Windows)

Ứng dụng trợ lý trí tuệ nhân tạo (AI Assistant) chạy trực tiếp trên hệ điều hành Windows 10/11, hỗ trợ người dùng tương tác bằng tiếng Việt qua giao diện chat để thực hiện các thao tác:
- Thao tác trên máy: tạo, đọc, sửa, sắp xếp file; mở ứng dụng, thư mục, website; thực thi lệnh an toàn.
- Trí nhớ dài hạn lưu trữ cục bộ (Local Long-term Memory).
- Nhắc việc đúng giờ (Timely Reminders).
- Kết hợp 2 nguồn model: Google Gemini API (khi trực tuyến) và Ollama cục bộ (khi ngoại tuyến hoặc dữ liệu riêng tư).

---

## 1. Yêu Cầu Môi Trường
- **Hệ điều hành**: Windows 10 hoặc Windows 11 (64-bit).
- **Phần cứng đề xuất**: RAM 16GB–32GB, Card đồ hoạ GPU NVIDIA (nếu chạy mô hình cục bộ qua Ollama).
- **Python**: Phiên bản 3.11 trở lên.
- **Git**: Đã cài đặt và có trong biến môi trường PATH.

---

## 2. Các Bước Khởi Tạo và Cài Đặt (Giai Đoạn 0)

### Bước 1: Kiểm tra nhanh Python và Git
Mở terminal (PowerShell hoặc Command Prompt) tại thư mục dự án và chạy:
```powershell
python scripts/check_env.py
```
*Nếu thiếu công cụ nào, script sẽ hướng dẫn bạn tải và cài đặt chi tiết.*

---

### Bước 2: Tạo và kích hoạt môi trường ảo Python
```powershell
python -m venv .venv
.venv\Scripts\activate
```

---

### Bước 3: Cài đặt ứng dụng ở chế độ phát triển
Cài đặt gói `assistant` cùng các công cụ kiểm thử (`pytest`, `ruff`):
```powershell
pip install -e ".[dev]"
```

---

### Bước 4: Kiểm tra hoạt động của Trợ Lý AI
Kiểm tra phiên bản:
```powershell
assistant --version
```

Chạy lệnh chẩn đoán toàn diện hệ thống:
```powershell
assistant doctor
```

---

### Bước 5: Cài đặt khóa Gemini API (Tùy chọn)
Nhập khóa API ẩn ký tự và lưu vào Windows Credential Manager:
```powershell
assistant set-key
```

---

### Bước 6: Xem danh sách các mô hình khả dụng
Liệt kê các model Gemini trên đám mây và Ollama trên máy:
```powershell
assistant models
```

---

### Bước 7: Trò chuyện tương tác trên Terminal (Streaming)
Khởi động giao diện chat:
```powershell
assistant chat
```
Trong phiên chat, bạn có thể ra lệnh bằng tiếng Việt:
- *"tạo file ghi-chu.txt trong workspace"* -> AI tự động tạo file mới.
- *"mở Notepad"* -> AI khởi động ứng dụng Notepad.
- *"mở thư mục workspace"* -> AI mở thư mục bằng File Explorer.
- *"xóa file ghi-chu.txt"* -> AI xin phép bạn duyệt `(y/N)`, nếu đồng ý sẽ chuyển file vào Thùng rác Windows an toàn qua `send2trash`.
- *"chạy lệnh dir"* -> AI hiển thị nguyên văn lệnh và xin phép duyệt `(y/N)` trước khi chạy.

Các lệnh điều khiển nhanh trong chat:
- `/model <auto|gemini|local>`: Đổi chế độ điều phối mô hình (Gemini khi có mạng, Ollama khi mất mạng hoặc nhạy cảm).
- `/sensitive`: Bật/tắt chế độ nhạy cảm (khi bật, mọi câu hỏi và trí nhớ CHỈ xử lý trên Ollama cục bộ, không gửi lên đám mây).
- `/history`: Xem danh sách các cuộc hội thoại cũ (`/history <id>` để chuyển, `/history new` để tạo mới, `/history del <id>` để xóa).
- `/memories`: Xem danh sách toàn bộ trí nhớ dài hạn mà AI đã ghi nhớ về bạn kèm ID và danh mục.
- `/memory-edit <id> <nội dung mới>`: Chủ động sửa lại thông tin trí nhớ nếu AI ghi nhận chưa chuẩn.
- `/memory-del <id>`: Xóa bỏ một mục trí nhớ theo ID.
- `/reminders`: Xem danh sách các lời nhắc việc (đang chờ, đã nhắc, hoãn, bị lỡ).
- `/snooze <id> [phút]`: Hoãn một lời nhắc lại thêm số phút (mặc định 10 phút).
- `/cancel <id>`: Huỷ một lời nhắc việc.
- `/briefing`: Xem bản tin sáng tổng hợp công việc và lịch nhắc trong ngày.
- `/clear`: Xóa ngữ cảnh cuộc trò chuyện hiện tại.
- `/exit` hoặc `/quit`: Thoát khỏi ứng dụng.

---

### Bước 8: Kiểm tra Trí Nhớ Dài Hạn (Long-term Memory)
Thử nghiệm ghi nhớ thông tin cá nhân hoặc quy tắc qua các phiên làm việc:
1. Bạn gõ: `Hãy nhớ tôi thích đặt tên file báo cáo theo mẫu YYYY-MM-DD_ten-bao-cao`
2. AI phản hồi và tự động lưu vào cơ sở dữ liệu SQLite (`assistant.db`).
3. Gõ `/memories` để kiểm tra danh sách trí nhớ.
4. Gõ `/exit` để thoát ứng dụng hoàn toàn.
5. Khởi động lại bằng `assistant chat` và hỏi: `Quy tắc đặt tên file báo cáo của tôi là gì?`
6. AI tự động truy xuất trí nhớ đã nạp vào ngữ cảnh và trả lời chính xác quy tắc của bạn.

---

### Bước 9: Đặt Lịch Nhắc Việc và Thông Báo Windows Toast (Reminders)
Thử nghiệm hệ thống nhắc việc đúng giờ (chạy thuần APScheduler, không phụ thuộc mạng khi đến giờ):
1. Bạn gõ: `Nhắc tôi uống nước sau 1 phút nữa`
2. AI xác nhận ngày, giờ cụ thể và lưu vào SQLite.
3. Sau 1 phút, Windows Toast hiển thị trên góc màn hình kèm âm thanh thông báo.
4. Gõ `/snooze <id> 5` để hoãn lại 5 phút, hoặc `/cancel <id>` để huỷ lời nhắc.
5. Gõ `/briefing` để nhận bản tin sáng chào ngày mới và tóm tắt công việc trong ngày.
6. Chạy kịch bản kiểm tra toàn diện luồng nhắc việc:
   ```powershell
   python scripts/test_reminder_flow.py
   ```

---

### Bước 10: Xử Lý Tài Liệu và Uỷ Quyền Cho Các Agent Chuyên Trách
Thử nghiệm xử lý tài liệu văn phòng và phân loại dọn dẹp thư mục:
1. Bạn gõ: `Tạo cho tôi file Excel danh sách chi tiêu mẫu trong workspace`
   -> AI gọi công cụ `create_excel` tạo file `.xlsx`.
2. Bạn gõ: `Tóm tắt file Word/PDF này giúp tôi`
   -> AI gọi `read_docx` hoặc `read_pdf`, bọc dữ liệu trong thẻ an toàn `<untrusted_content>` và tóm tắt.
3. Bạn gõ: `Phân loại các file trong thư mục X theo loại file`
   -> AI gọi `organize_directory` lập kế hoạch di chuyển trước và hỏi bạn duyệt `(y/N)`.
4. Khi tác vụ phức tạp nhiều bước, AI tự động uỷ quyền cho 1 trong 4 Agent chuyên trách:
   - `file_organizer_agent`: Chuyên dọn dẹp, sắp xếp thư mục.
   - `document_agent`: Chuyên xử lý tài liệu PDF, Word, Excel.
   - `research_agent`: Chuyên tra cứu web an toàn (chống SSRF, không có quyền xóa/chạy lệnh).
   - `coder_agent`: Chuyên viết code và chạy lệnh kiểm thử trong workspace.
5. Chạy kịch bản kiểm tra toàn diện:
   ```powershell
   python scripts/test_agents_flow.py
   ```

---

### Bước 11: Khởi Động Giao Diện Ứng Dụng Desktop (FastAPI + Edge App Mode)
Khởi động máy chủ backend và mở cửa sổ ứng dụng riêng biệt:
```powershell
# Cách 1: Gõ lệnh mặc định
assistant

# Hoặc gõ tường minh:
assistant ui

# Nếu chỉ muốn chạy backend không mở trình duyệt tự động:
assistant ui --no-browser
```
1. Cửa sổ Microsoft Edge độc lập tự động mở tại `http://127.0.0.1:8000/?token=<session_token>` (không có thanh địa chỉ trình duyệt).
2. Trò chuyện streaming thời gian thực, định dạng markdown và khối mã cascadia code.
3. Khi AI thực hiện thao tác mức `CONFIRM` (xoá file, ghi đè, chạy lệnh), **Hộp thoại Duyệt quyền (Approval Modal)** sẽ nổi lên hỏi xác nhận trực tiếp.
4. Xem, tìm kiếm và chỉnh sửa Trí nhớ dài hạn (`/api/memories`).
5. Quản lý, hoãn nhắc và nhận thông báo Lời nhắc việc (`/api/reminders`).
6. Chạy kịch bản kiểm thử toàn diện luồng Server & WebSocket:
   ```powershell
   python scripts/test_server_flow.py
   ```

---

### Bước 12: Khay Hệ Thống và Tự Khởi Động Cùng Windows (System Tray & Autostart)
1. Khi ứng dụng chạy, một biểu tượng icon hiện đại tự vẽ bằng Pillow sẽ xuất hiện ở góc dưới bên phải màn hình (System Tray).
2. Khi đóng cửa sổ giao diện Edge (nút X), ứng dụng vẫn chạy ngầm ở khay hệ thống để đảm bảo bộ nhắc việc nổ thông báo đúng giờ.
3. Nhấp đúp hoặc nhấp chuột phải vào icon khay hệ thống để:
   - 💬 **Mở cửa sổ Trợ lý**: Kích hoạt lại cửa sổ giao diện Edge.
   - 🤖 **Chế độ Model**: Chuyển nhanh giữa Tự động / Gemini Cloud / Ollama Cục bộ.
   - 🔄 **Khởi động cùng Windows**: Bật/tắt tự động khởi động cùng Windows (lưu vào Registry HKCU, không cần quyền Admin).
   - 📁 **Mở thư mục làm việc (Workspace)**: Mở nhanh trong Windows File Explorer.
   - 🚪 **Thoát hoàn toàn**: Tắt sạch tiến trình ngầm và giải phóng tài nguyên.
4. Chạy chế độ ngầm hoàn toàn (không tự bung cửa sổ):
   ```powershell
   assistant ui --minimized
   ```
5. Chạy kịch bản kiểm thử toàn diện luồng Khay hệ thống & Autostart:
   ```powershell
   python scripts/test_tray_flow.py
   ```

---

### Bước 13: Kiểm định khả năng gọi công cụ của Model
Chạy script kiểm tra xem mô hình có gọi đúng công cụ tạo file hay không:
```powershell
python scripts/check_tool_calling.py --model qwen2.5:7b
python scripts/check_tool_calling.py --model gemini-2.5-flash --provider gemini
```

---

### Bước 14: Chạy kiểm thử tự động và kiểm tra mã sạch
Chạy toàn bộ unit tests:
```powershell
pytest -v
```

Chạy riêng bộ kiểm thử Khay hệ thống & Autostart:
```powershell
pytest tests/test_tray_autostart.py -v
```

Kiểm tra cú pháp linter bằng `ruff`:
```powershell
ruff check .
```




---

## 3. Cấu Trúc Thư Mục Dự Án (src Layout)
```text
TroLy/
├── pyproject.toml          # Cấu hình gói assistant, ruff, pytest
├── README.md               # Tài liệu hướng dẫn cài đặt và sử dụng
├── .env.example            # Mẫu khai báo biến môi trường
├── .gitignore              # Danh sách file và thư mục loại trừ khỏi git
├── PROJECT_RULES.md        # 12 nguyên tắc an toàn bất biến của dự án
├── config/
│   └── settings.toml       # Tham số cấu hình hệ thống mặc định
├── docs/
│   └── DECISIONS.md        # Nhật ký quyết định kiến trúc và thư viện (ADR)
├── scripts/
│   ├── check_env.py        # Script kiểm tra môi trường Python 3.11+ và Git
│   └── setup_project.bat   # Script tự động hoá cài đặt một nhấp chuột
├── tests/
│   ├── __init__.py
│   └── test_config.py      # Unit test cho module config và bảo mật
└── src/
    └── assistant/          # Mã nguồn chính của ứng dụng
        ├── __init__.py
        ├── config.py       # Nạp cấu hình toml và biến môi trường
        ├── logging_setup.py# Xoay vòng file log và lọc mã bí mật
        ├── main.py         # Entrypoint CLI: assistant --version & doctor
        ├── core/           # Điều phối trung tâm
        ├── llm/            # Kết nối Gemini API & Ollama
        ├── tools/          # Công cụ thao tác file, app, shell
        ├── safety/         # Phân quyền, kiểm tra path traversal
        ├── memory/         # Trí nhớ dài hạn cục bộ
        ├── reminders/      # Quản lý nhắc việc
        ├── agents/         # Đa agent chuyên trách
        ├── server/         # Máy chủ web backend
        ├── desktop/        # Khay hệ thống và cửa sổ ứng dụng
        └── ui_static/      # Giao diện web người dùng
```
