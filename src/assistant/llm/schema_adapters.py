"""Chuyển đổi JSON Schema của các công cụ sang định dạng chuẩn của Gemini và Ollama.

Tuân thủ:
- Gemini API (google-genai mới): types.Tool(function_declarations=[...])
- Ollama API (OpenAI compatible): {"type": "function", "function": {...}}
"""

from typing import Any


def to_gemini_tools(tool_schemas: list[dict[str, Any]]) -> list[Any]:
    """Chuyển đổi danh sách schema sang định dạng types.Tool của SDK google-genai."""
    try:
        from google.genai import types

        declarations: list[types.FunctionDeclaration] = []
        for t in tool_schemas:
            # Chuyển đổi parameters schema sang Schema object của google-genai nếu cần
            # types.FunctionDeclaration chấp nhận dict schema chuẩn
            declarations.append(
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t.get("parameters"),
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
                        "parameters": t.get("parameters"),
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
