---
name: troly-phase-workflow
description: >-
  Use this skill to guide and enforce the mandatory 5-step development workflow
  for every phase of the Trợ lý AI project on Windows.
---

# Quy Trình Chuẩn Mỗi Giai Đoạn (Trợ Lý AI)

Kỹ sư luôn phải tuân thủ nghiêm ngặt chu trình 5 bước sau đây cho từng giai đoạn, không được bỏ qua bất kỳ bước nào:

## Bước a: Lập kế hoạch ngắn
- Tóm tắt kế hoạch công việc sắp làm trong **tối đa 10 dòng**.
- Nêu rõ các module, file cần tạo hoặc sửa và mục tiêu cần đạt được.

## Bước b: Kiểm tra chất lượng mã nguồn
- Định dạng và kiểm tra linter: `ruff check .` và `ruff format --check .` (sửa triệt để mọi cảnh báo).
- Chạy kiểm thử tự động: `pytest` (đảm bảo 100% test case quan trọng đều pass).
- Kiểm tra type hints đầy đủ cho toàn bộ hàm và lớp mới.

## Bước c: Tự chạy thử nghiệm
- Chủ động chạy trực tiếp các hàm hoặc script để kiểm chứng hoạt động thực tế trên Windows (trong phạm vi an toàn).
- Không dựa thuần tuý vào lý thuyết hay code giả lập nếu có thể chạy thực tế.

## Bước d: Báo cáo kết quả chuẩn theo mẫu
Báo cáo cho người dùng theo đúng 6 mục:
1. **Đã làm**: Liệt kê các tính năng, module đã hoàn thành.
2. **File đã tạo hoặc sửa**: Link đến các file tương ứng.
3. **Cách tôi chạy thử**: Ghi rõ lệnh cụ thể đã dùng để kiểm tra.
4. **Kết quả kiểm tra**: Trạng thái ruff, pytest và kết quả chạy thử.
5. **Vấn đề còn tồn đọng**: Điểm chưa hoàn hảo hoặc giới hạn kỹ thuật (nếu có).
6. **Đề xuất**: Gợi ý bước chuẩn bị tiếp theo.

## Bước e: Dừng lại và chờ lệnh
- **Tuyệt đối không tự ý chuyển sang giai đoạn tiếp theo.**
- Dừng câu trả lời và chờ người dùng gõ từ khóa "tiếp tục".
