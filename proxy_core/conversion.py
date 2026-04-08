import json
import logging
import uuid
from typing import Any, Dict, List, Union

from proxy_core.config import GEMINI_MODELS
from proxy_core.models import MessagesRequest, MessagesResponse, Usage

logger = logging.getLogger(__name__)


def clean_gemini_schema(schema: Any) -> Any:
    """Recursively removes unsupported fields from a JSON schema for Gemini."""
    if isinstance(schema, dict):
        schema.pop("additionalProperties", None)
        schema.pop("default", None)

        if schema.get("type") == "string" and "format" in schema:
            allowed_formats = {"enum", "date-time"}
            if schema["format"] not in allowed_formats:
                logger.debug(f"Removing unsupported format '{schema['format']}' for string type in Gemini schema.")
                schema.pop("format")

        for key, value in list(schema.items()):
            schema[key] = clean_gemini_schema(value)
    elif isinstance(schema, list):
        return [clean_gemini_schema(item) for item in schema]
    return schema


def parse_tool_result_content(content):
    if content is None:
        return "No content provided"
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        result = ""
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                result += item.get("text", "") + "\n"
            elif isinstance(item, str):
                result += item + "\n"
            elif isinstance(item, dict):
                if "text" in item:
                    result += item.get("text", "") + "\n"
                else:
                    try:
                        result += json.dumps(item) + "\n"
                    except Exception:
                        result += str(item) + "\n"
            else:
                try:
                    result += str(item) + "\n"
                except Exception:
                    result += "Unparseable content\n"
        return result.strip()
    if isinstance(content, dict):
        if content.get("type") == "text":
            return content.get("text", "")
        try:
            return json.dumps(content)
        except Exception:
            return str(content)
    try:
        return str(content)
    except Exception:
        return "Unparseable content"


def append_text_block(target_blocks: List[Dict[str, Any]], text: str) -> None:
    if not text:
        return
    if target_blocks and target_blocks[-1].get("type") == "text":
        target_blocks[-1]["text"] += text
    else:
        target_blocks.append({"type": "text", "text": text})


def flush_user_content(messages: List[Dict[str, Any]], content_blocks: List[Dict[str, Any]]) -> None:
    if not content_blocks:
        return
    if len(content_blocks) == 1 and content_blocks[0].get("type") == "text":
        messages.append({"role": "user", "content": content_blocks[0]["text"]})
    else:
        messages.append({"role": "user", "content": content_blocks.copy()})
    content_blocks.clear()


