"""OpenAI and OpenAI-compatible servers (Ollama, LM Studio, …) behind the
same conversation interface as Anthropic."""

import json
from types import SimpleNamespace
from typing import cast

import httpx2 as httpx  # the HTTP client the openai SDK uses
import openai
import pytest

from varda.kindling.providers import (
    OpenAIProvider,
    ProviderError,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from varda.kindling.tools import KindlingTools

SPEC = ToolSpec("write_file", "Write it.", {"type": "object", "properties": {}})


def _toolCall(id_: str, name: str, arguments: str):
    return SimpleNamespace(
        id=id_,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class FakeCompletions:
    def __init__(self, replies=None, error: Exception | None = None):
        self.calls: list[dict] = []
        self.replies = list(replies or [])
        self.error = error

    def create(self, **kwargs):
        if self.error is not None:
            raise self.error
        sent = {k: v for k, v in kwargs.items() if v is not openai.omit}  # as the SDK
        self.calls.append(json.loads(json.dumps(sent)))  # a snapshot
        content, toolCalls = self.replies.pop(0) if self.replies else ("Done.", [])
        message = SimpleNamespace(content=content, tool_calls=toolCalls)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )


def _provider(official=True, **fake) -> tuple[OpenAIProvider, FakeCompletions]:
    completions = FakeCompletions(**fake)
    models = SimpleNamespace(
        list=lambda: [SimpleNamespace(id="b-model"), SimpleNamespace(id="a-model")]
    )
    client = cast(
        openai.OpenAI,
        SimpleNamespace(chat=SimpleNamespace(completions=completions), models=models),
    )
    provider = OpenAIProvider(
        "key", "test-model", official=official, name="Test", client=client
    )
    return provider, completions


def _status(cls, code: int, message: str) -> Exception:
    request = httpx.Request("POST", "http://test/v1/chat/completions")
    response = httpx.Response(code, request=request)
    return cls(message, response=response, body={"error": {"message": message}})


def test_a_conversation_sends_the_system_prompt_and_tools():
    provider, completions = _provider()
    reply = provider.start("the docs", [SPEC]).send("build it")
    request = completions.calls[0]
    assert request["model"] == "test-model"
    assert request["messages"][0] == {"role": "system", "content": "the docs"}
    assert request["messages"][1] == {"role": "user", "content": "build it"}
    assert request["tools"][0]["function"]["name"] == "write_file"
    assert request["tools"][0]["function"]["parameters"] == SPEC.schema
    assert reply.text == "Done."
    assert reply.tokens == 120


def test_tool_calls_come_back_and_their_results_go_out_as_tool_messages():
    provider, completions = _provider(
        replies=[("Writing.", [_toolCall("c1", "write_file", '{"path": "a.py"}')])]
    )
    conversation = provider.start("docs", [SPEC])
    reply = conversation.send("build it")
    assert reply.toolCalls == (ToolCall("c1", "write_file", {"path": "a.py"}),)

    conversation.send(results=[ToolResult("c1", "Disk full", isError=True)])
    messages = completions.calls[1]["messages"]
    assistant = messages[2]
    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"][0]["id"] == "c1"
    assert messages[3] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "Error: Disk full",
    }
    assert len(messages) == 4  # no empty user message after the results


def test_arguments_that_are_not_json_are_reported_to_the_model():
    provider, _ = _provider(replies=[("", [_toolCall("c1", "write_file", "{oops")])])
    call = provider.start("docs", [SPEC]).send("build it").toolCalls[0]
    assert call.arguments == {}
    result = KindlingTools(cast(object, None), lambda folder: None).call(call)  # type: ignore[arg-type]
    assert result.isError and "valid JSON" in result.content


def test_calls_without_ids_get_one():
    provider, _ = _provider(replies=[("", [_toolCall("", "write_file", "{}")])])
    call = provider.start("docs", [SPEC]).send("go").toolCalls[0]
    assert call.id


def test_openai_and_local_servers_name_the_reply_limit_differently():
    official, officialCalls = _provider(official=True)
    local, localCalls = _provider(official=False)
    official.start("docs", [SPEC]).send("go")
    local.start("docs", [SPEC]).send("go")
    assert "max_completion_tokens" in officialCalls.calls[0]
    assert "max_tokens" not in officialCalls.calls[0]
    assert "max_tokens" in localCalls.calls[0]
    assert "max_completion_tokens" not in localCalls.calls[0]


def test_a_failed_request_leaves_the_conversation_valid_for_a_retry():
    provider, completions = _provider()
    conversation = provider.start("docs", [SPEC])
    completions.error = openai.APIConnectionError(
        request=httpx.Request("POST", "http://localhost:11434/v1")
    )
    with pytest.raises(ProviderError, match="couldn't be reached"):
        conversation.send(results=[ToolResult("c1", "ok")])
    assert conversation.messages == [{"role": "system", "content": "docs"}]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_status(openai.AuthenticationError, 401, "bad key"), "rejected the API key"),
        (_status(openai.NotFoundError, 404, "no such model"), "test-model"),
        (_status(openai.RateLimitError, 429, "slow down"), "rate limit"),
        (
            _status(openai.BadRequestError, 400, "test-model does not support tools"),
            "tool calls",
        ),
        (_status(openai.BadRequestError, 400, "something odd"), "something odd"),
    ],
)
def test_errors_are_explained(error, expected):
    provider, _ = _provider(error=error)
    with pytest.raises(ProviderError, match=expected):
        provider.start("docs", [SPEC]).send("go")


def test_a_server_that_does_not_list_models_says_so():
    provider, _ = _provider()

    def missing():
        raise _status(openai.NotFoundError, 404, "404 page not found")

    provider.client.models.list = missing  # type: ignore[method-assign]
    with pytest.raises(ProviderError, match="doesn't list its models"):
        provider.listModels()


def test_models_are_listed_by_name():
    provider, _ = _provider()
    assert provider.listModels() == ["a-model", "b-model"]


def test_a_local_server_needs_no_key():
    provider = OpenAIProvider(
        "", "llama", baseUrl="http://localhost:11434/v1", official=False
    )
    assert provider.client.api_key
    assert str(provider.client.base_url).startswith("http://localhost:11434/v1")
