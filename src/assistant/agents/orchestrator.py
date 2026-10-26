"""Bộ điều phối uỷ quyền công việc cho các Agent chuyên trách (Multi-Agent Orchestrator).

Nguyên tắc:
- Không dùng framework cồng kềnh.
- Chạy một vòng lặp con (child AgentLoop) với ToolRegistry được giới hạn nghiêm ngặt
  chỉ chứa các công cụ nằm trong allowed_tools của Agent đó (Nguyên tắc đặc quyền tối thiểu).
- Mọi yêu cầu phê duyệt phân quyền (CONFIRM) từ agent con vẫn đi qua người dùng như bình thường.
- Kết quả được tổng hợp và trả về cho Agent chính.
"""

import contextvars
from collections.abc import Callable
from typing import Any

from assistant.agents.spec import SPECIALIZED_AGENTS
from assistant.core.context import ConversationContext
from assistant.core.prompts import get_system_prompt
from assistant.core.router import ModelRouter
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import ToolRegistry, default_tool_registry, register_tool

_global_router: ModelRouter | None = None
_global_approval_callback: Callable[..., Any] | None = None
_orchestrator_approval_cb: contextvars.ContextVar[Callable[..., Any] | None] = contextvars.ContextVar(
    "_orchestrator_approval_cb", default=None
)


def set_orchestrator_router(router: ModelRouter) -> None:
    """Thiết lập tham chiếu router dùng chung cho Orchestrator."""
    global _global_router
    _global_router = router


def get_orchestrator_router() -> ModelRouter:
    """Lấy router dùng chung (tự động khởi tạo nếu chưa có)."""
    global _global_router
    if _global_router is None:
        _global_router = ModelRouter()
    return _global_router


def set_orchestrator_approval_callback(cb: Callable[..., Any] | None) -> None:
    """Thiết lập callback duyệt quyền dùng chung cho Orchestrator."""
    global _global_approval_callback
    _global_approval_callback = cb
    _orchestrator_approval_cb.set(cb)


def get_orchestrator_approval_callback() -> Callable[..., Any] | None:
    """Lấy callback duyệt quyền từ ContextVar hiện tại hoặc fallback biến toàn cục."""
    cb = _orchestrator_approval_cb.get()
    if cb is not None:
        return cb
    return _global_approval_callback


async def run_subagent(
    agent_name: str,
    task_description: str,
    router: ModelRouter | None = None,
    is_sensitive: bool = False,
    approval_callback: Callable[..., Any] | None = None,
    on_event: Callable[[str, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Thực thi một Agent chuyên trách với registry công cụ bị thu hẹp theo đặc quyền tối thiểu."""
    spec = SPECIALIZED_AGENTS.get(agent_name)
    if not spec:
        available = ", ".join(SPECIALIZED_AGENTS.keys())
        return {
            "ok": False,
            "data": None,
            "error": f"Không tìm thấy Agent chuyên trách '{agent_name}'. Các Agent khả dụng: {available}",
            "truncated": False,
        }

    active_router = router or get_orchestrator_router()
    active_approval = approval_callback or get_orchestrator_approval_callback()

    # 1. Tạo ToolRegistry bị thu hẹp (Sandboxed Registry) CHỈ chứa allowed_tools
    sandboxed_registry = ToolRegistry()
    for t_name in spec.allowed_tools:
        tool_def = default_tool_registry.get(t_name)
        if tool_def:
            sandboxed_registry.register(tool_def)

    # 2. Tạo ngữ cảnh riêng cho agent con
    child_context = ConversationContext(max_tokens=3000)
    child_context.add_user_message(task_description)

    # 3. Tạo system prompt riêng cho agent con
    child_system_prompt = get_system_prompt(
        custom_instructions=f"{spec.system_prompt}\nNhiệm vụ cụ thể: {task_description}"
    )

    # 4. Khởi tạo vòng lặp agent con với registry giới hạn và approval_callback
    from assistant.core.agent_loop import AgentLoop

    child_agent_loop = AgentLoop(
        router=active_router,
        registry=sandboxed_registry,
        approval_callback=active_approval,
        max_steps=spec.max_steps,
    )

    accumulated_chunks: list[str] = []
    try:
        async for event in child_agent_loop.run_turn(
            context=child_context,
            system_prompt=child_system_prompt,
            is_sensitive=is_sensitive,
            on_event=on_event,
        ):
            if event.type == "text_delta" and isinstance(event.content, str):
                accumulated_chunks.append(event.content)

        summary = "".join(accumulated_chunks).strip()
        if not summary:
            summary = "Agent đã thực thi xong tác vụ."

        return {
            "ok": True,
            "data": {
                "agent_name": agent_name,
                "task": task_description,
                "summary": summary,
            },
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {
            "ok": False,
            "data": None,
            "error": f"Lỗi khi thực thi agent '{agent_name}': {err}",
            "truncated": False,
        }


@register_tool(
    name="delegate_to_agent",
    description=(
        "Uỷ quyền một nhiệm vụ phức tạp nhiều bước cho một Agent chuyên trách. "
        "Các agent_name khả dụng: "
        "'file_organizer_agent' (tìm kiếm/sắp xếp thư mục), "
        "'document_agent' (xử lý PDF/Word/Excel), "
        "'research_agent' (tra cứu web/tổng hợp thông tin), "
        "'coder_agent' (lập trình Python/kiểm thử)."
    ),
    permission_level=PermissionLevel.READ,
)
async def delegate_to_agent(
    agent_name: str,
    task_description: str,
    approval_callback: Callable[..., Any] | None = None,
    on_event: Callable[[str, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Công cụ cho Agent chính gọi Agent chuyên trách (hỗ trợ bất đồng bộ trong AgentLoop)."""
    active_approval = approval_callback or get_orchestrator_approval_callback()
    return await run_subagent(
        agent_name=agent_name,
        task_description=task_description,
        approval_callback=active_approval,
        on_event=on_event,
    )
