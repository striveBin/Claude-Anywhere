import unittest

from server import (
    ContentBlockText,
    ContentBlockToolResult,
    Message,
    MessagesRequest,
    convert_anthropic_to_litellm,
    convert_litellm_to_anthropic,
)


class ProtocolConversionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