def convert_anthropic_to_litellm(anthropic_request: MessagesRequest) -> Dict[str, Any]:
    messages = []

    if anthropic_request.system:
        if isinstance(anthropic_request.system, str):
            messages.append({"role": "system", "content": anthropic_request.system})
        elif isinstance(anthropic_request.system, list):
            system_text = ""
            for block in anthropic_request.system:
                if hasattr(block, "type") and block.type == "text":
                    system_text += block.text + "\n\n"
                elif isinstance(block, dict) and block.get("type") == "text":
                    system_text += block.get("text", "") + "\n\n"
            if system_text:
                messages.append({"role": "system", "content": system_text.strip()})

    for msg in anthropic_request.messages:
        content = msg.content
        if isinstance(content, str):
            messages.append({"role": msg.role, "content": content})
        else:
            if msg.role == "assistant":
                assistant_text = ""
                assistant_tool_calls = []
                assistant_content_blocks = []

                for block in content:
                    block_type = getattr(block, "type", None)
                    if block_type == "text":
                        assistant_text += block.text
                    elif block_type == "image":
                        assistant_content_blocks.append({"type": "image", "source": block.source})
                    elif block_type == "tool_use":
                        assistant_tool_calls.append(
                            {
                                "id": block.id,
                                "type": "function",
                                "function": {"name": block.name, "arguments": json.dumps(block.input or {})},
                            }
                        )

                if assistant_tool_calls:
                    messages.append({"role": "assistant", "content": assistant_text or None, "tool_calls": assistant_tool_calls})
                elif assistant_content_blocks:
                    if assistant_text:
                        assistant_content_blocks.insert(0, {"type": "text", "text": assistant_text})
                    messages.append({"role": "assistant", "content": assistant_content_blocks})
                else:
                    messages.append({"role": "assistant", "content": assistant_text})
            elif msg.role == "user":
                user_content_blocks: List[Dict[str, Any]] = []
                for block in content:
                    block_type = getattr(block, "type", None)
                    if block_type == "text":
                        append_text_block(user_content_blocks, block.text)
                    elif block_type == "image":
                        user_content_blocks.append({"type": "image", "source": block.source})
                    elif block_type == "tool_result":
                        flush_user_content(messages, user_content_blocks)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": block.tool_use_id if hasattr(block, "tool_use_id") else "",
                                "content": parse_tool_result_content(getattr(block, "content", None)),
                            }
                        )
                    elif block_type == "tool_use":
                        append_text_block(
                            user_content_blocks,
                            f"[Tool: {block.name} (ID: {block.id})]\nInput: {json.dumps(block.input or {})}\n",
                        )
                flush_user_content(messages, user_content_blocks)
            else:
                processed_content = []
                for block in content:
                    if hasattr(block, "type"):
                        if block.type == "text":
                            processed_content.append({"type": "text", "text": block.text})
                        elif block.type == "image":
                            processed_content.append({"type": "image", "source": block.source})
                messages.append({"role": msg.role, "content": processed_content})

    max_tokens = anthropic_request.max_tokens
    if anthropic_request.model.startswith("openai/") or anthropic_request.model.startswith("gemini/"):
        max_tokens = min(max_tokens, 16384)
        logger.debug(f"Capping max_tokens to 16384 for OpenAI/Gemini model (original value: {anthropic_request.max_tokens})")

    litellm_request = {
        "model": anthropic_request.model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
        "temperature": anthropic_request.temperature,
        "stream": anthropic_request.stream,
    }

    if anthropic_request.thinking and anthropic_request.model.startswith("anthropic/"):
        litellm_request["thinking"] = anthropic_request.thinking
    if anthropic_request.stop_sequences:
        litellm_request["stop"] = anthropic_request.stop_sequences
    if anthropic_request.top_p:
        litellm_request["top_p"] = anthropic_request.top_p
    if anthropic_request.top_k:
        litellm_request["top_k"] = anthropic_request.top_k

    if anthropic_request.tools:
        openai_tools = []
        is_gemini_model = anthropic_request.model.startswith("gemini/")
        for tool in anthropic_request.tools:
            if hasattr(tool, "model_dump"):
                tool_dict = tool.model_dump()
            else:
                try:
                    tool_dict = dict(tool) if not isinstance(tool, dict) else tool
                except (TypeError, ValueError):
                    logger.error(f"Could not convert tool to dict: {tool}")
                    continue

            input_schema = tool_dict.get("input_schema", {})
            if is_gemini_model:
                logger.debug(f"Cleaning schema for Gemini tool: {tool_dict.get('name')}")
                input_schema = clean_gemini_schema(input_schema)

            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool_dict["name"],
                        "description": tool_dict.get("description", ""),
                        "parameters": input_schema,
                    },
                }
            )
        litellm_request["tools"] = openai_tools

    if anthropic_request.tool_choice:
        if hasattr(anthropic_request.tool_choice, "model_dump"):
            tool_choice_dict = anthropic_request.tool_choice.model_dump()
        else:
            tool_choice_dict = anthropic_request.tool_choice

        choice_type = tool_choice_dict.get("type")
        if choice_type == "auto":
            litellm_request["tool_choice"] = "auto"
        elif choice_type == "any":
            litellm_request["tool_choice"] = "required"
        elif choice_type == "tool" and "name" in tool_choice_dict:
            litellm_request["tool_choice"] = {"type": "function", "function": {"name": tool_choice_dict["name"]}}
        else:
            litellm_request["tool_choice"] = "auto"

    return litellm_request


