import json
import logging
import uuid

from proxy_core.models import MessagesRequest

logger = logging.getLogger(__name__)


async def handle_streaming(response_generator, original_request: MessagesRequest):
    try:
        message_id = f"msg_{uuid.uuid4().hex[:24]}"
        message_data = {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": original_request.model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 0,
                },
            },
        }
        yield f"event: message_start\ndata: {json.dumps(message_data)}\n\n"
        yield (
            "event: content_block_start\ndata: "
            f"{json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
        )
        yield f"event: ping\ndata: {json.dumps({'type': 'ping'})}\n\n"

        tool_index = None
        accumulated_text = ""
        text_sent = False
        text_block_closed = False
        output_tokens = 0
        has_sent_stop_reason = False
        last_tool_index = 0

        async for chunk in response_generator:
            try:
                if hasattr(chunk, "usage") and chunk.usage is not None and hasattr(chunk.usage, "completion_tokens"):
                    output_tokens = chunk.usage.completion_tokens

                if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    delta = choice.delta if hasattr(choice, "delta") else getattr(choice, "message", {})
                    finish_reason = getattr(choice, "finish_reason", None)

                    delta_content = getattr(delta, "content", None) if hasattr(delta, "content") else (
                        delta.get("content") if isinstance(delta, dict) else None
                    )

                    if delta_content is not None and delta_content != "":
                        accumulated_text += delta_content
                        if tool_index is None and not text_block_closed:
                            text_sent = True
                            yield (
                                "event: content_block_delta\ndata: "
                                f"{json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': delta_content}})}\n\n"
                            )

                    delta_tool_calls = getattr(delta, "tool_calls", None) if hasattr(delta, "tool_calls") else (
                        delta.get("tool_calls") if isinstance(delta, dict) else None
                    )

                    if delta_tool_calls:
                        if tool_index is None:
                            if text_sent and not text_block_closed:
                                text_block_closed = True
                                yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
                            elif accumulated_text and not text_sent and not text_block_closed:
                                text_sent = True
                                yield (
                                    "event: content_block_delta\ndata: "
                                    f"{json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': accumulated_text}})}\n\n"
                                )
                                text_block_closed = True
                                yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
                            elif not text_block_closed:
                                text_block_closed = True
                                yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"

                        if not isinstance(delta_tool_calls, list):
                            delta_tool_calls = [delta_tool_calls]

                        for tool_call in delta_tool_calls:
                            current_index = tool_call["index"] if isinstance(tool_call, dict) and "index" in tool_call else (
                                tool_call.index if hasattr(tool_call, "index") else 0
                            )

                            if tool_index is None or current_index != tool_index:
                                tool_index = current_index
                                last_tool_index += 1
                                anthropic_tool_index = last_tool_index

                                if isinstance(tool_call, dict):
                                    function = tool_call.get("function", {})
                                    name = function.get("name", "") if isinstance(function, dict) else ""
                                    tool_id = tool_call.get("id", f"toolu_{uuid.uuid4().hex[:24]}")
                                else:
                                    function = getattr(tool_call, "function", None)
                                    name = getattr(function, "name", "") if function else ""
                                    tool_id = getattr(tool_call, "id", f"toolu_{uuid.uuid4().hex[:24]}")

                                yield (
                                    "event: content_block_start\ndata: "
                                    f"{json.dumps({'type': 'content_block_start', 'index': anthropic_tool_index, 'content_block': {'type': 'tool_use', 'id': tool_id, 'name': name, 'input': {}}})}\n\n"
                                )

                            if isinstance(tool_call, dict) and "function" in tool_call:
                                function = tool_call.get("function", {})
                                arguments = function.get("arguments", "") if isinstance(function, dict) else ""
                            elif hasattr(tool_call, "function"):
                                function = getattr(tool_call, "function", None)
                                arguments = getattr(function, "arguments", "") if function else ""
                            else:
                                arguments = None

                            if arguments:
                                try:
                                    if isinstance(arguments, dict):
                                        args_json = json.dumps(arguments)
                                    else:
                                        json.loads(arguments)
                                        args_json = arguments
                                except (json.JSONDecodeError, TypeError):
                                    args_json = arguments

                                yield (
                                    "event: content_block_delta\ndata: "
                                    f"{json.dumps({'type': 'content_block_delta', 'index': anthropic_tool_index, 'delta': {'type': 'input_json_delta', 'partial_json': args_json}})}\n\n"
                                )

                    if finish_reason and not has_sent_stop_reason:
                        has_sent_stop_reason = True

                        if tool_index is not None:
                            for i in range(1, last_tool_index + 1):
                                yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': i})}\n\n"

                        if not text_block_closed:
                            if accumulated_text and not text_sent:
                                yield (
                                    "event: content_block_delta\ndata: "
                                    f"{json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': accumulated_text}})}\n\n"
                                )
                            yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"

                        stop_reason = "end_turn"
                        if finish_reason == "length":
                            stop_reason = "max_tokens"
                        elif finish_reason == "tool_calls":
                            stop_reason = "tool_use"

                        yield (
                            "event: message_delta\ndata: "
                            f"{json.dumps({'type': 'message_delta', 'delta': {'stop_reason': stop_reason, 'stop_sequence': None}, 'usage': {'output_tokens': output_tokens}})}\n\n"
                        )
                        yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
            except Exception as e:
                logger.error(f"Error processing chunk: {str(e)}")
                continue

        if not has_sent_stop_reason:
            if tool_index is not None:
                for i in range(1, last_tool_index + 1):
                    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': i})}\n\n"

            yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
            yield (
                "event: message_delta\ndata: "
                f"{json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': output_tokens}})}\n\n"
            )
            yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
            yield "data: [DONE]\n\n"
    except Exception as e:
        import traceback

        logger.error(f"Error in streaming: {str(e)}\n\nFull traceback:\n{traceback.format_exc()}")
        yield (
            "event: message_delta\ndata: "
            f"{json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'error', 'stop_sequence': None}, 'usage': {'output_tokens': 0}})}\n\n"
        )
        yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
        yield "data: [DONE]\n\n"
