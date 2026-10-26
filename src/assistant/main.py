"""Điểm khởi nhập dòng lệnh (CLI) cho ứng dụng Trợ Lý AI trên Windows.

Cung cấp các lệnh:
- `assistant --version`: Kiểm tra phiên bản.
- `assistant doctor`: Chẩn đoán toàn diện hệ thống.
- `assistant set-key`: Nhập và lưu Gemini API Key an toàn bằng keyring (getpass).
- `assistant models`: Liệt kê các model khả dụng từ Gemini API và Ollama cục bộ.
- `assistant chat`: Chat tương tác trên terminal hỗ trợ streaming và tự chuyển nguồn model.
"""

import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.request

from assistant import __version__
from assistant.config import load_config
from assistant.core.context import ConversationContext
from assistant.core.prompts import get_system_prompt
from assistant.core.router import ModelRouter, RouterMode
from assistant.llm.base import ProviderError
from assistant.llm.gemini_provider import GeminiProvider
from assistant.llm.ollama_provider import OllamaProvider
from assistant.logging_setup import setup_logging


def check_gemini_key() -> str:
    """Kiểm tra có GEMINI_API_KEY trong môi trường hoặc Windows Credential Manager hay không.

    Tuyệt đối tuân thủ Nguyên tắc 3: Chỉ trả về trạng thái có/không, không bao giờ in key.
    """
    key_in_env = os.getenv("GEMINI_API_KEY")
    if key_in_env and key_in_env.strip():
        return "Có (từ biến môi trường)"

    try:
        import keyring

        key_in_keyring = keyring.get_password("TroLyAI", "GEMINI_API_KEY")
        if key_in_keyring and key_in_keyring.strip():
            return "Có (từ Windows Credential Manager)"
    except Exception:
        pass

    return "Không"


def check_ollama(host: str = "http://127.0.0.1:11434") -> str:
    """Kiểm tra máy chủ Ollama cục bộ có đang hoạt động và liệt kê các model đã tải."""
    url = f"{host.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                models = [m.get("name", "") for m in data.get("models", [])]
                if models:
                    return f"Đang hoạt động ({len(models)} model: {', '.join(models)})"
                return "Đang hoạt động (chưa cài đặt model nào)"
            return f"Phản hồi mã trạng thái {response.status}"
    except urllib.error.URLError:
        return "Không thể kết nối (máy chủ Ollama chưa được bật hoặc chưa cài đặt)"
    except Exception as err:
        return f"Lỗi kiểm tra ({err})"


def check_edge_browser() -> str:
    """Kiểm tra trình duyệt Microsoft Edge có sẵn trên Windows hay không."""
    which_edge = shutil.which("msedge")
    if which_edge:
        return f"Có sẵn ({which_edge})"

    common_paths = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
    ]

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        common_paths.append(
            Path(local_appdata) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        )

    for p in common_paths:
        if p.is_file():
            return f"Có sẵn ({p})"

    return "Không tìm thấy"


def run_doctor() -> int:
    """Thực thi chẩn đoán toàn diện môi trường hệ thống cho Trợ Lý AI."""
    print("=" * 65)
    print(f"BÁO CÁO CHẨN ĐOÁN MÔI TRƯỜNG TRỢ LÝ AI (v{__version__})")
    print("=" * 65)

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_status = "[OK]" if sys.version_info >= (3, 11) else "[CẢNH BÁO]"
    print(f"1. Phiên bản Python         : {py_status} {py_ver}")

    config = load_config(create_dirs=True)
    setup_logging(data_dir=config.data_dir, log_level=config.log_level)

    ws_status = "[TỒN TẠI]" if config.workspace_dir.exists() else "[CHƯA TẠO]"
    print(f"2. Thư mục làm việc (WS)    : {ws_status} {config.workspace_dir}")

    data_status = "[TỒN TẠI]" if config.data_dir.exists() else "[CHƯA TẠO]"
    print(f"3. Thư mục dữ liệu (Data)   : {data_status} {config.data_dir}")

    gemini_key_status = check_gemini_key()
    print(f"4. Tìm thấy GEMINI_API_KEY  : {gemini_key_status}")

    ollama_host = config.ollama_host
    ollama_status = check_ollama(ollama_host)
    print(f"5. Máy chủ Ollama ({ollama_host}): {ollama_status}")

    edge_status = check_edge_browser()
    print(f"6. Trình duyệt MS Edge      : {edge_status}")

    print("=" * 65)
    print("Chẩn đoán hoàn tất.")
    return 0


