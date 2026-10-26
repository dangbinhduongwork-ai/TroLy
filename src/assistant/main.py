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
from assistant.config import Config, load_config
from assistant.core.context import ConversationContext
from assistant.core.prompts import get_system_prompt
from assistant.core.router import ModelRouter, RouterMode
from assistant.llm.base import ProviderError
from assistant.llm.gemini_provider import GeminiProvider
from assistant.llm.ollama_provider import OllamaProvider
from assistant.agents.orchestrator import set_orchestrator_router
from assistant.logging_setup import setup_logging
from assistant.memory.extractor import extract_and_store_memories
from assistant.memory.store import MemoryStore
from assistant.reminders.briefing import generate_morning_briefing
from assistant.reminders.scheduler import ReminderScheduler, set_global_scheduler
from assistant.reminders.store import ReminderStore
from assistant.tools.reminder_tools import format_vietnamese_datetime, parse_iso_datetime



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

    try:
        from assistant.desktop.autostart import is_autostart_enabled
        autostart_status = "[BẬT]" if is_autostart_enabled() else "[TẮT]"
    except Exception:
        autostart_status = "[CHƯA KIỂM TRA ĐƯỢC]"
    print(f"7. Khởi động cùng Windows   : {autostart_status}")

    try:
        from assistant.desktop.tray import SystemTrayManager
        tray_mgr = SystemTrayManager(
            port=config.ui_port,
            session_token="",
            workspace_dir=config.workspace_dir,
            data_dir=config.data_dir,
        )
        tray_status = "[SẴN SÀNG]" if tray_mgr.is_available() else "[THIẾU PYSTRAY/PILLOW]"
    except Exception:
        tray_status = "[LỖI NẠP]"
    print(f"8. Khay hệ thống (Tray)     : {tray_status}")

    try:
        from assistant.desktop.single_instance import get_instance_info
        inst_info = get_instance_info(config.data_dir)
        inst_status = f"[ĐANG CHẠY - PID {inst_info['pid']}]" if inst_info else "[CHƯA CHẠY]"
    except Exception:
        inst_status = "[CHƯA RÕ]"
    print(f"9. Tiến trình Single Instance: {inst_status}")

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
    """Phiên chat tương tác trực tiếp trên terminal với streaming và trí nhớ dài hạn SQLite."""
    config = load_config(create_dirs=True)
    setup_logging(data_dir=config.data_dir, log_level=config.log_level)

    store = MemoryStore(config.data_dir / "assistant.db")
    reminder_store = ReminderStore(config.data_dir / "assistant.db")
    router = ModelRouter(config=config)
    set_orchestrator_router(router)

    # Khởi động bộ lập lịch nhắc việc APScheduler
    scheduler = ReminderScheduler(config=config, store=reminder_store)
    set_global_scheduler(scheduler)
    missed_report = scheduler.start()

    try:
        await _interactive_chat_loop(
            config=config,
            store=store,
            reminder_store=reminder_store,
            router=router,
            scheduler=scheduler,
            missed_report=missed_report,
        )
    finally:
        scheduler.shutdown()
        set_global_scheduler(None)


