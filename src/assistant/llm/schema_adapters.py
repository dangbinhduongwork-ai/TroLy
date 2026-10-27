"""Chuyển đổi JSON Schema của các công cụ sang định dạng chuẩn của Gemini và Ollama.

Tuân thủ:
- Gemini API (google-genai mới): types.Tool(function_declarations=[...])
- Ollama API (OpenAI compatible): {"type": "function", "function": {...}}
"""

from typing import Any


def _clean_schema_for_gemini(raw_schema: dict[str, Any] | None) -> dict[str, Any] | None:
    """Làm sạch và chuẩn hoá JSON Schema để tương thích hoàn toàn với Google Gemini API.

    Quy tắc bắt buộc của Gemini API (OpenAPI 3.0 subset):
    1. Không truyền `default` (Gemini OpenAPI không hỗ trợ thuộc tính default, truyền null gây 400).
    2. Không truyền `required: []` (nếu mảng required rỗng, phải xoá trường required).
    3. Nếu properties rỗng ({}), parameters phải là None (Gemini từ chối schema object rỗng).
    4. Chỉ giữ lại các trường hợp lệ: type, description, properties, required, items, enum.
    """
    if not raw_schema or not isinstance(raw_schema, dict):
        return None

    properties = raw_schema.get("properties")
    if not properties or not isinstance(properties, dict) or len(properties) == 0:
        return None

    cleaned_props: dict[str, Any] = {}
    for p_name, p_val in properties.items():
        if not isinstance(p_val, dict):
            cleaned_props[p_name] = {"type": "string", "description": f"Tham số {p_name}"}
            continue

        prop_clean: dict[str, Any] = {}
        # Chuẩn hoá type
        p_type = p_val.get("type", "string")
        prop_clean["type"] = str(p_type).lower()

        # Mô tả
        if "description" in p_val and p_val["description"]:
            prop_clean["description"] = str(p_val["description"])

        # Items cho array
        if "items" in p_val and isinstance(p_val["items"], dict):
            cleaned_items = _clean_schema_for_gemini(p_val["items"]) or {"type": "string"}
            prop_clean["items"] = cleaned_items

        # Enum nếu có
        if "enum" in p_val and isinstance(p_val["enum"], list):
            prop_clean["enum"] = p_val["enum"]

        # TUYỆT ĐỐI BỎ "default" vì Gemini OpenAPI không hỗ trợ
        cleaned_props[p_name] = prop_clean

    if not cleaned_props:
        return None

    cleaned_required = [
        r for r in raw_schema.get("required", [])
        if isinstance(r, str) and r in cleaned_props
    ]

    result: dict[str, Any] = {
        "type": "object",
        "properties": cleaned_props,
    }
    if cleaned_required:
        result["required"] = cleaned_required

    return result


def to_gemini_tools(tool_schemas: list[dict[str, Any]]) -> list[Any]:
    """Chuyển đổi danh sách schema sang định dạng types.Tool của SDK google-genai."""
    try:
        from google.genai import types

        declarations: list[types.FunctionDeclaration] = []
        for t in tool_schemas:
            clean_params = _clean_schema_for_gemini(t.get("parameters"))
            declarations.append(
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=clean_params,
                )
            )
        return [types.Tool(function_declarations=declarations)]
    except ImportError:
        # Dự phòng trả về dict nếu chưa cài đặt thư viện google-genai
        return [
            {
                "function_declarations": [
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": _clean_schema_for_gemini(t.get("parameters")),
                    }
                    for t in tool_schemas
                ]
            }
        ]


def to_ollama_tools(tool_schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chuyển đổi danh sách schema sang định dạng Function Calling chuẩn OpenAI/Ollama."""
    tools: list[dict[str, Any]] = []
    for t in tool_schemas:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("parameters", {}),
                },
            }
        )
    return tools
