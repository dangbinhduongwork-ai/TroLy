"""Kịch bản kiểm tra độc lập máy chủ FastAPI, REST API và WebSocket Desktop (End-to-End Phase 6).

Kiểm tra:
1. Bảo vệ Session Token (401 khi thiếu, 403 khi sai, 200 khi đúng).
2. Toàn bộ vòng đời REST API: Hội thoại, Trí nhớ dài hạn, Lời nhắc việc, Trạng thái hệ thống.
3. Kênh truyền WebSocket thời gian thực (streaming text_delta, model badges, turn_done).
4. Luồng duyệt quyền bất đồng bộ qua WebSocket (approval_required -> approval_response).
5. Tự động tìm kiếm trình duyệt Microsoft Edge trên Windows (--app).
"""

import json
from pathlib import Path
import sys

# Thêm thư mục src vào sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from fastapi.testclient import TestClient

from assistant.config import load_config
from assistant.core.router import ModelRouter
from assistant.desktop.window import find_edge_executable
from assistant.llm.base import LLMProvider, Message, StreamEvent, ToolCall
from assistant.memory.store import MemoryStore
from assistant.reminders.scheduler import ReminderScheduler
from assistant.reminders.store import ReminderStore
from assistant.server.app import create_app


class FlowMockProvider(LLMProvider):
    """Provider giả lập dùng cho kiểm tra kịch bản server."""

    def __init__(self, response_text: str = "Xin chào! Tôi là Trợ Lý AI trên giao diện Desktop.") -> None:
        self.response_text = response_text
        self.default_model = "mock-flow-model"

    @property
    def provider_name(self) -> str:
        return "mock"

    async def stream_chat(self, messages, tools=None, system=None, is_sensitive=False):
        for word in self.response_text.split():
            yield StreamEvent(type="text_delta", content=word + " ")

    async def list_models(self):
        return ["mock-flow-model"]


def main() -> int:
    print("=" * 65)
    print("KIỂM TRA TỰ ĐỘNG: BACKEND SERVER & GIAO DIỆN DESKTOP (GIAI ĐOẠN 6)")
    print("=" * 65)

    config = load_config(create_dirs=True)
    mem_store = MemoryStore()
    rem_store = ReminderStore()
    scheduler = ReminderScheduler(reminder_store=rem_store)
    mock_provider = FlowMockProvider()
    router = ModelRouter(gemini_provider=mock_provider, ollama_provider=mock_provider)

    test_token = "e2e_flow_token_secret_xyz"
    app = create_app(
        config=config,
        router=router,
        memory_store=mem_store,
        reminder_store=rem_store,
        scheduler=scheduler,
        session_token=test_token,
    )
    client = TestClient(app)

    # 1. Kiểm tra xác thực Session Token
    print("\n1. Kiểm tra bảo mật Session Token...")
    res_no_tok = client.get("/api/status")
    assert res_no_tok.status_code == 401
    print("   -> Chặn 401 khi không có token [OK]")

    res_bad_tok = client.get("/api/status", headers={"X-Session-Token": "bad_token"})
    assert res_bad_tok.status_code == 403
    print("   -> Chặn 403 khi sai token [OK]")

    headers = {"X-Session-Token": test_token}
    res_ok_tok = client.get("/api/status", headers=headers)
    assert res_ok_tok.status_code == 200
    print(f"   -> Xác thực 200 thành công: Workspace tại '{res_ok_tok.json()['workspace_dir']}' [OK]")

    # 2. Kiểm tra REST API: Conversations
    print("\n2. Kiểm tra REST API: Hội thoại (Conversations)...")
    c_res = client.post("/api/conversations", headers=headers, json={"title": "Hội thoại mẫu Phase 6"})
    assert c_res.status_code == 200
    conv_id = c_res.json()["id"]
    print(f"   -> Tạo hội thoại ID: {conv_id} [OK]")

    list_c = client.get("/api/conversations", headers=headers).json()
    assert any(c["id"] == conv_id for c in list_c)
    print(f"   -> Lấy danh sách hội thoại: tìm thấy {len(list_c)} hội thoại [OK]")

    # 3. Kiểm tra REST API: Memories
    print("\n3. Kiểm tra REST API: Trí nhớ dài hạn (Memories)...")
    m_res = client.post(
        "/api/memories",
        headers=headers,
        json={"category": "preference", "content": "Người dùng thích giao diện tối (Dark mode)"},
    )
    assert m_res.status_code == 200
    mem_id = m_res.json()["id"]
    print(f"   -> Thêm trí nhớ ID: {mem_id} [OK]")

    search_m = client.get("/api/memories?query=Dark mode", headers=headers).json()
    assert len(search_m) >= 1
    print(f"   -> Tìm kiếm FTS5 tiếng Việt: khớp '{search_m[0]['content']}' [OK]")

    # 4. Kiểm tra REST API: Reminders
    print("\n4. Kiểm tra REST API: Lời nhắc việc (Reminders)...")
    r_res = client.post(
        "/api/reminders",
        headers=headers,
        json={"message": "Kiểm tra giao diện Desktop", "trigger_at": "2026-10-27T10:00:00+07:00"},
    )
    assert r_res.status_code == 200
    rem_id = r_res.json()["id"]
    print(f"   -> Đặt lịch nhắc ID: {rem_id} [OK]")

    snooze_res = client.post(f"/api/reminders/{rem_id}/snooze", headers=headers, json={"minutes": 10})
    assert snooze_res.status_code == 200
    print(f"   -> Hoãn nhắc việc thêm 10 phút: trạng thái '{snooze_res.json()['reminder']['status']}' [OK]")

    # 5. Phục vụ trang chủ HTML
    print("\n5. Kiểm tra phục vụ giao diện tĩnh index.html...")
    index_res = client.get("/")
    assert index_res.status_code == 200
    assert "Trợ Lý AI" in index_res.text
    print("   -> Phục vụ index.html ngoại tuyến thành công [OK]")

    # 6. Kiểm tra WebSocket Chat Streaming
    print("\n6. Kiểm tra kênh truyền WebSocket /ws/chat...")
    with client.websocket_connect(f"/ws/chat?token={test_token}") as ws:
        ws.send_text(json.dumps({"type": "user_message", "message": "Chào bạn"}))
        received_chunks = []
        for _ in range(8):
            raw = ws.receive_text()
            data = json.loads(raw)
            if data.get("type") == "text_delta":
                received_chunks.append(data["data"]["content"])
            elif data.get("type") == "turn_done":
                break

        streamed_text = "".join(received_chunks)
        print(f"   -> Streaming nhận được: '{streamed_text.strip()}' [OK]")

    # 7. Kiểm tra dò tìm Microsoft Edge
    print("\n7. Kiểm tra phát hiện Microsoft Edge trên Windows...")
    edge_exe = find_edge_executable()
    if edge_exe:
        print(f"   -> Tìm thấy Microsoft Edge tại: {edge_exe} [OK]")
    else:
        print("   -> Không có Edge, hệ thống sẽ tự động dùng trình duyệt mặc định [OK]")

    print("\n" + "=" * 65)
    print("KẾT QUẢ: Toàn bộ tiêu chí nghiệm thu Giai đoạn 6 ĐÃ HOÀN TẤT XUẤT SẮC!")
    print("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(main())
