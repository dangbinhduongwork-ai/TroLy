"""Kiểm thử tự động cho hệ thống Quản lý hội thoại và Danh mục trí nhớ động."""

from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import pytest

from assistant.config import Config
from assistant.memory.store import MemoryStore
from assistant.server.app import create_app


@pytest.fixture
def test_db_store(tmp_path: Path) -> MemoryStore:
    """Fixture tạo MemoryStore trên database tạm thời."""
    db_file = tmp_path / "test_store.db"
    store = MemoryStore(db_path=db_file)
    return store


def test_categories_init_and_seed(test_db_store: MemoryStore) -> None:
    """Kiểm tra khởi tạo và tự động nạp 4 danh mục mặc định."""
    cats = test_db_store.list_categories()
    assert len(cats) >= 4
    names = [c["name"] for c in cats]
    assert "preference" in names
    assert "project" in names
    assert "naming_rule" in names
    assert "general" in names


def test_add_and_update_category(test_db_store: MemoryStore) -> None:
    """Kiểm tra thêm mới và cập nhật danh mục trí nhớ."""
    cat_id = test_db_store.add_category(
        name="finance",
        label="Tài chính & Chi tiêu",
        icon="briefcase",
        color="#10b981",
    )
    assert cat_id is not None

    cat = test_db_store.get_category_by_id(cat_id)
    assert cat is not None
    assert cat["name"] == "finance"
    assert cat["label"] == "Tài chính & Chi tiêu"

    # Cập nhật nhãn và màu
    updated = test_db_store.update_category(cat_id, label="Quản lý Tài chính", color="#059669")
    assert updated is True

    cat_after = test_db_store.get_category_by_id(cat_id)
    assert cat_after["label"] == "Quản lý Tài chính"
    assert cat_after["color"] == "#059669"


def test_delete_category_safe_migration(test_db_store: MemoryStore) -> None:
    """Kiểm tra xóa danh mục an toàn: chuyển toàn bộ dữ kiện sang 'general'."""
    cat_id = test_db_store.add_category(
        name="temporary",
        label="Tạm thời",
        icon="tag",
        color="#f59e0b",
    )
    # Thêm một dữ kiện thuộc danh mục 'temporary'
    mem_id = test_db_store.add_memory(category="temporary", content="Dữ liệu tạm thời cần chuyển giao")

    # Xóa danh mục 'temporary'
    deleted = test_db_store.delete_category("temporary")
    assert deleted is True

    # Kiểm tra dữ kiện đã được chuyển sang 'general'
    mem_after = test_db_store.get_memory(mem_id)
    assert mem_after is not None
    assert mem_after["category"] == "general"

    # Chặn xóa danh mục mặc định 'general'
    cannot_delete_general = test_db_store.delete_category("general")
    assert cannot_delete_general is False


def test_conversation_rename_and_save_to_memory_api(tmp_path: Path) -> None:
    """Kiểm tra API đổi tên hội thoại và trích xuất lưu vào trí nhớ."""
    cfg = Config(
        workspace_dir=tmp_path / "ws",
        data_dir=tmp_path / "data",
    )
    cfg.workspace_dir.mkdir(parents=True, exist_ok=True)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(cfg)
    client = TestClient(app)

    # 1. Lấy session token
    status_resp = client.get("/api/status")
    assert status_resp.status_code == 200

    token_file = cfg.data_dir / "session.token"
    token = token_file.read_text(encoding="utf-8").strip()
    headers = {"X-Session-Token": token}

    # 2. Tạo hội thoại mới
    conv_resp = client.post(
        "/api/conversations",
        headers=headers,
        json={"title": "Hội thoại thiết kế", "is_sensitive": False},
    )
    assert conv_resp.status_code == 200
    conv_id = conv_resp.json()["id"]

    # 3. Đổi tên hội thoại qua PUT /api/conversations/{id}
    put_resp = client.put(
        f"/api/conversations/{conv_id}",
        headers=headers,
        json={"title": "Thiết kế hệ thống v2"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["ok"] is True
    assert put_resp.json()["conversation"]["title"] == "Thiết kế hệ thống v2"

    # 4. Thêm tin nhắn vào cuộc hội thoại
    from assistant.memory.store import MemoryStore

    store = MemoryStore(db_path=cfg.data_dir / "assistant.db")
    store.add_message(conv_id, role="user", content="Tôi muốn dùng kiến trúc microservices và Python 3.12")
    store.add_message(conv_id, role="assistant", content="Đã hiểu, chúng ta sẽ áp dụng Python 3.12")

    # 5. Lưu vào trí nhớ qua POST /api/conversations/{id}/save-to-memory
    save_resp = client.post(f"/api/conversations/{conv_id}/save-to-memory", headers=headers)
    assert save_resp.status_code == 200
    save_data = save_resp.json()
    assert save_data["ok"] is True
    assert save_data["count"] >= 1

    # Kiểm tra mục trí nhớ xuất hiện trong database
    memories = store.list_memories()
    assert len(memories) >= 1


def test_category_rest_api_crud(tmp_path: Path) -> None:
    """Kiểm tra toàn bộ CRUD danh mục qua REST API."""
    cfg = Config(
        workspace_dir=tmp_path / "ws",
        data_dir=tmp_path / "data",
    )
    cfg.workspace_dir.mkdir(parents=True, exist_ok=True)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(cfg)
    client = TestClient(app)

    token = (cfg.data_dir / "session.token").read_text(encoding="utf-8").strip()
    headers = {"X-Session-Token": token}

    # GET categories
    get_resp = client.get("/api/memories/categories", headers=headers)
    assert get_resp.status_code == 200
    assert len(get_resp.json()) >= 4

    # POST new category
    post_resp = client.post(
        "/api/memories/categories",
        headers=headers,
        json={"name": "study", "label": "Học tập", "icon": "code", "color": "#8b5cf6"},
    )
    assert post_resp.status_code == 200
    cat_id = post_resp.json()["id"]

    # PUT update category
    put_resp = client.put(
        f"/api/memories/categories/{cat_id}",
        headers=headers,
        json={"label": "Nghiên cứu & Học tập", "color": "#7c3aed"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["category"]["label"] == "Nghiên cứu & Học tập"

    # DELETE category
    del_resp = client.delete(f"/api/memories/categories/{cat_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True

    # DELETE general (bị chặn)
    cats = client.get("/api/memories/categories", headers=headers).json()
    general_cat = next(c for c in cats if c["name"] == "general")
    del_gen_resp = client.delete(f"/api/memories/categories/{general_cat['id']}", headers=headers)
    assert del_gen_resp.status_code == 400
