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
        self.usage = SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=100,
            cache_read_input_tokens=None,
        )

    def create(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[
                TextBlock(type="text", text="Checking."),
                ToolUseBlock(type="tool_use", id="t1", name="run_checks", input={}),
            ],
            usage=self.usage,
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
    cached = {
        "type": "text",
        "text": "build it",
        "cache_control": {"type": "ephemeral"},
    }
    assert request["messages"][0] == {"role": "user", "content": [cached]}
    assert reply.text == "Checking." and reply.toolCalls[0].name == "run_checks"
    assert reply.tokens == 115  # cache writes count in full


def test_tool_results_come_first_then_text():
    provider, messages = _provider()
    conversation = provider.start("docs", [SPEC])
    conversation.send("build it")
    conversation.send("and also", [ToolResult("t1", "PASSED")])
    sent = messages.calls[1]["messages"]
    assert sent[1]["role"] == "assistant"
    assert sent[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "t1",
        "content": "PASSED",
        "is_error": False,
    }
    # The cache breakpoint moves to the newest message
    assert sent[2]["content"][1] == {
        "type": "text",
        "text": "and also",
        "cache_control": {"type": "ephemeral"},
    }
    assert "cache_control" not in sent[0]["content"][0]


def test_cached_reads_count_a_tenth():
    provider, messages = _provider()
    messages.usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=1000,
    )
    assert provider.start("docs", [SPEC]).send("go").tokens == 115


def test_a_failed_request_leaves_the_conversation_as_it_was():
    provider, messages = _provider()
    conversation = provider.start("docs", [SPEC])
    conversation.send("build it")
    messages.error = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://x")
    )
    with pytest.raises(ProviderError):
        conversation.send("", [ToolResult("t1", "PASSED")])
    assert len(conversation.messages) == 2  # the user message and the reply


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


def test_a_workspace_id_is_sent_with_every_request():
    provider = AnthropicProvider("key", "claude-test", "wrkspc_123")
    assert provider.client.default_headers["anthropic-workspace-id"] == "wrkspc_123"
    assert (
        "anthropic-workspace-id"
        not in AnthropicProvider("key", "m").client.default_headers
    )


def _badRequest(message: str) -> anthropic.BadRequestError:
    body = {
        "type": "error",
        "error": {"type": "invalid_request_error", "message": message},
    }
    return anthropic.BadRequestError(str(body), response=_response(400), body=body)


def test_a_key_without_a_workspace_says_what_to_do():
    message = (
        "This API key is not scoped to a workspace, so this request must include "
        "the anthropic-workspace-id header with the ID of the workspace to use."
    )
    provider, _ = _provider(_badRequest(message))
    with pytest.raises(ProviderError, match="Enter your workspace ID"):
        provider.test()


def test_other_errors_show_anthropics_own_sentence():
    provider, _ = _provider(_badRequest("max_tokens is too large"))
    with pytest.raises(ProviderError) as raised:
        provider.test()
    assert str(raised.value) == "Anthropic returned an error: max_tokens is too large"