def run_set_key() -> int:
    """Nhập Gemini API Key ẩn ký tự và lưu vào Windows Credential Manager."""
    print("=" * 65)
    print("CÀI ĐẶT GEMINI API KEY (BẢO VỆ QUA KEYRING)")
    print("=" * 65)
    print("Lưu ý: Ký tự bạn nhập hoặc dán vào sẽ được ẩn để bảo mật.")

    try:
        key = getpass.getpass("Nhập khóa Gemini API Key của bạn: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n[ĐÃ HỦY] Thao tác bị người dùng hủy.")
        return 1

    if not key:
        print("[LỖI] Khóa API Key không được để trống!")
        return 1

    try:
        import keyring

        keyring.set_password("TroLyAI", "GEMINI_API_KEY", key)
        print("[THÀNH CÔNG] Đã lưu Gemini API Key an toàn vào Windows Credential Manager!")
        print("  - Ứng dụng sẽ tự động sử dụng khóa này khi gọi Gemini API.")
        print("  - Bạn có thể kiểm tra trạng thái bằng lệnh: assistant doctor")
        return 0
    except Exception as err:
        print(f"[LỖI] Không thể lưu vào Windows Credential Manager: {err}")
        print("Gợi ý: Bạn có thể tạm thời đặt biến môi trường GEMINI_API_KEY trong file .env.")
        return 1


async def _list_models_async() -> int:
    """Bất đồng bộ liệt kê các model từ Gemini và Ollama."""
    config = load_config(create_dirs=False)
    print("=" * 65)
    print("DANH SÁCH MÔ HÌNH KHẢ DỤNG (GEMINI & OLLAMA)")
    print("=" * 65)

    # 1. Kiểm tra Gemini
    print("\n1. Mô hình Gemini API (Đám mây):")
    gemini_provider = GeminiProvider(config)
    try:
        gemini_models = await gemini_provider.list_models()
        if gemini_models:
            print(f"   (Model mặc định trong cấu hình: {config.gemini_model})")
            for m in gemini_models:
                marker = " [*]" if m == config.gemini_model else "    "
                print(f"{marker} - {m}")
        else:
            print("   Không tìm thấy model nào khả dụng.")
    except ProviderError as err:
        print(f"   [CẢNH BÁO] Không lấy được danh sách Gemini: {err.message}")

    # 2. Kiểm tra Ollama
    print(f"\n2. Mô hình Ollama Cục bộ ({config.ollama_host}):")
    ollama_provider = OllamaProvider(config)
    try:
        ollama_models = await ollama_provider.list_models()
        if ollama_models:
            print(f"   (Model mặc định trong cấu hình: {config.local_model})")
            for m in ollama_models:
                marker = " [*]" if m == config.local_model else "    "
                print(f"{marker} - {m}")
        else:
            print("   Chưa có model nào được tải về trong Ollama.")
            print(f"   Gợi ý lệnh tải: ollama pull {config.local_model}")
    except ProviderError as err:
        print(f"   [CẢNH BÁO] {err.message}")

    print("=" * 65)
    return 0


def run_models() -> int:
    """Lệnh liệt kê các model khả dụng cho key và máy tính hiện hành."""
    return asyncio.run(_list_models_async())


