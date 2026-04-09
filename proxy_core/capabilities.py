from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class BackendCapabilities:
    family: str
    supports_thinking: bool
    supports_top_k: bool
    supports_image_input: bool
    enforces_gemini_tool_schema_rules: bool
    supports_reasoning_effort: bool


BACKEND_CAPABILITIES: Dict[str, BackendCapabilities] = {
    "openai": BackendCapabilities(
        family="openai",
        supports_thinking=False,
        supports_top_k=False,
        supports_image_input=False,
        enforces_gemini_tool_schema_rules=False,
        supports_reasoning_effort=True,
    ),
    "gemini": BackendCapabilities(
        family="gemini",
        supports_thinking=False,
        supports_top_k=False,
        supports_image_input=True,
        enforces_gemini_tool_schema_rules=True,
        supports_reasoning_effort=False,
    ),
    "anthropic": BackendCapabilities(
        family="anthropic",
        supports_thinking=True,
        supports_top_k=True,
        supports_image_input=True,
        enforces_gemini_tool_schema_rules=False,
        supports_reasoning_effort=False,
    ),
    "unknown": BackendCapabilities(
        family="unknown",
        supports_thinking=False,
        supports_top_k=False,
        supports_image_input=False,
        enforces_gemini_tool_schema_rules=False,
        supports_reasoning_effort=False,
    ),
}


def get_backend_family(model: str) -> str:
    if model.startswith("openai/"):
        return "openai"
    if model.startswith("gemini/"):
        return "gemini"
    if model.startswith("anthropic/"):
        return "anthropic"
    return "unknown"


def get_backend_capabilities(model: str) -> BackendCapabilities:
    return BACKEND_CAPABILITIES[get_backend_family(model)]
