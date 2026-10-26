"""Đăng ký công cụ (Tool Registry) bằng decorator và tự động sinh JSON Schema từ Type Hints.

Mỗi công cụ khi đăng ký sẽ tự động khai báo:
- Tên và mô tả công dụng.
- Mức quyền hạn an toàn (READ, WRITE_SAFE, CONFIRM).
- Đánh dấu nếu kết quả trả về là dữ liệu bên ngoài (is_external_content).
- JSON Schema chuẩn hoá cho danh sách tham số.
"""

from collections.abc import Callable
from dataclasses import dataclass
import inspect
from typing import Any, get_args, get_origin, get_type_hints

from assistant.safety.permissions import PermissionLevel


def _type_to_json_schema(py_type: Any) -> dict[str, Any]:
    """Chuyển đổi kiểu dữ liệu Python thành JSON Schema type."""
    origin = get_origin(py_type)

    # Xử lý kiểu Union hoặc Optional (Union[T, None])
    if origin is not None:
        args = get_args(py_type)
        # Bỏ qua kiểu NoneType trong Optional
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _type_to_json_schema(non_none_args[0])
        elif origin is list:
            item_schema = _type_to_json_schema(args[0]) if args else {"type": "string"}
            return {"type": "array", "items": item_schema}
        elif origin is dict:
            return {"type": "object"}

    if py_type is str:
        return {"type": "string"}
    elif py_type is int:
        return {"type": "integer"}
    elif py_type is float:
        return {"type": "number"}
    elif py_type is bool:
        return {"type": "boolean"}
    elif py_type in (list, list):
        return {"type": "array", "items": {"type": "string"}}
    elif py_type in (dict, dict):
        return {"type": "object"}

    return {"type": "string"}


def generate_parameters_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """Tự động phân tích hàm và sinh JSON Schema từ type hints và default values."""
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        # Bỏ qua tham số ngữ cảnh nội bộ nếu có
        if param_name in ("self", "context", "approval_callback", "on_event"):
            continue

        param_type = type_hints.get(param_name, str)
        schema = _type_to_json_schema(param_type)

        # Ghi nhận mô tả từ docstring nếu có (hoặc tên tham số)
        schema["description"] = f"Tham số {param_name}"

        # Kiểm tra tham số bắt buộc (không có giá trị mặc định)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            schema["default"] = param.default

        properties[param_name] = schema

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


@dataclass
class ToolDefinition:
    """Định nghĩa chi tiết của một công cụ đã đăng ký."""

    name: str
    description: str
    func: Callable[..., Any]
    permission_level: PermissionLevel
    is_external_content: bool
    parameters_schema: dict[str, Any]

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Thực thi công cụ và trả về kết quả chuẩn {ok, data, error, truncated}."""
        try:
            res = self.func(**kwargs)
            if inspect.isawaitable(res):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop is not None and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        res = pool.submit(asyncio.run, res).result()
                else:
                    res = asyncio.run(res)

            if isinstance(res, dict) and "ok" in res:
                return res
            return {"ok": True, "data": res, "error": None, "truncated": False}
        except Exception as err:
            return {"ok": False, "data": None, "error": str(err), "truncated": False}


class ToolRegistry:
    """Kho lưu trữ và quản lý toàn bộ các công cụ của hệ thống."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_level: PermissionLevel = PermissionLevel.READ,
        is_external_content: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator đăng ký một hàm thành công cụ của Trợ lý AI."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or func.__name__
            tool_desc = (description or func.__doc__ or f"Công cụ {tool_name}").strip()
            param_schema = generate_parameters_schema(func)

            tool_def = ToolDefinition(
                name=tool_name,
                description=tool_desc,
                func=func,
                permission_level=permission_level,
                is_external_content=is_external_content,
                parameters_schema=param_schema,
            )
            self._tools[tool_name] = tool_def
            return func

        return decorator

    def get(self, name: str) -> ToolDefinition | None:
        """Lấy định nghĩa công cụ theo tên."""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """Lấy toàn bộ danh sách công cụ đã đăng ký."""
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        """Trả về danh sách schema của tất cả các công cụ."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
                "permission_level": t.permission_level.value,
                "is_external_content": t.is_external_content,
            }
            for t in self._tools.values()
        ]


# Registry toàn cục dùng chung cho toàn bộ dự án
default_tool_registry = ToolRegistry()
register_tool = default_tool_registry.register
