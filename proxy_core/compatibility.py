from typing import Any, List

from proxy_core.capabilities import get_backend_capabilities
from proxy_core.config import UNSUPPORTED_THINKING_BEHAVIOR
from proxy_core.models import MessagesRequest


class RequestCompatibilityError(Exception):
    """Raised when the Anthropic request cannot be represented safely for the target backend."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

def collect_gemini_schema_incompatibilities(schema: Any, path: str = "$") -> List[str]:
    issues: List[str] = []

    if isinstance(schema, dict):
        if "additionalProperties" in schema:
            issues.append(f"{path}: Gemini tool schema does not support 'additionalProperties'")
        if "default" in schema:
            issues.append(f"{path}: Gemini tool schema does not support 'default'")
        if schema.get("type") == "string" and "format" in schema:
            allowed_formats = {"enum", "date-time"}
            if schema["format"] not in allowed_formats:
                issues.append(f"{path}: Gemini tool schema does not support string format '{schema['format']}'")

        for key, value in schema.items():
            issues.extend(collect_gemini_schema_incompatibilities(value, f"{path}.{key}"))
    elif isinstance(schema, list):
        for index, item in enumerate(schema):
            issues.extend(collect_gemini_schema_incompatibilities(item, f"{path}[{index}]"))

    return issues


def validate_request_compatibility(anthropic_request: MessagesRequest) -> None:
    capabilities = get_backend_capabilities(anthropic_request.model)

    if anthropic_request.thinking and not capabilities.supports_thinking:
        if UNSUPPORTED_THINKING_BEHAVIOR == "drop":
            anthropic_request.thinking = None
        else:
            raise RequestCompatibilityError(
                "The 'thinking' option is only supported when proxying to Anthropic models. "
                "Set UNSUPPORTED_THINKING_BEHAVIOR=drop to ignore it automatically."
            )

    if anthropic_request.top_k is not None and not capabilities.supports_top_k:
        raise RequestCompatibilityError("The 'top_k' option is only supported when proxying to Anthropic models.")

    if anthropic_request.tool_choice:
        choice_type = anthropic_request.tool_choice.get("type")
        if choice_type not in {"auto", "any", "tool"}:
            raise RequestCompatibilityError(
                f"Unsupported tool_choice type '{choice_type}'. Expected one of: auto, any, tool."
            )
        if choice_type == "tool" and not anthropic_request.tool_choice.get("name"):
            raise RequestCompatibilityError("tool_choice.type='tool' requires a tool name.")

    if anthropic_request.tools:
        for tool in anthropic_request.tools:
            schema = tool.input_schema or {}
            if schema.get("type") != "object":
                raise RequestCompatibilityError(
                    f"Tool '{tool.name}' must use a JSON Schema object as input_schema."
                )

            if capabilities.enforces_gemini_tool_schema_rules:
                issues = collect_gemini_schema_incompatibilities(schema)
                if issues:
                    issue_preview = "; ".join(issues[:3])
                    raise RequestCompatibilityError(
                        f"Tool '{tool.name}' is incompatible with the Gemini adapter: {issue_preview}."
                    )

    for msg in anthropic_request.messages:
        content = msg.content
        if isinstance(content, str):
            continue

        for block in content:
            block_type = getattr(block, "type", None)

            if msg.role == "user" and block_type == "tool_use":
                raise RequestCompatibilityError(
                    "User messages cannot contain tool_use blocks. tool_use must come from the assistant."
                )

            if block_type == "image" and not capabilities.supports_image_input:
                raise RequestCompatibilityError(
                    f"Image content blocks are not supported for {capabilities.family} backends in this proxy yet."
                )
