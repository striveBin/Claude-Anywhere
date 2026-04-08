import logging
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, field_validator

from proxy_core.config import BIG_MODEL, GEMINI_MODELS, OPENAI_MODELS, PREFERRED_PROVIDER, SMALL_MODEL

logger = logging.getLogger(__name__)


class ContentBlockText(BaseModel):
    type: Literal["text"]
    text: str


class ContentBlockImage(BaseModel):
    type: Literal["image"]
    source: Dict[str, Any]


class ContentBlockToolUse(BaseModel):
    type: Literal["tool_use"]
    id: str
    name: str
    input: Dict[str, Any]


class ContentBlockToolResult(BaseModel):
    type: Literal["tool_result"]
    tool_use_id: str
    content: Union[str, List[Dict[str, Any]], Dict[str, Any], List[Any], Any]


class SystemContent(BaseModel):
    type: Literal["text"]
    text: str


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: Union[str, List[Union[ContentBlockText, ContentBlockImage, ContentBlockToolUse, ContentBlockToolResult]]]


class Tool(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: Dict[str, Any]


class ThinkingConfig(BaseModel):
    enabled: bool = True


def map_model_name(v: str, log_prefix: str) -> str:
    original_model = v
    new_model = v

    logger.debug(
        f"{log_prefix}: Original='{original_model}', Preferred='{PREFERRED_PROVIDER}', BIG='{BIG_MODEL}', SMALL='{SMALL_MODEL}'"
    )

    clean_v = v
    if clean_v.startswith("anthropic/"):
        clean_v = clean_v[10:]
    elif clean_v.startswith("openai/"):
        clean_v = clean_v[7:]
    elif clean_v.startswith("gemini/"):
        clean_v = clean_v[7:]

    mapped = False
    if PREFERRED_PROVIDER == "anthropic":
        new_model = f"anthropic/{clean_v}"
        mapped = True
    elif "haiku" in clean_v.lower():
        if PREFERRED_PROVIDER == "google" and SMALL_MODEL in GEMINI_MODELS:
            new_model = f"gemini/{SMALL_MODEL}"
        else:
            new_model = f"openai/{SMALL_MODEL}"
        mapped = True
    elif "sonnet" in clean_v.lower():
        if PREFERRED_PROVIDER == "google" and BIG_MODEL in GEMINI_MODELS:
            new_model = f"gemini/{BIG_MODEL}"
        else:
            new_model = f"openai/{BIG_MODEL}"
        mapped = True
    elif clean_v in GEMINI_MODELS and not v.startswith("gemini/"):
        new_model = f"gemini/{clean_v}"
        mapped = True
    elif clean_v in OPENAI_MODELS and not v.startswith("openai/"):
        new_model = f"openai/{clean_v}"
        mapped = True

    if mapped:
        logger.debug(f"{log_prefix.replace('VALIDATION', 'MAPPING')}: '{original_model}' -> '{new_model}'")
    else:
        if not v.startswith(("openai/", "gemini/", "anthropic/")):
            logger.warning(f"No prefix or mapping rule for model: '{original_model}'. Using as is.")
        new_model = v

    return new_model


class MessagesRequest(BaseModel):
    model: str
    max_tokens: int
    messages: List[Message]
    system: Optional[Union[str, List[SystemContent]]] = None
    stop_sequences: Optional[List[str]] = None
    stream: Optional[bool] = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Dict[str, Any]] = None
    thinking: Optional[ThinkingConfig] = None
    original_model: Optional[str] = None

    @field_validator("model")
    def validate_model_field(cls, v, info):
        mapped_model = map_model_name(v, "MODEL VALIDATION")
        values = info.data
        if isinstance(values, dict):
            values["original_model"] = v
        return mapped_model


class TokenCountRequest(BaseModel):
    model: str
    messages: List[Message]
    system: Optional[Union[str, List[SystemContent]]] = None
    tools: Optional[List[Tool]] = None
    thinking: Optional[ThinkingConfig] = None
    tool_choice: Optional[Dict[str, Any]] = None
    original_model: Optional[str] = None

    @field_validator("model")
    def validate_model_token_count(cls, v, info):
        mapped_model = map_model_name(v, "TOKEN COUNT VALIDATION")
        values = info.data
        if isinstance(values, dict):
            values["original_model"] = v
        return mapped_model


class TokenCountResponse(BaseModel):
    input_tokens: int


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class MessagesResponse(BaseModel):
    id: str
    model: str
    role: Literal["assistant"] = "assistant"
    content: List[Union[ContentBlockText, ContentBlockToolUse]]
    type: Literal["message"] = "message"
    stop_reason: Optional[Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"]] = None
    stop_sequence: Optional[str] = None
    usage: Usage