def convert_litellm_to_anthropic(litellm_response: Union[Dict[str, Any], Any], original_request: MessagesRequest) -> MessagesResponse:
    try:
        if hasattr(litellm_response, "choices") and hasattr(litellm_response, "usage"):
            choices = litellm_response.choices
            message = choices[0].message if choices and len(choices) > 0 else None
            content_text = message.content if message and hasattr(message, "content") else ""
            tool_calls = message.tool_calls if message and hasattr(message, "tool_calls") else None
            finish_reason = choices[0].finish_reason if choices and len(choices) > 0 else "stop"
            usage_info = litellm_response.usage
            response_id = getattr(litellm_response, "id", f"msg_{uuid.uuid4()}")
        else:
            try:
                response_dict = litellm_response if isinstance(litellm_response, dict) else litellm_response.model_dump()
            except AttributeError:
                try:
                    response_dict = litellm_response.model_dump() if hasattr(litellm_response, "model_dump") else litellm_response.__dict__
                except AttributeError:
                    response_dict = {
                        "id": getattr(litellm_response, "id", f"msg_{uuid.uuid4()}"),
                        "choices": getattr(litellm_response, "choices", [{}]),
                        "usage": getattr(litellm_response, "usage", {}),
                    }

            choices = response_dict.get("choices", [{}])
            message = choices[0].get("message", {}) if choices and len(choices) > 0 else {}
            content_text = message.get("content", "")
            tool_calls = message.get("tool_calls", None)
            finish_reason = choices[0].get("finish_reason", "stop") if choices and len(choices) > 0 else "stop"
            usage_info = response_dict.get("usage", {})
            response_id = response_dict.get("id", f"msg_{uuid.uuid4()}")

        content = []
        if content_text is not None and content_text != "":
            content.append({"type": "text", "text": content_text})

        if tool_calls:
            logger.debug(f"Processing tool calls: {tool_calls}")
            if not isinstance(tool_calls, list):
                tool_calls = [tool_calls]
            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    function = tool_call.get("function", {})
                    tool_id = tool_call.get("id", f"tool_{uuid.uuid4()}")
                    name = function.get("name", "")
                    arguments = function.get("arguments", "{}")
                else:
                    function = getattr(tool_call, "function", None)
                    tool_id = getattr(tool_call, "id", f"tool_{uuid.uuid4()}")
                    name = getattr(function, "name", "") if function else ""
                    arguments = getattr(function, "arguments", "{}") if function else "{}"

                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse tool arguments as JSON: {arguments}")
                        arguments = {"raw": arguments}

                content.append({"type": "tool_use", "id": tool_id, "name": name, "input": arguments})

        if isinstance(usage_info, dict):
            prompt_tokens = usage_info.get("prompt_tokens", 0)
            completion_tokens = usage_info.get("completion_tokens", 0)
        else:
            prompt_tokens = getattr(usage_info, "prompt_tokens", 0)
            completion_tokens = getattr(usage_info, "completion_tokens", 0)

        if finish_reason == "stop":
            stop_reason = "end_turn"
        elif finish_reason == "length":
            stop_reason = "max_tokens"
        elif finish_reason == "tool_calls":
            stop_reason = "tool_use"
        else:
            stop_reason = "end_turn"

        if not content:
            content.append({"type": "text", "text": ""})

        return MessagesResponse(
            id=response_id,
            model=original_request.model,
            role="assistant",
            content=content,
            stop_reason=stop_reason,
            stop_sequence=None,
            usage=Usage(input_tokens=prompt_tokens, output_tokens=completion_tokens),
        )
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        logger.error(f"Error converting response: {str(e)}\n\nFull traceback:\n{error_traceback}")
        return MessagesResponse(
            id=f"msg_{uuid.uuid4()}",
            model=original_request.model,
            role="assistant",
            content=[{"type": "text", "text": f"Error converting response: {str(e)}. Please check server logs."}],
            stop_reason="end_turn",
            usage=Usage(input_tokens=0, output_tokens=0),
        )
