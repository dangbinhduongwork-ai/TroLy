"""Script kiểm tra khả năng gọi công cụ (Tool Calling) của một model cụ thể.

Cách dùng:
    python scripts/check_tool_calling.py --model qwen2.5:7b
    python scripts/check_tool_calling.py --model gemini-2.5-flash --provider gemini

Yêu cầu model: "tạo file hello.txt có nội dung xin chào trong workspace".
Kiểm tra xem file có thực sự xuất hiện không và in ra: PASS hoặc FAIL.
"""

import argparse
import asyncio
import sys

from assistant.config import Config, load_config
from assistant.core.agent_loop import AgentLoop
from assistant.core.context import ConversationContext
from assistant.core.prompts import get_system_prompt
from assistant.core.router import ModelRouter
from assistant.llm.base import LLMProvider
from assistant.llm.gemini_provider import GeminiProvider
from assistant.llm.ollama_provider import OllamaProvider
from assistant.safety.paths import resolve_in_workspace
import assistant.tools  # noqa: F401


async def check_tool_calling(model_name: str, provider_name: str | None = None) -> bool:
    """Thực hiện bài test gọi công cụ tạo file hello.txt."""
    config = load_config(create_dirs=True)

    # 1. Dọn dẹp file hello.txt nếu đã có sẵn từ trước
    try:
        hello_file = resolve_in_workspace("hello.txt", config.workspace_dir)
        if hello_file.exists():
            hello_file.unlink()
    except Exception:
        pass

    # 2. Xác định provider
    if provider_name is None:
        provider_name = "gemini" if "gemini" in model_name.lower() else "ollama"

    print(f"[TEST TOOL CALLING] Đang kiểm tra model: {model_name} (Provider: {provider_name.upper()})")

    # Tạo config ghi đè model cho bài test
    test_config = Config(
        workspace_dir=config.workspace_dir,
        data_dir=config.data_dir,
        timezone=config.timezone,
        gemini_model=model_name if provider_name == "gemini" else config.gemini_model,
        local_model=model_name if provider_name == "ollama" else config.local_model,
        ollama_host=config.ollama_host,
        daily_soft_limit=config.daily_soft_limit,
        max_context_tokens=config.max_context_tokens,
        network_cache_seconds=config.network_cache_seconds,
        ui_port=config.ui_port,
        log_level="INFO",
    )

    provider: LLMProvider
    if provider_name == "gemini":
        provider = GeminiProvider(test_config)
    else:
        provider = OllamaProvider(test_config)

    # Khởi tạo Router ép buộc dùng provider tương ứng
    router = ModelRouter(
        config=test_config,
        gemini_provider=provider if provider_name == "gemini" else None,
        ollama_provider=provider if provider_name == "ollama" else None,
    )
    router.set_mode(provider_name)  # type: ignore[arg-type]

    # Callback tự động duyệt cho bài test kịch bản tự động
    def auto_approve(tool_name: str, args: dict, reason: str) -> bool:
        print(f"  -> [Tự động duyệt]: {tool_name} {args}")
        return True

    agent_loop = AgentLoop(
        router=router,
        approval_callback=auto_approve,
        max_steps=5,
    )

    context = ConversationContext()
    context.add_user_message("Hãy tạo file hello.txt có nội dung 'xin chào' trong workspace.")

    sys_prompt = get_system_prompt(timezone_str=config.timezone)

    print("  -> Đang gửi yêu cầu tới mô hình...")
    try:
        async for event in agent_loop.run_turn(context=context, system_prompt=sys_prompt):
            if event.type == "text_delta" and isinstance(event.content, str):
                sys.stdout.write(event.content)
                sys.stdout.flush()
        print()
    except Exception as err:
        print(f"\n[LỖI THỰC THI] {err}")
        print("FAIL")
        return False

    # 3. Xác minh file hello.txt có xuất hiện trong workspace không
    try:
        hello_file = resolve_in_workspace("hello.txt", config.workspace_dir)
        if hello_file.exists():
            content = hello_file.read_text(encoding="utf-8").strip().lower()
            if "xin chào" in content or "chào" in content or len(content) > 0:
                print("\n========================================================")
                print(f"KẾT QUẢ KIỂM TRA MÔ HÌNH '{model_name}': PASS")
                print("========================================================")
                return True
    except Exception:
        pass

    print("\n========================================================")
    print(f"KẾT QUẢ KIỂM TRA MÔ HÌNH '{model_name}': FAIL")
    print("(Mô hình không gọi công cụ write_file hoặc file không được tạo)")
    print("========================================================")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra khả năng Tool Calling của model")
    parser.add_argument("--model", type=str, required=True, help="Tên model cần kiểm tra (ví dụ: qwen2.5:7b)")
    parser.add_argument("--provider", type=str, choices=["gemini", "ollama"], help="Nhà cung cấp (gemini hoặc ollama)")

    args = parser.parse_args()
    success = asyncio.run(check_tool_calling(args.model, args.provider))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
