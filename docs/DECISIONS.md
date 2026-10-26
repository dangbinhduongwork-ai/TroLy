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
- **Thư viện mới (nếu có)**:
  - `keyring>=24.0.0`: Quản lý bí mật an toàn trên Windows Credential Manager.
  - `pytest>=8.0.0` (dev): Khung kiểm thử tự động.
  - `ruff>=0.3.0` (dev): Công cụ kiểm tra chất lượng mã nguồn và định dạng nhanh.
