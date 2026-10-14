from types import SimpleNamespace
from typing import cast

import anthropic
from anthropic.types import TextBlock, ToolUseBlock
import httpx2 as httpx  # the HTTP client the anthropic SDK uses
import pytest

from varda.kindling.providers import (
    AnthropicProvider,
    ProviderError,
    ToolResult,
    ToolSpec,
)

SPEC = ToolSpec("run_checks", "Check it.", {"type": "object", "properties": {}})


class FakeMessages:
    def __init__(self, error: Exception | None = None):
        self.calls: list[dict] = []
        self.error = error

    def create(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[
                TextBlock(type="text", text="Checking."),
                ToolUseBlock(type="tool_use", id="t1", name="run_checks", input={}),
            ],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_creation_input_tokens=100,
                cache_read_input_tokens=None,
            ),
        )


def _provider(error=None) -> tuple[AnthropicProvider, FakeMessages]:
    messages = FakeMessages(error)
    client = cast(anthropic.Anthropic, SimpleNamespace(messages=messages))
    return AnthropicProvider("key", "claude-test", client=client), messages


def test_a_conversation_sends_tools_and_caches_the_system_prompt():
    provider, messages = _provider()
    reply = provider.start("the docs", [SPEC]).send("build it")
    request = messages.calls[0]
    assert request["model"] == "claude-test"
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert request["tools"][0]["name"] == "run_checks"
    assert request["messages"][0] == {
        "role": "user",
        "content": [{"type": "text", "text": "build it"}],
    }
    assert reply.text == "Checking." and reply.toolCalls[0].name == "run_checks"
    assert reply.tokens == 115


def test_tool_results_come_first_then_text():
    provider, messages = _provider()
    conversation = provider.start("docs", [SPEC])
    conversation.send("build it")
    conversation.send("and also", [ToolResult("t1", "PASSED")])
    content = messages.calls[1]["messages"][2]["content"]
    assert content[0] == {
        "type": "tool_result",
        "tool_use_id": "t1",
        "content": "PASSED",
        "is_error": False,
    }
    assert content[1] == {"type": "text", "text": "and also"}
    assert messages.calls[1]["messages"][1]["role"] == "assistant"


def _response(status: int) -> httpx.Response:
    return httpx.Response(
        status, request=httpx.Request("POST", "https://api.anthropic.com")
    )


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            anthropic.AuthenticationError("bad", response=_response(401), body=None),
            "key was rejected",
        ),
        (
            anthropic.NotFoundError("no", response=_response(404), body=None),
            "no model called claude-test",
        ),
        (
            anthropic.APIConnectionError(request=httpx.Request("POST", "https://x")),
            "internet connection",
        ),
    ],
)
def test_errors_become_messages_for_the_user(error, message):
    provider, _ = _provider(error)
    with pytest.raises(ProviderError, match=message):
        provider.test()