async def _interactive_chat_loop(
    config: Config,
    store: MemoryStore,
    reminder_store: ReminderStore,
    router: ModelRouter,
    scheduler: ReminderScheduler,
    missed_report: str,
) -> None:
    """Vòng lặp tương tác nhập lệnh và hỏi đáp với trợ lý trong terminal."""
    # Khởi tạo cuộc hội thoại mới trong DB
    current_conv_id = store.create_conversation(title="Cuộc trò chuyện mới", is_sensitive=False)
    is_sensitive = False
    context = ConversationContext(max_tokens=config.max_context_tokens, conversation_id=current_conv_id)

    print("=" * 65)
    print("   ỨNG DỤNG TRỢ LÝ AI TRÊN WINDOWS — TERMINAL CHAT")
    print("=" * 65)
    print("Lệnh nhanh:")
    print("  /model <auto|gemini|local>  : Đổi chế độ điều phối model")
    print("  /sensitive                  : Bật/tắt chế độ nhạy cảm (chỉ dùng model cục bộ)")
    print("  /history                    : Xem và quản lý các cuộc hội thoại cũ")
    print("  /memories                   : Liệt kê toàn bộ trí nhớ dài hạn về người dùng")
    print("  /memory-edit <id> <nội dung>: Sửa nội dung một mục trí nhớ")
    print("  /memory-del <id>            : Xóa một mục trí nhớ")
    print("  /reminders                  : Xem danh sách các lời nhắc việc")
    print("  /snooze <id> [phút]         : Hoãn lời nhắc thêm số phút (mặc định 10p)")
    print("  /cancel <id>                : Huỷ một lời nhắc việc")
    print("  /briefing                   : Xem bản tin sáng tổng hợp việc trong ngày")
    print("  /clear                      : Xoá ngữ cảnh cuộc trò chuyện hiện tại")
    print("  /exit                       : Thoát khỏi ứng dụng")
    print("-" * 65)
    print(f"Chế độ hiện tại: [{router.mode.upper()}] (Gemini: {config.gemini_model} | Local: {config.local_model})")
    print(f"Hội thoại ID  : {current_conv_id}")

    if missed_report:
        print("\n" + missed_report)
    print()

    import assistant.tools  # noqa: F401 (Nạp toàn bộ công cụ hệ thống vào registry)
    from assistant.core.agent_loop import AgentLoop

    agent_loop = AgentLoop(router=router)

    while True:
        try:
            sensitive_tag = " [NHẠY CẢM]" if is_sensitive else ""
            user_input = input(f"Bạn{sensitive_tag}: ").strip()
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
            print("[Hệ thống] Đã xoá sạch lịch sử hội thoại hiện tại.\n")
            continue

        if user_input == "/sensitive":
            is_sensitive = not is_sensitive
            store.update_conversation(current_conv_id, is_sensitive=is_sensitive)
            if is_sensitive:
                print(
                    "[Bảo mật] ĐÃ BẬT chế độ nhạy cảm. Mọi yêu cầu và trích xuất trí nhớ "
                    "sẽ CHỈ dùng model cục bộ (Ollama), tuyệt đối không gửi lên đám mây.\n"
                )
            else:
                print("[Bảo mật] ĐÃ TẮT chế độ nhạy cảm. Trở lại định tuyến bình thường.\n")
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

        if user_input.startswith("/history"):
            parts = user_input.split(maxsplit=2)
            if len(parts) == 1:
                convs = store.list_conversations(limit=10)
                print("\n" + "=" * 65)
                print("LỊCH SỬ CÁC CUỘC HỘI THOẠI GẦN ĐÂY:")
                print("=" * 65)
                for c in convs:
                    cid = c["id"]
                    marker = "[*] " if cid == current_conv_id else "    "
                    sens_tag = " [Bảo mật: Cục bộ]" if c.get("is_sensitive") else ""
                    print(f"{marker}ID: {cid} | Tiêu đề: {c['title']}{sens_tag}")
                    print(f"       Cập nhật: {c['updated_at']}")
                print("-" * 65)
                print("Lệnh quản lý:")
                print("  /history <id>          : Chuyển sang cuộc hội thoại có ID này")
                print("  /history new [tiêu đề] : Tạo một cuộc hội thoại mới")
                print("  /history del <id>      : Xóa cuộc hội thoại\n")
            elif parts[1] == "new":
                title = parts[2].strip() if len(parts) > 2 else "Cuộc trò chuyện mới"
                current_conv_id = store.create_conversation(title=title, is_sensitive=is_sensitive)
                context.clear()
                context.conversation_id = current_conv_id
                print(f"[Hệ thống] Đã tạo cuộc hội thoại mới: '{title}' (ID: {current_conv_id})\n")
            elif parts[1] == "del":
                if len(parts) < 3:
                    print("[Hướng dẫn] Cú pháp: /history del <id>\n")
                else:
                    target_id = parts[2].strip()
                    if store.delete_conversation(target_id):
                        print(f"[Hệ thống] Đã xóa thành công cuộc hội thoại: {target_id}\n")
                        if target_id == current_conv_id:
                            current_conv_id = store.create_conversation(
                                title="Cuộc trò chuyện mới", is_sensitive=is_sensitive
                            )
                            context.clear()
                            context.conversation_id = current_conv_id
                    else:
                        print(f"[Lỗi] Không tìm thấy hoặc không thể xóa hội thoại ID: {target_id}\n")
            else:
                target_id = parts[1].strip()
                conv = store.get_conversation(target_id)
                if conv:
                    current_conv_id = target_id
                    is_sensitive = bool(conv.get("is_sensitive", 0))
                    context.load_from_store(store, current_conv_id)
                    print(
                        f"[Hệ thống] Đã chuyển sang hội thoại '{conv['title']}' "
                        f"(ID: {target_id}, {len(context.messages)} tin nhắn).\n"
                    )
                else:
                    print(f"[Lỗi] Không tìm thấy cuộc hội thoại với ID: {target_id}\n")
            continue

        if user_input == "/memories":
            all_mems = store.list_memories(limit=50)
            print("\n" + "=" * 65)
            print(f"DANH SÁCH TRÍ NHỚ DÀI HẠN VỀ NGƯỜI DÙNG ({len(all_mems)} mục):")
            print("=" * 65)
            if not all_mems:
                print("  (Chưa có ghi nhớ nào được lưu. Bạn có thể nói 'Hãy nhớ tôi thích...')")
            else:
                for idx, m in enumerate(all_mems, start=1):
                    print(f"{idx}. [{m['category']}] {m['content']}")
                    print(f"   ID: {m['id']} | Cập nhật: {m['updated_at']}")
            print("-" * 65)
            print("Lệnh quản lý:")
            print("  /memory-edit <id> <nội dung mới> : Sửa nội dung trí nhớ")
            print("  /memory-del <id>                 : Xóa mục trí nhớ\n")
            continue

        if user_input.startswith("/memory-edit"):
            parts = user_input.split(maxsplit=2)
            if len(parts) < 3:
                print("[Hướng dẫn] Cú pháp: /memory-edit <id> <nội dung mới>\n")
            else:
                target_id = parts[1].strip()
                new_content = parts[2].strip()
                if store.update_memory(target_id, content=new_content):
                    print(f"[Thành công] Đã cập nhật trí nhớ ID '{target_id}': {new_content}\n")
                else:
                    print(f"[Lỗi] Không tìm thấy mục trí nhớ với ID: {target_id}\n")
            continue

        if user_input.startswith("/memory-del"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                print("[Hướng dẫn] Cú pháp: /memory-del <id>\n")
            else:
                target_id = parts[1].strip()
                if store.delete_memory(target_id):
                    print(f"[Thành công] Đã xóa mục trí nhớ ID: {target_id}\n")
                else:
                    print(f"[Lỗi] Không tìm thấy mục trí nhớ với ID: {target_id}\n")
            continue

        if user_input == "/reminders":
            rems = reminder_store.list_reminders(limit=25)
            print("\n" + "=" * 65)
            print(f"DANH SÁCH CÁC LỜI NHẮC VIỆC GẦN ĐÂY ({len(rems)} mục):")
            print("=" * 65)
            if not rems:
                print("  (Hiện chưa có lời nhắc việc nào. Bạn có thể nói 'Nhắc tôi họp lúc 15h...')")
            else:
                status_map = {
                    "pending": "Đang chờ",
                    "fired": "Đã nhắc",
                    "snoozed": "Đang hoãn",
                    "cancelled": "Đã huỷ",
                    "missed": "Bị lỡ",
                }
                for r in rems:
                    try:
                        dt = parse_iso_datetime(r["trigger_at"], config.timezone)
                        t_str = format_vietnamese_datetime(dt)
                    except Exception:
                        t_str = r["trigger_at"]
                    cron_info = f" [Lặp lại: {r['cron_expr']}]" if r.get("cron_expr") else ""
                    st = status_map.get(r["status"], r["status"])
                    print(f"[{st}] ID: {r['id']}")
                    print(f"       Thời gian: {t_str}{cron_info}")
                    print(f"       Nội dung : {r['message']}")
            print("-" * 65)
            print("Lệnh quản lý: /snooze <id> [phút] | /cancel <id>\n")
            continue

        if user_input.startswith("/snooze"):
            parts = user_input.split()
            if len(parts) < 2:
                print("[Hướng dẫn] Cú pháp: /snooze <id> [số_phút]\n")
            else:
                target_id = parts[1].strip()
                mins = 10
                if len(parts) >= 3:
                    try:
                        mins = int(parts[2])
                    except ValueError:
                        mins = 10
                updated = reminder_store.snooze_reminder(
                    target_id, minutes=mins, timezone_str=config.timezone
                )
                if updated:
                    scheduler.schedule_reminder(updated)
                    try:
                        dt = parse_iso_datetime(updated["trigger_at"], config.timezone)
                        t_str = format_vietnamese_datetime(dt)
                    except Exception:
                        t_str = updated["trigger_at"]
                    print(
                        f"[Thành công] Đã hoãn lời nhắc thêm {mins} phút. "
                        f"Sẽ nhắc lại vào lúc {t_str}: \"{updated['message']}\"\n"
                    )
                else:
                    print(f"[Lỗi] Không tìm thấy lời nhắc với ID: {target_id}\n")
            continue

        if user_input.startswith("/cancel"):
            parts = user_input.split()
            if len(parts) < 2:
                print("[Hướng dẫn] Cú pháp: /cancel <id>\n")
            else:
                target_id = parts[1].strip()
                if reminder_store.cancel_reminder(target_id):
                    scheduler.cancel_scheduled_job(target_id)
                    print(f"[Thành công] Đã huỷ lời nhắc ID: {target_id}\n")
                else:
                    print(f"[Lỗi] Không tìm thấy lời nhắc với ID: {target_id}\n")
            continue

        if user_input == "/briefing":
            print("\n[Hệ thống] Đang tạo bản tin sáng...")
            briefing_text = await generate_morning_briefing(
                router=router,
                store=reminder_store,
                timezone_str=config.timezone,
            )
            print("\n" + briefing_text + "\n")
            continue


        # Cập nhật tiêu đề hội thoại nếu là tin nhắn đầu tiên
        curr_conv = store.get_conversation(current_conv_id)
        if curr_conv and curr_conv.get("title") == "Cuộc trò chuyện mới":
            new_title = user_input[:40].replace("\n", " ").strip()
            store.update_conversation(current_conv_id, title=new_title)

        # Lưu tin nhắn người dùng vào SQLite và context
        store.add_message(conversation_id=current_conv_id, role="user", content=user_input)
        context.add_user_message(user_input)

        # Kiểm tra nén ngữ cảnh nếu vượt ngưỡng token
        await context.check_and_compress(local_provider=router.ollama_provider)

        # Tự động chèn các trí nhớ quan trọng vào system prompt (Hybrid Search theo nội dung người dùng hỏi)
        active_memories = context.get_relevant_memories(
            store,
            max_tokens=600,
            max_memories=15,
            query=user_input,
        )
        sys_prompt = get_system_prompt(
            timezone_str=config.timezone,
            memories=active_memories,
        )

        print("Trợ lý: ", end="", flush=True)

        accumulated_text_chunks: list[str] = []
        try:
            async for event in agent_loop.run_turn(
                context=context,
                system_prompt=sys_prompt,
                is_sensitive=is_sensitive,
            ):
                if event.type == "text_delta" and isinstance(event.content, str):
                    sys.stdout.write(event.content)
                    sys.stdout.flush()
                    accumulated_text_chunks.append(event.content)

            print()  # Xuống dòng sau khi hoàn tất lượt

            full_response = "".join(accumulated_text_chunks).strip()
            model_info = router.last_model_used or router.mode
            print(f"[Nguồn: {router.last_provider_used.upper()} ({model_info})]\n")

            # Lưu phản hồi của trợ lý vào SQLite
            if full_response:
                store.add_message(
                    conversation_id=current_conv_id,
                    role="assistant",
                    content=full_response,
                    model_used=f"{router.last_provider_used}:{model_info}",
                )

                # Tự động trích xuất trí nhớ dài hạn (tuân thủ nguyên tắc an toàn: sensitive -> local only)
                try:
                    extracted = await extract_and_store_memories(
                        user_message=user_input,
                        assistant_response=full_response,
                        store=store,
                        router=router,
                        is_sensitive=is_sensitive,
                        source_conv_id=current_conv_id,
                    )
                    if extracted:
                        for ext in extracted:
                            label = "Đã lưu trí nhớ" if ext["action"] == "created" else "Đã cập nhật trí nhớ"
                            print(f"💡 [{label}: ({ext['category']}) {ext['content']}]")
                        print()
                except Exception:
                    pass

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


def run_ui(
    port: int | None = None,
    no_browser: bool = False,
    minimized: bool = False,
) -> int:
    """Khởi động Uvicorn server, APScheduler, Khay hệ thống và mở giao diện ứng dụng Desktop."""
    import threading
    import time

    try:
        import uvicorn
        from assistant.desktop.single_instance import check_or_acquire_instance, release_instance
        from assistant.desktop.tray import SystemTrayManager
        from assistant.desktop.window import launch_desktop_window
        from assistant.server.app import create_app, get_current_session_token
    except ImportError as err:
        print("=" * 65)
        print("❌ [LỖI THIẾU THƯ VIỆN GIAO DIỆN]")
        print(f"   Chi tiết: {err}")
        print("=" * 65)
        print("👉 Vui lòng chạy lệnh sau trên terminal để cài đặt tự động đầy đủ thư viện:")
        print("   pip install -e \".[dev]\"")
        print("=" * 65)
        return 1


    config = load_config(create_dirs=True)
    setup_logging(data_dir=config.data_dir, log_level=config.log_level)

    active_port = port or config.ui_port
    token = get_current_session_token()

    # 1. Kiểm tra Single Instance Lock
    is_primary = check_or_acquire_instance(
        data_dir=config.data_dir,
        port=active_port,
        session_token=token,
        open_window_if_running=not minimized,
    )
    if not is_primary:
        print("=" * 65)
        print("ℹ️  [THÔNG BÁO] Trợ lý AI đã đang chạy ngầm ở khay hệ thống.")
        if not minimized:
            print("   Đã kích hoạt lại cửa sổ ứng dụng giao diện hiện có.")
        print("=" * 65)
        return 0

    app = create_app(config=config, session_token=token)
    router: ModelRouter = app.state.router

    print("=" * 65)
    print("🤖 TRỢ LÝ AI - KHỞI ĐỘNG GIAO DIỆN ỨNG DỤNG DESKTOP")
    print(f"Địa chỉ cục bộ : http://127.0.0.1:{active_port}/?token={token}")
    if minimized:
        print("Chế độ chạy    : Chạy ngầm ở khay hệ thống (minimized)")
    print("=" * 65)

    # 2. Khởi chạy biểu tượng Khay hệ thống (System Tray)
    tray = SystemTrayManager(
        port=active_port,
        session_token=token,
        workspace_dir=config.workspace_dir,
        data_dir=config.data_dir,
        on_mode_change=lambda mode: router.set_mode(mode),  # type: ignore
        get_current_mode=lambda: router.mode,
    )
    tray.start()

    # 3. Mở cửa sổ giao diện nếu không yêu cầu chạy ngầm (minimized) hoặc no_browser
    if not no_browser and not minimized:
        def _open_window() -> None:
            time.sleep(1.2)
            launch_desktop_window(port=active_port, session_token=token)

        threading.Thread(target=_open_window, daemon=True).start()

    try:
        # Chỉ lắng nghe trên 127.0.0.1 (localhost)
        uvicorn.run(app, host="127.0.0.1", port=active_port, log_level="warning")
        return 0
    except Exception as err:
        print(f"[LỖI KHỞI ĐỘNG MÁY CHỦ] {err}")
        return 1
    finally:
        tray.stop()
        release_instance(config.data_dir)


def cli() -> None:
    """Hàm điểm đầu (entry point) khi chạy lệnh `assistant` trên terminal."""
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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

    # Lệnh ui
    ui_parser = subparsers.add_parser("ui", help="Khởi động giao diện ứng dụng Desktop (mặc định)")
    ui_parser.add_argument("--port", type=int, default=None, help="Cổng chạy giao diện (mặc định từ config)")
    ui_parser.add_argument("--no-browser", action="store_true", help="Không tự động mở cửa sổ trình duyệt")
    ui_parser.add_argument(
        "--minimized",
        "--background",
        action="store_true",
        help="Khởi động ngầm ở khay hệ thống, không tự mở cửa sổ chat",
    )

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
    elif args.command == "ui" or args.command is None:
        port_val = getattr(args, "port", None)
        no_browser_val = getattr(args, "no_browser", False)
        minimized_val = getattr(args, "minimized", False)
        sys.exit(run_ui(port=port_val, no_browser=no_browser_val, minimized=minimized_val))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    cli()
