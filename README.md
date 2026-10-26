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
Trong phiên chat, bạn có thể gõ:
- `/model auto`: Tự động chọn model (Gemini khi có mạng, Ollama khi mất mạng hoặc nhạy cảm).
- `/model gemini`: Ép buộc sử dụng Gemini.
- `/model local`: Ép buộc sử dụng mô hình Ollama cục bộ trên máy.
- `/clear`: Xóa lịch sử hội thoại hiện tại.
- `/exit`: Thoát khỏi ứng dụng.

---

### Bước 8: Chạy kiểm thử tự động và kiểm tra mã sạch
Chạy unit test:
```powershell
pytest -v
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