async def _chat_session() -> None:
    """Phiên chat tương tác trực tiếp trên terminal với streaming."""
    config = load_config(create_dirs=True)
    setup_logging(data_dir=config.data_dir, log_level=config.log_level)

    router = ModelRouter(config=config)
    context = ConversationContext(max_tokens=config.max_context_tokens)

    print("=" * 65)
    print("   ỨNG DỤNG TRỢ LÝ AI TRÊN WINDOWS — TERMINAL CHAT")
    print("=" * 65)
    print("Lệnh nhanh:")
    print("  /model <auto|gemini|local> : Đổi chế độ điều phối model")
    print("  /clear                     : Xoá lịch sử hội thoại hiện tại")
    print("  /exit                      : Thoát khỏi ứng dụng")
    print("-" * 65)
    print(f"Chế độ hiện tại: [{router.mode.upper()}] (Gemini: {config.gemini_model} | Local: {config.local_model})\n")

    while True:
        try:
            user_input = input("Bạn: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nTạm biệt!")
            break

        if not user_input:
            continue

        # Xử lý các lệnh đặc biệt trong chat
        if user_input in ("/exit", "/quit"):
            print("Tạm biệt bạn!")
            break

        if user_input == "/clear":
            context.clear()
            print("[Hệ thống] Đã xoá sạch lịch sử hội thoại.\n")
            continue

        if user_input.startswith("/model"):
            parts = user_input.split()
            if len(parts) >= 2 and parts[1].lower() in ("auto", "gemini", "local"):
                new_mode = parts[1].lower()  # type: ignore[assignment]
                router.set_mode(new_mode)  # type: ignore[arg-type]
                print(f"[Hệ thống] Đã chuyển sang chế độ định tuyến: [{new_mode.upper()}]\n")
            else:
                print("[Hướng dẫn] Cú pháp hợp lệ: /model auto | /model gemini | /model local\n")
            continue

        # Thêm câu hỏi người dùng vào context
        context.add_user_message(user_input)

        # Kiểm tra nén ngữ cảnh nếu vượt ngưỡng token
        await context.check_and_compress(local_provider=router.ollama_provider)

        # Chuẩn bị gọi mô hình
        sys_prompt = get_system_prompt(timezone_str=config.timezone)
        messages_to_send = context.get_messages_for_llm()

        print("Trợ lý: ", end="", flush=True)

        full_response_chunks: list[str] = []
        try:
            async for event in router.stream_chat(
                messages=messages_to_send,
                system=sys_prompt,
            ):
                if event.type == "text_delta" and isinstance(event.content, str):
                    sys.stdout.write(event.content)
                    sys.stdout.flush()
                    full_response_chunks.append(event.content)

            print()  # Xuống dòng sau khi stream hoàn tất
            full_response = "".join(full_response_chunks).strip()
            context.add_assistant_message(full_response)

            # In thông tin model đã phục vụ lượt trả lời này
            model_info = router.last_model_used or router.mode
            print(f"[Nguồn: {router.last_provider_used.upper()} ({model_info})]\n")

        except ProviderError as err:
            print(f"\n[LỖI TRỢ LÝ] {err.message}\n")
        except Exception as err:
            print(f"\n[LỖI KHÔNG MONG MUỐN] Đã xảy ra lỗi: {err}\n")


def run_chat() -> int:
    """Khởi động giao diện chat trong terminal."""
    try:
        asyncio.run(_chat_session())
        return 0
    except Exception as err:
        print(f"[LỖI KHỞI ĐỘNG CHAT] {err}")
        return 1


def cli() -> None:
    """Hàm điểm đầu (entry point) khi chạy lệnh `assistant` trên terminal."""
    parser = argparse.ArgumentParser(
        prog="assistant",
        description="Trợ lý AI trên Windows (AI Assistant)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Hiển thị phiên bản ứng dụng",
    )

    subparsers = parser.add_subparsers(dest="command", help="Lệnh chức năng")

    # Lệnh doctor
    subparsers.add_parser("doctor", help="Kiểm tra môi trường và các kết nối hệ thống")

    # Lệnh set-key
    subparsers.add_parser("set-key", help="Cài đặt khóa Gemini API Key vào Windows Credential Manager")

    # Lệnh models
    subparsers.add_parser("models", help="Liệt kê danh sách các mô hình khả dụng")

    # Lệnh chat
    subparsers.add_parser("chat", help="Khởi động phiên trò chuyện tương tác trên terminal")

    args = parser.parse_args()

    if args.command == "doctor":
        sys.exit(run_doctor())
    elif args.command == "set-key":
        sys.exit(run_set_key())
    elif args.command == "models":
        sys.exit(run_models())
    elif args.command == "chat":
        sys.exit(run_chat())
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    cli()
