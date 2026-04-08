import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from proxy_core.adapters import prepare_backend_request
from proxy_core.providers import normalize_openai_messages
from server import (
    ContentBlockImage,
    ContentBlockText,
    ContentBlockToolUse,
    ContentBlockToolResult,
    Message,
    MessagesRequest,
    RequestCompatibilityError,
    app,
    convert_anthropic_to_litellm,
    convert_litellm_to_anthropic,
    validate_request_compatibility,
)


class ProtocolConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_user_tool_result_becomes_tool_role_message(self):
        request = MessagesRequest(
            model="claude-3-5-sonnet-latest",
            max_tokens=256,
            messages=[
                Message(
                    role="user",
                    content=[ContentBlockText(type="text", text="Please use the tool.")],
                ),
                Message(
                    role="assistant",
                    content=[
                        {
                            "type": "tool_use",
                            "id": "toolu_123",
                            "name": "bash",
                            "input": {"command": "pwd"},
                        }
                    ],
                ),
                Message(
                    role="user",
                    content=[
                        ContentBlockToolResult(
                            type="tool_result",
                            tool_use_id="toolu_123",
                            content=[{"type": "text", "text": "/workspace"}],
                        ),
                        ContentBlockText(type="text", text="Continue."),
                    ],
                ),
            ],
        )

        converted = convert_anthropic_to_litellm(request)
        messages = converted["messages"]

        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["tool_calls"][0]["id"], "toolu_123")
        self.assertIsNone(messages[1]["content"])

        self.assertEqual(messages[2]["role"], "tool")
        self.assertEqual(messages[2]["tool_call_id"], "toolu_123")
        self.assertEqual(messages[2]["content"], "/workspace")

        self.assertEqual(messages[3]["role"], "user")
        self.assertEqual(messages[3]["content"], "Continue.")

    def test_backend_tool_calls_always_return_anthropic_tool_use(self):
        request = MessagesRequest(
            model="gpt-4.1",
            max_tokens=128,
            messages=[Message(role="user", content="List files.")],
        )

        litellm_response = {
            "id": "resp_1",
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "shell",
                                    "arguments": "{\"command\":\"ls\"}",
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        converted = convert_litellm_to_anthropic(litellm_response, request)

        self.assertEqual(converted.stop_reason, "tool_use")
        self.assertEqual(converted.content[0].type, "tool_use")
        self.assertEqual(converted.content[0].name, "shell")
        self.assertEqual(converted.content[0].input, {"command": "ls"})

    def test_thinking_is_rejected_for_non_anthropic_backends(self):
        request = MessagesRequest(
            model="gpt-4.1",
            max_tokens=128,
            thinking={"enabled": True},
            messages=[Message(role="user", content="Hello")],
        )

        with patch("proxy_core.compatibility.UNSUPPORTED_THINKING_BEHAVIOR", "error"):
            with self.assertRaises(RequestCompatibilityError) as ctx:
                validate_request_compatibility(request)

        self.assertIn("thinking", str(ctx.exception))
        self.assertIn("UNSUPPORTED_THINKING_BEHAVIOR=drop", str(ctx.exception))

    def test_thinking_can_be_dropped_for_non_anthropic_backends(self):
        request = MessagesRequest(
            model="gpt-4.1",
            max_tokens=128,
            thinking={"enabled": True},
            messages=[Message(role="user", content="Hello")],
        )

        with patch("proxy_core.compatibility.UNSUPPORTED_THINKING_BEHAVIOR", "drop"):
            validate_request_compatibility(request)

        self.assertIsNone(request.thinking)

    def test_gemini_rejects_incompatible_tool_schema(self):
        request = MessagesRequest(
            model="gemini-2.5-pro",
            max_tokens=128,
            messages=[Message(role="user", content="Run a tool")],
            tools=[
                {
                    "name": "search",
                    "description": "Search",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "default": "hello",
                                "format": "uri",
                            }
                        },
                        "additionalProperties": False,
                    },
                }
            ],
        )

        with self.assertRaises(RequestCompatibilityError) as ctx:
            validate_request_compatibility(request)

        self.assertIn("Gemini adapter", str(ctx.exception))

    def test_openai_rejects_image_content_blocks(self):
        request = MessagesRequest(
            model="gpt-4.1",
            max_tokens=128,
            messages=[
                Message(
                    role="user",
                    content=[
                        ContentBlockImage(
                            type="image",
                            source={"type": "base64", "media_type": "image/png", "data": "abc"},
                        )
                    ],
                )
            ],
        )

        with self.assertRaises(RequestCompatibilityError) as ctx:
            validate_request_compatibility(request)

        self.assertIn("Image content blocks", str(ctx.exception))

    def test_user_tool_use_is_rejected(self):
        request = MessagesRequest(
            model="gpt-4.1",
            max_tokens=128,
            messages=[
                Message(
                    role="user",
                    content=[
                        ContentBlockToolUse(
                            type="tool_use",
                            id="toolu_bad",
                            name="shell",
                            input={"command": "pwd"},
                        )
                    ],
                )
            ],
        )

        with self.assertRaises(RequestCompatibilityError) as ctx:
            validate_request_compatibility(request)

        self.assertIn("User messages cannot contain tool_use", str(ctx.exception))

    def test_invalid_tool_choice_is_rejected(self):
        request = MessagesRequest(
            model="gpt-4.1",
            max_tokens=128,
            tool_choice={"type": "invalid"},
            messages=[Message(role="user", content="Hello")],
        )

        with self.assertRaises(RequestCompatibilityError) as ctx:
            validate_request_compatibility(request)

        self.assertIn("Unsupported tool_choice type", str(ctx.exception))

    def test_normalize_openai_messages_keeps_tool_calls_and_fills_empty_content(self):
        litellm_request = {
            "model": "openai/gpt-4.1",
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {"name": "shell", "arguments": "{\"command\":\"pwd\"}"},
                        }
                    ],
                    "unsupported": True,
                }
            ],
        }

        normalize_openai_messages(litellm_request)

        self.assertIn("tool_calls", litellm_request["messages"][0])
        self.assertIsNone(litellm_request["messages"][0]["content"])
        self.assertNotIn("unsupported", litellm_request["messages"][0])

    def test_messages_endpoint_returns_400_for_incompatible_request(self):
        response = self.client.post(
            "/v1/messages",
            json={
                "model": "gpt-4.1",
                "max_tokens": 128,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {"type": "base64", "media_type": "image/png", "data": "abc"},
                            }
                        ],
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Image content blocks", response.json()["detail"])

    def test_openai_adapter_adds_api_key_and_normalizes_messages(self):
        request = MessagesRequest(
            model="gpt-4.1",
            max_tokens=64,
            messages=[
                Message(
                    role="assistant",
                    content=[ContentBlockText(type="text", text="hello")],
                )
            ],
        )

        litellm_request = prepare_backend_request(request)

        self.assertEqual(litellm_request["model"], "openai/gpt-4.1")
        self.assertIn("api_key", litellm_request)
        self.assertEqual(litellm_request["messages"][0]["content"], "hello")

    def test_gemini_adapter_sets_gemini_model_without_openai_normalization(self):
        request = MessagesRequest(
            model="gemini-2.5-pro",
            max_tokens=64,
            messages=[Message(role="user", content="hello")],
        )

        litellm_request = prepare_backend_request(request)

        self.assertEqual(litellm_request["model"], "gemini/gemini-2.5-pro")
        self.assertEqual(litellm_request["messages"][0]["content"], "hello")

    def test_anthropic_adapter_sets_anthropic_prefix(self):
        request = MessagesRequest(
            model="anthropic/claude-3-opus-20240229",
            max_tokens=64,
            messages=[Message(role="user", content="hello")],
        )

        litellm_request = prepare_backend_request(request)

        self.assertEqual(litellm_request["model"], "anthropic/claude-3-opus-20240229")
        self.assertIn("api_key", litellm_request)

    def test_shell_style_tool_schema_survives_openai_preparation(self):
        request = MessagesRequest(
            model="gpt-4.1",
            max_tokens=128,
            messages=[Message(role="user", content="Run a shell command")],
            tools=[
                {
                    "name": "bash",
                    "description": "Execute a shell command",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "timeout_ms": {"type": "integer"},
                        },
                        "required": ["command"],
                    },
                }
            ],
        )

        litellm_request = prepare_backend_request(request)

        self.assertEqual(litellm_request["tools"][0]["function"]["name"], "bash")
        self.assertEqual(
            litellm_request["tools"][0]["function"]["parameters"]["required"],
            ["command"],
        )

    def test_file_write_tool_result_chain_stays_structured(self):
        request = MessagesRequest(
            model="gpt-4.1",
            max_tokens=256,
            messages=[
                Message(role="user", content="Write a file."),
                Message(
                    role="assistant",
                    content=[
                        {
                            "type": "tool_use",
                            "id": "toolu_write_1",
                            "name": "write_file",
                            "input": {"path": "README.md", "content": "hello"},
                        }
                    ],
                ),
                Message(
                    role="user",
                    content=[
                        ContentBlockToolResult(
                            type="tool_result",
                            tool_use_id="toolu_write_1",
                            content=[{"type": "text", "text": "File written successfully"}],
                        )
                    ],
                ),
            ],
        )

        converted = convert_anthropic_to_litellm(request)

        self.assertEqual(converted["messages"][1]["tool_calls"][0]["function"]["name"], "write_file")
        self.assertEqual(converted["messages"][2]["role"], "tool")
        self.assertEqual(converted["messages"][2]["tool_call_id"], "toolu_write_1")
        self.assertEqual(converted["messages"][2]["content"], "File written successfully")


if __name__ == "__main__":
    unittest.main()
