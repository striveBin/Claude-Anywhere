import json
import logging
from typing import Any, Dict

import httpx
import openai

from proxy_core.config import (
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    USE_VERTEX_AUTH,
    VERTEX_LOCATION,
    VERTEX_PROJECT,
)

logger = logging.getLogger(__name__)

_sync_openai_clients: Dict[str, openai.OpenAI] = {}
_async_openai_clients: Dict[str, openai.AsyncOpenAI] = {}


def get_openai_sync_client(api_key: str | None, base_url: str | None) -> openai.OpenAI:
    cache_key = f"{base_url or 'default'}::{api_key or ''}"
    if cache_key not in _sync_openai_clients:
        _sync_openai_clients[cache_key] = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.Client(trust_env=False),
        )
    return _sync_openai_clients[cache_key]


def get_openai_async_client(api_key: str | None, base_url: str | None) -> openai.AsyncOpenAI:
    cache_key = f"{base_url or 'default'}::{api_key or ''}"
    if cache_key not in _async_openai_clients:
        _async_openai_clients[cache_key] = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.AsyncClient(trust_env=False),
        )
    return _async_openai_clients[cache_key]


def apply_provider_auth(litellm_request: Dict[str, Any], request_model: str) -> None:
    if request_model.startswith("openai/"):
        litellm_request["api_key"] = OPENAI_API_KEY
        if OPENAI_BASE_URL:
            litellm_request["api_base"] = OPENAI_BASE_URL
            logger.debug(f"Using OpenAI API key and custom base URL {OPENAI_BASE_URL} for model: {request_model}")
    elif request_model.startswith("gemini/"):
        if USE_VERTEX_AUTH:
            litellm_request["vertex_project"] = VERTEX_PROJECT
            litellm_request["vertex_location"] = VERTEX_LOCATION
            litellm_request["custom_llm_provider"] = "vertex_ai"
            logger.debug(f"Using Gemini ADC with project={VERTEX_PROJECT}, location={VERTEX_LOCATION} and model: {request_model}")
        else:
            litellm_request["api_key"] = GEMINI_API_KEY
            logger.debug(f"Using Gemini API key for model: {request_model}")
    else:
        litellm_request["api_key"] = ANTHROPIC_API_KEY
        logger.debug(f"Using Anthropic API key for model: {request_model}")


def normalize_openai_messages(litellm_request: Dict[str, Any]) -> None:
    if "openai" not in litellm_request["model"] or "messages" not in litellm_request:
        return

    logger.debug(f"Processing OpenAI model request: {litellm_request['model']}")

    for i, msg in enumerate(litellm_request["messages"]):
        if "content" in msg and isinstance(msg["content"], list):
            text_content = ""
            for block in msg["content"]:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_content += block.get("text", "") + "\n"
                    elif block.get("type") == "image":
                        text_content += "[Image content - not displayed in text format]\n"
            litellm_request["messages"][i]["content"] = text_content.strip() or "..."
        elif msg.get("content") is None and not msg.get("tool_calls"):
            litellm_request["messages"][i]["content"] = "..."

        for key in list(msg.keys()):
            if key not in ["role", "content", "name", "tool_call_id", "tool_calls"]:
                del msg[key]

    for i, msg in enumerate(litellm_request["messages"]):
        if isinstance(msg.get("content"), list):
            litellm_request["messages"][i]["content"] = f"Content as JSON: {json.dumps(msg.get('content'))}"
        elif msg.get("content") is None and not msg.get("tool_calls"):
            litellm_request["messages"][i]["content"] = "..."
